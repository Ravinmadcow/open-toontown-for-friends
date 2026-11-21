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
        self._atticItemsBlob = b''
        self._interiorItemsBlob = b''
        self._atticWallpaperBlob = b''
        self.interiorWallpaper = b''
        self._atticWindowsBlob = b''
        self.interiorWindows = b''
        self.deletedItems = b''
        self.cannonEnabled = 0
        self.interiorZone = None
        self.interior = None
        self.furnitureMgr = None
        self.door = None
        self.insideDoor = None
        self.mailbox = None

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
        self._atticItemsBlob = items

    def getAtticItems(self):
        return self._atticItemsBlob

    def setInteriorItems(self, items):
        self._interiorItemsBlob = items

    def getInteriorItems(self):
        return self._interiorItemsBlob

    def setAtticWallpaper(self, items):
        self._atticWallpaperBlob = items

    def getAtticWallpaper(self):
        return self._atticWallpaperBlob

    def setInteriorWallpaper(self, items):
        self.interiorWallpaper = items

    def getInteriorWallpaper(self):
        return self.interiorWallpaper

    def setAtticWindows(self, items):
        self._atticWindowsBlob = items

    def getAtticWindows(self):
        return self._atticWindowsBlob

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
        from toontown.estate import HouseStorageAI

        # Load this toon's saved house, if they have one.
        saved = HouseStorageAI.load(self.air, self.avatarId) or {}

        self.interiorZone = self.air.allocateZone()

        self.interior = DistributedHouseInteriorAI(self.air, self, saved.get('wallpaper'), saved.get('windows'))
        self.interior.generateWithRequired(self.interiorZone)

        self.furnitureMgr = DistributedFurnitureManagerAI(self.air, self, self.interior, saved)
        self.furnitureMgr.generateWithRequired(self.interiorZone)
        self.furnitureMgr.createFurniture()

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

        # The mailbox out front, for catalogue deliveries.
        from toontown.estate.DistributedMailboxAI import DistributedMailboxAI
        self.mailbox = DistributedMailboxAI(self.air, self)
        self.mailbox.generateWithRequired(estateZoneId)

    def cleanupInterior(self):
        # The furniture manager saves the house as it cleans up.
        if self.furnitureMgr is not None:
            self.furnitureMgr.cleanup()
        for obj in (self.door, self.insideDoor, self.interior, self.mailbox):
            if obj is not None:
                obj.requestDelete()
        self.mailbox = None
        self.door = self.insideDoor = self.interior = self.furnitureMgr = None
        if self.interiorZone is not None:
            self.air.deallocateZone(self.interiorZone)
            self.interiorZone = None

    # ---- used by catalogue items when they are accepted from the mailbox ----
    @property
    def atticItems(self):
        return self.furnitureMgr.atticItems if self.furnitureMgr else []

    @property
    def atticWallpaper(self):
        return self.furnitureMgr.atticWallpaper if self.furnitureMgr else []

    @property
    def atticWindows(self):
        return self.furnitureMgr.atticWindows if self.furnitureMgr else []

    @property
    def interiorItems(self):
        return [item.item for item in self.furnitureMgr.items] if self.furnitureMgr else []

    def addAtticItem(self, catalogItem):
        if self.furnitureMgr:
            self.furnitureMgr.addAtticItem(catalogItem)

    def addWallpaper(self, catalogItem):
        if self.furnitureMgr:
            self.furnitureMgr.addWallpaper(catalogItem)

    def addWindow(self, catalogItem):
        if self.furnitureMgr:
            self.furnitureMgr.addWindow(catalogItem)
