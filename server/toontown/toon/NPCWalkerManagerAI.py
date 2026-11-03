import random
from collections import deque
from panda3d.core import Vec3
from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from toontown.makeatoon.NameGenerator import NameGenerator
from toontown.safezone.DistributedTrolleyAI import DistributedTrolleyAI
from toontown.toonbase import GameConfig
from . import NPCWalkerGlobals as WG
from . import ToonDNA
from .DistributedNPCWalkerAI import DistributedNPCWalkerAI
from .DistributedToonAI import DistributedToonAI

CHECK_SECONDS = 2.0
# How long a playground keeps its walkers after the last real toon leaves it
EMPTY_GRACE = 45.0
# Toons a playground knows: the walkers are drawn from these, so the same faces turn up again
REGULARS = 14
MAX_COUNT = 12
# Seconds before someone new turns up after a walker leaves
REFILL_DELAY = (20, 60)

_managers = {}
_nameGenerator = None


def create(hood):
    """The walker manager for a hood's playground, or None when the playground has no route for walkers."""
    route = WG.getRoute(hood.canonicalHoodId)
    if not route:
        return None
    manager = NPCWalkerManagerAI(hood, route)
    _managers[hood.zoneId] = manager
    if len(_managers) == 1:
        taskMgr.doMethodLater(CHECK_SECONDS, _checkAll, 'npcWalkerCheck')
    return manager


def playerChangedZone(zoneId):
    """A real toon arrived somewhere: fill that playground at once, before the toon's game asks for what is in it."""
    manager = _managers.get(zoneId)
    if manager:
        manager.update(playerCount=1)


def getManagers():
    return list(_managers.values())


def _checkAll(task):
    counts = {}
    for do in list(simbase.air.doId2do.values()):
        if isinstance(do, DistributedToonAI) and do.isPlayerControlled():
            counts[do.zoneId] = counts.get(do.zoneId, 0) + 1
    for zoneId, manager in list(_managers.items()):
        manager.update(counts.get(zoneId, 0))
    return Task.again


def _randomName(gender):
    global _nameGenerator
    if _nameGenerator is None:
        _nameGenerator = NameGenerator()
    if gender == 'm':
        return _nameGenerator.randomName(boy=1)
    return _nameGenerator.randomName(girl=1)


def _randomIdentity():
    gender = random.choice(('m', 'f'))
    dna = ToonDNA.ToonDNA()
    dna.newToonRandom(gender=gender)
    return {'name': _randomName(gender), 'dna': dna.makeNetString(), 'backAt': 0.0}


class NPCWalkerManagerAI:
    """Keeps a playground's walking toons: none while no real toon is there, about six while someone is."""
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCWalkerManagerAI')

    def __init__(self, hood, route):
        self.air = hood.air
        self.hood = hood
        self.zoneId = hood.zoneId
        self.route = route
        self.walkers = []
        self.regulars = [_randomIdentity() for i in range(REGULARS)]
        self.lastPlayerTime = 0.0
        self.nextRefill = 0.0
        self.trolleyUser = None
        self.trolleyApproach = WG.getTrolleyApproach(hood.canonicalHoodId)
        if self.trolleyApproach is not None:
            self.trolleyHop = WG.getTrolleyHop(hood.canonicalHoodId)
            self.trolleyNode = min(route, key=lambda n: Vec3(WG.CCharPaths.getNodePos(n, route) - self.trolleyApproach).length())

    def shutdown(self):
        _managers.pop(self.zoneId, None)
        if not _managers:
            taskMgr.remove('npcWalkerCheck')
        self.removeAll()

    def getCount(self):
        try:
            count = int(GameConfig.get('walkers', WG.DEFAULT_COUNT))
        except (TypeError, ValueError):
            count = WG.DEFAULT_COUNT
        return max(0, min(MAX_COUNT, count))

    def update(self, playerCount):
        now = globalClock.getRealTime()
        if playerCount:
            self.lastPlayerTime = now
        elif now - self.lastPlayerTime > EMPTY_GRACE:
            self.removeAll()
            return
        if not self.walkers and playerCount:
            # The first toon to arrive finds the playground already busy
            for i in range(self.getCount()):
                self.spawn(teleportIn=False)
            return
        if len(self.walkers) < self.getCount() and now >= self.nextRefill:
            self.spawn(teleportIn=True)
            self.nextRefill = now + random.uniform(*REFILL_DELAY)
        elif len(self.walkers) > self.getCount():
            self.removeWalker(self.walkers[-1])

    def spawn(self, teleportIn):
        now = globalClock.getRealTime()
        busy = set(id(w.identity) for w in self.walkers)
        free = [r for r in self.regulars if id(r) not in busy and r['backAt'] <= now]
        if not free:
            return
        identity = random.choice(free)
        walker = DistributedNPCWalkerAI(self.air, self, identity)
        walker.setName(identity['name'])
        walker.setDNAString(identity['dna'])
        walker.setHp(15)
        walker.setMaxHp(15)
        walker.setPositionIndex(0)
        walker.placeAt(random.choice(list(self.route.keys())), hidden=teleportIn)
        walker.generateWithRequired(self.zoneId)
        self.walkers.append(walker)
        walker.startLife(teleportIn)

    def removeWalker(self, walker):
        if walker in self.walkers:
            self.walkers.remove(walker)
        self.releaseTrolley(walker)
        walker.requestDelete()

    def removeAll(self):
        for walker in list(self.walkers):
            self.removeWalker(walker)

    def walkerLeft(self, walker, awayTime):
        now = globalClock.getRealTime()
        walker.identity['backAt'] = now + awayTime
        self.nextRefill = max(self.nextRefill, now + random.uniform(*REFILL_DELAY))
        self.removeWalker(walker)

    def mayLeave(self):
        # Leave only when there are spare regulars to come in instead
        return len(self.walkers) + 2 < len(self.regulars)

    # The trolley: one walker at a time, and only while no real toon is on it or waiting to leave in it

    def claimTrolley(self, walker):
        if self.trolleyApproach is None or self.trolleyUser is not None or not self.trolleyIsFree():
            return False
        self.trolleyUser = walker
        return True

    def releaseTrolley(self, walker):
        if self.trolleyUser is walker:
            self.trolleyUser = None

    def trolleyIsFree(self):
        trolley = self.__findTrolley()
        return trolley is not None and trolley.getState() == 'waitEmpty' and trolley.countFullSeats() == 0

    def __findTrolley(self):
        for do in self.hood.doId2do.values():
            if isinstance(do, DistributedTrolleyAI):
                return do
        return None

    def pathTo(self, fromNode, toNode):
        """The nodes from one node to another along the route (the shortest number of hops)."""
        previous = {fromNode: None}
        queue = deque([fromNode])
        while queue:
            node = queue.popleft()
            if node == toNode:
                break
            for n in WG.getNeighbours(self.route, node):
                if n not in previous:
                    previous[n] = node
                    queue.append(n)
        if toNode not in previous:
            return [fromNode]
        nodes = []
        node = toNode
        while node is not None:
            nodes.insert(0, node)
            node = previous[node]
        return nodes
