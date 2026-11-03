import json
import math
import os
import time
import traceback

from direct.directnotify import DirectNotifyGlobal
from toontown.battle import SuitBattleGlobals
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import GameConfig
from toontown.toonbase import ToontownGlobals


class CommunityGoalAI:
    """Save Glonktown: one goal the whole town works on together. Every Cog anyone defeats adds its level in points; taking back a
    building or a Field Office, finishing off an invasion and beating a boss add a bonus. At each quarter of the goal (community_goal in
    gameconfig.json) every toon is told and the town gets a reward. A toon that is busy (in a battle, a trolley game, an estate) or not
    playing when a gift is handed out gets it as soon as it is back on a street, in a playground or in a building.

    Everything is kept in one JSON file in the data folder, which the web server also hands to the welcome page's card."""
    notify = DirectNotifyGlobal.directNotify.newCategory('CommunityGoalAI')
    FILE = os.environ.get('OT_COMMUNITY_GOAL_FILE', '/ot/data/community_goal.json')
    DEFAULT_TARGET = 1500
    FLOOR_POINTS = 10
    INVASION_POINTS = 50
    BOSS_POINTS = 100
    NUM_EVENTS = 8
    SAVE_EVERY = 5.0
    TICK_EVERY = 10.0
    MILESTONES = (
        {'percent': 25, 'reward': '100 jellybeans for every toon', 'beans': 100},
        {'percent': 50, 'reward': 'Double gag experience for the rest of the party', 'doubleXp': True},
        {'percent': 75, 'reward': 'Full Laff and a full gag bag for every toon', 'refill': True},
        {'percent': 100, 'reward': 'Fireworks in every playground, and 500 jellybeans for every toon', 'beans': 500, 'fireworks': True},
    )
    BOSS_NAMES = {'s': 'the Sellbot V.P.', 'm': 'the Cashbot C.F.O.', 'l': 'the Lawbot Chief Justice', 'c': 'the Bossbot C.E.O.'}
    FIREWORK_STYLES = {ToontownGlobals.ToontownCentral: 0, ToontownGlobals.DonaldsDock: 5, ToontownGlobals.DaisyGardens: 1,
                       ToontownGlobals.MinniesMelodyland: 3, ToontownGlobals.TheBrrrgh: 4, ToontownGlobals.DonaldsDreamland: 2,
                       ToontownGlobals.GoofySpeedway: 0, ToontownGlobals.OutdoorZone: 0}

    def __init__(self, air):
        self.air = air
        self.fireworkShows = {}
        self.dirty = False
        self.lastTarget = self.target()
        self.__load()

    # ---- the file
    def __load(self):
        data = {}
        try:
            with open(self.FILE) as f:
                data = json.load(f)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            self.notify.warning('could not read the goal, starting from zero: ' + traceback.format_exc())
        self.points = int(data.get('points', 0))
        self.counts = {key: int(data.get('counts', {}).get(key, 0)) for key in ('cogs', 'buildings', 'invasions', 'bosses')}
        self.reached = [m['percent'] for m in data.get('milestones', []) if m.get('reached')]
        self.gifted = {int(percent): set(avIds) for percent, avIds in data.get('gifted', {}).items()}
        self.helpers = {int(avId): helper for avId, helper in data.get('helpers', {}).items()}
        self.events = data.get('events', [])

    def __save(self, task=None):
        if self.dirty:
            self.dirty = False
            target = self.target()
            data = {
                'updated': int(time.time()),
                'target': target,
                'points': self.points,
                'counts': self.counts,
                'milestones': [{'percent': m['percent'], 'at': self.__pointsFor(m, target), 'reward': m['reward'],
                                'reached': m['percent'] in self.reached} for m in self.MILESTONES],
                'helpers': {str(avId): helper for avId, helper in self.helpers.items()},
                'events': self.events,
                'gifted': {str(percent): sorted(avIds) for percent, avIds in self.gifted.items()},
            }
            try:
                tmp = self.FILE + '.tmp'
                with open(tmp, 'w') as f:
                    json.dump(data, f)
                os.replace(tmp, self.FILE)
            except OSError:
                self.notify.warning('could not save the goal: ' + traceback.format_exc())
        return task.again if task else None

    # ---- running it
    def start(self):
        """Call once the district's news manager exists."""
        self.dirty = True
        self.__checkMilestones()
        taskMgr.doMethodLater(self.TICK_EVERY, self.__tick, 'communityGoalTick')
        taskMgr.doMethodLater(self.SAVE_EVERY, self.__save, 'communityGoalSave')

    def __tick(self, task):
        try:
            target = self.target()
            if target != self.lastTarget:
                self.lastTarget = target
                self.dirty = True
                self.__checkMilestones()
            self.__handOutGifts()
        except Exception:
            self.notify.warning('community goal tick failed: ' + traceback.format_exc())
        return task.again

    def target(self):
        return max(1, int(GameConfig.get('community_goal', self.DEFAULT_TARGET)))

    def xpMultiplier(self):
        return 2 if any(m.get('doubleXp') and m['percent'] in self.reached for m in self.MILESTONES) else 1

    # ---- what the town does
    def cogDefeated(self, level, avIds):
        self.counts['cogs'] += 1
        self.__add(level, avIds)

    def buildingRescued(self, numFloors, avIds, fieldOffice=False):
        self.counts['buildings'] += 1
        what = 'a Field Office' if fieldOffice else 'a %d-story building' % numFloors
        self.__add(numFloors * self.FLOOR_POINTS, avIds, '%s took back %s' % (self.__names(avIds), what))

    def invasionDefeated(self, cogType):
        self.counts['invasions'] += 1
        name = SuitBattleGlobals.SuitAttributes.get(cogType, {}).get('pluralname', 'Cog')
        self.__add(self.INVASION_POINTS, [], 'The town stopped the %s invasion' % name)

    def bossDefeated(self, dept, avIds):
        self.counts['bosses'] += 1
        self.__add(self.BOSS_POINTS, avIds, '%s beat %s' % (self.__names(avIds), self.BOSS_NAMES.get(dept, 'a boss')))

    def addPoints(self, points):
        self.__add(points, [], 'The host %s %d points' % ('added' if points >= 0 else 'took away', abs(points)))

    def reset(self):
        self.points = 0
        self.counts = dict.fromkeys(self.counts, 0)
        self.reached = []
        self.gifted = {}
        self.helpers = {}
        self.events = []
        self.dirty = True

    def status(self):
        target = self.target()
        if self.points >= target:
            return 'Glonktown is saved: %d points, the goal was %d.' % (self.points, target)
        text = 'Save Glonktown: %d of %d points (%d%%).' % (self.points, target, 100 * self.points // target)
        upcoming = [m for m in self.MILESTONES if m['percent'] not in self.reached]
        if upcoming:
            text += ' Next at %d: %s.' % (self.__pointsFor(upcoming[0], target), upcoming[0]['reward'])
        return text

    def __add(self, points, avIds, event=None):
        self.points = max(0, self.points + points)
        for avId in avIds:
            toon = self.air.doId2do.get(avId)
            helper = self.helpers.setdefault(avId, {'name': '', 'points': 0})
            helper['name'] = toon.getName() if toon else helper['name']
            helper['points'] += points
        if event:
            self.__event(event)
        self.dirty = True
        self.__checkMilestones()

    def __event(self, text):
        self.events = ([{'time': int(time.time()), 'text': text}] + self.events)[:self.NUM_EVENTS]
        self.dirty = True

    def __names(self, avIds):
        names = [self.air.doId2do[avId].getName() for avId in avIds if avId in self.air.doId2do]
        if not names:
            return 'Some toons'
        return names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]

    # ---- milestones and rewards
    @staticmethod
    def __pointsFor(milestone, target):
        return int(math.ceil(target * milestone['percent'] / 100.0))

    def __checkMilestones(self):
        target = self.target()
        for milestone in self.MILESTONES:
            if milestone['percent'] not in self.reached and self.points >= self.__pointsFor(milestone, target):
                self.__reach(milestone)

    def __reach(self, milestone):
        self.reached.append(milestone['percent'])
        self.notify.info('reached %d%% of the goal' % milestone['percent'])
        if milestone['percent'] == 100:
            message = 'Glonktown is saved! Thank you, everyone. Reward: %s.' % milestone['reward']
            self.__event('Glonktown is saved!')
        else:
            message = 'Save Glonktown: %d%% there! Reward: %s.' % (milestone['percent'], milestone['reward'])
            self.__event('%d%% reached: %s' % (milestone['percent'], milestone['reward']))
        self.__tellEveryone(message)
        if milestone.get('fireworks'):
            self.__startFireworks()
        self.__handOutGifts()

    def __tellEveryone(self, message):
        news = getattr(self.air, 'newsManager', None)
        if news is not None:
            news.sendUpdate('sendSystemMessage', [message, 0])

    def __tellToon(self, avId, message):
        news = getattr(self.air, 'newsManager', None)
        if news is not None:
            news.sendUpdateToAvatarId(avId, 'sendSystemMessage', [message, 0])

    def __handOutGifts(self):
        gifts = [m for m in self.MILESTONES if m['percent'] in self.reached and (m.get('beans') or m.get('refill'))]
        if not gifts:
            return
        for toon in list(self.air.doId2do.values()):
            if not (isinstance(toon, DistributedToonAI) and toon.isPlayerControlled() and self.__canTakeGift(toon)):
                continue
            for milestone in gifts:
                given = self.gifted.setdefault(milestone['percent'], set())
                if toon.doId in given:
                    continue
                given.add(toon.doId)
                self.dirty = True
                if milestone.get('beans'):
                    toon.addMoney(milestone['beans'])
                    self.__tellToon(toon.doId, 'Save Glonktown gift: %d jellybeans!' % milestone['beans'])
                if milestone.get('refill'):
                    toon.toonUp(toon.getMaxHp())
                    toon.inventory.maxOutInv(filterUberGags=1)
                    toon.d_setInventory(toon.inventory.makeNetString())
                    self.__tellToon(toon.doId, 'Save Glonktown gift: full Laff and a full gag bag!')

    @staticmethod
    def __canTakeGift(toon):
        """Not in the middle of something that keeps its own copy of the toon's Laff, gags or jellybeans (a battle, a trolley game)."""
        return not toon.getBattleId() and not toon.hpOwnedByBattle and toon.zoneId < ToontownGlobals.DynamicZonesBegin

    # ---- the finale
    def __startFireworks(self):
        from toontown.effects.DistributedFireworkShowAI import DistributedFireworkShowAI
        for zoneId, style in self.FIREWORK_STYLES.items():
            if zoneId in self.fireworkShows:
                continue
            show = DistributedFireworkShowAI(self.air, self)
            show.generateWithRequired(zoneId)
            self.fireworkShows[zoneId] = show
            show.d_startShow(ToontownGlobals.NEWYEARS_FIREWORKS, style)

    def isShowRunning(self, zoneId):
        return zoneId in self.fireworkShows

    def stopShow(self, zoneId):
        show = self.fireworkShows.pop(zoneId, None)
        if show is not None:
            show.requestDelete()
