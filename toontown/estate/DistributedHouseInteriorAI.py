from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogItem
from toontown.catalog.CatalogItemList import CatalogItemList
from toontown.catalog.CatalogWallpaperItem import CatalogWallpaperItem
from toontown.catalog.CatalogMouldingItem import CatalogMouldingItem
from toontown.catalog.CatalogFlooringItem import CatalogFlooringItem
from toontown.catalog.CatalogWainscotingItem import CatalogWainscotingItem


def makeDefaultWallpaper():
    # Two rooms (main room, then bedroom), each with wallpaper, moulding,
    # flooring and wainscoting, in that order.
    mainRoom = [CatalogWallpaperItem(1100, 0, 1000, 0),
                CatalogMouldingItem(1000, 0),
                CatalogFlooringItem(1000, 0),
                CatalogWainscotingItem(1010, 0)]
    bedroom = [CatalogWallpaperItem(1100, 0, 1000, 0),
               CatalogMouldingItem(1000, 0),
               CatalogFlooringItem(1010, 0),
               CatalogWainscotingItem(1010, 0)]
    return CatalogItemList(mainRoom + bedroom)


class DistributedHouseInteriorAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseInteriorAI')

    def __init__(self, air, house, wallpaper=None, windows=None):
        DistributedObjectAI.__init__(self, air)
        self.houseId = house.getDoId()
        self.houseIndex = house.getHousePos()
        if wallpaper is None or len(wallpaper) < 8:
            wallpaper = makeDefaultWallpaper()
        self.wallpaper = wallpaper
        self.windows = windows if windows is not None else CatalogItemList()

    def getHouseId(self):
        return self.houseId

    def getHouseIndex(self):
        return self.houseIndex

    def getWallpaper(self):
        return self.wallpaper.getBlob(store=CatalogItem.Customization)

    def getWindows(self):
        return self.windows.getBlob(store=CatalogItem.Customization | CatalogItem.WindowPlacement)

    def d_setWallpaper(self):
        self.sendUpdate('setWallpaper', [self.getWallpaper()])

    def d_setWindows(self):
        self.sendUpdate('setWindows', [self.getWindows()])
