from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta

from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.estate.BankGlobals import *


class DistributedBankAI(DistributedFurnitureItemAI):
    """The jellybean bank: the house owner can deposit and withdraw jellybeans."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBankAI')

    def __init__(self, air, furnitureMgr, item, posHpr):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, item, posHpr)
        self.busy = 0

    def delete(self):
        self.__stopUsing()
        taskMgr.remove(self.uniqueName('clearMovie'))
        DistributedFurnitureItemAI.delete(self)

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId, globalClockDelta.getRealNetworkTime()])

    def __clearMovieLater(self):
        taskMgr.remove(self.uniqueName('clearMovie'))
        taskMgr.doMethodLater(3.0, self.__clearMovie, self.uniqueName('clearMovie'))

    def __clearMovie(self, task=None):
        self.d_setMovie(BANK_MOVIE_CLEAR, 0)
        return task.done if task else None

    def __stopUsing(self):
        if self.busy:
            self.ignore(self.air.getAvatarExitEvent(self.busy))
        self.busy = 0

    # ---- client messages ------------------------------------------------------
    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return

        if self.busy and self.busy != avId:
            # Someone else is using the bank.
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return

        ownerId = self.furnitureMgr.ownerId
        if not ownerId:
            self.d_setMovie(BANK_MOVIE_NO_OWNER, avId)
            self.__clearMovieLater()
            return
        if avId != ownerId:
            self.d_setMovie(BANK_MOVIE_NOT_OWNER, avId)
            self.__clearMovieLater()
            return

        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__stopUsing)
        self.d_setMovie(BANK_MOVIE_GUI, avId)

    def transferMoney(self, amount):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.busy:
            return
        av = self.air.doId2do.get(avId)
        if av is None:
            self.__stopUsing()
            return

        # Never trust the client's number: clamp it to what is actually possible.
        if amount > 0:
            amount = min(amount, av.getMoney(), av.getMaxBankMoney() - av.getBankMoney())
            amount = max(amount, 0)
        elif amount < 0:
            amount = -min(-amount, av.getBankMoney(), av.getMaxMoney() - av.getMoney())
            amount = min(amount, 0)

        if amount:
            av.b_setMoney(av.getMoney() - amount)
            av.b_setBankMoney(av.getBankMoney() + amount)

        if amount > 0:
            self.d_setMovie(BANK_MOVIE_DEPOSIT, avId)
        elif amount < 0:
            self.d_setMovie(BANK_MOVIE_WITHDRAW, avId)
        else:
            self.d_setMovie(BANK_MOVIE_NO_OP, avId)

        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
        self.__stopUsing()
        self.__clearMovieLater()
