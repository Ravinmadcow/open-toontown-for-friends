from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedHouseAI(DistributedObjectAI):
    """
    One house on an estate. Stage 1: shows the house with its owner's name
    and colour. Doors, interiors and furniture come with stage 2.
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
