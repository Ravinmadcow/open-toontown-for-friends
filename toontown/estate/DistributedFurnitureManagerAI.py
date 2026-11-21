from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog.CatalogFurnitureItem import CatalogFurnitureItem, FLBank, FLCloset, FLTrunk
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI


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
    Owns the furniture in one house. Stage 2 places the starting furniture;
    the attic, moving and buying furniture come later.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureManagerAI')

    def __init__(self, air, house, interior):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.interior = interior
        self.ownerId = house.getAvatarId()
        self.ownerName = house.getName()
        self.director = 0
        self.items = []

    def createDefaultFurniture(self):
        owner = self.air.doId2do.get(self.ownerId)
        isGirl = owner is not None and owner.getStyle().gender == 'f'
        for furnitureType, posHpr in DEFAULT_FURNITURE:
            if isGirl:
                furnitureType = GIRL_SWAPS.get(furnitureType, furnitureType)
            catalogItem = CatalogFurnitureItem(furnitureType)
            item = getItemClass(catalogItem)(self.air, self, catalogItem, posHpr)
            item.generateWithRequired(self.zoneId)
            self.items.append(item)

    def cleanup(self):
        for item in self.items:
            item.requestDelete()
        self.items = []
        self.requestDelete()

    # ---- required fields ----------------------------------------------------
    def getOwnerId(self):
        return self.ownerId

    def getOwnerName(self):
        return self.ownerName

    def getInteriorId(self):
        return self.interior.getDoId()

    def getAtticItems(self):
        return b''

    def getAtticWallpaper(self):
        return b''

    def getAtticWindows(self):
        return b''

    def getDeletedItems(self):
        return b''

    def getDirector(self):
        return self.director

    # ---- client messages (furniture moving comes later) ----------------------
    def suggestDirector(self, avId):
        pass

    def avatarEnter(self):
        pass

    def avatarExit(self):
        pass
