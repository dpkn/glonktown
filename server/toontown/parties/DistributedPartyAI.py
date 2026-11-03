from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.parties.PartyGlobals import ActivityIds
from toontown.parties.DistributedPartyCannonActivityAI import DistributedPartyCannonActivityAI
from toontown.parties.DistributedPartyCatchActivityAI import DistributedPartyCatchActivityAI
from toontown.parties.DistributedPartyCogActivityAI import DistributedPartyCogActivityAI
from toontown.parties.DistributedPartyDance20ActivityAI import DistributedPartyDance20ActivityAI
from toontown.parties.DistributedPartyDanceActivityAI import DistributedPartyDanceActivityAI
from toontown.parties.DistributedPartyFireworksActivityAI import DistributedPartyFireworksActivityAI
from toontown.parties.DistributedPartyJukebox40ActivityAI import DistributedPartyJukebox40ActivityAI
from toontown.parties.DistributedPartyJukeboxActivityAI import DistributedPartyJukeboxActivityAI
from toontown.parties.DistributedPartyTrampolineActivityAI import DistributedPartyTrampolineActivityAI
from toontown.parties.DistributedPartyTugOfWarActivityAI import DistributedPartyTugOfWarActivityAI
from toontown.parties.DistributedPartyValentineDance20ActivityAI import DistributedPartyValentineDance20ActivityAI
from toontown.parties.DistributedPartyValentineDanceActivityAI import DistributedPartyValentineDanceActivityAI
from toontown.parties.DistributedPartyValentineJukebox40ActivityAI import DistributedPartyValentineJukebox40ActivityAI
from toontown.parties.DistributedPartyValentineJukeboxActivityAI import DistributedPartyValentineJukeboxActivityAI
from toontown.parties.DistributedPartyValentineTrampolineActivityAI import DistributedPartyValentineTrampolineActivityAI
from toontown.parties.DistributedPartyVictoryTrampolineActivityAI import DistributedPartyVictoryTrampolineActivityAI
from toontown.parties.DistributedPartyWinterCatchActivityAI import DistributedPartyWinterCatchActivityAI
from toontown.parties.DistributedPartyWinterCogActivityAI import DistributedPartyWinterCogActivityAI
from toontown.parties.DistributedPartyWinterTrampolineActivityAI import DistributedPartyWinterTrampolineActivityAI


class DistributedPartyAI(DistributedObjectAI):
    """A party that has started, in its own zone of the Party Grounds, with one object per activity on the planner's grid.
    The cannons are one activity with a cannon object for each cannon placed."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyAI')
    ActivityClasses = {ActivityIds.PartyJukebox: DistributedPartyJukeboxActivityAI,
                       ActivityIds.PartyJukebox40: DistributedPartyJukebox40ActivityAI,
                       ActivityIds.PartyValentineJukebox: DistributedPartyValentineJukeboxActivityAI,
                       ActivityIds.PartyValentineJukebox40: DistributedPartyValentineJukebox40ActivityAI,
                       ActivityIds.PartyTrampoline: DistributedPartyTrampolineActivityAI,
                       ActivityIds.PartyValentineTrampoline: DistributedPartyValentineTrampolineActivityAI,
                       ActivityIds.PartyVictoryTrampoline: DistributedPartyVictoryTrampolineActivityAI,
                       ActivityIds.PartyWinterTrampoline: DistributedPartyWinterTrampolineActivityAI,
                       ActivityIds.PartyCatch: DistributedPartyCatchActivityAI,
                       ActivityIds.PartyWinterCatch: DistributedPartyWinterCatchActivityAI,
                       ActivityIds.PartyCog: DistributedPartyCogActivityAI,
                       ActivityIds.PartyWinterCog: DistributedPartyWinterCogActivityAI,
                       ActivityIds.PartyDance: DistributedPartyDanceActivityAI,
                       ActivityIds.PartyDance20: DistributedPartyDance20ActivityAI,
                       ActivityIds.PartyValentineDance: DistributedPartyValentineDanceActivityAI,
                       ActivityIds.PartyValentineDance20: DistributedPartyValentineDance20ActivityAI,
                       ActivityIds.PartyTugOfWar: DistributedPartyTugOfWarActivityAI,
                       ActivityIds.PartyFireworks: DistributedPartyFireworksActivityAI}

    def __init__(self, air, manager, partyId, party, startedTime):
        DistributedObjectAI.__init__(self, air)
        self.manager = manager
        self.partyId = partyId
        self.party = party
        self.startedTime = startedTime
        self.avIdsAtParty = []
        self.isPartyEnding = False
        self.activities = []

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        activities = [tuple(activity) for activity in self.party['activities']]
        cannons = [activity for activity in activities if activity[0] == ActivityIds.PartyCannon]
        for activity in activities:
            activityClass = self.ActivityClasses.get(activity[0])
            if activityClass is not None:
                self.__addActivity(activityClass(self.air, self, activity))
        if cannons:
            self.__addActivity(DistributedPartyCannonActivityAI(self.air, self, cannons))

    def __addActivity(self, activity):
        activity.generateWithRequired(self.zoneId)
        self.activities.append(activity)

    def delete(self):
        for activity in self.activities:
            activity.requestDelete()
        self.activities = []
        self.ignoreAll()
        DistributedObjectAI.delete(self)

    def getHostId(self):
        return self.party['hostId']

    def getPartyClockInfo(self):
        for activityId, x, y, h in self.party['activities']:
            if activityId == ActivityIds.PartyClock:
                return [x, y, h]
        return [0, 0, 0]

    def getInviteeIds(self):
        return [int(inviteeId) for inviteeId in self.party['invites']]

    def getPartyState(self):
        return self.isPartyEnding

    def b_setPartyState(self, isPartyEnding):
        self.isPartyEnding = isPartyEnding
        self.sendUpdate('setPartyState', [isPartyEnding])

    def getPartyInfoTuple(self):
        return self.manager.partyTuple(self.partyId, self.party)

    def getAvIdsAtParty(self):
        return self.avIdsAtParty

    def getPartyStartedTime(self):
        return self.startedTime

    def getHostName(self):
        return self.party['hostName']

    def avIdEnteredParty(self, avId):
        senderId = self.air.getAvatarIdFromSender()
        toon = self.air.doId2do.get(senderId)
        if toon is None or toon.zoneId != self.zoneId or senderId in self.avIdsAtParty:
            return
        self.avIdsAtParty.append(senderId)
        self.acceptOnce(self.air.getAvatarExitEvent(senderId), self.removeGuest, extraArgs=[senderId])
        self.sendUpdate('setAvIdsAtParty', [self.avIdsAtParty])

    def removeGuest(self, avId):
        """A toon left the party (walked out, teleported, logged off): it is taken out of every activity too."""
        if avId not in self.avIdsAtParty:
            return
        self.avIdsAtParty.remove(avId)
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.sendUpdate('setAvIdsAtParty', [self.avIdsAtParty])
        for activity in self.activities:
            activity.removeToon(avId)

    def removeGuestsWhoLeft(self):
        for avId in list(self.avIdsAtParty):
            toon = self.air.doId2do.get(avId)
            if toon is None or toon.zoneId != self.zoneId:
                self.removeGuest(avId)

    def getToonsInZone(self):
        return [do.doId for do in self.air.doId2do.values() if do.__class__.__name__ == 'DistributedToonAI' and do.zoneId == self.zoneId]
