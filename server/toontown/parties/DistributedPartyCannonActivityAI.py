from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties import PartyUtils
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.DistributedPartyCannonAI import DistributedPartyCannonAI
from toontown.toonbase import TTLocalizer


class DistributedPartyCannonActivityAI(DistributedPartyActivityAI):
    """All of a party's cannons and the clouds above them. Each cannon seats a toon and lets them aim; once it is lit
    the flight belongs to this activity, which shows it to everyone, colours the clouds the toon bounces off and pays
    for those clouds when they land."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyCannonActivityAI')
    # PartyLoader puts 12 clouds on each of three rings and numbers each one by its ring's radius followed by its index.
    CloudNumbers = frozenset(int('%d%d' % (radius, index)) for radius in (50, 70, 30) for index in range(12))

    def __init__(self, air, party, cannonTuples):
        DistributedPartyActivityAI.__init__(self, air, party, cannonTuples[0])
        self.cannonTuples = cannonTuples
        self.cannons = []
        self.cloudsHitByFlyingToon = {}
        self.cloudColors = {}
        self.beansEarned = {}

    def announceGenerate(self):
        DistributedPartyActivityAI.announceGenerate(self)
        for activityId, gridX, gridY, gridH in self.cannonTuples:
            cannon = DistributedPartyCannonAI(self.air, self.doId,
                                              PartyUtils.convertDistanceFromPartyGrid(gridX, 0),
                                              PartyUtils.convertDistanceFromPartyGrid(gridY, 1),
                                              PartyUtils.convertDegreesFromPartyGrid(gridH))
            cannon.generateWithRequired(self.zoneId)
            self.cannons.append(cannon)

    def delete(self):
        for cannon in self.cannons:
            cannon.requestDelete()
        self.cannons = []
        DistributedPartyActivityAI.delete(self)

    def canJoin(self, avId):
        # Toons get in through the cannons. setToonsPlaying would also replace the list of flying toons the clients
        # keep themselves, which they expect to still hold a toon when it lands.
        return False

    def isToonInCannon(self, avId):
        return any(cannon.avId == avId for cannon in self.cannons)

    def fireToon(self, cannonId, avId, zRot, angle):
        self.cloudsHitByFlyingToon[avId] = 0
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__endFlight, extraArgs=[avId])
        self.sendUpdate('setCannonWillFire', [cannonId, zRot, angle])

    def __endFlight(self, avId):
        self.ignore(self.air.getAvatarExitEvent(avId))
        return self.cloudsHitByFlyingToon.pop(avId, 0)

    def setToonTrajectoryAi(self, launchTime, x, y, z, h, p, r, vx, vy, vz):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.cloudsHitByFlyingToon:
            self.sendUpdate('setToonTrajectory', [avId, launchTime, x, y, z, h, p, r, vx, vy, vz])

    def updateToonTrajectoryStartVelAi(self, vx, vy, vz):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.cloudsHitByFlyingToon:
            self.sendUpdate('updateToonTrajectoryStartVel', [avId, vx, vy, vz])

    def requestCloudHit(self, cloudNumber, r, g, b):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.cloudsHitByFlyingToon or cloudNumber not in self.CloudNumbers:
            return
        self.cloudsHitByFlyingToon[avId] += 1
        self.cloudColors[cloudNumber] = (r, g, b)
        self.sendUpdate('setCloudHit', [cloudNumber, r, g, b])

    def cloudsColorRequest(self):
        avId = self.air.getAvatarIdFromSender()
        cloudColors = [[cloudNumber, r, g, b] for cloudNumber, (r, g, b) in self.cloudColors.items()]
        self.sendUpdateToAvatarId(avId, 'cloudsColorResponse', [cloudColors])

    def setLanded(self, toonId):
        avId = self.air.getAvatarIdFromSender()
        if toonId != avId or avId not in self.cloudsHitByFlyingToon:
            return
        cloudsHit = self.__endFlight(avId)
        # A toon who hit clouds keeps waiting for their reward screen after landing, and once the landing movie has
        # dropped them from the flying toons the client ignores it, so the reward goes first, down the same channel.
        if cloudsHit:
            self.__rewardCloudsHit(avId, cloudsHit)
        self.sendUpdateToAvatarId(avId, 'setMovie', [PartyGlobals.CANNON_MOVIE_LANDED, avId])

    def __rewardCloudsHit(self, avId, cloudsHit):
        alreadyEarned = self.beansEarned.get(avId, 0)
        earned = min(cloudsHit * PartyGlobals.CannonJellyBeanReward, PartyGlobals.CannonMaxTotalReward - alreadyEarned)
        self.beansEarned[avId] = alreadyEarned + earned
        self.rewardBeans(avId, earned, TTLocalizer.PartyCannonResults % (earned, cloudsHit))
