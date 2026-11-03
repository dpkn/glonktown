"""Walking toons in Cog battles.

A battle expects every toon in it to have a game that answers it: the toon picks a gag, says when it has watched the movie, and so
on. A walker has no game, so this answers for it, through the same calls a game makes (the battle cannot tell the difference). A
walker waits for the real toons in its battle before it says it has finished watching something, so it never hurries them; in a
battle of walkers alone the battle's own time limits set the pace.
"""
import random
from toontown.battle.BattleBase import PASS, attackAffectsGroup
from toontown.toonbase import ToontownBattleGlobals
from . import NPCWalkerGlobals as WG

# Seconds a walker takes to choose a gag, like a toon thinking it over
CHOOSE_TIME = (2.0, 5.0)
# Seconds a walker watches a toon join before it says it has seen it
JOIN_WATCH_TIME = 2.0
# Seconds of reward movie in a battle with no real toons in it (the battle would otherwise wait two minutes)
REWARD_TIME = 12.0


def asToon(air, avId, method, *args):
    """Calls a battle's message handler as if the toon's own game had sent it."""
    air.getAvatarIdFromSender = lambda: avId
    try:
        return method(*args)
    finally:
        del air.getAvatarIdFromSender


def isWalker(air, avId):
    from .DistributedNPCWalkerAI import DistributedNPCWalkerAI
    return isinstance(air.doId2do.get(avId), DistributedNPCWalkerAI)


def drive(walker, battle, now):
    """Answers whatever the battle is waiting for from this walker."""
    air = walker.air
    me = walker.doId
    state = battle.fsm.getCurrentState().getName()
    if state != walker.battleState:
        walker.battleState = state
        walker.battleStateSince = now
        walker.battleChoiceDelay = random.uniform(*CHOOSE_TIME)
        walker.battleTries = 0
    elapsed = now - walker.battleStateSince
    realToons = [t for t in battle.toons if not isWalker(air, t)]

    for avId, responses in list(battle.joinResponses.items()):
        if responses.get(me) == 0:
            seen = walker.joinsSeen.setdefault(avId, now)
            if now - seen >= JOIN_WATCH_TIME:
                asToon(air, me, battle.joinDone, avId)

    if battle.adjustFsm.getCurrentState().getName() == 'Adjusting' and not battle.ignoreAdjustingResponses:
        if battle.adjustingResponses.get(me) == 0:
            asToon(air, me, battle.adjustDone)

    if battle.ignoreResponses or battle.responses.get(me) != 0:
        return
    if state == 'WaitForInput':
        if me in battle.activeToons and elapsed >= walker.battleChoiceDelay:
            # A choice the battle turns down (say, a heal for a toon who ran) leaves the answer unset: pass the second time
            track, level, target = chooseAttack(walker, battle) if walker.battleTries == 0 else (PASS, -1, -1)
            walker.battleTries += 1
            asToon(air, me, battle.requestAttack, track, level, target)
    elif state == 'PlayMovie':
        watching = [t for t in realToons if t in battle.pendingToons + battle.activeToons]
        if watching and all(battle.responses.get(t) for t in watching):
            asToon(air, me, battle.movieDone)
    elif state in ('Reward', 'BuildingReward'):
        if realToons:
            if all(battle.responses.get(t) for t in realToons if t in battle.activeToons):
                asToon(air, me, battle.rewardDone)
        elif elapsed >= REWARD_TIME:
            asToon(air, me, battle.rewardDone)


def _levels(walker, track):
    if not walker.hasTrackAccess(track):
        return []
    return [level for level in range(ToontownBattleGlobals.MAX_LEVEL_INDEX + 1) if walker.inventory.numItem(track, level) > 0]


def chooseAttack(walker, battle):
    """(track, level, target) for this round: a Toon-Up for a friend in trouble, otherwise a gag at a Cog."""
    air = walker.air
    toons = [air.doId2do.get(t) for t in battle.activeToons]
    toons = [t for t in toons if t is not None and t.maxHp > 0]
    heals = _levels(walker, ToontownBattleGlobals.HEAL_TRACK)
    if heals and len(toons) > 1:
        hurt = [t for t in toons if t.hp < t.maxHp * 0.5]
        others = [t for t in hurt if t.doId != walker.doId]
        if others or len(hurt) > 1:
            groupHeals = [l for l in heals if attackAffectsGroup(ToontownBattleGlobals.HEAL_TRACK, l)]
            singleHeals = [l for l in heals if not attackAffectsGroup(ToontownBattleGlobals.HEAL_TRACK, l)]
            if groupHeals and (len(hurt) > 1 or not singleHeals or not others):
                return ToontownBattleGlobals.HEAL_TRACK, max(groupHeals), -1
            if singleHeals and others:
                patient = min(others, key=lambda t: t.hp / float(t.maxHp))
                return ToontownBattleGlobals.HEAL_TRACK, max(singleHeals), patient.doId
    suits = list(battle.activeSuits)
    options = [t for t in WG.FIGHT_TRACKS if _levels(walker, t)]
    if not suits or not options:
        return PASS, -1, -1
    track = random.choice(options)
    levels = _levels(walker, track)
    level = max(levels) if random.random() < 0.6 else random.choice(levels)
    if attackAffectsGroup(track, level):
        return track, level, -1
    # Gang up on the weakest Cog, as toons do
    target = min(suits, key=lambda s: s.getHP()) if random.random() < 0.6 else random.choice(suits)
    return track, level, target.doId
