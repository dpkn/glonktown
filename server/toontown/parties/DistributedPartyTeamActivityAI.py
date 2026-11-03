from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.activityFSMs import TeamActivityAIFSM


class DistributedPartyTeamActivityAI(DistributedPartyActivityAI):
    """A two-team activity (Cog pie toss, tug of war). It waits until each team has its minimum (WaitForEnough), counts
    down (WaitToStart), shows every player the rules and waits for them (WaitClientsReady, 'Rules' on the clients), plays
    (Active) and shows the result (Conclusion), then empties the teams and waits again.

    Subclasses override startGame/stopGame for the game itself, getConclusionData for the number the clients get with
    'Conclusion', and rewardPlayers to pay out. endGame() ends the game early."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyTeamActivityAI')
    WaitingStates = ('WaitForEnough', 'WaitToStart')

    def __init__(self, air, party, activityTuple,
                 minPlayersPerTeam=PartyGlobals.TeamActivityDefaultMinPlayersPerTeam,
                 maxPlayersPerTeam=PartyGlobals.TeamActivityDefaultMaxPlayersPerTeam,
                 duration=PartyGlobals.TeamActivityDefaultDuration,
                 startDelay=PartyGlobals.TeamActivityStartDelay,
                 conclusionDuration=PartyGlobals.TeamActivityDefaultConclusionDuration,
                 canSwitchTeams=False, balanceTeams=False):
        DistributedPartyActivityAI.__init__(self, air, party, activityTuple)
        self.minPlayersPerTeam = minPlayersPerTeam
        self.maxPlayersPerTeam = maxPlayersPerTeam
        self.duration = duration
        self.startDelay = startDelay
        self.conclusionDuration = conclusionDuration
        self.canSwitchTeams = canSwitchTeams
        self.balanceTeams = balanceTeams
        self.toonIds = ([], [])
        self.readyToons = []
        self.activityFSM = TeamActivityAIFSM(self)

    def announceGenerate(self):
        DistributedPartyActivityAI.announceGenerate(self)
        self.activityFSM.request('WaitForEnough')

    def delete(self):
        taskMgr.remove(self.taskName('requestState'))
        taskMgr.remove(self.taskName('stateTimer'))
        self.activityFSM.request('Off')
        DistributedPartyActivityAI.delete(self)

    def getPlayersPerTeam(self):
        return [self.minPlayersPerTeam, self.maxPlayersPerTeam]

    def getDuration(self):
        return int(self.duration)

    def getCanSwitchTeams(self):
        return self.canSwitchTeams

    def getToonsPlaying(self):
        return [list(self.toonIds[0]), list(self.toonIds[1])]

    def d_setToonsPlaying(self):
        self.sendUpdate('setToonsPlaying', self.getToonsPlaying())

    def d_setState(self, state, data=0):
        self.sendUpdate('setState', [state, globalClockDelta.getRealNetworkTime(), data])

    def getTeam(self, avId):
        for team in PartyGlobals.TeamActivityTeams:
            if avId in self.toonIds[team]:
                return team
        return None

    def getPlayers(self):
        return self.toonIds[0] + self.toonIds[1]

    def isActive(self):
        return self.activityFSM.getCurrentOrNextState() == 'Active'

    # ---- joining, leaving and switching
    def toonJoinRequest(self, team):
        avId = self.air.getAvatarIdFromSender()
        if self.activityFSM.state not in self.WaitingStates or self.getTeam(avId) is not None or \
                avId not in self.air.doId2do or team not in tuple(PartyGlobals.TeamActivityTeams):
            self.sendUpdateToAvatarId(avId, 'joinRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        if len(self.toonIds[team]) >= self.maxPlayersPerTeam:
            self.sendUpdateToAvatarId(avId, 'joinRequestDenied', [PartyGlobals.DenialReasons.Full])
            return
        self.toonIds[team].append(avId)
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.removeToon, extraArgs=[avId])
        self.d_setToonsPlaying()
        self.toonJoined(avId)
        self.__checkTeams()

    def toonExitRequest(self, team):
        avId = self.air.getAvatarIdFromSender()
        if self.getTeam(avId) is None or self.activityFSM.state not in self.WaitingStates:
            self.sendUpdateToAvatarId(avId, 'exitRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        self.removeToon(avId)

    def toonExitDemand(self):
        self.removeToon(self.air.getAvatarIdFromSender())

    def toonSwitchTeamRequest(self):
        avId = self.air.getAvatarIdFromSender()
        team = self.getTeam(avId)
        if not self.canSwitchTeams or team is None or self.activityFSM.state not in self.WaitingStates:
            self.sendUpdateToAvatarId(avId, 'switchTeamRequestDenied', [PartyGlobals.DenialReasons.Default])
            return
        otherTeam = 1 - team
        if len(self.toonIds[otherTeam]) >= self.maxPlayersPerTeam:
            self.sendUpdateToAvatarId(avId, 'switchTeamRequestDenied', [PartyGlobals.DenialReasons.Full])
            return
        self.toonIds[team].remove(avId)
        self.toonIds[otherTeam].append(avId)
        self.d_setToonsPlaying()
        self.__checkTeams()

    def removeToon(self, avId):
        team = self.getTeam(avId)
        if team is None:
            return
        self.toonIds[team].remove(avId)
        if avId in self.readyToons:
            self.readyToons.remove(avId)
        self.ignore(self.air.getAvatarExitEvent(avId))
        self.d_setToonsPlaying()
        self.toonExited(avId)
        state = self.activityFSM.state
        if state == 'Active' and not (self.toonIds[0] and self.toonIds[1]):
            self.endGame()
        elif state == 'WaitClientsReady':
            if not self.__enoughToStart():
                self.requestState('WaitForEnough')
            elif self.__everyoneReady():
                self.requestState('Active')
        else:
            self.__checkTeams()

    def toonReady(self):
        avId = self.air.getAvatarIdFromSender()
        if self.activityFSM.state != 'WaitClientsReady' or self.getTeam(avId) is None or avId in self.readyToons:
            return
        self.readyToons.append(avId)
        if self.__everyoneReady():
            self.requestState('Active')

    def __enoughToStart(self):
        left, right = len(self.toonIds[0]), len(self.toonIds[1])
        if self.balanceTeams:
            return left + right >= self.minPlayersPerTeam * 2
        return left >= self.minPlayersPerTeam and right >= self.minPlayersPerTeam

    def __everyoneReady(self):
        return all(avId in self.readyToons for avId in self.getPlayers())

    def __checkTeams(self):
        state = self.activityFSM.state
        if state == 'WaitForEnough' and self.__enoughToStart():
            self.requestState('WaitToStart')
        elif state == 'WaitToStart' and not self.__enoughToStart():
            self.requestState('WaitForEnough')

    def __balanceTeams(self):
        moved = False
        while abs(len(self.toonIds[0]) - len(self.toonIds[1])) > 1:
            bigger = 0 if len(self.toonIds[0]) > len(self.toonIds[1]) else 1
            self.toonIds[1 - bigger].append(self.toonIds[bigger].pop())
            moved = True
        if moved:
            self.d_setToonsPlaying()

    # ---- the state machine (TeamActivityAIFSM calls these)
    def requestState(self, state, *args):
        """Changes state on the next frame, so it is safe from inside a state change."""
        taskMgr.remove(self.taskName('requestState'))
        taskMgr.doMethodLater(0, self.__doRequestState, self.taskName('requestState'), extraArgs=[state] + list(args))

    def __doRequestState(self, state, *args):
        if state not in self.activityFSM.defaultTransitions.get(self.activityFSM.state, []):
            return
        if state == 'WaitToStart' and not self.__enoughToStart():
            return
        self.activityFSM.request(state, *args)

    def __startTimer(self, delay, state, *args):
        taskMgr.remove(self.taskName('stateTimer'))
        taskMgr.doMethodLater(delay, self.__doRequestState, self.taskName('stateTimer'), extraArgs=[state] + list(args))

    def __stopTimer(self):
        taskMgr.remove(self.taskName('stateTimer'))

    def startWaitForEnough(self):
        self.d_setState('WaitForEnough')
        self.__checkTeams()

    def finishWaitForEnough(self):
        pass

    def startWaitToStart(self):
        self.d_setState('WaitToStart')
        self.__startTimer(self.startDelay, 'WaitClientsReady')

    def finishWaitToStart(self):
        self.__stopTimer()

    def startWaitClientsReady(self):
        if self.balanceTeams:
            self.__balanceTeams()
        self.readyToons = []
        self.d_setState('Rules')
        self.__startTimer(PartyGlobals.TeamActivityClientWaitDelay, 'Active')

    def finishWaitClientsReady(self):
        self.__stopTimer()

    def startActive(self):
        self.d_setState('Active')
        self.startGame()
        self.__startTimer(self.duration, 'Conclusion', 0)

    def finishActive(self):
        self.__stopTimer()
        self.stopGame()

    def endGame(self):
        """Ends the game now (also when time runs out): the clients get the result from getConclusionData."""
        if self.isActive():
            self.requestState('Conclusion', 0)

    def startConclusion(self, data=0):
        data = self.getConclusionData()
        self.d_setState('Conclusion', data)
        self.rewardPlayers(data)
        self.__startTimer(self.conclusionDuration, 'WaitForEnough')

    def finishConclusion(self):
        self.__stopTimer()
        for avId in self.getPlayers():
            self.ignore(self.air.getAvatarExitEvent(avId))
        self.toonIds = ([], [])
        self.readyToons = []
        self.d_setToonsPlaying()

    # ---- for subclasses
    def startGame(self):
        pass

    def stopGame(self):
        pass

    def getConclusionData(self):
        return 0

    def rewardPlayers(self, data):
        pass
