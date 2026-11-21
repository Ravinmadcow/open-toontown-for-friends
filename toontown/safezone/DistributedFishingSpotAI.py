from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.fishing import FishGlobals


class DistributedFishingSpotAI(DistributedObjectAI):
    """
    One fishing spot on a pond dock. A toon sits here, pays to cast, and
    when their bob lands on a fish shadow the pond tells us to reel in a catch.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingSpotAI')

    def __init__(self, air, pond=None):
        DistributedObjectAI.__init__(self, air)
        self.pond = pond
        self.pondDoId = pond.getDoId() if pond else 0
        self.posHpr = (0, 0, 0, 0, 0, 0)
        self.avId = 0
        self.cast = False

    def delete(self):
        self.__removeToon()
        DistributedObjectAI.delete(self)

    # ---- required fields ----------------------------------------------------
    def setPondDoId(self, pondDoId):
        self.pondDoId = pondDoId

    def getPondDoId(self):
        return self.pondDoId

    def setPosHpr(self, x, y, z, h, p, r):
        self.posHpr = (x, y, z, h, p, r)

    def getPosHpr(self):
        return self.posHpr

    def getOccupied(self):
        return self.avId

    # ---- helpers ------------------------------------------------------------
    def d_setOccupied(self, avId):
        self.sendUpdate('setOccupied', [avId])

    def d_setMovie(self, mode, code=0, item1=0, item2=0, item3=0, power=0, heading=0):
        self.sendUpdate('setMovie', [mode, code, item1, item2, item3, power, heading])

    def __startTimeout(self):
        taskMgr.remove(self.uniqueName('timeout'))
        taskMgr.doMethodLater(FishGlobals.CastTimeout, self.__timeout, self.uniqueName('timeout'))

    def __timeout(self, task):
        # Sat here without casting for too long.
        if self.avId:
            self.d_setMovie(FishGlobals.ExitMovie)
            self.__removeToon()
        return task.done

    def __removeToon(self):
        taskMgr.remove(self.uniqueName('timeout'))
        if self.avId:
            self.ignore(self.air.getAvatarExitEvent(self.avId))
            self.avId = 0
            self.cast = False
            self.d_setOccupied(0)

    # ---- client messages ------------------------------------------------------
    def requestEnter(self):
        avId = self.air.getAvatarIdFromSender()
        if self.avId and self.avId != avId:
            self.sendUpdateToAvatarId(avId, 'rejectEnter', [])
            return
        if avId not in self.air.doId2do:
            return
        self.avId = avId
        self.cast = False
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__removeToon)
        self.d_setOccupied(avId)
        self.d_setMovie(FishGlobals.EnterMovie)
        self.__startTimeout()

    def requestExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.avId:
            return
        self.d_setMovie(FishGlobals.ExitMovie)
        self.__removeToon()

    def doCast(self, power, heading):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.avId:
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        castCost = FishGlobals.getCastCost(av.getFishingRod())
        if av.getMoney() < castCost:
            return
        av.b_setMoney(av.getMoney() - castCost)
        self.cast = True
        self.d_setMovie(FishGlobals.CastMovie, 0, 0, 0, 0, power, heading)
        self.__startTimeout()

    def sellFish(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.avId:
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        trophyResult = self.air.fishManager.creditFishTank(av)
        self.sendUpdateToAvatarId(avId, 'sellFishComplete', [1 if trophyResult else 0, len(av.fishCollection)])

    # ---- called by the pond -------------------------------------------------
    def rewardIfValid(self):
        if not self.avId or not self.cast:
            return
        av = self.air.doId2do.get(self.avId)
        if av is None:
            return
        self.cast = False
        area = self.pond.getArea() if self.pond else 0
        code, item1, item2, item3 = self.air.fishManager.generateCatch(av, area, self.zoneId)
        self.d_setMovie(FishGlobals.PullInMovie, code, item1, item2, item3)
        self.__startTimeout()
