from direct.directnotify import DirectNotifyGlobal

from toontown.estate import GardenGlobals
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedStatuaryAI(DistributedLawnDecorAI):
    """A garden statue, planted from a garden special bought in the catalogue."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedStatuaryAI')

    def __init__(self, air, garden, plot, x, y, h, typeIndex, waterLevel=0, growthLevel=0):
        DistributedLawnDecorAI.__init__(self, air, garden, plot, x, y, h)
        self.typeIndex = typeIndex
        self.species = typeIndex
        self.variety = 0
        self.attributes = GardenGlobals.PlantAttributes[typeIndex]
        self.waterLevel = waterLevel
        self.growthLevel = growthLevel
        self.pendingRemove = False

    # ---- required fields ----------------------------------------------------
    def getTypeIndex(self):
        return self.typeIndex

    def getWaterLevel(self):
        return self.waterLevel

    def getGrowthLevel(self):
        return self.growthLevel

    def b_setWaterLevel(self, level):
        self.waterLevel = level
        self.sendUpdate('setWaterLevel', [level])

    def b_setGrowthLevel(self, level):
        self.growthLevel = level
        self.sendUpdate('setGrowthLevel', [level])

    def growOneDay(self):
        pass  # statues don't change

    # ---- digging up -----------------------------------------------------------
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
        if self.pendingRemove:
            self.pendingRemove = False
            self.movieAvId = 0
            self.garden.removePlant(self, avId)
        else:
            self.clearMovie(avId)
