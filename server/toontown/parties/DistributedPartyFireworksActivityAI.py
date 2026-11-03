from direct.directnotify import DirectNotifyGlobal
from toontown.effects.FireworkShow import FireworkShow
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.activityFSMs import FireworksActivityFSM


class DistributedPartyFireworksActivityAI(DistributedPartyActivityAI):
    """The party's fireworks show. Only the host can start it, by pulling the lever, and it plays once per party: Idle
    until then, Active while the rocket launches and the show plays (every client runs the show from the Active
    timestamp), then Disabled. Nobody ever joins it as a player: the client has no handler for toons joining."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyFireworksActivityAI')
    SkyFadeAndPauseDuration = 4.5

    def __init__(self, air, party, activityTuple):
        DistributedPartyActivityAI.__init__(self, air, party, activityTuple)
        self.eventId = PartyGlobals.FireworkShows.Summer
        self.showStyle = 0
        self.activityFSM = FireworksActivityFSM(self)

    def announceGenerate(self):
        DistributedPartyActivityAI.announceGenerate(self)
        self.activityFSM.request('Idle')

    def delete(self):
        taskMgr.remove(self.taskName('showDone'))
        self.activityFSM.request('Off')
        DistributedPartyActivityAI.delete(self)

    def getEventId(self):
        return self.eventId

    def getShowStyle(self):
        return self.showStyle

    def toonJoinRequest(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.party.getHostId() or self.activityFSM.state != 'Idle':
            self.sendUpdateToAvatarId(avId, 'joinRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        self.activityFSM.request('Active')

    def getShowDuration(self):
        """Seconds from the lever pull until the clients are done: the rocket launch, the sky fading to night and a
        pause, the fireworks, then the sky fading back and a pause (FireworkShowMixin.startShow)."""
        fireworksDuration = FireworkShow(self.eventId).getShowDuration()
        return PartyGlobals.FireworksPostLaunchDelay + self.SkyFadeAndPauseDuration * 2 + fireworksDuration

    def startIdle(self):
        pass

    def finishIdle(self):
        pass

    def startActive(self):
        self.d_setState('Active')
        taskMgr.doMethodLater(self.getShowDuration() + PartyGlobals.FireworksTransitionToDisabledDelay,
                              self.__showDone, self.taskName('showDone'), extraArgs=[])

    def __showDone(self):
        self.activityFSM.request('Disabled')

    def finishActive(self):
        taskMgr.remove(self.taskName('showDone'))

    def startDisabled(self):
        self.d_setState('Disabled')

    def finishDisabled(self):
        pass
