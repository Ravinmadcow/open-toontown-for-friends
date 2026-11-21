from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogItem
from toontown.estate import HouseGlobals


class DistributedFurnitureItemAI(DistributedObjectAI):
    """
    One piece of furniture in a house. The toon arranging the house (the
    'director') can move it; the final position is saved.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureItemAI')

    def __init__(self, air, furnitureMgr, item, posHpr=None):
        DistributedObjectAI.__init__(self, air)
        self.furnitureMgr = furnitureMgr
        self.item = item
        if posHpr is None:
            posHpr = getattr(item, 'posHpr', None) or (0, 0, 0, 0, 0, 0)
        self.posHpr = tuple(posHpr)
        self.item.posHpr = self.posHpr
        self.moving = False

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.sendUpdate('setPosHpr', list(self.posHpr))

    def getItem(self):
        return [self.furnitureMgr.getDoId(), self.item.getBlob(store=CatalogItem.Customization)]

    def getMode(self):
        return [HouseGlobals.FURNITURE_MODE_OFF, 0]

    def requestPosHpr(self, final, x, y, z, h, p, r, timestamp):
        avId = self.air.getAvatarIdFromSender()
        if not avId or avId != self.furnitureMgr.director:
            return

        if not self.moving:
            self.moving = True
            self.sendUpdate('setMode', [HouseGlobals.FURNITURE_MODE_START, avId])

        # Let everyone else watch it move smoothly.
        self.sendUpdate('setSmPosHpr', [x, y, z, h, p, r, timestamp])

        if final:
            self.moving = False
            self.posHpr = (x, y, z, h, p, r)
            self.item.posHpr = self.posHpr
            self.sendUpdate('setMode', [HouseGlobals.FURNITURE_MODE_STOP, avId])
            self.sendUpdate('setPosHpr', list(self.posHpr))
            self.furnitureMgr.saveHouse()
