import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import HouseGlobals


class DistributedEstateAI(DistributedObjectAI):
    """
    The estate grounds. Stage 1 keeps this simple: it runs the day/night
    cycle and answers the client, but gardens, flowers, cannons and
    rentals are not active yet.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedEstateAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.estateType = 0
        self.dawnTime = int(time.time()) % HouseGlobals.DAY_NIGHT_PERIOD
        self.decorData = []
        self.lastEpochTimeStamp = int(time.time())
        self.rentalTimeStamp = 0
        self.rentalType = 0
        self.slotToonIds = [0] * 6
        self.slotItems = [[] for _ in range(6)]
        self.clouds = 0
        self.idList = []
        self.treasureIds = []

    # ---- required fields ----------------------------------------------------
    def setEstateType(self, estateType):
        self.estateType = estateType

    def getEstateType(self):
        return self.estateType

    def setDawnTime(self, dawnTime):
        self.dawnTime = dawnTime

    def getDawnTime(self):
        return self.dawnTime

    def setDecorData(self, decorData):
        self.decorData = decorData

    def getDecorData(self):
        return self.decorData

    def setLastEpochTimeStamp(self, ts):
        self.lastEpochTimeStamp = ts

    def getLastEpochTimeStamp(self):
        return self.lastEpochTimeStamp

    def setRentalTimeStamp(self, ts):
        self.rentalTimeStamp = ts

    def getRentalTimeStamp(self):
        return self.rentalTimeStamp

    def setRentalType(self, rentalType):
        self.rentalType = rentalType

    def getRentalType(self):
        return self.rentalType

    def setClouds(self, clouds):
        self.clouds = clouds

    def getClouds(self):
        return self.clouds

    def getIdList(self):
        return self.idList

    def getTreasureIds(self):
        return self.treasureIds

    # Six garden slots, each with a toon id and its lawn items.
    def setSlot0ToonId(self, avId): self.slotToonIds[0] = avId
    def getSlot0ToonId(self): return self.slotToonIds[0]
    def setSlot0Items(self, items): self.slotItems[0] = items
    def getSlot0Items(self): return self.slotItems[0]
    def setSlot1ToonId(self, avId): self.slotToonIds[1] = avId
    def getSlot1ToonId(self): return self.slotToonIds[1]
    def setSlot1Items(self, items): self.slotItems[1] = items
    def getSlot1Items(self): return self.slotItems[1]
    def setSlot2ToonId(self, avId): self.slotToonIds[2] = avId
    def getSlot2ToonId(self): return self.slotToonIds[2]
    def setSlot2Items(self, items): self.slotItems[2] = items
    def getSlot2Items(self): return self.slotItems[2]
    def setSlot3ToonId(self, avId): self.slotToonIds[3] = avId
    def getSlot3ToonId(self): return self.slotToonIds[3]
    def setSlot3Items(self, items): self.slotItems[3] = items
    def getSlot3Items(self): return self.slotItems[3]
    def setSlot4ToonId(self, avId): self.slotToonIds[4] = avId
    def getSlot4ToonId(self): return self.slotToonIds[4]
    def setSlot4Items(self, items): self.slotItems[4] = items
    def getSlot4Items(self): return self.slotItems[4]
    def setSlot5ToonId(self, avId): self.slotToonIds[5] = avId
    def getSlot5ToonId(self): return self.slotToonIds[5]
    def setSlot5Items(self, items): self.slotItems[5] = items
    def getSlot5Items(self): return self.slotItems[5]

    # ---- broadcasts ---------------------------------------------------------
    def d_setEstateReady(self):
        self.sendUpdate('setEstateReady', [])

    # ---- client messages ------------------------------------------------------
    def requestServerTime(self):
        avId = self.air.getAvatarIdFromSender()
        serverTime = int(time.time()) % HouseGlobals.DAY_NIGHT_PERIOD
        self.sendUpdateToAvatarId(avId, 'setServerTime', [serverTime])

    def setClientReady(self):
        pass

    def setClosestHouse(self, index):
        pass

    def completeFlowerSale(self, flag):
        # Flower selling comes with gardening (stage 4).
        pass
