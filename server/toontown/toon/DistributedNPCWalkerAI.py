import random
import traceback
from panda3d.core import Point3, Vec3
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from otp.avatar.DistributedPlayerAI import DistributedPlayerAI
from toontown.hood import ZoneUtil
from toontown.toonbase import ToontownGlobals
from . import DistributedNPCToonBaseAI
from . import Experience
from . import InventoryBase
from . import NPCWalkerBattleAI
from . import NPCWalkerGlobals as WG

# How far a walker strays from the route's nodes, so a group does not walk in single file
NODE_SPREAD = 2.5
GREET_COOLDOWN = 90.0
# A chase after a Cog gives up after this many tries to catch it
MAX_CHASES = 3
# Within this many feet of a Cog, a walker starts the battle
CATCH_DISTANCE = 30.0


class DistributedNPCWalkerAI(DistributedNPCToonBaseAI.DistributedNPCToonBaseAI):
    """A toon that wanders around a playground or street so it feels busy. NPCWalkerManagerAI creates and removes them.

    The server owns where the walker is: each setWalk names a path and the time it started, and every client walks the toon
    along it by itself, so a walk costs one message. On a street it also fights Cogs, alone or in real toons' battles
    (NPCWalkerBattleAI plays its part in the battle).
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
        self.gameAccess = ToontownGlobals.AccessFull
        self.battleDoId = None
        self.battlePos = None
        self.battleState = None
        self.battleStateSince = 0.0
        self.battleChoiceDelay = 0.0
        self.battleTries = 0
        self.joinsSeen = {}
        self.chases = 0

    def setupFighter(self, stats):
        """Gives the walker its laff, gag tracks, experience and a full gag pouch, before it is generated."""
        self.setMaxHp(stats['maxHp'])
        self.setHp(stats['maxHp'])
        self.setTrackAccess(list(stats['tracks']))
        self.experience = Experience.Experience(owner=self)
        self.experience.experience = list(stats['experience'])
        self.setMaxCarry(stats['maxCarry'])
        self.inventory = InventoryBase.InventoryBase(self)
        self.inventory.maxOutInv(1, 0)
        self.setBattleId(0)
        self.setCogTypes([0] * 4)
        self.setCogLevels([0] * 4)
        self.setCogParts([0] * 4)
        self.setCogMerits([0] * 4)
        # The rest of what battles, rewards and ToonTasks read from a toon, which a player's toon gets from the database
        self.trackBonusLevel = [-1] * len(stats['tracks'])
        self.pinkSlips = 0
        self.DISLid = 0
        self.rewardTier = 0
        self.rewardHistory = []
        self.questHistory = []
        self.questCarryLimit = 1

    def getGameAccess(self):
        return ToontownGlobals.AccessFull

    def sendUpdate(self, fieldName, args=[]):
        # A walker's network class has only the toon fields its look and its battles need; the rest of DistributedToonAI's
        # updates (gags, experience, quests...) stay on the server
        if self.dclass.getFieldByName(fieldName) is None:
            return
        DistributedNPCToonBaseAI.DistributedNPCToonBaseAI.sendUpdate(self, fieldName, args)

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
        self.battleDoId = None
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
        if self.manager.isStreet and len(points) > 1:
            # Streets slope and curb: keep to the ground all the way
            flags |= WG.FLAG_RAYCAST
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
            legPoints, raycast = self.manager.getLegPoints(fromNode, toNode)
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
            try:
                method(*extraArgs)
            except Exception:
                # Walkers are decoration: a mistake in one must never stop the district. Send it home instead
                self.notify.warning('walker %s: %s' % (self.doId, traceback.format_exc()))
                if self.manager:
                    self.manager.walkerLeft(self, 60)
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
        if self.manager.isStreet:
            self.__decideOnStreet()
            return
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

    # Streets: fighting Cogs

    def __decideOnStreet(self):
        battle = self.manager.findBattleToJoin(self)
        if battle is not None and random.random() < 0.7:
            self.__goToBattle(battle)
            return
        roll = random.random()
        if roll < 0.35:
            suit = self.manager.findSuitToFight(self)
            if suit is not None:
                self.chases = 0
                self.__chase(suit)
                return
        if roll > 0.95 and self.manager.mayLeave():
            self.__leave()
        else:
            self.__wander()

    def __pathToward(self, target):
        """The points from where the walker stands along the route to the node nearest target, and on to target."""
        nodes = self.manager.pathTo(self.node, self.manager.nearestNode(target))
        points, flags = self.__routePoints(nodes)
        points.append(Point3(target))
        self.node = nodes[-1]
        return points, flags | WG.FLAG_RUN

    def __chase(self, suit):
        if random.random() < 0.3 and self.chases == 0:
            self.d_doSpeedChat(random.choice((1102, 1000, 305)))
        points, flags = self.__pathToward(self.manager.getSuitPos(suit))
        duration = self.__sendPath(points, flags=flags)
        self.__later(duration, self.__reachSuit, [suit])

    def __reachSuit(self, suit):
        self.chases += 1
        if not self.manager.canFightSuit(suit):
            self.__idle(random.uniform(1, 3))
            return
        pos = self.getCurrentPos()
        if Vec3(self.manager.getSuitPos(suit) - pos).length() > CATCH_DISTANCE:
            if self.chases < MAX_CHASES:
                self.__chase(suit)
            else:
                self.__idle(random.uniform(1, 3))
            return
        self.__stand()
        NPCWalkerBattleAI.asToon(self.air, self.doId, suit.requestBattle, pos[0], pos[1], pos[2], 0, 0, 0)
        battle = self.manager.getBattleInZone(suit.zoneId)
        if battle is not None and self.doId in battle.toons:
            self.__enterBattle(battle)
        else:
            self.__idle(random.uniform(1, 3))

    def __goToBattle(self, battle):
        if random.random() < 0.4:
            self.d_doSpeedChat(random.choice((1000, 513, 508)))
        toBattle = Vec3(self.getCurrentPos() - battle.pos)
        toBattle.normalize()
        points, flags = self.__pathToward(Point3(battle.pos + toBattle * 12))
        duration = self.__sendPath(points, flags=flags)
        self.__later(duration, self.__reachBattle, [battle.doId])

    def __reachBattle(self, battleId):
        battle = self.air.doId2do.get(battleId)
        if battle is None or not self.manager.canJoinBattle(battle):
            self.__idle(random.uniform(1, 3))
            return
        pos = self.getCurrentPos()
        self.__stand()
        NPCWalkerBattleAI.asToon(self.air, self.doId, battle.toonRequestJoin, pos[0], pos[1], pos[2])
        if self.doId in battle.toons:
            self.__enterBattle(battle)
        else:
            self.__idle(random.uniform(1, 3))

    def __enterBattle(self, battle):
        taskMgr.remove(self.uniqueName('walkerNext'))
        self.battleDoId = battle.doId
        self.battlePos = Point3(battle.pos)
        self.battleState = None
        self.joinsSeen = {}

    def driveBattle(self, now):
        """Called twice a second while the walker is in a battle (see NPCWalkerManagerAI)."""
        battle = self.air.doId2do.get(self.battleDoId)
        if battle is None or battle.fsm is None or self.doId not in battle.toons:
            self.__leaveBattle()
            return
        NPCWalkerBattleAI.drive(self, battle, now)

    def __leaveBattle(self):
        self.battleDoId = None
        self.b_setBattleId(0)
        # The battle left the toon standing around its middle; walk on from there
        self.__setPath([self.battlePos], WG.KEEP_HEADING, 0)
        self.node = self.manager.nearestNode(self.battlePos)
        if self.hp <= 0:
            self.leaving = True
            self.d_doSpeedChat(random.choice((401, 403, 410)))
            self.__later(4, self.__teleportOut)
        elif self.hp < self.maxHp * 0.4 and random.random() < 0.7:
            # Off to the playground to heal up
            self.__later(2, self.__leave)
        else:
            self.inventory.maxOutInv(1, 0)
            roll = random.random()
            if roll < 0.4:
                self.d_playEmote(6)
            elif roll < 0.7:
                self.d_doSpeedChat(random.choice((505, 506, 509, 304, 315)))
            self.__later(random.uniform(3, 6), self.__decide)

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
        """For the ~walkers magic word: go to the trolley, fight a Cog, join a battle or leave now. False when the walker
        cannot."""
        if self.leaving or self.atTrolley or self.battleDoId:
            return False
        if action == 'trolley':
            if not self.manager.claimTrolley(self):
                return False
            self.__goToTrolley()
        elif action == 'fight':
            suit = self.manager.findSuitToFight(self) if self.manager.isStreet else None
            if suit is None:
                return False
            self.chases = 0
            self.__chase(suit)
        elif action == 'join':
            battle = self.manager.findBattleToJoin(self) if self.manager.isStreet else None
            if battle is None:
                return False
            self.__goToBattle(battle)
        else:
            self.__leave()
        return True

    # A real toon walked up to this one

    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if not isinstance(av, DistributedPlayerAI) or ZoneUtil.getBranchZone(av.zoneId) != self.zoneId:
            return
        now = globalClock.getRealTime()
        if self.battleDoId or self.leaving or self.atTrolley or self.walkFlags & WG.FLAG_HIDDEN or now - self.lastGreet.get(avId, -GREET_COOLDOWN) < GREET_COOLDOWN:
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
