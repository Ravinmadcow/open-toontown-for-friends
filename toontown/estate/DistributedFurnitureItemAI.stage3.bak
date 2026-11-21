from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogItem


class DistributedFurnitureItemAI(DistributedObjectAI):
    """
    One piece of furniture in a house. Stage 2: it is placed and shown;
    moving it comes later.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFurnitureItemAI')

    def __init__(self, air, furnitureMgr, item, posHpr):
        DistributedObjectAI.__init__(self, air)
        self.furnitureMgr = furnitureMgr
        self.item = item
        self.posHpr = posHpr

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.sendUpdate('setPosHpr', list(self.posHpr))

    def getItem(self):
        return [self.furnitureMgr.getDoId(), self.item.getBlob(store=CatalogItem.Customization)]

    def getMode(self):
        return [0, 0]

    def requestPosHpr(self, final, x, y, z, h, p, r, timestamp):
        # Moving furniture comes in a later stage.
        pass
