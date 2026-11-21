from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogItem
from toontown.catalog.CatalogItemList import CatalogItemList
from toontown.catalog.CatalogFurnitureItem import CatalogFurnitureItem, FLBank, FLCloset, FLTrunk
from toontown.catalog.CatalogSurfaceItem import CatalogSurfaceItem, NUM_ST_TYPES
from toontown.catalog.CatalogWindowItem import CatalogWindowItem
from toontown.estate import HouseStorageAI
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.toonbase import ToontownGlobals


def getItemClass(item):
    """Picks the server object for a piece of furniture: special items get their own class."""
    flags = item.getFlags()
    if flags & FLBank:
        from toontown.estate.DistributedBankAI import DistributedBankAI
        return DistributedBankAI
    if flags & FLTrunk:
        from toontown.estate.DistributedTrunkAI import DistributedTrunkAI
        return DistributedTrunkAI
    if flags & FLCloset:
        from toontown.estate.DistributedClosetAI import DistributedClosetAI
        return DistributedClosetAI
    return DistributedFurnitureItemAI


def _isDeletable(item):
    check = getattr(item, 'isDeletable', None)
    return check() if check else True


# Girls get the girls' wardrobe and trunk.
GIRL_SWAPS = {500: 510, 4000: 4010}

# Starting furniture: (furniture type, (x, y, z, h, p, r)).
# Main room is roughly x -19..16, y -26..3; bedroom is x -24..-1, y 3..26.
DEFAULT_FURNITURE = [
    (1000, (0.0, -12.0, 0.0, 0, 0, 0)),     # rug
    (100, (4.0, 0.5, 0.0, 0, 0, 0)),        # chair
    (700, (13.5, -10.0, 0.0, 270, 0, 0)),   # armchair
    (600, (13.5, -4.0, 0.0, 0, 0, 0)),      # lamp
    (1300, (13.5, -18.0, 0.0, 270, 0, 0)),  # jellybean bank
    (1399, (10.0, 3.0, 0.0, 0, 0, 0)),      # phone (on the wall)
    (200, (-12.0, 25.0, 0.0, 0, 0, 0)),     # bed
    (500, (-21.8, 12.0, 0.0, 90, 0, 0)),    # wardrobe
    (4000, (-21.8, 6.0, 0.0, 90, 0, 0)),    # trunk
    (600, (-4.0, 24.0, 0.0, 0, 0, 0)),      # bedroom lamp
]


