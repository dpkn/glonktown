from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.PartyGlobals import ToonDancingStates


class DistributedPartyDanceActivityBaseAI(DistributedPartyActivityAI):
    """The dance floor. Toons join by stepping onto it and leave by stepping off. Each dancer's heading when they stepped
    on goes out with the dancer list (their arrow keys and camera are turned to it), and their dance moves are passed on to
    everyone else. The floor stays open the whole party: the client does not turn it off for the fireworks."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyDanceActivityBaseAI')
    dancePatternToAnims = PartyGlobals.DancePatternToAnims

    def __init__(self, air, party, activityTuple):
        DistributedPartyActivityAI.__init__(self, air, party, activityTuple)
        self.danceAnims = set(self.dancePatternToAnims.values())
        self.toonHeadings = {}

    def addToon(self, avId):
        self.toonHeadings[avId] = self.air.doId2do[avId].getH() % 360
        DistributedPartyActivityAI.addToon(self, avId)

    def toonExited(self, avId):
        self.toonHeadings.pop(avId, None)
        self.d_setDancingToonState(avId, ToonDancingStates.Cleanup, '')

    def toonExitRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toonsPlaying:
            self.sendUpdateToAvatarId(avId, 'exitRequestDenied', [PartyGlobals.DenialReasons.SilentFail])
            return
        self.removeToon(avId)

    def d_setToonsPlaying(self):
        headings = [self.toonHeadings[avId] for avId in self.toonsPlaying]
        self.sendUpdate('setToonsPlaying', [self.toonsPlaying, headings])

    def updateDancingToon(self, state, anim):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toonsPlaying:
            return
        if state == ToonDancingStates.Cleanup:
            self.removeToon(avId)
        elif state in (ToonDancingStates.Run, ToonDancingStates.DanceMove) and (not anim or anim in self.danceAnims):
            self.d_setDancingToonState(avId, state, anim)

    def d_setDancingToonState(self, avId, state, anim):
        self.sendUpdate('setDancingToonState', [avId, state, anim])
