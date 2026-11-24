from direct.directnotify import DirectNotifyGlobal

from toontown.estate import GardenGlobals
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedGardenPlotAI(DistributedLawnDecorAI):
    """An empty spot in the garden, ready for planting."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGardenPlotAI')

    def __init__(self, air, garden, plot, x, y, h):
        DistributedLawnDecorAI.__init__(self, air, garden, plot, x, y, h)
        self.pendingFlower = None
        self.pendingTree = None
        self.pendingStatue = None

    def plantFlower(self, species, variety):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self.isOwner(avId) or self.movieAvId:
            self.d_interactionDenied(avId)
            return
        attributes = GardenGlobals.PlantAttributes.get(species)
        beans = GardenGlobals.getNumBeansRequired(species, variety)
        if attributes is None or attributes['plantType'] != GardenGlobals.FLOWER_TYPE or beans <= 0:
            self.movieAvId = avId
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        shovelPower = GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill())
        if beans > shovelPower or av.getMoney() < beans:
            self.movieAvId = avId
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        # Each bean in the recipe costs one jellybean.
        av.b_setMoney(av.getMoney() - beans)
        self.pendingFlower = (species, variety)
        self.movieAvId = avId
        self.d_setMovie(GardenGlobals.MOVIE_PLANT, avId)

    def plantNothing(self, burntBeans):
        # Not a real recipe: the beans are used up and nothing grows.
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self.isOwner(avId):
            self.d_interactionDenied(avId)
            return
        av.b_setMoney(max(0, av.getMoney() - max(0, burntBeans)))
        self.movieAvId = avId
        self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)

    def plantGagTree(self, track, level):
        # Planting a gag tree uses up one of that gag from your inventory.
        from toontown.toonbase import ToontownBattleGlobals
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self.isOwner(avId) or self.movieAvId:
            self.d_interactionDenied(avId)
            return
        hardPoint = GardenGlobals.estatePlots[self.garden.slot][self.plot]
        allowed = (hardPoint[3] == GardenGlobals.GAG_TREE_TYPE
                   and 0 <= track < ToontownBattleGlobals.NUM_GAG_TRACKS
                   and 0 <= level <= ToontownBattleGlobals.UBER_GAG_LEVEL_INDEX
                   and av.hasTrackAccess(track)
                   and av.inventory.numItem(track, level) > 0
                   and self.garden.getTree(track, level) is None
                   and self.garden.hasRequiredTrees(track, level))
        self.movieAvId = avId
        if not allowed:
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        av.inventory.useItem(track, level)
        av.b_setInventory(av.inventory.makeNetString())
        self.pendingTree = GardenGlobals.getTreeTypeIndex(track, level)
        self.d_setMovie(GardenGlobals.MOVIE_PLANT, avId)

    def plantStatuary(self, species):
        if species in GardenGlobals.ToonStatuaryTypeIndices:
            # Toon statues need a toon to copy, sent with plantToonStatuary.
            avId = self.air.getAvatarIdFromSender()
            self.movieAvId = avId
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        self.__plantStatue(species, 0)

    def plantToonStatuary(self, species, dnaCode):
        if species not in GardenGlobals.ToonStatuaryTypeIndices:
            avId = self.air.getAvatarIdFromSender()
            self.movieAvId = avId
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        self.__plantStatue(species, dnaCode)

    def __plantStatue(self, species, optional):
        # A statue uses up the garden special bought from the catalogue, plus
        # one jellybean per bean in its planting recipe.
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self.isOwner(avId) or self.movieAvId:
            self.d_interactionDenied(avId)
            return
        self.movieAvId = avId
        attributes = GardenGlobals.PlantAttributes.get(species)
        recipe = None
        if attributes and attributes['plantType'] == GardenGlobals.STATUARY_TYPE:
            recipe = GardenGlobals.Recipes.get(attributes['varieties'][0][0])
        hardPoint = GardenGlobals.estatePlots[self.garden.slot][self.plot]
        if recipe is None or recipe['special'] < 0 or hardPoint[3] != GardenGlobals.STATUARY_TYPE:
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        special = recipe['special']
        beans = len(recipe['beans'])
        hasSpecial = any(index == special and count > 0 for index, count in av.getGardenSpecials())
        shovelPower = GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill())
        if not hasSpecial or beans > shovelPower or av.getMoney() < beans:
            self.d_setMovie(GardenGlobals.MOVIE_PLANT_REJECTED, avId)
            return
        av.b_setMoney(av.getMoney() - beans)
        av.removeGardenItem(special, 1)
        self.pendingStatue = (species, optional)
        self.d_setMovie(GardenGlobals.MOVIE_PLANT, avId)

    def movieDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.movieAvId:
            return
        if self.pendingStatue is not None:
            species, optional = self.pendingStatue
            self.pendingStatue = None
            self.movieAvId = 0
            self.garden.plantStatue(self, species, optional, avId)
        elif self.pendingTree is not None:
            typeIndex = self.pendingTree
            self.pendingTree = None
            self.movieAvId = 0
            self.garden.plantGagTree(self, typeIndex, avId)
        elif self.pendingFlower is not None:
            species, variety = self.pendingFlower
            self.pendingFlower = None
            self.movieAvId = 0
            self.garden.plantFlower(self, species, variety, avId)
        else:
            self.clearMovie(avId)
