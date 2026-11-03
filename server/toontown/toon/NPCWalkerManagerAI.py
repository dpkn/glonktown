import random
import traceback
from collections import deque
from panda3d.core import Vec3
from direct.directnotify import DirectNotifyGlobal
from direct.task import Task
from toontown.hood import ZoneUtil
from toontown.makeatoon.NameGenerator import NameGenerator
from toontown.safezone.DistributedTrolleyAI import DistributedTrolleyAI
from panda3d.toontown import SuitLeg
from toontown.toonbase import GameConfig
from . import NPCWalkerGlobals as WG
from . import ToonDNA
from .DistributedNPCWalkerAI import DistributedNPCWalkerAI
from .DistributedToonAI import DistributedToonAI

CHECK_SECONDS = 2.0
BATTLE_SECONDS = 0.5
# How long a place keeps its walkers after the last real toon leaves it
EMPTY_GRACE = 45.0
# Toons a place knows beyond the ones out at once: the walkers are drawn from these, so the same faces turn up again
SPARE_REGULARS = 10
# Seconds before someone new turns up after a walker leaves
REFILL_DELAY = (20, 60)
# Battles of walkers alone on one street at a time, so most Cogs are left for the real toons
MAX_WALKER_BATTLES = 2
# How far a walker looks for a Cog to fight or a battle to join, in feet
FIGHT_RANGE = 250.0

_managers = {}
_nameGenerator = None


def create(hood):
    """The walker managers for a hood: its playground (when it has a route for walkers) and each of its streets."""
    managers = []
    route = WG.getRoute(hood.canonicalHoodId)
    if route:
        managers.append(PlaygroundWalkersAI(hood, route))
    for suitPlanner in hood.suitPlanners:
        route = WG.getStreetRoute(suitPlanner)
        if route:
            managers.append(StreetWalkersAI(hood, suitPlanner, route))
    for manager in managers:
        _managers[manager.zoneId] = manager
    if managers and not taskMgr.hasTaskNamed('npcWalkerCheck'):
        taskMgr.doMethodLater(CHECK_SECONDS, _checkAll, 'npcWalkerCheck')
        taskMgr.doMethodLater(BATTLE_SECONDS, _driveBattles, 'npcWalkerBattles')
    return managers


def playerChangedZone(zoneId):
    """A real toon arrived somewhere: fill that place at once, before the toon's game asks for what is in it."""
    manager = _managers.get(zoneId) or _managers.get(ZoneUtil.getBranchZone(zoneId))
    if manager:
        try:
            manager.update(playerCount=1)
        except Exception:
            NPCWalkerManagerAI.notify.warning('walkers in %s: %s' % (zoneId, traceback.format_exc()))


def getManagers():
    return list(_managers.values())


def getManager(zoneId):
    return _managers.get(zoneId) or _managers.get(ZoneUtil.getBranchZone(zoneId))


def _checkAll(task):
    counts = {}
    for do in list(simbase.air.doId2do.values()):
        if isinstance(do, DistributedToonAI) and do.isPlayerControlled() and do.zoneId:
            # A toon on a street is in one of its small zones; the street's walkers live in its branch zone
            for zoneId in set((do.zoneId, ZoneUtil.getBranchZone(do.zoneId))):
                counts[zoneId] = counts.get(zoneId, 0) + 1
    for zoneId, manager in list(_managers.items()):
        try:
            manager.update(counts.get(zoneId, 0))
        except Exception:
            # Walkers are decoration: a mistake in them must never stop the district
            NPCWalkerManagerAI.notify.warning('walkers in %s: %s' % (zoneId, traceback.format_exc()))
    return Task.again


def _driveBattles(task):
    now = globalClock.getRealTime()
    for manager in list(_managers.values()):
        for walker in list(manager.walkers):
            if walker.battleDoId:
                try:
                    walker.driveBattle(now)
                except Exception:
                    NPCWalkerManagerAI.notify.warning('walker %s in battle: %s' % (walker.doId, traceback.format_exc()))
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
    return {'name': _randomName(gender), 'dna': dna.makeNetString(), 'backAt': 0.0, 'fighter': WG.randomFighter()}


