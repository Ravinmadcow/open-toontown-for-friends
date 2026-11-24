from direct.directnotify import DirectNotifyGlobal

from toontown.estate import GardenGlobals
from toontown.estate.DistributedPlantBaseAI import DistributedPlantBaseAI


class DistributedGagTreeAI(DistributedPlantBaseAI):
    """
    A gag tree, grown by planting a gag from your inventory.

    - Full grown: that gag, and every lower gag in the same track that has a
      tree, becomes organic (stronger) in battle while the tree is watered.
    - Fruiting: the tree carries up to 9 of its gag, which you can harvest.
      After harvesting it drops back to full grown and fruits again later.
    - Wilted: a tree that runs out of water wilts. It stops growing, can't be
      harvested and loses its organic bonus until it is watered again.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGagTreeAI')

    def __init__(self, air, garden, plot, x, y, h, typeIndex, waterLevel=0, growthLevel=0):
        DistributedPlantBaseAI.__init__(self, air, garden, plot, x, y, h, typeIndex, waterLevel, growthLevel)
        self.species = typeIndex
        self.variety = 0
        self.track, self.level = GardenGlobals.getTreeTrackAndLevel(typeIndex)
        self.thresholds = self.attributes['growthThresholds']
        self.lastWilted = self.isWilted()
        self.pendingRemove = False
        self.pendingHarvest = False

    # ---- state ------------------------------------------------------------------
    def isWilted(self):
        return self.waterLevel < 0

    def getWilted(self):
        return int(self.isWilted())

    def isGTEFullGrown(self):
        return self.growthLevel >= self.thresholds[1]

    def b_setWaterLevel(self, level):
        DistributedPlantBaseAI.b_setWaterLevel(self, level)
        # Sent after the water level and before any growth update, so the
        # client loads the right (wilted or healthy) model.
        self.sendUpdate('setWilted', [self.getWilted()])

    def growOneDay(self):
        DistributedPlantBaseAI.growOneDay(self)
        # Trees stop growing once they are fruiting.
        self.growthLevel = min(self.growthLevel, self.thresholds[2])

    def refreshWilted(self):
        """If the tree wilted or recovered, reload its model on clients."""
        if self.isWilted() != self.lastWilted:
            self.lastWilted = self.isWilted()
            self.b_setGrowthLevel(self.growthLevel)

    # ---- watering -------------------------------------------------------------
    def waterPlantDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.waterAvId:
            return
        DistributedPlantBaseAI.waterPlantDone(self)
        self.refreshWilted()
        self.garden.updateTrackBonus()

    # ---- harvesting -----------------------------------------------------------
    def requestHarvest(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self.isOwner(avId) or self.movieAvId:
            self.d_interactionDenied(avId)
            return
        if not self.isFruiting() or self.isWilted() or \
                not self.garden.hasRequiredTrees(self.track, self.level, fullGrown=True):
            self.d_interactionDenied(avId)
            return
        given = 0
        for i in range(self.attributes.get('maxFruit', 9)):
            if av.inventory.addItem(self.track, self.level) <= 0:
                break  # that gag is full, or the toon can't carry any more
            given += 1
        if not given:
            # Leave the fruit on the tree for later.
            self.d_interactionDenied(avId)
            return
        av.b_setInventory(av.inventory.makeNetString())
        self.movieAvId = avId
        self.pendingHarvest = True
        self.d_setMovie(GardenGlobals.MOVIE_HARVEST, avId)

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
        if self.pendingHarvest:
            self.pendingHarvest = False
            self.b_setGrowthLevel(self.thresholds[1])
            self.clearMovie(avId)
            self.garden.save()
        elif self.pendingRemove:
            self.pendingRemove = False
            self.movieAvId = 0
            self.garden.removePlant(self, avId)
        else:
            self.clearMovie(avId)
