from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate import GardenGlobals


class DistributedLawnDecorAI(DistributedObjectAI):
    """Base for everything placed in an estate garden (plots, boxes, plants)."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedLawnDecorAI')

    def __init__(self, air, garden, plot, x, y, h):
        DistributedObjectAI.__init__(self, air)
        self.garden = garden
        self.plot = plot
        self.position = (x, y, 0.0)
        self.heading = h
        self.ownerIndex = garden.slot if garden else 0
        self.movieAvId = 0

    # ---- required fields ----------------------------------------------------
    def getPlot(self):
        return self.plot

    def getHeading(self):
        return self.heading

    def getPosition(self):
        return self.position

    def getOwnerIndex(self):
        return self.ownerIndex

    # ---- helpers ------------------------------------------------------------
    def isOwner(self, avId):
        return bool(avId) and self.garden is not None and avId == self.garden.ownerId

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def d_interactionDenied(self, avId):
        self.sendUpdate('interactionDenied', [avId])

    def clearMovie(self, avId):
        self.movieAvId = 0
        self.d_setMovie(GardenGlobals.MOVIE_CLEAR, avId)

    # ---- client messages ------------------------------------------------------
    def plotEntered(self):
        pass

    def removeItem(self):
        avId = self.air.getAvatarIdFromSender()
        self.d_interactionDenied(avId)

    def movieDone(self):
        avId = self.air.getAvatarIdFromSender()
        if avId == self.movieAvId:
            self.clearMovie(avId)
