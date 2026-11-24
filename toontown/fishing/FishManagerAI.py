import random

from direct.directnotify import DirectNotifyGlobal

from toontown.fishing import FishGlobals
from toontown.fishing.FishBase import FishBase


class FishManagerAI:
    """
    Decides what a toon catches, and pays them when they sell their bucket.
    Selling also adds the fish to their collection, and every 10 species
    earns a fishing trophy (and +1 Laff), as in the original game.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('FishManagerAI')

    def __init__(self, air):
        self.air = air

    def generateCatch(self, av, area, zoneId):
        """Returns (code, itemDesc1, itemDesc2, itemDesc3) for the fishing spot movie."""
        rodId = av.getFishingRod()

        # Fishing quests: sometimes the "catch" is a quest item.
        questManager = getattr(self.air, 'questManager', None)
        if questManager is not None:
            try:
                questItem = questManager.findItemInWater(av, zoneId)
            except Exception as e:
                self.notify.warning('Quest check failed: %s' % e)
                questItem = None
            if questItem:
                return (FishGlobals.QuestItem, questItem, 0, 0)

        roll = random.random() * 100.0
        itemType = FishGlobals.BootItem
        for cutoff in FishGlobals.SortedProbabilityCutoffs:
            if roll <= cutoff:
                itemType = FishGlobals.ProbabilityDict[cutoff]
                break

        if itemType == FishGlobals.FishItem:
            success, genus, species, weight = FishGlobals.getRandomFishVitals(area, rodId)
            if not success:
                return (FishGlobals.BootItem, 0, 0, 0)
            if len(av.fishTank) >= av.getMaxFishTank():
                return (FishGlobals.OverTankLimit, 0, 0, 0)
            fish = FishBase(genus, species, weight)
            result = av.fishCollection.getCollectResult(fish)
            if result == FishGlobals.COLLECT_NEW_ENTRY:
                code = FishGlobals.FishItemNewEntry
            elif result == FishGlobals.COLLECT_NEW_RECORD:
                code = FishGlobals.FishItemNewRecord
            else:
                code = FishGlobals.FishItem
            av.addFishToTank(fish)
            av.toonUp(FishGlobals.HealAmount)
            return (code, genus, species, weight)

        if itemType == FishGlobals.JellybeanItem:
            from toontown.ai import JellybeanRewards
            amount = JellybeanRewards.scale(FishGlobals.Rod2JellybeanDict.get(rodId, 10))
            av.addMoney(amount)
            return (FishGlobals.JellybeanItem, amount, 0, 0)

        return (FishGlobals.BootItem, 0, 0, 0)

    def creditFishTank(self, av):
        """Sells everything in the toon's bucket. Returns True if they earned a new trophy."""
        value = av.fishTank.getTotalValue()
        for fish in av.fishTank.getFish():
            av.fishCollection.collectFish(fish)
        av.b_setFishCollection(*av.fishCollection.getNetLists())
        av.b_setFishTank([], [], [])
        if value:
            from toontown.ai import JellybeanRewards
            av.addMoney(JellybeanRewards.scale(value))

        trophies = len(av.fishCollection) // 10
        oldTrophies = len(av.getFishingTrophies())
        if trophies > oldTrophies:
            av.b_setMaxHp(av.getMaxHp() + (trophies - oldTrophies))
            av.toonUp(av.getMaxHp())
            av.b_setFishingTrophies(list(range(trophies)))
            return True
        return False
