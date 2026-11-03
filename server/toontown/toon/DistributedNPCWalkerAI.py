import random
from panda3d.core import Point3, Vec3
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from otp.avatar.DistributedPlayerAI import DistributedPlayerAI
from . import DistributedNPCToonBaseAI
from . import NPCWalkerGlobals as WG

# How far a walker strays from the route's nodes, so a group does not walk in single file
NODE_SPREAD = 2.5
GREET_COOLDOWN = 90.0


class DistributedNPCWalkerAI(DistributedNPCToonBaseAI.DistributedNPCToonBaseAI):
    """A toon that wanders around a playground so it feels busy. NPCWalkerManagerAI creates and removes them.

    The server owns where the walker is: each setWalk names a path and the time it started, and every client walks the toon
    along it by itself, so a walk costs one message.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedNPCWalkerAI')

    def __init__(self, air, manager, identity):
        DistributedNPCToonBaseAI.DistributedNPCToonBaseAI.__init__(self, air, 0)
        self.manager = manager
        self.identity = identity
        self.route = manager.route
        self.givesQuests = 0
        self.busy = 0
        self.node = None
        self.leaving = False
        self.atTrolley = False
        self.lastGreet = {}
        self.walkPoints = [Point3(0, 0, 0)]
        self.walkStart = 0.0
        self.walkDuration = 0.0
        self.walkHeading = WG.KEEP_HEADING
        self.walkFlags = 0
        self.walkStamp = 0

    def placeAt(self, node, hidden=False):
        """Puts the walker on a node before it is generated; a hidden one stays out of sight until it teleports in."""
        self.node = node
        self.__setPath([self.__nodePoint(node)], random.randint(0, 359), WG.FLAG_HIDDEN if hidden else 0)

    def startLife(self, teleportIn):
        if teleportIn:
            self.d_doTeleport(WG.TELEPORT_IN)
            self.__later(3.5, self.__arrived)
        elif random.random() < 0.5:
            self.__wander()
        else:
            self.__idle(random.uniform(0, 8))

    def delete(self):
        taskMgr.remove(self.uniqueName('walkerNext'))
        taskMgr.remove(self.uniqueName('walkerChat'))
        self.manager = None
        DistributedNPCToonBaseAI.DistributedNPCToonBaseAI.delete(self)

    # The path every client walks the toon along

    def getWalk(self):
        points = [(p[0], p[1], p[2]) for p in self.walkPoints]
        return [points, self.walkHeading, self.walkFlags, self.walkStamp]

    def __setPath(self, points, heading, flags):
        self.walkPoints = points
        self.walkHeading = heading
        self.walkFlags = flags
        self.walkStart = globalClock.getRealTime()
        self.walkStamp = globalClockDelta.getRealNetworkTime()
        speed = WG.RUN_SPEED if flags & WG.FLAG_RUN else WG.WALK_SPEED
        self.walkDuration = WG.pathLength(points) / speed
        return self.walkDuration

    def __sendPath(self, points, heading=WG.KEEP_HEADING, flags=0):
        duration = self.__setPath(points, heading, flags)
        self.sendUpdate('setWalk', self.getWalk())
        return duration

    def __progress(self):
        """Where the walker is now, partway along its path, and the points of the path it has still to walk."""
        points = self.walkPoints
        if len(points) == 1 or self.walkDuration <= 0:
            return Point3(points[-1]), []
        travelled = min(1.0, (globalClock.getRealTime() - self.walkStart) / self.walkDuration) * WG.pathLength(points)
        for i in range(len(points) - 1):
            leg = Vec3(points[i + 1] - points[i])
            if travelled < leg.length():
                return Point3(points[i] + leg * (travelled / leg.length())), [Point3(p) for p in points[i + 1:]]
            travelled -= leg.length()
        return Point3(points[-1]), []

    def getCurrentPos(self):
        return self.__progress()[0]

    def __stand(self, heading=WG.KEEP_HEADING):
        self.__sendPath([self.getCurrentPos()], heading)

    def __nodePoint(self, node):
        pos = WG.CCharPaths.getNodePos(node, self.route)
        return Point3(pos[0] + random.uniform(-NODE_SPREAD, NODE_SPREAD), pos[1] + random.uniform(-NODE_SPREAD, NODE_SPREAD), pos[2])

    def __routePoints(self, nodes):
        """The points through a list of neighbouring nodes, starting where the walker stands (finishing a walk that was cut short
        first, since nodes[0] is where that walk was going), and the setWalk raycast flag."""
        pos, remaining = self.__progress()
        points = [pos] + remaining
        flags = self.walkFlags & WG.FLAG_RAYCAST if remaining else 0
        for fromNode, toNode in zip(nodes, nodes[1:]):
            legPoints, raycast = WG.getLegPoints(self.route, fromNode, toNode)
            points += legPoints
            points.append(self.__nodePoint(toNode))
            if raycast:
                flags |= WG.FLAG_RAYCAST
        return points, flags

    # What the walker does

    def __later(self, delay, method, extraArgs=[]):
        taskMgr.remove(self.uniqueName('walkerNext'))
        taskMgr.doMethodLater(delay, self.__run, self.uniqueName('walkerNext'), extraArgs=[method, extraArgs])

    def __run(self, method, extraArgs):
        if self.manager:
            method(*extraArgs)
        return Task.done

    def __arrived(self):
        self.__stand()
        self.__idle(random.uniform(2, 6))

    def __idle(self, duration=None):
        if duration is None:
            duration = random.uniform(3, 12)
        roll = random.random()
        if roll < 0.3:
            self.d_playEmote(random.choice(WG.IdleEmotes))
        elif roll < 0.5:
            self.d_doSpeedChat(random.choice(WG.IdlePhrases))
        self.__later(duration, self.__decide)

    def __decide(self):
        roll = random.random()
        if roll < 0.12 and self.manager.claimTrolley(self):
            self.__goToTrolley()
        elif roll < 0.15 and self.manager.mayLeave():
            self.__leave()
        else:
            self.__wander()

    def __wander(self):
        nodes = [self.node]
        for i in range(random.choice((1, 1, 2, 2, 3))):
            neighbours = [n for n in WG.getNeighbours(self.route, nodes[-1]) if len(nodes) < 2 or n != nodes[-2]]
            if not neighbours:
                neighbours = WG.getNeighbours(self.route, nodes[-1])
            nodes.append(random.choice(neighbours))
        points, flags = self.__routePoints(nodes)
        if random.random() < 0.3:
            flags |= WG.FLAG_RUN
        self.node = nodes[-1]
        duration = self.__sendPath(points, flags=flags)
        if random.random() < 0.6:
            self.__later(duration, self.__idle)
        else:
            self.__later(duration, self.__decide)

    def __goToTrolley(self):
        nodes = self.manager.pathTo(self.node, self.manager.trolleyNode)
        if nodes[-1] != self.manager.trolleyNode:
            self.manager.releaseTrolley(self)
            self.__wander()
            return
        points, flags = self.__routePoints(nodes)
        points.append(self.manager.trolleyApproach)
        self.node = None
        self.atTrolley = True
        if random.random() < 0.4:
            self.d_doSpeedChat(random.choice(WG.TrolleyPhrases))
        duration = self.__sendPath(points, flags=flags | WG.FLAG_RAYCAST | WG.FLAG_RUN)
        self.__later(duration + 0.5, self.__atTrolley)

    def __atTrolley(self):
        if not self.manager.trolleyIsFree():
            # Real toons are boarding or the trolley is away: never ride with them; walk off instead
            self.d_playEmote(5)
            self.__later(3, self.__walkAwayFromTrolley)
            return
        self.leaving = True
        hop = self.manager.trolleyHop
        self.sendUpdate('doBoardTrolley', [hop[0], hop[1], hop[2], globalClockDelta.getRealNetworkTime()])
        self.__later(2.5, self.__gone, [random.uniform(*WG.TROLLEY_TRIP_TIME)])

    def __walkAwayFromTrolley(self):
        self.atTrolley = False
        self.manager.releaseTrolley(self)
        self.node = self.manager.trolleyNode
        duration = self.__sendPath([self.getCurrentPos(), self.__nodePoint(self.node)], flags=WG.FLAG_RAYCAST)
        self.d_doSpeedChat(1017)
        self.__later(duration, self.__idle)

    def __leave(self):
        self.leaving = True
        self.__stand()
        self.d_doSpeedChat(random.choice(WG.LeavePhrases))
        self.__later(2, self.__teleportOut)

    def __teleportOut(self):
        self.d_doTeleport(WG.TELEPORT_OUT)
        self.__later(4, self.__gone, [random.uniform(60, 240)])

    def __gone(self, awayTime):
        self.manager.walkerLeft(self, awayTime)

    def command(self, action):
        """For the ~walkers magic word: go to the trolley or leave now. False when the walker cannot."""
        if self.leaving or self.atTrolley:
            return False
        if action == 'trolley':
            if not self.manager.claimTrolley(self):
                return False
            self.__goToTrolley()
        else:
            self.__leave()
        return True

    # A real toon walked up to this one

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if not isinstance(av, DistributedPlayerAI) or av.zoneId != self.zoneId:
            return
        now = globalClock.getRealTime()
        if self.leaving or self.atTrolley or self.walkFlags & WG.FLAG_HIDDEN or now - self.lastGreet.get(avId, -GREET_COOLDOWN) < GREET_COOLDOWN:
            return
        self.lastGreet[avId] = now
        if random.random() < 0.3:
            return
        self.__stand()
        self.d_playEmote(WG.EmoteWave, avId)
        taskMgr.doMethodLater(1.0, self.__greet, self.uniqueName('walkerChat'))
        self.__later(random.uniform(4, 8), self.__decide)

    def __greet(self, task):
        self.d_doSpeedChat(random.choice(WG.GreetPhrases))
        return Task.done

    # Messages

    def d_playEmote(self, emote, lookAtAvId=0):
        self.sendUpdate('playEmote', [emote, lookAtAvId, globalClockDelta.getRealNetworkTime()])

    def d_doSpeedChat(self, msgIndex):
        self.sendUpdate('doSpeedChat', [msgIndex])

    def d_doTeleport(self, direction):
        self.sendUpdate('doTeleport', [direction, globalClockDelta.getRealNetworkTime()])
