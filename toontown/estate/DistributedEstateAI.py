import json
import os
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import HouseGlobals
from toontown.toonbase import ToontownGlobals

# Where rented items go on the estate grounds.
TARGET_POS = (30.0, -126.0, 0.0)               # floating over the pond
GAME_TABLE_POSHPR = (-20.0, -100.0, 2.22, 0, 0, 0)


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
        self.accountId = 0
        self.rentalObjects = []
        self.gardens = {}   # slot -> GardenAI

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

    # ---- gardens --------------------------------------------------------------
    def d_setIdList(self, idList):
        self.idList = list(idList)
        self.sendUpdate('setIdList', [self.idList])

    def createGarden(self, slot, ownerId):
        from toontown.estate.GardenAI import GardenAI
        if slot in self.gardens:
            return self.gardens[slot]
        garden = GardenAI(self.air, self, slot, ownerId)
        garden.create()
        self.gardens[slot] = garden
        return garden

    def placeStarterGarden(self, avId):
        """Called when a Garden Starter Kit is accepted from the mailbox."""
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.b_setGardenStarted(1)
        if avId in self.idList:
            self.createGarden(self.idList.index(avId), avId)

    def cleanupGardens(self):
        for garden in self.gardens.values():
            try:
                garden.cleanup()
            except Exception as e:
                self.notify.warning('Could not clean up garden: %s' % e)
        self.gardens = {}

    def completeFlowerSale(self, flag):
        """Selling the flower basket at the estate wheelbarrow."""
        if not flag:
            return
        from toontown.estate import GardenGlobals
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not len(av.flowerBasket):
            return
        value = av.flowerBasket.getTotalValue()
        for flower in av.flowerBasket.getFlower():
            av.flowerCollection.collectFlower(flower)
        av.b_setFlowerCollection(*av.flowerCollection.getNetLists())
        av.b_setFlowerBasket([], [])
        av.addMoney(value)
        trophies = len(av.flowerCollection) // GardenGlobals.FLOWERS_PER_BONUS
        oldTrophies = len(av.getGardenTrophies())
        if trophies > oldTrophies:
            av.b_setGardenTrophies(list(range(trophies)))
            av.b_setMaxHp(av.getMaxHp() + (trophies - oldTrophies))
            av.toonUp(av.getMaxHp())
            self.sendUpdate('awardedTrophy', [avId])

    # ---- rentals (cannons and the game table) ---------------------------------
    def __rentalPath(self):
        folder = os.path.join(getattr(self.air, 'dataFolder', '') or '', 'estates')
        return folder, os.path.join(folder, '%d.json' % self.accountId)

    def __saveRental(self):
        if not self.accountId:
            return
        folder, path = self.__rentalPath()
        try:
            os.makedirs(folder, exist_ok=True)
            with open(path, 'w') as f:
                json.dump({'rentalType': self.rentalType, 'rentalEnd': self.rentalTimeStamp}, f)
        except Exception as e:
            self.notify.warning('Could not save rental: %s' % e)

    def loadRental(self, accountId):
        """Called once the estate is up: brings back a rental that has time left."""
        self.accountId = accountId
        folder, path = self.__rentalPath()
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            self.rentalType = data.get('rentalType', 0)
            self.rentalTimeStamp = data.get('rentalEnd', 0)
        except Exception:
            return
        if self.rentalType and self.rentalTimeStamp > time.time():
            self.__startRental()

    def rentItem(self, typeIndex, duration):
        """Called when a rental from the catalogue is accepted. duration is in minutes."""
        now = time.time()
        if self.rentalType == typeIndex and self.rentalTimeStamp > now:
            self.rentalTimeStamp += duration * 60  # extend the current rental
        else:
            self.__stopRental(announce=False)
            self.rentalType = typeIndex
            self.rentalTimeStamp = now + duration * 60
            self.__startRental()
        self.__scheduleEnd()
        self.__saveRental()

    def __startRental(self):
        if self.rentalType == ToontownGlobals.RentalCannon:
            from toontown.estate.DistributedTargetAI import DistributedTargetAI
            from toontown.estate.DistributedCannonAI import DistributedCannonAI
            from toontown.estate import CannonGlobals
            target = DistributedTargetAI(self.air, *TARGET_POS)
            target.generateWithRequired(self.zoneId)
            self.rentalObjects.append(target)
            for drop in CannonGlobals.cannonDrops:
                cannon = DistributedCannonAI(self.air, self.getDoId(), target.getDoId(), *drop)
                cannon.generateWithRequired(self.zoneId)
                self.rentalObjects.append(cannon)
        elif self.rentalType == ToontownGlobals.RentalGameTable:
            from toontown.safezone.DistributedPicnicTableAI import DistributedPicnicTableAI
            # This table generates itself when it is created.
            table = DistributedPicnicTableAI(self.air, self.zoneId, '1', *GAME_TABLE_POSHPR)
            self.rentalObjects.append(table)
        self.__scheduleEnd()

    def __scheduleEnd(self):
        taskMgr.remove(self.uniqueName('rentalEnd'))
        remaining = self.rentalTimeStamp - time.time()
        if self.rentalType and remaining > 0:
            taskMgr.doMethodLater(remaining, self.__rentalOver, self.uniqueName('rentalEnd'))

    def __rentalOver(self, task):
        self.__stopRental(announce=True)
        self.rentalType = 0
        self.rentalTimeStamp = 0
        self.__saveRental()
        return task.done

    def __stopRental(self, announce):
        taskMgr.remove(self.uniqueName('rentalEnd'))
        for obj in self.rentalObjects:
            try:
                obj.requestDelete()
            except Exception as e:
                self.notify.warning('Could not remove rental object: %s' % e)
        if self.rentalObjects and announce:
            if self.rentalType == ToontownGlobals.RentalCannon:
                self.sendUpdate('cannonsOver', [])
            elif self.rentalType == ToontownGlobals.RentalGameTable:
                self.sendUpdate('gameTableOver', [])
        self.rentalObjects = []

    def cleanupRentals(self):
        """Estate unloading: remove the rented items but keep the time left."""
        self.__stopRental(announce=False)
