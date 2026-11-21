from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedLawnDecorAI import DistributedLawnDecorAI


class DistributedGardenBoxAI(DistributedLawnDecorAI):
    """A wooden flower box. Purely for show: the flower spots sit inside it."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedGardenBoxAI')

    def __init__(self, air, garden, x, y, h, typeIndex):
        DistributedLawnDecorAI.__init__(self, air, garden, -1, x, y, h)
        self.typeIndex = typeIndex

    def getTypeIndex(self):
        return self.typeIndex
