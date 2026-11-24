from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI


class DistributedToonStatuaryAI(DistributedStatuaryAI):
    """A stone statue of one of the owner's toons. 'optional' holds the toon's
    look (species, legs, torso and head) as the client packs it."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedToonStatuaryAI')

    def __init__(self, air, garden, plot, x, y, h, typeIndex, waterLevel=0, growthLevel=0, optional=0):
        DistributedStatuaryAI.__init__(self, air, garden, plot, x, y, h, typeIndex, waterLevel, growthLevel)
        self.optional = optional

    def getOptional(self):
        return self.optional
