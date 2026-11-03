from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyCogUtils
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyTeamActivityAI import DistributedPartyTeamActivityAI
from toontown.toonbase import TTLocalizer

LeftTeam = PartyGlobals.TeamActivityTeams.LeftTeam
RightTeam = PartyGlobals.TeamActivityTeams.RightTeam


class DistributedPartyCogActivityAI(DistributedPartyTeamActivityAI):
    """Cog-O-War: two teams throw pies at three cogs to push them toward the other team.

    A cog's distance runs from -1.0 (the right team's end) to 1.0 (the left team's end). When time is up, a team's
    score is how many feet the cogs stand inside the other team's half, and the higher score wins."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyCogActivityAI')
    NumCogs = 3
    # The clients first play the results (time's up, each cog's distances, the totals, the winner), about 8.5 seconds;
    # a reward that arrives sooner cuts that short.
    RewardDelay = 9.5

    def __init__(self, air, party, activityTuple):
        DistributedPartyTeamActivityAI.__init__(self, air, party, activityTuple,
                                                minPlayersPerTeam=PartyGlobals.CogActivityMinPlayersPerTeam,
                                                maxPlayersPerTeam=PartyGlobals.CogActivityMaxPlayersPerTeam,
                                                duration=PartyGlobals.CogActivityDuration,
                                                startDelay=PartyGlobals.CogActivityStartDelay,
                                                conclusionDuration=PartyGlobals.CogActivityConclusionDuration,
                                                canSwitchTeams=True,
                                                balanceTeams=PartyGlobals.CogActivityBalanceTeams)
        self.cogDistances = [0.0] * self.NumCogs
        self.playerScores = {}
        self.highScoreName = ''
        self.highScore = 0

    def delete(self):
        taskMgr.remove(self.taskName('reward'))
        DistributedPartyTeamActivityAI.delete(self)

    def d_setCogDistances(self):
        self.sendUpdate('setCogDistances', [self.cogDistances])

    def d_setHighScore(self):
        self.sendUpdate('setHighScore', [self.highScoreName, self.highScore])

    def pieHitsCog(self, toonId, timestamp, hitCogNum, x, y, z, direction, hitHead):
        avId = self.air.getAvatarIdFromSender()
        team = self.getTeam(avId)
        if toonId != avId or team is None or not self.isActive() or not 0 <= hitCogNum < self.NumCogs:
            return
        if hitHead:
            push, points = PartyGlobals.CogPinataPushHeadFactor, PartyGlobals.CogActivityHitPointsForHead
        else:
            push, points = PartyGlobals.CogPinataPushBodyFactor, PartyGlobals.CogActivityHitPoints
        if team == LeftTeam:
            push = -push
        self.cogDistances[hitCogNum] = round(min(max(self.cogDistances[hitCogNum] + push, -1.0), 1.0), 2)
        self.playerScores[avId] = self.playerScores.get(avId, 0) + points
        self.d_setCogDistances()

    def startGame(self):
        self.cogDistances = [0.0] * self.NumCogs
        self.playerScores = {avId: 0 for avId in self.getPlayers()}
        self.d_setCogDistances()

    def getCogFeetFromCenter(self):
        return [PartyCogUtils.getCogDistanceUnitsFromCenter(distance) for distance in self.cogDistances]

    def getTeamScores(self):
        cogFeet = self.getCogFeetFromCenter()
        leftScore = -sum(feet for feet in cogFeet if feet < 0)
        rightScore = sum(feet for feet in cogFeet if feet > 0)
        return leftScore, rightScore

    def getConclusionData(self):
        leftScore, rightScore = self.getTeamScores()
        return leftScore * 10000 + rightScore

    def getWinner(self):
        leftScore, rightScore = self.getTeamScores()
        if leftScore == rightScore:
            return None
        return LeftTeam if leftScore > rightScore else RightTeam

    def isPerfectWin(self, winner):
        cogFeet = self.getCogFeetFromCenter()
        if winner == LeftTeam:
            return all(feet < 0 for feet in cogFeet)
        return all(feet > 0 for feet in cogFeet)

    def getBeansForTeam(self, team, winner, perfect):
        if winner is None:
            return PartyGlobals.CogActivityTieBeans
        if team == winner:
            return PartyGlobals.CogActivityPerfectWinBeans if perfect else PartyGlobals.CogActivityWinBeans
        return PartyGlobals.CogActivityPerfectLossBeans if perfect else PartyGlobals.CogActivityLossBeans

    def rewardPlayers(self, data):
        winner = self.getWinner()
        perfect = winner is not None and self.isPerfectWin(winner)
        rewards = []
        for avId in self.getPlayers():
            team = self.getTeam(avId)
            beans = self.getBeansForTeam(team, winner, perfect)
            score = self.playerScores.get(avId, 0)
            message = TTLocalizer.PartyCogRewardMessage % score
            if team == winner:
                bonus = beans - PartyGlobals.CogActivityTieBeans
                plural = TTLocalizer.PartyCogJellybeanPlural if bonus != 1 else ''
                message += TTLocalizer.PartyCogRewardBonus % (bonus, plural)
            rewards.append((avId, beans, message))
        self.updateHighScore()
        taskMgr.doMethodLater(self.RewardDelay, self.__payRewards, self.taskName('reward'), extraArgs=[rewards])

    def __payRewards(self, rewards):
        for avId, beans, message in rewards:
            self.rewardBeans(avId, beans, message)

    def updateHighScore(self):
        bestScore, bestName = self.highScore, None
        for avId, score in self.playerScores.items():
            toon = self.air.doId2do.get(avId)
            if toon is not None and score > bestScore:
                bestScore, bestName = score, toon.getName()
        if bestName is not None:
            self.highScoreName, self.highScore = bestName, min(bestScore, 0xFFFF)
            self.d_setHighScore()
