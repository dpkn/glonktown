from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyTeamActivityAI import DistributedPartyTeamActivityAI
from toontown.toonbase import TTLocalizer

LeftTeam = PartyGlobals.TeamActivityTeams.LeftTeam
RightTeam = PartyGlobals.TeamActivityTeams.RightTeam

# How far the rope moves before a front toon is within 2 of the middle, where the client throws its team in the water.
FallInDistance = PartyGlobals.TugOfWarInitialToonPositionsXOffset - 2.0
ToonPositionTolerance = 1.0
FallInAnimDuration = 2.0
PullReportTimeout = 1.0
MaxKeyRate = 20


class DistributedPartyTugOfWarActivityAI(DistributedPartyTeamActivityAI):
    """Party tug of war. Every client reports its toon's pulling force; the server adds up each team's force, moves
    the rope by the difference and broadcasts the offset (positive drags the left team towards the water). A team
    whose front toon reaches the water falls in and loses; when time runs out the team pulled furthest loses."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyTugOfWarActivityAI')

    def __init__(self, air, party, activityTuple):
        DistributedPartyTeamActivityAI.__init__(self, air, party, activityTuple,
                                                minPlayersPerTeam=PartyGlobals.TugOfWarMinimumPlayersPerTeam,
                                                maxPlayersPerTeam=PartyGlobals.TugOfWarMaximumPlayersPerTeam,
                                                duration=PartyGlobals.TugOfWarDuration,
                                                startDelay=PartyGlobals.TugOfWarStartDelay,
                                                conclusionDuration=PartyGlobals.TugOfWarConclusionDuration)
        self.offset = 0.0
        self.fallenTeam = None
        self.pullStartTime = 0.0
        self.advantages = {}
        self.pulls = {}
        self.shownKeyRates = {}

    def startGame(self):
        self.offset = 0.0
        self.fallenTeam = None
        self.pulls = {}
        self.shownKeyRates = {}
        self.pullStartTime = globalClock.getFrameTime() + PartyGlobals.TugOfWarReadyDuration + \
            PartyGlobals.TugOfWarGoDuration
        self.__sendAdvantages()
        taskMgr.doMethodLater(PartyGlobals.TugOfWarKeyPressReportRate, self.__pullRope, self.taskName('pullRope'))

    def stopGame(self):
        taskMgr.remove(self.taskName('pullRope'))
        taskMgr.remove(self.taskName('fallIn'))

    def __sendAdvantages(self):
        """The smaller team pulls harder, so a lone toon has a chance against four. The client scales its force by it."""
        self.advantages = {}
        for team in PartyGlobals.TeamActivityTeams:
            teamSize, otherTeamSize = len(self.toonIds[team]), len(self.toonIds[1 - team])
            advantage = max(1.0, otherTeamSize / teamSize) if teamSize else 1.0
            for avId in self.toonIds[team]:
                self.advantages[avId] = advantage
                self.sendUpdateToAvatarId(avId, 'setAdvantage', [advantage])

    def __isPulling(self):
        return self.isActive() and self.fallenTeam is None

    def reportKeyRateForce(self, keyRate, force):
        avId = self.air.getAvatarIdFromSender()
        now = globalClock.getFrameTime()
        if self.getTeam(avId) is None or not self.__isPulling() or now < self.pullStartTime:
            return
        keyRate = min(keyRate, MaxKeyRate)
        force = min(max(force, 0.0), self.__getMaxForce(avId, keyRate, now))
        self.pulls[avId] = (keyRate, force, now)

    def __getMaxForce(self, avId, keyRate, now):
        """The most an honest client's computeForce can return by now: its rate-match bonus grows by 0.3 every
        key press update while the toon keeps to the target rate."""
        maxRateMatchAward = 0.3 * ((now - self.pullStartTime) / PartyGlobals.TugOfWarKeyPressUpdateRate + 1)
        maxIdealRate = max(rate for duration, rate in PartyGlobals.TugOfWarTargetRateList)
        matchedForce = self.advantages.get(avId, 1.0) * (maxRateMatchAward + 4 + 0.4 * maxIdealRate)
        allOutForce = 0.75 * keyRate
        return max(matchedForce, allOutForce)

    def __getCurrentPull(self, avId, now):
        keyRate, force, reportTime = self.pulls.get(avId, (0, 0.0, 0.0))
        if now - reportTime > PullReportTimeout:
            return 0, 0.0
        return keyRate, force

    def __pullRope(self, task):
        now = globalClock.getFrameTime()
        teamForces = [0.0, 0.0]
        for team in PartyGlobals.TeamActivityTeams:
            for avId in self.toonIds[team]:
                keyRate, force = self.__getCurrentPull(avId, now)
                teamForces[team] += force
                if keyRate != self.shownKeyRates.get(avId, 0):
                    self.shownKeyRates[avId] = keyRate
                    self.sendUpdate('updateToonKeyRate', [avId, keyRate])
        self.offset += (teamForces[RightTeam] - teamForces[LeftTeam]) * PartyGlobals.TugOfWarMovementFactor
        for team in PartyGlobals.TeamActivityTeams:
            if self.__getDistancePulled(team) >= FallInDistance:
                self.__teamFellIn(team)
                return task.done
        self.d_updateToonPositions()
        return task.again

    def d_updateToonPositions(self):
        self.sendUpdate('updateToonPositions', [self.offset])

    def __getDistancePulled(self, team):
        return self.offset if team == LeftTeam else -self.offset

    def reportFallIn(self, losingTeam):
        avId = self.air.getAvatarIdFromSender()
        if self.getTeam(avId) is None or not self.__isPulling() or losingTeam not in (LeftTeam, RightTeam):
            return
        if self.__getDistancePulled(losingTeam) >= FallInDistance - ToonPositionTolerance:
            self.__teamFellIn(losingTeam)

    def __teamFellIn(self, team):
        """Pulls the team clearly past the edge so every client throws it in, then ends once the splash has played."""
        self.fallenTeam = team
        taskMgr.remove(self.taskName('pullRope'))
        pastEdge = FallInDistance + ToonPositionTolerance
        self.offset = pastEdge if team == LeftTeam else -pastEdge
        self.d_updateToonPositions()
        taskMgr.doMethodLater(FallInAnimDuration, self.endGame, self.taskName('fallIn'), extraArgs=[])

    def getConclusionData(self):
        if self.fallenTeam is not None:
            return self.fallenTeam
        for team in PartyGlobals.TeamActivityTeams:
            if not self.toonIds[team]:
                return team
        if abs(self.offset) < PartyGlobals.TugOfWarTieThreshold:
            return PartyGlobals.TeamActivityNeitherTeam
        return LeftTeam if self.offset > 0 else RightTeam

    def rewardPlayers(self, losingTeam):
        for team in PartyGlobals.TeamActivityTeams:
            beans, message = self.__getReward(team, losingTeam)
            for avId in self.toonIds[team]:
                self.rewardBeans(avId, beans, message)

    def __getReward(self, team, losingTeam):
        teamFellIn = self.fallenTeam is not None
        if losingTeam == PartyGlobals.TeamActivityNeitherTeam:
            return PartyGlobals.TugOfWarTieReward, TTLocalizer.PartyTeamActivityGameTie
        if team == losingTeam:
            beans = PartyGlobals.TugOfWarFallInLossReward if teamFellIn else PartyGlobals.TugOfWarLossReward
            return beans, TTLocalizer.PartyTugOfWarGameEnd
        beans = PartyGlobals.TugOfWarFallInWinReward if teamFellIn else PartyGlobals.TugOfWarWinReward
        return beans, TTLocalizer.PartyTeamActivityLocalAvatarTeamWins