class DistributedFurnitureManagerAI(DistributedObjectAI):
    """
    Owns everything in one house: the furniture on the floor, the attic,
    the wallpaper and windows, and recently thrown-away items. The house
    owner can arrange it all, and every change is saved.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureManagerAI')

    def __init__(self, air, house, interior, saved=None):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.interior = interior
        self.ownerId = house.getAvatarId()
        self.ownerName = house.getName()
        self.director = 0
        self.items = []
        saved = saved or {}
        self.savedInteriorItems = saved.get('interiorItems')
        self.atticItems = saved.get('atticItems') or CatalogItemList()
        self.atticWallpaper = saved.get('atticWallpaper') or CatalogItemList()
        self.atticWindows = saved.get('atticWindows') or CatalogItemList()
        self.deletedItems = saved.get('deletedItems') or CatalogItemList()

    # ---- setup / teardown -----------------------------------------------------
    def createFurniture(self):
        if self.savedInteriorItems is not None:
            for catalogItem in self.savedInteriorItems:
                self.__spawnItem(catalogItem)
            return

        owner = self.air.doId2do.get(self.ownerId)
        isGirl = owner is not None and owner.getStyle().gender == 'f'
        for furnitureType, posHpr in DEFAULT_FURNITURE:
            if isGirl:
                furnitureType = GIRL_SWAPS.get(furnitureType, furnitureType)
            self.__spawnItem(CatalogFurnitureItem(furnitureType, posHpr=posHpr), posHpr)
        self.saveHouse()

    # Kept for older callers.
    createDefaultFurniture = createFurniture

    def __spawnItem(self, catalogItem, posHpr=None):
        cls = getItemClass(catalogItem) if isinstance(catalogItem, CatalogFurnitureItem) else DistributedFurnitureItemAI
        item = cls(self.air, self, catalogItem, posHpr)
        item.generateWithRequired(self.zoneId)
        self.items.append(item)
        return item

    def cleanup(self):
        self.saveHouse()
        self.ignoreAll()
        for item in self.items:
            item.requestDelete()
        self.items = []
        self.requestDelete()

    # ---- saving -------------------------------------------------------------
    def saveHouse(self):
        if not self.ownerId:
            return
        HouseStorageAI.save(self.air, self.ownerId, {
            'interiorItems': CatalogItemList([item.item for item in self.items]),
            'atticItems': self.atticItems,
            'atticWallpaper': self.atticWallpaper,
            'atticWindows': self.atticWindows,
            'deletedItems': self.deletedItems,
            'wallpaper': self.interior.wallpaper,
            'windows': self.interior.windows,
        })

    # ---- required fields ----------------------------------------------------
    def getOwnerId(self):
        return self.ownerId

    def getOwnerName(self):
        return self.ownerName

    def getInteriorId(self):
        return self.interior.getDoId()

    def getAtticItems(self):
        return self.atticItems.getBlob(store=CatalogItem.Customization)

    def getAtticWallpaper(self):
        return self.atticWallpaper.getBlob(store=CatalogItem.Customization)

    def getAtticWindows(self):
        return self.atticWindows.getBlob(store=CatalogItem.Customization)

    def getDeletedItems(self):
        return self.deletedItems.getBlob(store=CatalogItem.Customization)

    def getDirector(self):
        return self.director

    def d_setAtticItems(self):
        self.sendUpdate('setAtticItems', [self.getAtticItems()])

    def d_setAtticWallpaper(self):
        self.sendUpdate('setAtticWallpaper', [self.getAtticWallpaper()])

    def d_setAtticWindows(self):
        self.sendUpdate('setAtticWindows', [self.getAtticWindows()])

    def d_setDeletedItems(self):
        self.sendUpdate('setDeletedItems', [self.getDeletedItems()])

    # ---- who is arranging the house -------------------------------------------
    def suggestDirector(self, avId):
        senderId = self.air.getAvatarIdFromSender()
        if avId == 0:
            # Leaving furniture mode.
            if senderId == self.director:
                self.__setDirector(0)
            return
        if senderId != avId or senderId != self.ownerId:
            # Only the owner can arrange their house.
            return
        self.__setDirector(avId)

    def __setDirector(self, avId):
        if self.director:
            self.ignore(self.air.getAvatarExitEvent(self.director))
        self.director = avId
        if avId:
            self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__setDirector, [0])
        self.sendUpdate('setDirector', [avId])

    def avatarEnter(self):
        pass

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId == self.director:
            self.__setDirector(0)

    def __checkDirector(self, responseField, context, *extra):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.director or avId != self.ownerId:
            self.sendUpdateToAvatarId(avId, responseField, [ToontownGlobals.FM_NotDirector] + list(extra) + [context])
            return None
        return avId

    def __respond(self, avId, field, args):
        self.sendUpdateToAvatarId(avId, field, args)

    def __findItem(self, doId):
        for item in self.items:
            if item.getDoId() == doId:
                return item
        return None

    def __addDeleted(self, catalogItem):
        self.deletedItems.append(catalogItem)
        while len(self.deletedItems) > HouseStorageAI.MAX_DELETED_ITEMS:
            del self.deletedItems[0]
        self.d_setDeletedItems()

    # ---- furniture --------------------------------------------------------------
    def moveItemToAtticMessage(self, doId, context):
        avId = self.__checkDirector('moveItemToAtticResponse', context)
        if avId is None:
            return
        item = self.__findItem(doId)
        if item is None:
            self.__respond(avId, 'moveItemToAtticResponse', [ToontownGlobals.FM_InvalidItem, context])
            return
        self.items.remove(item)
        item.requestDelete()
        self.atticItems.append(item.item)
        self.d_setAtticItems()
        self.saveHouse()
        self.__respond(avId, 'moveItemToAtticResponse', [ToontownGlobals.FM_MovedItem, context])

    def moveItemFromAtticMessage(self, index, x, y, z, h, p, r, context):
        avId = self.__checkDirector('moveItemFromAtticResponse', context, 0)
        if avId is None:
            return
        if index < 0 or index >= len(self.atticItems):
            self.__respond(avId, 'moveItemFromAtticResponse', [ToontownGlobals.FM_InvalidIndex, 0, context])
            return
        if len(self.items) >= ToontownGlobals.MaxHouseItems:
            self.__respond(avId, 'moveItemFromAtticResponse', [ToontownGlobals.FM_HouseFull, 0, context])
            return
        catalogItem = self.atticItems.pop(index)
        posHpr = (x, y, z, h, p, r)
        catalogItem.posHpr = posHpr
        item = self.__spawnItem(catalogItem, posHpr)
        self.d_setAtticItems()
        self.saveHouse()
        # Give the new object a moment to reach the client before answering.
        taskMgr.doMethodLater(0.5, self.__delayedRespond, self.uniqueName('respond-%d' % context),
                              extraArgs=[avId, 'moveItemFromAtticResponse',
                                         [ToontownGlobals.FM_MovedItem, item.getDoId(), context]])

    def __delayedRespond(self, avId, field, args):
        self.__respond(avId, field, args)

    def deleteItemFromAtticMessage(self, blob, index, context):
        avId = self.__checkDirector('deleteItemFromAtticResponse', context)
        if avId is None:
            return
        if index < 0 or index >= len(self.atticItems):
            self.__respond(avId, 'deleteItemFromAtticResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        catalogItem = self.atticItems[index]
        if not _isDeletable(catalogItem):
            self.__respond(avId, 'deleteItemFromAtticResponse', [ToontownGlobals.FM_NondeletableItem, context])
            return
        del self.atticItems[index]
        self.__addDeleted(catalogItem)
        self.d_setAtticItems()
        self.saveHouse()
        self.__respond(avId, 'deleteItemFromAtticResponse', [ToontownGlobals.FM_DeletedItem, context])

    def deleteItemFromRoomMessage(self, blob, doId, context):
        avId = self.__checkDirector('deleteItemFromRoomResponse', context)
        if avId is None:
            return
        item = self.__findItem(doId)
        if item is None:
            self.__respond(avId, 'deleteItemFromRoomResponse', [ToontownGlobals.FM_InvalidItem, context])
            return
        if not _isDeletable(item.item):
            self.__respond(avId, 'deleteItemFromRoomResponse', [ToontownGlobals.FM_NondeletableItem, context])
            return
        self.items.remove(item)
        item.requestDelete()
        self.__addDeleted(item.item)
        self.saveHouse()
        self.__respond(avId, 'deleteItemFromRoomResponse', [ToontownGlobals.FM_DeletedItem, context])

    # ---- wallpaper ------------------------------------------------------------
    def moveWallpaperFromAtticMessage(self, index, room, context):
        avId = self.__checkDirector('moveWallpaperFromAtticResponse', context)
        if avId is None:
            return
        if index < 0 or index >= len(self.atticWallpaper) or room not in (0, 1):
            self.__respond(avId, 'moveWallpaperFromAtticResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        newItem = self.atticWallpaper[index]
        slot = room * NUM_ST_TYPES + newItem.getSurfaceType()
        wallpaper = self.interior.wallpaper
        oldItem = wallpaper[slot]
        wallpaper[slot] = newItem
        self.atticWallpaper[index] = oldItem
        self.interior.d_setWallpaper()
        self.d_setAtticWallpaper()
        self.saveHouse()
        self.__respond(avId, 'moveWallpaperFromAtticResponse', [ToontownGlobals.FM_SwappedItem, context])

    def deleteWallpaperFromAtticMessage(self, blob, index, context):
        avId = self.__checkDirector('deleteWallpaperFromAtticResponse', context)
        if avId is None:
            return
        if index < 0 or index >= len(self.atticWallpaper):
            self.__respond(avId, 'deleteWallpaperFromAtticResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        self.__addDeleted(self.atticWallpaper.pop(index))
        self.d_setAtticWallpaper()
        self.saveHouse()
        self.__respond(avId, 'deleteWallpaperFromAtticResponse', [ToontownGlobals.FM_DeletedItem, context])

    # ---- windows --------------------------------------------------------------
    def __windowAt(self, slot):
        for item in self.interior.windows:
            if item.placement == slot:
                return item
        return None

    def moveWindowToAtticMessage(self, slot, context):
        avId = self.__checkDirector('moveWindowToAtticResponse', context)
        if avId is None:
            return
        window = self.__windowAt(slot)
        if window is None:
            self.__respond(avId, 'moveWindowToAtticResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        self.interior.windows.remove(window)
        window.placement = None
        self.atticWindows.append(window)
        self.interior.d_setWindows()
        self.d_setAtticWindows()
        self.saveHouse()
        self.__respond(avId, 'moveWindowToAtticResponse', [ToontownGlobals.FM_MovedItem, context])

    def moveWindowFromAtticMessage(self, index, slot, context):
        avId = self.__checkDirector('moveWindowFromAtticResponse', context)
        if avId is None:
            return
        if index < 0 or index >= len(self.atticWindows):
            self.__respond(avId, 'moveWindowFromAtticResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        window = self.atticWindows.pop(index)
        retcode = ToontownGlobals.FM_MovedItem
        existing = self.__windowAt(slot)
        if existing is not None:
            self.interior.windows.remove(existing)
            existing.placement = None
            self.atticWindows.append(existing)
            retcode = ToontownGlobals.FM_SwappedItem
        window.placement = slot
        self.interior.windows.append(window)
        self.interior.d_setWindows()
        self.d_setAtticWindows()
        self.saveHouse()
        self.__respond(avId, 'moveWindowFromAtticResponse', [retcode, context])

    def moveWindowMessage(self, fromSlot, toSlot, context):
        avId = self.__checkDirector('moveWindowResponse', context)
        if avId is None:
            return
        window = self.__windowAt(fromSlot)
        if window is None:
            self.__respond(avId, 'moveWindowResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        retcode = ToontownGlobals.FM_MovedItem
        other = self.__windowAt(toSlot)
        if other is not None:
            other.placement = fromSlot
            retcode = ToontownGlobals.FM_SwappedItem
        window.placement = toSlot
        self.interior.d_setWindows()
        self.saveHouse()
        self.__respond(avId, 'moveWindowResponse', [retcode, context])

    def deleteWindowFromAtticMessage(self, blob, index, context):
        avId = self.__checkDirector('deleteWindowFromAtticResponse', context)
        if avId is None:
            return
        if index < 0 or index >= len(self.atticWindows):
            self.__respond(avId, 'deleteWindowFromAtticResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        self.__addDeleted(self.atticWindows.pop(index))
        self.d_setAtticWindows()
        self.saveHouse()
        self.__respond(avId, 'deleteWindowFromAtticResponse', [ToontownGlobals.FM_DeletedItem, context])

    # ---- trash ----------------------------------------------------------------
    def recoverDeletedItemMessage(self, blob, index, context):
        avId = self.__checkDirector('recoverDeletedItemResponse', context)
        if avId is None:
            return
        if index < 0 or index >= len(self.deletedItems):
            self.__respond(avId, 'recoverDeletedItemResponse', [ToontownGlobals.FM_InvalidIndex, context])
            return
        catalogItem = self.deletedItems.pop(index)
        if isinstance(catalogItem, CatalogSurfaceItem):
            self.atticWallpaper.append(catalogItem)
            self.d_setAtticWallpaper()
        elif isinstance(catalogItem, CatalogWindowItem):
            catalogItem.placement = None
            self.atticWindows.append(catalogItem)
            self.d_setAtticWindows()
        else:
            self.atticItems.append(catalogItem)
            self.d_setAtticItems()
        self.d_setDeletedItems()
        self.saveHouse()
        self.__respond(avId, 'recoverDeletedItemResponse', [ToontownGlobals.FM_RecoveredItem, context])
