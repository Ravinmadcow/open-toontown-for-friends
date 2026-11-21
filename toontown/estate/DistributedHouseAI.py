from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.building import DoorTypes


class DistributedHouseAI(DistributedObjectAI):
    """
    One house on an estate: the outside (name, colour), its front door, and
    for houses that belong to a toon, an interior with starting furniture.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.housePos = 0
        self.houseType = 0
        self.gardenPos = 0
        self.avatarId = 0
        self.name = ''
        self.color = 0
        self.atticItems = b''
        self.interiorItems = b''
        self.atticWallpaper = b''
        self.interiorWallpaper = b''
        self.atticWindows = b''
        self.interiorWindows = b''
        self.deletedItems = b''
        self.cannonEnabled = 0
        self.interiorZone = None
        self.interior = None
        self.furnitureMgr = None
        self.door = None
        self.insideDoor = None

    def setHousePos(self, pos):
        self.housePos = pos

    def getHousePos(self):
        return self.housePos

    def setHouseType(self, houseType):
        self.houseType = houseType

    def getHouseType(self):
        return self.houseType

    def setGardenPos(self, pos):
        self.gardenPos = pos

    def getGardenPos(self):
        return self.gardenPos

    def setAvatarId(self, avId):
        self.avatarId = avId

    def getAvatarId(self):
        return self.avatarId

    def setName(self, name):
        self.name = name

    def getName(self):
        return self.name

    def setColor(self, color):
        self.color = color

    def getColor(self):
        return self.color

    def setAtticItems(self, items):
        self.atticItems = items

    def getAtticItems(self):
        return self.atticItems

    def setInteriorItems(self, items):
        self.interiorItems = items

    def getInteriorItems(self):
        return self.interiorItems

    def setAtticWallpaper(self, items):
        self.atticWallpaper = items

    def getAtticWallpaper(self):
        return self.atticWallpaper

    def setInteriorWallpaper(self, items):
        self.interiorWallpaper = items

    def getInteriorWallpaper(self):
        return self.interiorWallpaper

    def setAtticWindows(self, items):
        self.atticWindows = items

    def getAtticWindows(self):
        return self.atticWindows

    def setInteriorWindows(self, items):
        self.interiorWindows = items

    def getInteriorWindows(self):
        return self.interiorWindows

    def setDeletedItems(self, items):
        self.deletedItems = items

    def getDeletedItems(self):
        return self.deletedItems

    def setCannonEnabled(self, enabled):
        self.cannonEnabled = enabled

    def getCannonEnabled(self):
        return self.cannonEnabled

    def d_setHouseReady(self):
        self.sendUpdate('setHouseReady', [])

    # ---- interior (stage 2) -----------------------------------------------------
    def setupInterior(self, estateZoneId):
        # Imported here so the estate still loads if anything below is missing.
        from toontown.estate.DistributedHouseInteriorAI import DistributedHouseInteriorAI
        from toontown.estate.DistributedFurnitureManagerAI import DistributedFurnitureManagerAI
        from toontown.estate.DistributedHouseDoorAI import DistributedHouseDoorAI

        self.interiorZone = self.air.allocateZone()

        self.interior = DistributedHouseInteriorAI(self.air, self)
        self.interior.generateWithRequired(self.interiorZone)

        self.furnitureMgr = DistributedFurnitureManagerAI(self.air, self, self.interior)
        self.furnitureMgr.generateWithRequired(self.interiorZone)
        self.furnitureMgr.createDefaultFurniture()

        door = DistributedHouseDoorAI(self.air, self.getDoId(), DoorTypes.EXT_STANDARD)
        insideDoor = DistributedHouseDoorAI(self.air, self.getDoId(), DoorTypes.INT_STANDARD)
        door.setOtherDoor(insideDoor)
        insideDoor.setOtherDoor(door)
        door.zoneId = estateZoneId
        insideDoor.zoneId = self.interiorZone
        door.generateWithRequired(estateZoneId)
        insideDoor.generateWithRequired(self.interiorZone)
        self.door = door
        self.insideDoor = insideDoor

    def cleanupInterior(self):
        for obj in (self.door, self.insideDoor, self.interior):
            if obj is not None:
                obj.requestDelete()
        if self.furnitureMgr is not None:
            self.furnitureMgr.cleanup()
        self.door = self.insideDoor = self.interior = self.furnitureMgr = None
        if self.interiorZone is not None:
            self.air.deallocateZone(self.interiorZone)
            self.interiorZone = None
