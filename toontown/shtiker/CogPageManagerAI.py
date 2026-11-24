from direct.directnotify import DirectNotifyGlobal

from toontown.shtiker import CogPageGlobals
from toontown.suit import SuitDNA


class CogPageManagerAI:
    """
    Keeps each toon's Cog page in the Shticker Book up to date:
    - fighting a Cog marks it as seen;
    - defeating one counts towards its quota (COG_QUOTAS), so the page shows
      how many you've beaten;
    - finishing the first quota for all 8 Cogs in a department gives that
      department's Cog radar; the second quota gives its building radar.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('CogPageManagerAI')

    def __init__(self, air):
        self.air = air

    @staticmethod
    def __suitIndex(suit):
        try:
            return SuitDNA.suitHeadTypes.index(suit['type'])
        except (KeyError, ValueError):
            return None

    def toonEncounteredCogs(self, toon, suitsEncountered, zoneId):
        cogs = list(toon.getCogStatus())
        changed = False
        for suit in suitsEncountered:
            if toon.getDoId() not in suit.get('activeToons', ()):
                continue
            index = self.__suitIndex(suit)
            if index is None or index >= len(cogs):
                continue
            if cogs[index] == CogPageGlobals.COG_UNSEEN:
                cogs[index] = CogPageGlobals.COG_BATTLED
                changed = True
        if changed:
            toon.b_setCogStatus(cogs)

    def toonKilledCogs(self, toon, suitsKilled, zoneId):
        cogs = list(toon.getCogStatus())
        counts = list(toon.getCogCount())
        changed = False
        for suit in suitsKilled:
            if toon.getDoId() not in suit.get('activeToons', ()):
                continue
            if suit.get('isVP') or suit.get('isCFO'):
                continue
            index = self.__suitIndex(suit)
            if index is None or index >= len(cogs) or index >= len(counts):
                continue
            level = index % SuitDNA.suitsPerDept
            quota1 = CogPageGlobals.COG_QUOTAS[0][level]
            quota2 = CogPageGlobals.COG_QUOTAS[1][level]
            counts[index] = min(counts[index] + 1, quota2)
            if counts[index] >= quota2:
                status = CogPageGlobals.COG_COMPLETE2
            elif counts[index] >= quota1:
                status = CogPageGlobals.COG_COMPLETE1
            else:
                status = CogPageGlobals.COG_DEFEATED
            cogs[index] = max(cogs[index], status)
            changed = True
        if not changed:
            return
        toon.b_setCogCount(counts)
        toon.b_setCogStatus(cogs)
        self.__updateRadars(toon, cogs)

    def __updateRadars(self, toon, cogs):
        cogRadar = list(toon.getCogRadar())
        buildingRadar = list(toon.getBuildingRadar())
        newCog, newBuilding = list(cogRadar), list(buildingRadar)
        for dept in range(len(SuitDNA.suitDepts)):
            deptCogs = cogs[dept * SuitDNA.suitsPerDept:(dept + 1) * SuitDNA.suitsPerDept]
            if len(deptCogs) < SuitDNA.suitsPerDept:
                continue
            if min(deptCogs) >= CogPageGlobals.COG_COMPLETE1:
                newCog[dept] = 1
            if min(deptCogs) >= CogPageGlobals.COG_COMPLETE2:
                newBuilding[dept] = 1
        if newCog != cogRadar:
            toon.b_setCogRadar(newCog)
        if newBuilding != buildingRadar:
            toon.b_setBuildingRadar(newBuilding)
