from direct.directnotify import DirectNotifyGlobal

from toontown.estate import GardenGlobals
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI


class DistributedFlowerAI(DistributedPlantBaseAI):
    """A flower. Once it blooms, picking it puts it in your flower basket."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFlowerAI')

    def __init__(self, air, garden, plot, x, y, h, species, variety, waterLevel=0, growthLevel=0):
        DistributedPlantBaseAI.__init__(self, air, garden, plot, x, y, h, species, waterLevel, growthLevel)
        self.species = species
        self.variety = variety
        self.pendingRemove = False

    def getVariety(self):
        return self.variety

    def removeItem(self):
        avId = self.air.getAvatarIdFromSender()
        if not self.isOwner(avId) or self.movieAvId:
            self.d_interactionDenied(avId)
            return
        self.movieAvId = avId
        self.pendingRemove = True
        self.d_setMovie(GardenGlobals.MOVIE_REMOVE, avId)

    def movieDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.movieAvId:
            return
        if not self.pendingRemove:
            self.clearMovie(avId)
            return
        self.pendingRemove = False
        self.movieAvId = 0
        av = self.air.doId2do.get(avId)
        if av is not None and self.isFruiting() and self.waterLevel >= 0:
            if av.addFlowerToBasket(self.species, self.variety):
                # Picking a flower that uses all your shovel's beans improves your skill.
                beans = GardenGlobals.getNumBeansRequired(self.species, self.variety)
                shovelPower = GardenGlobals.getShovelPower(av.getShovel(), av.getShovelSkill())
                if beans == shovelPower and av.getShovelSkill() < GardenGlobals.getMaxShovelSkill():
                    av.b_setShovelSkill(av.getShovelSkill() + 1)
        self.garden.removePlant(self, avId)
