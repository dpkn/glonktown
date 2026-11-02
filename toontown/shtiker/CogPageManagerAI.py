from direct.directnotify import DirectNotifyGlobal
from toontown.suit import SuitDNA
from toontown.shtiker.CogPageGlobals import *


class CogPageManagerAI:
    """Keeps each toon's Cog Gallery (the Cogs page of the Shticker Book): which cogs it has fought and how many of each it has
    defeated. Filling a department's first quotas earns that department's cog radar, the second quotas its building radar."""
    notify = DirectNotifyGlobal.directNotify.newCategory('CogPageManagerAI')
    BOSS_FLAGS = ('isVP', 'isCFO', 'isCJ', 'isCEO')

    def __init__(self, air):
        self.air = air

    @staticmethod
    def __index(suit):
        if any(suit.get(flag) for flag in CogPageManagerAI.BOSS_FLAGS):
            return None                  # the bosses are not on the page
        try:
            return SuitDNA.suitHeadTypes.index(suit.get('type'))
        except ValueError:
            return None

    @staticmethod
    def __lists(toon):
        size = len(SuitDNA.suitHeadTypes)
        cogs = list(toon.getCogStatus() or [])
        counts = list(toon.getCogCount() or [])
        cogs += [COG_UNSEEN] * (size - len(cogs))
        counts += [0] * (size - len(counts))
        return cogs, counts

    def toonEncounteredCogs(self, toon, suitsEncountered, zoneId):
        cogs, counts = self.__lists(toon)
        changed = False
        for suit in suitsEncountered:
            if toon.doId not in suit.get('activeToons', [toon.doId]):
                continue
            index = self.__index(suit)
            if index is not None and cogs[index] < COG_BATTLED:
                cogs[index] = COG_BATTLED
                changed = True
        if changed:
            toon.b_setCogStatus(cogs)

    def toonKilledCogs(self, toon, suitsKilled, zoneId):
        cogs, counts = self.__lists(toon)
        before = (list(cogs), list(counts))
        for suit in suitsKilled:
            if toon.doId not in suit.get('activeToons', [toon.doId]):
                continue
            index = self.__index(suit)
            if index is None:
                continue
            # the count runs on past the first quota (the page then shows it against the second) and stops at the second
            type = index % SuitDNA.suitsPerDept
            quota1, quota2 = COG_QUOTAS[0][type], COG_QUOTAS[1][type]
            if counts[index] < quota2:
                counts[index] += 1
            if cogs[index] < COG_DEFEATED:
                cogs[index] = COG_DEFEATED
            if cogs[index] < COG_COMPLETE1 and counts[index] >= quota1:
                cogs[index] = COG_COMPLETE1
            if cogs[index] == COG_COMPLETE1 and counts[index] >= quota2:
                cogs[index] = COG_COMPLETE2
        if (cogs, counts) == before:
            return
        toon.b_setCogCount(counts)
        toon.b_setCogStatus(cogs)
        self.__checkRadars(toon, cogs)

    def __checkRadars(self, toon, cogs):
        cogRadar = list(toon.getCogRadar())
        buildingRadar = list(toon.getBuildingRadar())
        newCog = newBuilding = False
        for dept in range(len(SuitDNA.suitDepts)):
            status = cogs[dept * SuitDNA.suitsPerDept:(dept + 1) * SuitDNA.suitsPerDept]
            if not cogRadar[dept] and min(status) >= COG_COMPLETE1:
                cogRadar[dept] = 1
                newCog = True
            if not buildingRadar[dept] and min(status) >= COG_COMPLETE2:
                buildingRadar[dept] = 1
                newBuilding = True
        if newCog:
            toon.b_setCogRadar(cogRadar)
        if newBuilding:
            toon.b_setBuildingRadar(buildingRadar)
