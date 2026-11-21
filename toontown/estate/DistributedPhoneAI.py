import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from panda3d.core import ConfigVariableBool

from toontown.catalog import CatalogItem
from toontown.catalog.CatalogItemList import CatalogItemList
from toontown.estate import PhoneGlobals
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.toonbase import ToontownGlobals


class DistributedPhoneAI(DistributedFurnitureItemAI):
    """
    The phone: the house owner orders items from their catalogue. Orders
    arrive in the mailbox. With 'instant-catalog-delivery' on (the default),
    they arrive within seconds; turn it off in etc/Configrc.prc to use the
    original delivery times.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPhoneAI')

    def __init__(self, air, furnitureMgr, item, posHpr):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, item, posHpr)
        self.busy = 0
        self.initialScale = (1.0, 1.0, 1.0)
        self.instantDelivery = ConfigVariableBool('instant-catalog-delivery', True).value

    def delete(self):
        self.__stopUsing()
        taskMgr.remove(self.uniqueName('clearMovie'))
        DistributedFurnitureItemAI.delete(self)

    def getInitialScale(self):
        return self.initialScale

    def setNewScale(self, sx, sy, sz):
        pass

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId, globalClockDelta.getRealNetworkTime(bits=32)])

    def __clearMovieLater(self):
        taskMgr.remove(self.uniqueName('clearMovie'))
        taskMgr.doMethodLater(3.0, self.__clearMovie, self.uniqueName('clearMovie'))

    def __clearMovie(self, task):
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_CLEAR, 0)
        return task.done

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
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return

        hasCatalog = len(av.monthlyCatalog) + len(av.weeklyCatalog) + len(av.backCatalog) > 0
        if avId != self.furnitureMgr.ownerId or not hasCatalog:
            # The client closes the 'nothing to order' message itself.
            self.d_setMovie(PhoneGlobals.PHONE_MOVIE_EMPTY, avId)
            self.__clearMovieLater()
            return

        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__stopUsing)
        self.sendUpdateToAvatarId(avId, 'setLimits', [self.furnitureMgr.getNumHouseItems()])
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_PICKUP, avId)

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.busy:
            return
        self.d_setMovie(PhoneGlobals.PHONE_MOVIE_HANGUP, avId)
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
        self.__stopUsing()
        self.__clearMovieLater()

    def requestPurchaseMessage(self, context, blob, optional):
        avId = self.air.getAvatarIdFromSender()
        retcode = self.__purchase(avId, blob, optional)
        self.sendUpdateToAvatarId(avId, 'requestPurchaseResponse', [context, retcode])

    def requestGiftPurchaseMessage(self, context, targetDoId, blob, optional):
        # Gifting is not supported yet.
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'requestGiftPurchaseResponse', [context, ToontownGlobals.P_NoPurchaseMethod])

    # ---- buying ----------------------------------------------------------------
    def __findInCatalog(self, av, item):
        if item in av.monthlyCatalog:
            return CatalogItem.CatalogTypeMonthly, av.monthlyCatalog[av.monthlyCatalog.index(item)]
        if item in av.weeklyCatalog:
            return CatalogItem.CatalogTypeWeekly, av.weeklyCatalog[av.weeklyCatalog.index(item)]
        if item in av.backCatalog:
            return CatalogItem.CatalogTypeBackorder, av.backCatalog[av.backCatalog.index(item)]
        return None, None

    def __purchase(self, avId, blob, optional):
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.busy:
            return ToontownGlobals.P_NotShopping
        try:
            item = CatalogItem.getItem(blob, store=CatalogItem.Customization)
        except Exception:
            return ToontownGlobals.P_NotInCatalog

        catalogType, catalogItem = self.__findInCatalog(av, item)
        if catalogItem is None:
            self.air.writeServerEvent('suspicious', avId, 'tried to buy %s which is not in their catalogue' % item)
            return ToontownGlobals.P_NotInCatalog
        if item.reachedPurchaseLimit(av):
            return ToontownGlobals.P_ReachedPurchaseLimit
        if len(av.onOrder) + len(av.mailboxContents) >= ToontownGlobals.MaxMailboxContents:
            return ToontownGlobals.P_OnOrderListFull

        # Use the catalogue's copy for the price, so sale prices are honoured.
        price = catalogItem.getPrice(catalogType)
        if not av.takeMoney(price):
            return ToontownGlobals.P_NotEnoughMoney

        now = int(time.time() / 60 + 0.5)
        delay = 0 if self.instantDelivery else item.getDeliveryTime()
        item.deliveryDate = now + delay
        onOrder = CatalogItemList(list(av.onOrder) + [item],
                                  store=CatalogItem.Customization | CatalogItem.DeliveryDate)
        av.b_setDeliverySchedule(onOrder)
        self.air.writeServerEvent('catalog-purchase', avId, '%s for %s jellybeans' % (item, price))
        return ToontownGlobals.P_ItemOnOrder