class NPCWalkerManagerAI:
    """Keeps one place's walking toons: none while no real toon is there, a crowd while someone is."""
    notify = DirectNotifyGlobal.directNotify.newCategory('NPCWalkerManagerAI')
    isStreet = False
    countSetting = 'walkers'
    defaultCount = WG.DEFAULT_COUNT

    def __init__(self, hood, zoneId, route):
        self.air = hood.air
        self.hood = hood
        self.zoneId = zoneId
        self.route = route
        self.walkers = []
        self.regulars = []
        self.lastPlayerTime = None
        self.nextRefill = 0.0

    def shutdown(self):
        _managers.pop(self.zoneId, None)
        if not _managers:
            taskMgr.remove('npcWalkerCheck')
            taskMgr.remove('npcWalkerBattles')
        self.removeAll()

    def getCount(self):
        try:
            count = int(GameConfig.get(self.countSetting, self.defaultCount))
        except (TypeError, ValueError):
            count = self.defaultCount
        return max(0, min(WG.MAX_COUNT, count))

    def update(self, playerCount):
        now = globalClock.getRealTime()
        if playerCount:
            self.lastPlayerTime = now
        elif self.lastPlayerTime is None or now - self.lastPlayerTime > EMPTY_GRACE:
            self.removeAll()
            return
        count = self.getCount()
        while len(self.regulars) < count + SPARE_REGULARS:
            self.regulars.append(_randomIdentity())
        if not self.walkers and playerCount:
            # The first toon to arrive finds the place already busy
            for i in range(count):
                self.spawn(teleportIn=False)
            return
        if len(self.walkers) < count and now >= self.nextRefill:
            self.spawn(teleportIn=True)
            self.nextRefill = now + random.uniform(*REFILL_DELAY)
        elif len(self.walkers) > count:
            idle = [w for w in self.walkers if not w.battleDoId]
            if idle:
                self.removeWalker(idle[-1])

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
        walker.setupFighter(identity['fighter'])
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

    def getLegPoints(self, fromNode, toNode):
        return [], 0

    def nearestNode(self, pos):
        return min(self.route, key=lambda n: Vec3(self.route[n][0] - pos).length())

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

    def claimTrolley(self, walker):
        return False

    def releaseTrolley(self, walker):
        pass


class PlaygroundWalkersAI(NPCWalkerManagerAI):

    def __init__(self, hood, route):
        NPCWalkerManagerAI.__init__(self, hood, hood.zoneId, route)
        self.trolleyUser = None
        self.trolleyApproach = WG.getTrolleyApproach(hood.canonicalHoodId)
        if self.trolleyApproach is not None:
            self.trolleyHop = WG.getTrolleyHop(hood.canonicalHoodId)
            self.trolleyNode = self.nearestNode(self.trolleyApproach)

    def getLegPoints(self, fromNode, toNode):
        return WG.getLegPoints(self.route, fromNode, toNode)

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


class StreetWalkersAI(NPCWalkerManagerAI):
    """A street's walkers. They live in the street's branch zone, which every toon on the street has interest in, so they can
    walk its whole length; they fight Cogs and join battles there."""
    isStreet = True
    countSetting = 'street_walkers'
    defaultCount = WG.DEFAULT_STREET_COUNT

    def __init__(self, hood, suitPlanner, route):
        NPCWalkerManagerAI.__init__(self, hood, suitPlanner.zoneId, route)
        self.suitPlanner = suitPlanner

    def getBattles(self):
        return list(self.suitPlanner.battleMgr.cellId2battle.values())

    def getBattleInZone(self, zoneId):
        return self.suitPlanner.battleMgr.getBattle(zoneId)

    def __hasRealToons(self, battle):
        return any(not isinstance(self.air.doId2do.get(t), DistributedNPCWalkerAI) for t in battle.toons)

    def canJoinBattle(self, battle):
        if not battle.toonCanJoin() or battle.fsm is None:
            return False
        if self.__hasRealToons(battle):
            # Help real toons, but leave a place for one more of their friends
            return len(battle.toons) < 3
        return len(battle.toons) < 4

    def findBattleToJoin(self, walker):
        pos = walker.getCurrentPos()
        battles = [b for b in self.getBattles() if self.canJoinBattle(b) and Vec3(b.pos - pos).length() < FIGHT_RANGE]
        if not battles:
            return None
        # Real toons' battles first
        battles.sort(key=lambda b: (not self.__hasRealToons(b), Vec3(b.pos - pos).length()))
        return battles[0]

    def getSuitPos(self, suit):
        elapsed = globalClock.getFrameTime() - suit.pathStartTime
        legIndex = suit.legList.getLegIndexAtTime(elapsed, suit.currentLeg)
        leg = suit.legList.getLeg(legIndex)
        return leg.getPosAtTime(elapsed - leg.getStartTime())

    def canFightSuit(self, suit):
        return (suit.doId in self.air.doId2do and suit.pathState == 1 and suit.legType == SuitLeg.TWalk and
                ZoneUtil.getCanonicalZoneId(suit.zoneId) in self.suitPlanner.battlePosDict and
                not self.suitPlanner.battleMgr.cellHasBattle(suit.zoneId))

    def findSuitToFight(self, walker):
        walkerBattles = [b for b in self.getBattles() if not self.__hasRealToons(b)]
        if len(walkerBattles) >= MAX_WALKER_BATTLES:
            return None
        pos = walker.getCurrentPos()
        suits = [s for s in self.suitPlanner.suitList if self.canFightSuit(s)]
        suits = [s for s in suits if Vec3(self.getSuitPos(s) - pos).length() < FIGHT_RANGE]
        if not suits:
            return None
        return min(suits, key=lambda s: Vec3(self.getSuitPos(s) - pos).length())
