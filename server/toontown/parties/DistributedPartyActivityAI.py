from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties import PartyGlobals
from toontown.parties import PartyUtils
from toontown.toonbase import ToontownGlobals


class DistributedPartyActivityAI(DistributedObjectAI):
    """One activity at a running party. Keeps who is playing it; subclasses add the game.

    activityTuple is the planner's (activityId, gridX, gridY, gridH); the client wants the position in world units."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyActivityAI')

    def __init__(self, air, party, activityTuple):
        DistributedObjectAI.__init__(self, air)
        self.party = party
        self.activityId, gridX, gridY, gridH = activityTuple
        self.x = PartyUtils.convertDistanceFromPartyGrid(gridX, 0)
        self.y = PartyUtils.convertDistanceFromPartyGrid(gridY, 1)
        self.h = PartyUtils.convertDegreesFromPartyGrid(gridH)
        self.toonsPlaying = []

    def delete(self):
        self.ignoreAll()
        self.party = None
        DistributedObjectAI.delete(self)

    def getX(self):
        return self.x

    def getY(self):
        return self.y

    def getH(self):
        return self.h

    def getPartyDoId(self):
        return self.party.doId

    def toonJoinRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.toonsPlaying or avId not in self.air.doId2do or not self.canJoin(avId):
            self.sendUpdateToAvatarId(avId, 'joinRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        self.addToon(avId)

    def toonExitRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toonsPlaying or not self.canExit(avId):
            self.sendUpdateToAvatarId(avId, 'exitRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        self.removeToon(avId)

    def toonExitDemand(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.toonsPlaying:
            self.removeToon(avId)

    def toonReady(self):
        pass

    def canJoin(self, avId):
        return True

    def canExit(self, avId):
        return True

    def addToon(self, avId):
        self.toonsPlaying.append(avId)
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__toonLeftDistrict, extraArgs=[avId])
        self.d_setToonsPlaying()
        self.toonJoined(avId)

    def removeToon(self, avId):
        if avId not in self.toonsPlaying:
            return
        self.toonsPlaying.remove(avId)
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.d_setToonsPlaying()
        self.toonExited(avId)

    def __toonLeftDistrict(self, avId):
        if avId in self.toonsPlaying:
            self.removeToon(avId)

    def toonJoined(self, avId):
        pass

    def toonExited(self, avId):
        pass

    def d_setToonsPlaying(self):
        self.sendUpdate('setToonsPlaying', [self.toonsPlaying])

    def d_setState(self, state):
        self.sendUpdate('setState', [state, globalClockDelta.getRealNetworkTime()])

    def rewardBeans(self, avId, earned, message=''):
        """Puts jellybeans in the toon's jar (more on Jellybean Days) and shows them the reward screen, also for none:
        some activities only let the toon walk again once that screen is closed."""
        toon = self.air.doId2do.get(avId)
        if toon is None:
            return 0
        earned = max(0, earned)
        if self.air.holidayManager.isHolidayRunning(ToontownGlobals.JELLYBEAN_PARTIES_HOLIDAY) or \
                self.air.holidayManager.isHolidayRunning(ToontownGlobals.JELLYBEAN_PARTIES_HOLIDAY_MONTH):
            earned = int(earned * PartyGlobals.JellybeanMultiplier)
        jarBefore = toon.getMoney()
        toon.addMoney(earned)
        self.sendUpdateToAvatarId(avId, 'showJellybeanReward', [earned, min(jarBefore, 255), message])
        return earned
