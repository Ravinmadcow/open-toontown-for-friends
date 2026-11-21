from direct.directnotify import DirectNotifyGlobal

from toontown.estate import GardenGlobals
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedGardenPlotAI(DistributedLawnDecorAI):
    """An empty spot in the garden, ready for planting."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGardenPlotAI')

    def __init__(self, air, garden, plot, x, y, h):
        DistributedLawnDecorAI.__init__(self, air, garden, plot, x, y, h)
        self.pendingFlower = None

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

    # Gag trees and statues come in the next gardening round.
    def plantGagTree(self, track, level):
        self.d_interactionDenied(self.air.getAvatarIdFromSender())

    def plantStatuary(self, species):
        self.d_interactionDenied(self.air.getAvatarIdFromSender())

    def plantToonStatuary(self, species, dnaCode):
        self.d_interactionDenied(self.air.getAvatarIdFromSender())

    def movieDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.movieAvId:
            return
        if self.pendingFlower is not None:
            species, variety = self.pendingFlower
            self.pendingFlower = None
            self.movieAvId = 0
            self.garden.plantFlower(self, species, variety, avId)
        else:
            self.clearMovie(avId)
