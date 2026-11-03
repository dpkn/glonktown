from panda3d.core import *
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.interval.IntervalGlobal import *
from direct.controls.ControlManager import CollisionHandlerRayStart
from direct.showbase.PythonUtil import reduceAngle, closestDestAngle
from otp.otpbase import OTPGlobals, OTPLocalizer
from panda3d.otp import CFSpeech, CFQuicktalker, CFTimeout, NametagGroup
from toontown.toonbase import ToontownGlobals
from . import DistributedNPCToonBase
from . import NPCWalkerGlobals as WG

GREET_RESEND = 20.0
CATCH_UP_DISTANCE = 15.0


class DistributedNPCWalker(DistributedNPCToonBase.DistributedNPCToonBase):
    """A toon wandering around the playground (see DistributedNPCWalkerAI). The server sends the path and when the walk
    started; this walks the toon along it."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedNPCWalker')

    def __init__(self, cr):
        try:
            self.DistributedNPCWalker_initialized
        except:
            self.DistributedNPCWalker_initialized = 1
            DistributedNPCToonBase.DistributedNPCToonBase.__init__(self, cr)
            # Name tags like a real toon's (NPCs' are greyed out), but clicking one does nothing: there is no player to befriend
            self.setPickable(1)
            self.setPlayerType(NametagGroup.CCNormal)
            self.gameAccess = OTPGlobals.AccessFull
            self.placed = False
            self.walkInfo = None
            self.walkTrack = None
            self.boardTrack = None
            self.lastEnter = -GREET_RESEND
            self.__initFloorRay()

    def disable(self):
        self.__stopTracks()
        self.enableRaycast(0)
        DistributedNPCToonBase.DistributedNPCToonBase.disable(self)

    def delete(self):
        try:
            self.DistributedNPCWalker_deleted
        except:
            self.DistributedNPCWalker_deleted = 1
            self.__deleteFloorRay()
            DistributedNPCToonBase.DistributedNPCToonBase.delete(self)

    def generateToon(self):
        DistributedNPCToonBase.DistributedNPCToonBase.generateToon(self)
        self.setupToonNodes()

    def initToonState(self):
        self.setAnimState('neutral', 1.0)
        self.reparentTo(render)

    def announceGenerate(self):
        DistributedNPCToonBase.DistributedNPCToonBase.announceGenerate(self)
        self.__startWalk()

    def clickedNametag(self):
        pass

    def getCollSphereRadius(self):
        return 4.0

    def handleCollisionSphereEnter(self, collEntry):
        now = globalClock.getFrameTime()
        if now - self.lastEnter > GREET_RESEND:
            self.lastEnter = now
            self.sendUpdate('avatarEnter', [])

    # Keeping to the ground on slopes, as the classic characters do

    def __initFloorRay(self):
        self.cRay = CollisionRay(0.0, 0.0, CollisionHandlerRayStart, 0.0, 0.0, -1.0)
        self.cRayNode = CollisionNode('walkerRay')
        self.cRayNode.addSolid(self.cRay)
        self.cRayNodePath = self.attachNewNode(self.cRayNode)
        self.cRayNodePath.hide()
        self.cRayNode.setFromCollideMask(ToontownGlobals.FloorBitmask)
        self.cRayNode.setIntoCollideMask(BitMask32.allOff())
        self.lifter = CollisionHandlerFloor()
        self.lifter.setOffset(ToontownGlobals.FloorOffset)
        self.lifter.setReach(10.0)
        self.lifter.setMaxVelocity(0.0)
        self.lifter.addCollider(self.cRayNodePath, self)
        self.raycasting = False

    def __deleteFloorRay(self):
        self.cRayNodePath.removeNode()
        self.cRay = None
        self.cRayNode = None
        self.cRayNodePath = None
        self.lifter = None

    def enableRaycast(self, enable=1):
        if not hasattr(base, 'localAvatar') or not getattr(base.localAvatar, 'cTrav', None) or not self.cRayNodePath:
            return
        cTrav = base.localAvatar.cTrav
        if self.raycasting:
            cTrav.removeCollider(self.cRayNodePath)
            self.raycasting = False
        if enable:
            cTrav.addCollider(self.cRayNodePath, self.lifter)
            self.raycasting = True

    # Walking

    def setWalk(self, points, heading, flags, timestamp):
        self.walkInfo = ([Point3(*p) for p in points], heading, flags, timestamp)
        if self.isGenerated():
            self.__startWalk()

    def __stopTracks(self):
        if self.walkTrack:
            self.walkTrack.pause()
            self.walkTrack = None
        if self.boardTrack:
            self.boardTrack.finish()
            self.boardTrack = None
        if self.emote:
            self.emote.finish()
            self.emote = None

    def __startWalk(self):
        if not self.walkInfo:
            return
        points, heading, flags, timestamp = self.walkInfo
        self.__stopTracks()
        self.enableRaycast(0)
        if flags & WG.FLAG_HIDDEN:
            self.hide()
        elif self.animFSM.getCurrentState().getName() != 'TeleportIn':
            self.show()
        if len(points) == 1:
            self.placed = True
            self.setPos(points[0])
            if heading != WG.KEEP_HEADING:
                self.setH(heading)
            if self.animFSM.getCurrentState().getName() in ('walk', 'run'):
                self.setAnimState('neutral', 1.0)
            return
        if self.placed and Vec3(self.getPos() - points[0]).length() < CATCH_UP_DISTANCE:
            # Start from where the toon really stands (a battle leaves it a few feet from where the server thinks), not with a jump
            points[0] = self.getPos()
        self.placed = True
        run = flags & WG.FLAG_RUN
        speed = WG.RUN_SPEED if run else WG.WALK_SPEED
        track = Sequence(Func(self.setAnimState, 'run' if run else 'walk', 1.0))
        if flags & WG.FLAG_RAYCAST:
            track.append(Func(self.enableRaycast, 1))
        self.setPos(points[0])
        startHpr = self.getHpr()
        for start, end in zip(points, points[1:]):
            duration = Vec3(end - start).length() / speed
            if duration <= 0.01:
                continue
            curH = reduceAngle(self.getH())
            self.headsUp(end[0], end[1], start[2])
            destH = closestDestAngle(curH, reduceAngle(self.getH()))
            self.setH(destH)
            turnTime = min(duration, abs(destH - curH) / 270.0)
            track.append(Parallel(LerpHprInterval(self, turnTime, Vec3(destH, 0, 0), startHpr=Vec3(curH, 0, 0)),
                                  LerpPosInterval(self, duration, end, startPos=start, fluid=1)))
        self.setHpr(startHpr)
        track.append(Func(self.enableRaycast, 0))
        track.append(Func(self.setAnimState, 'neutral', 1.0))
        self.walkTrack = track
        track.start(globalClockDelta.localElapsedTime(timestamp))

    # Things the server asks for

    def playEmote(self, emote, lookAtAvId, timestamp):
        av = self.cr.doId2do.get(lookAtAvId)
        if av:
            self.headsUp(av)
        self.doEmote(emote, 1, globalClockDelta.localElapsedTime(timestamp))

    def doSpeedChat(self, msgIndex):
        text = OTPLocalizer.SpeedChatStaticText.get(msgIndex)
        if text:
            self.setChatAbsolute(text, CFSpeech | CFQuicktalker | CFTimeout)

    def doTeleport(self, direction, timestamp):
        self.__stopTracks()
        ts = globalClockDelta.localElapsedTime(timestamp)
        if direction == WG.TELEPORT_IN:
            self.show()
            self.setAnimState('TeleportIn', 1.0, timestamp, callback=self.__teleportedIn)
        else:
            self.setAnimState('TeleportOut', 1.0, timestamp)

    def __teleportedIn(self):
        self.setAnimState('neutral', 1.0)

    def doBoardTrolley(self, x, y, z, timestamp):
        self.__stopTracks()
        hop = Point3(x, y, z)
        self.headsUp(hop[0], hop[1], self.getZ())
        self.setTransparency(1)
        self.boardTrack = Sequence(Func(self.setAnimState, 'jump', 1.0),
                                   Wait(0.3),
                                   ProjectileInterval(self, duration=0.8, startPos=self.getPos(), endPos=hop),
                                   LerpColorScaleInterval(self, 0.5, Vec4(1, 1, 1, 0)),
                                   Func(self.hide),
                                   Func(self.clearColorScale))
        self.boardTrack.start(globalClockDelta.localElapsedTime(timestamp))
