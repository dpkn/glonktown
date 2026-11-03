from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.minigame import CannonGameGlobals
from toontown.parties import PartyGlobals


class DistributedPartyCannonAI(DistributedObjectAI):
    """One cannon at a party. Seats one toon at a time and relays their aim; lighting it hands the shot to the
    cannon activity. A toon who doesn't light it before their timer runs out is put back out."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyCannonAI')
    # The client's Cannon.py bounds; the barrel angle shares the cannon minigame's.
    MinRotation = -70
    MaxRotation = 70
    NetworkSlack = 2.0
    FiredTimeout = 10.0

    def __init__(self, air, activityDoId, x, y, h):
        DistributedObjectAI.__init__(self, air)
        self.activityDoId = activityDoId
        self.posHpr = [x, y, 0, h, 0, 0]
        self.avId = 0
        self.isLit = False
        self.timerStarted = False

    def delete(self):
        taskMgr.remove(self.taskName('timeout'))
        self.ignoreAll()
        DistributedObjectAI.delete(self)

    def getActivityDoId(self):
        return self.activityDoId

    def getPosHpr(self):
        return self.posHpr

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def requestEnter(self):
        avId = self.air.getAvatarIdFromSender()
        toon = self.air.doId2do.get(avId)
        activity = self.air.doId2do.get(self.activityDoId)
        if self.avId or toon is None or toon.zoneId != self.zoneId or activity is None or activity.isToonInCannon(avId):
            self.sendUpdateToAvatarId(avId, 'requestExit', [])
            return
        self.avId = avId
        self.isLit = False
        self.timerStarted = False
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__removeToon)
        self.d_setMovie(PartyGlobals.CANNON_MOVIE_LOAD, avId)
        self.__startTimeout(PartyGlobals.DefaultRulesTimeout + PartyGlobals.CANNON_TIMEOUT + self.NetworkSlack)

    def setTimeout(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.isAiming(avId) or self.timerStarted:
            return
        self.timerStarted = True
        self.__startTimeout(PartyGlobals.CANNON_TIMEOUT + self.NetworkSlack)

    def setCannonPosition(self, zRot, angle):
        avId = self.air.getAvatarIdFromSender()
        if self.isAiming(avId):
            self.sendUpdate('updateCannonPosition', [avId] + self.boundAim(zRot, angle))

    def setCannonLit(self, zRot, angle):
        avId = self.air.getAvatarIdFromSender()
        activity = self.air.doId2do.get(self.activityDoId)
        if not self.isAiming(avId) or activity is None:
            return
        self.isLit = True
        activity.fireToon(self.doId, avId, *self.boundAim(zRot, angle))
        self.__startTimeout(self.FiredTimeout)

    def setFired(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId and avId == self.avId and self.isLit:
            self.__emptyCannon(PartyGlobals.CANNON_MOVIE_CLEAR)

    def setLanded(self, toonId):
        avId = self.air.getAvatarIdFromSender()
        if toonId == avId and self.isAiming(avId):
            self.__emptyCannon(PartyGlobals.CANNON_MOVIE_CLEAR)

    def isAiming(self, avId):
        return self.avId != 0 and avId == self.avId and not self.isLit

    def boundAim(self, zRot, angle):
        return [min(max(zRot, self.MinRotation), self.MaxRotation),
                min(max(angle, CannonGameGlobals.CANNON_ANGLE_MIN), CannonGameGlobals.CANNON_ANGLE_MAX)]

    def __startTimeout(self, delay):
        taskMgr.remove(self.taskName('timeout'))
        taskMgr.doMethodLater(delay, self.__handleTimeout, self.taskName('timeout'))

    def __handleTimeout(self, task):
        self.__removeToon()
        return task.done

    def __removeToon(self):
        # A lit toon is already on their way out of the barrel, and forcing them out would unload the aiming
        # controls their flight still uses; clearing just frees the cannon.
        if self.isLit:
            self.__emptyCannon(PartyGlobals.CANNON_MOVIE_CLEAR)
        else:
            self.__emptyCannon(PartyGlobals.CANNON_MOVIE_FORCE_EXIT)

    def __emptyCannon(self, movie):
        avId = self.avId
        taskMgr.remove(self.taskName('timeout'))
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.avId = 0
        self.isLit = False
        self.d_setMovie(movie, avId)
