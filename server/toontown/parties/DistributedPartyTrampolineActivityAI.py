from direct.directnotify import DirectNotifyGlobal
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.activityFSMs import TrampolineActivityFSM
from toontown.toonbase import TTLocalizer


class DistributedPartyTrampolineActivityAI(DistributedPartyActivityAI):
    """The jellybean trampoline, one toon at a time. The client does the bouncing; the server runs the turn (Idle, Rules
    until the toon has read them, Active), says when time is up, passes collected beans and animations on to the other
    guests, pays out the beans it saw collected and keeps the party's best height.

    The toon ends its own turn (after 'Hop Off' or leaveTrampoline): it bounces to a stop, hops off and sends awardBeans,
    reportHeightInformation if it beat the record, then toonExitDemand."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyTrampolineActivityAI')
    AnimStates = ('Off', 'Neutral', 'Jump', 'Falling', 'Land')
    RulesTimeout = PartyGlobals.DefaultRulesTimeout + 5.0
    ReadyGoDuration = 1.2
    HopOffTimeout = 20.0
    # Perfect bouncing (the client's physics) needs at least 2.2s per bean, 38s for the top one at 90 ft, and levels
    # off at about 105 ft.
    MinSecondsPerBean = 1.5
    MaxHeight = 110

    def __init__(self, air, party, activityTuple):
        DistributedPartyActivityAI.__init__(self, air, party, activityTuple)
        self.activityFSM = TrampolineActivityFSM(self)
        self.bestHeight = 0
        self.collectedBeans = set()
        self.roundStartTime = 0.0
        self.rewarded = False

    def announceGenerate(self):
        DistributedPartyActivityAI.announceGenerate(self)
        self.activityFSM.request('Idle')

    def delete(self):
        self.__stopTimer()
        self.activityFSM.request('Off')
        DistributedPartyActivityAI.delete(self)

    def canJoin(self, avId):
        return self.activityFSM.state == 'Idle'

    def toonJoined(self, avId):
        self.collectedBeans = set()
        self.rewarded = False
        self.activityFSM.request('Rules')

    def toonExited(self, avId):
        self.activityFSM.request('Idle')

    def toonReady(self):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.toonsPlaying and self.activityFSM.state == 'Rules':
            self.activityFSM.request('Active')

    def removeBeans(self, beanIndexes):
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toonsPlaying or self.activityFSM.state != 'Active':
            return
        secondsBouncing = globalClock.getRealTime() - self.roundStartTime
        newlyCollected = []
        for index in beanIndexes:
            if index in self.collectedBeans or not 0 <= index < PartyGlobals.TrampolineNumJellyBeans:
                continue
            if secondsBouncing < (index + 1) * self.MinSecondsPerBean:
                self.air.writeServerEvent('suspicious', avId, 'trampoline bean %d after only %.1fs' % (index, secondsBouncing))
                continue
            self.collectedBeans.add(index)
            newlyCollected.append(index)
        if newlyCollected:
            self.sendUpdate('removeBeansEcho', [newlyCollected])

    def awardBeans(self, numBeansCollected, topHeight):
        """The toon's end-of-turn report. The result screen is sent even for 0 beans: closing it is what puts the toon
        back to walking."""
        avId = self.air.getAvatarIdFromSender()
        if avId not in self.toonsPlaying or self.rewarded:
            return
        self.rewarded = True
        beans = min(numBeansCollected, len(self.collectedBeans))
        if beans == PartyGlobals.TrampolineNumJellyBeans:
            message = TTLocalizer.PartyTrampolineBonusBeanResults % (beans, PartyGlobals.TrampolineJellyBeanBonus)
            beans += PartyGlobals.TrampolineJellyBeanBonus
        else:
            message = TTLocalizer.PartyTrampolineBeanResults % beans
        message += '\n\n' + TTLocalizer.PartyTrampolineTopHeightResults % min(topHeight, self.MaxHeight)
        self.rewardBeans(avId, beans, message)

    def reportHeightInformation(self, height):
        avId = self.air.getAvatarIdFromSender()
        toon = self.air.doId2do.get(avId)
        if avId not in self.toonsPlaying or self.activityFSM.state != 'Active' or toon is None:
            return
        if height > self.MaxHeight:
            self.air.writeServerEvent('suspicious', avId, 'trampoline height %d' % height)
            return
        if height > self.bestHeight:
            self.bestHeight = height
            self.sendUpdate('setBestHeightInfo', [toon.getName(), height])

    def requestAnim(self, request):
        avId = self.air.getAvatarIdFromSender()
        if avId in self.toonsPlaying and request in self.AnimStates:
            self.sendUpdate('requestAnimEcho', [request])

    def __startTimer(self, delay, callback):
        self.__stopTimer()
        taskMgr.doMethodLater(delay, callback, self.taskName('turnTimer'), extraArgs=[])

    def __stopTimer(self):
        taskMgr.remove(self.taskName('turnTimer'))

    # ---- the state machine (TrampolineActivityFSM calls these)
    def startIdle(self):
        self.d_setState('Idle')

    def finishIdle(self):
        pass

    def startRules(self):
        self.__startTimer(self.RulesTimeout, self.__rulesTimedOut)

    def __rulesTimedOut(self):
        self.activityFSM.request('Active')

    def finishRules(self):
        self.__stopTimer()

    def startActive(self):
        self.roundStartTime = globalClock.getRealTime()
        self.d_setState('Active')
        self.__startTimer(self.ReadyGoDuration + PartyGlobals.TrampolineDuration, self.__timeUp)

    def __timeUp(self):
        self.sendUpdate('leaveTrampoline')
        self.__startTimer(self.HopOffTimeout, self.__takeToonsOff)

    def __takeToonsOff(self):
        for avId in list(self.toonsPlaying):
            self.removeToon(avId)

    def finishActive(self):
        self.__stopTimer()
