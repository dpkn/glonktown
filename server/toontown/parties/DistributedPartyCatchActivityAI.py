from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.showbase.RandomNumGen import RandomNumGen
from toontown.minigame.DropScheduler import ThreePhaseDropScheduler
from toontown.parties import PartyGlobals
from toontown.parties.DistributedPartyActivityAI import DistributedPartyActivityAI
from toontown.parties.DistributedPartyCatchActivityBase import DistributedPartyCatchActivityBase
from toontown.parties.activityFSMs import CatchActivityFSM
from toontown.toonbase import TTLocalizer

AnvilTypeId = PartyGlobals.Name2DOTypeId['anvil']


class CatchGeneration:
    """One drop schedule. drops[objNum] is (seconds after startTime, is it fruit), numbered the way the clients do."""

    def __init__(self, generationId, startTime, numPlayers, drops):
        self.generationId = generationId
        self.startTime = startTime
        self.timestamp = globalClockDelta.localToNetworkTime(startTime, bits=32)
        self.numPlayers = numPlayers
        self.drops = drops
        self.endTime = None
        self.caughtObjNums = set()


class DistributedPartyCatchActivityAI(DistributedPartyActivityAI, DistributedPartyCatchActivityBase):
    """Catch the falling fruit, dodge the anvils.

    The clients drop everything themselves. From a generation (id, timestamp, number of players) each client seeds the
    same shuffle of fruit and anvils and the same 80 second drop schedule starting at the timestamp, numbers the objects
    in the order they fall, and drops from the newest generation that has begun. A new generation starts when the
    players change. The server plans every generation the same way, so it knows which object is fruit and when it fell.

    A round starts when the first toon walks into the trees (Idle -> Active) and lasts one schedule plus the time its
    last drops take to land; more toons can walk in meanwhile. Then 'Good Game!' (Conclusion) and Idle, where everyone
    still playing is paid one jellybean per piece of fruit and taken out. Walking out of the trees earlier pays what was
    caught so far, and the round ends early when the last player leaves."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPartyCatchActivityAI')
    RewardMessage = TTLocalizer.PartyCatchRewardMessage
    # Toons joining or leaving close together share one new generation.
    GenerationSpacing = 1.0
    # A client keeps dropping from a generation until it hears about the next one.
    LateDropAllowance = 2.0

    def __init__(self, air, party, activityTuple):
        DistributedPartyActivityAI.__init__(self, air, party, activityTuple)
        self.activityFSM = CatchActivityFSM(self)
        self.startTimestamp = globalClockDelta.getRealNetworkTime(bits=32)
        self.generationSeedBase = 0
        self.nextGenerationId = 0
        self.generations = {}
        self.latestGeneration = None
        self.fruitCaught = {}

    def announceGenerate(self):
        DistributedPartyActivityAI.announceGenerate(self)
        self.generationSeedBase = RandomNumGen(self.doId).randrange(1000)
        self.activityFSM.request('Idle')

    def delete(self):
        for avId in self.toonsPlaying:
            self.__payOut(avId)
        self.activityFSM.request('Off')
        DistributedPartyActivityAI.delete(self)

    def getStartTimestamp(self):
        return self.startTimestamp

    def getGenerations(self):
        return [[generation.generationId, generation.timestamp, generation.numPlayers]
                for generation in self.generations.values()]

    def d_setGenerations(self):
        self.sendUpdate('setGenerations', [self.getGenerations()])

    # ---- joining and leaving
    def canJoin(self, avId):
        return self.activityFSM.state in ('Idle', 'Active')

    def toonJoined(self, avId):
        if self.activityFSM.state == 'Idle':
            self.activityFSM.request('Active')
        else:
            self.__playersChanged()

    def removeToon(self, avId):
        """Pays before taking the toon out: a client only shows the reward while its toon is still listed as playing,
        and it stays frozen in the activity until a reward arrives."""
        if avId in self.toonsPlaying:
            self.__payOut(avId)
        DistributedPartyActivityAI.removeToon(self, avId)

    def toonExited(self, avId):
        if self.activityFSM.state != 'Active':
            return
        if self.toonsPlaying:
            self.__playersChanged()
        else:
            self.activityFSM.request('Conclusion')

    def requestActivityStart(self):
        """The client never sends this, it starts the game by walking in. A host may start a round from Idle; toons
        standing in the trees then join by themselves."""
        avId = self.air.getAvatarIdFromSender()
        started = avId == self.party.getHostId() and self.activityFSM.state == 'Idle'
        if started:
            self.activityFSM.request('Active')
        self.sendUpdateToAvatarId(avId, 'startRequestResponse', [int(started)])

    def claimCatch(self, generationId, objNum, objType):
        avId = self.air.getAvatarIdFromSender()
        generation = self.generations.get(generationId)
        if avId not in self.toonsPlaying or generation is None or not 0 <= objNum < len(generation.drops) or \
                objNum in generation.caughtObjNums:
            return
        dropOffset, isFruit = generation.drops[objNum]
        dropTime = generation.startTime + dropOffset
        if dropTime > globalClock.getRealTime() or \
                (generation.endTime is not None and dropTime > generation.endTime + self.LateDropAllowance):
            self.air.writeServerEvent('suspicious', avId, 'party catch object %d of generation %d never fell'
                                      % (objNum, generationId))
            return
        clientSaysFruit = objType != AnvilTypeId
        if clientSaysFruit != isFruit:
            self.notify.warning('%s says object %d of generation %d is type %s, the server has fruit=%s'
                                % (avId, objNum, generationId, objType, isFruit))
        generation.caughtObjNums.add(objNum)
        if isFruit:
            self.fruitCaught[avId] = self.fruitCaught.get(avId, 0) + 1
        if self.activityFSM.state == 'Active':
            self.sendUpdate('setObjectCaught', [avId, generationId, objNum])

    def __payOut(self, avId):
        """Sends the result even for no fruit: that is what puts the toon back to walking."""
        fruitCaught = self.fruitCaught.pop(avId, 0)
        beans = min(fruitCaught, PartyGlobals.CatchMaxTotalReward)
        self.rewardBeans(avId, beans, self.RewardMessage % (fruitCaught, beans))

    # ---- generations
    def __playersChanged(self):
        taskName = self.taskName('newGeneration')
        if taskMgr.hasTaskNamed(taskName):
            return
        delay = self.latestGeneration.startTime + self.GenerationSpacing - globalClock.getRealTime()
        taskMgr.doMethodLater(max(delay, 0), self.__startGeneration, taskName, extraArgs=[])

    def __startGeneration(self):
        now = globalClock.getRealTime()
        if self.latestGeneration is not None:
            self.latestGeneration.endTime = now
        generationId = self.nextGenerationId
        self.nextGenerationId += 1
        numPlayers = len(self.toonsPlaying)
        self.latestGeneration = CatchGeneration(generationId, now, numPlayers, self.__planDrops(generationId, numPlayers))
        self.generations[generationId] = self.latestGeneration
        self.d_setGenerations()

    def __planDrops(self, generationId, numPlayers):
        """What DistributedPartyCatchActivity.scheduleDrops will drop for this generation, in objNum order."""
        self.calcDifficultyConstants(numPlayers)
        isFruit = [True] * self.numFruits + [False] * self.numAnvils
        RandomNumGen(generationId + self.generationSeedBase).shuffle(isFruit)
        scheduler = ThreePhaseDropScheduler(PartyGlobals.CatchActivityDuration, self.FirstDropDelay, self.DropPeriod,
                                            self.MaxDropDuration, self.SlowerDropPeriodMult, self.NormalDropDelay,
                                            self.FasterDropDelay, self.FasterDropPeriodMult)
        dropOffsets = []
        while not scheduler.doneDropping(continuous=True):
            dropOffsets.append(scheduler.getT())
            scheduler.stepT()
        return list(zip(dropOffsets, isFruit))

    # ---- the state machine (CatchActivityFSM calls these)
    def __requestStateLater(self, delay, state):
        taskMgr.doMethodLater(delay, self.__requestState, self.taskName('stateTimer'), extraArgs=[state])

    def __requestState(self, state):
        self.activityFSM.request(state)

    def startIdle(self):
        self.d_setState('Idle')
        for avId in list(self.toonsPlaying):
            self.removeToon(avId)
        if self.generations:
            self.generations = {}
            self.latestGeneration = None
            self.d_setGenerations()

    def finishIdle(self):
        pass

    def startActive(self):
        self.__startGeneration()
        self.d_setState('Active')
        self.__requestStateLater(self.generationDuration + self.MaxDropDuration, 'Conclusion')

    def finishActive(self):
        taskMgr.remove(self.taskName('stateTimer'))
        taskMgr.remove(self.taskName('newGeneration'))

    def startConclusion(self):
        self.d_setState('Conclusion')
        self.__requestStateLater(PartyGlobals.CatchConclusionDuration, 'Idle')

    def finishConclusion(self):
        taskMgr.remove(self.taskName('stateTimer'))
