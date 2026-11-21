from direct.directnotify import DirectNotifyGlobal

from toontown.estate import GardenGlobals
from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedPlantBaseAI(DistributedLawnDecorAI):
    """Anything that grows: it has a water level and a growth level."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPlantBaseAI')

    def __init__(self, air, garden, plot, x, y, h, typeIndex, waterLevel=0, growthLevel=0):
        DistributedLawnDecorAI.__init__(self, air, garden, plot, x, y, h)
        self.typeIndex = typeIndex
        self.attributes = GardenGlobals.PlantAttributes[typeIndex]
        self.waterLevel = waterLevel
        self.growthLevel = growthLevel
        self.waterAvId = 0

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

    def isFruiting(self):
        return self.growthLevel >= self.attributes['growthThresholds'][2]

    def growOneDay(self):
        """One garden day passes: watered plants grow, and use up some water."""
        minWater = self.attributes.get('minWaterLevel', -2)
        if self.waterLevel >= 0:
            self.growthLevel = min(self.growthLevel + 1, 127)
        self.waterLevel = max(self.waterLevel - 1, minWater)

    # ---- watering ---------------------------------------------------------------
    def waterPlant(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self.isOwner(avId) or self.waterAvId:
            self.d_interactionDenied(avId)
            return
        power = int(GardenGlobals.getWateringCanPower(av.getWateringCan(), av.getWateringCanSkill()))
        maxWater = self.attributes.get('maxWaterLevel', GardenGlobals.getMaxWateringCanPower())
        self.waterLevel = min(self.waterLevel + power, int(maxWater))
        self.waterAvId = avId
        self.d_setMovie(GardenGlobals.MOVIE_WATER, avId)

    def waterPlantDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.waterAvId:
            return
        self.waterAvId = 0
        self.b_setWaterLevel(self.waterLevel)
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.b_setWateringCanSkill(av.getWateringCanSkill() + 1)
        self.garden.save()
