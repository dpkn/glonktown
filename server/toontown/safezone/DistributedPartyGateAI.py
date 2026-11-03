from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedPartyGateAI(DistributedObjectAI):
    """The gate in Toontown Central that lists the public parties running now and sends a toon to the one they pick."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyGateAI')

    def getPartyList(self, avId):
        senderId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(senderId, 'listAllPublicParties', [self.air.partyManager.getPublicParties()])

    def partyChoiceRequest(self, avId, shardId, zoneId):
        senderId = self.air.getAvatarIdFromSender()
        partyInfo, denialReason = self.air.partyManager.choosePublicParty(senderId, zoneId)
        if partyInfo is None:
            self.sendUpdateToAvatarId(senderId, 'partyRequestDenied', [denialReason])
        else:
            self.sendUpdateToAvatarId(senderId, 'setParty', [partyInfo])
