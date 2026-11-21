from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.catalog import CatalogItem
from toontown.catalog.CatalogItemList import CatalogItemList
from toontown.estate import MailboxGlobals
from toontown.toonbase import ToontownGlobals


class DistributedMailboxAI(DistributedObjectAI):
    """
    The mailbox outside each toon's house. The owner collects catalogue
    orders (and award items) here; accepting an item puts it to use, for
    example furniture goes to the attic and clothes to the wardrobe.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedMailboxAI')

    def __init__(self, air, house):
        DistributedObjectAI.__init__(self, air)
        self.house = house
        self.houseId = house.getDoId()
        self.housePos = house.getHousePos()
        self.name = house.getName()
        self.ownerId = house.getAvatarId()
        self.fullIndicator = 0
        self.busy = 0

    def delete(self):
        self.__stopUsing()
        taskMgr.remove(self.uniqueName('clearMovie'))
        DistributedObjectAI.delete(self)

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        owner = self.air.doId2do.get(self.ownerId)
        if owner is not None and hasattr(owner, 'checkMailboxFullIndicator'):
            owner.checkMailboxFullIndicator()

    # ---- required fields ----------------------------------------------------
    def getHouseId(self):
        return self.houseId

    def getHousePos(self):
        return self.housePos

    def getName(self):
        return self.name

    def getFullIndicator(self):
        return self.fullIndicator

    def b_setFullIndicator(self, full):
        self.fullIndicator = 1 if full else 0
        self.sendUpdate('setFullIndicator', [self.fullIndicator])

    # ---- helpers ------------------------------------------------------------
    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId])

    def __clearMovieLater(self):
        taskMgr.remove(self.uniqueName('clearMovie'))
        taskMgr.doMethodLater(3.0, self.__clearMovie, self.uniqueName('clearMovie'))

    def __clearMovie(self, task):
        self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_CLEAR, 0)
        return task.done

    def __stopUsing(self):
        if self.busy:
            self.ignore(self.air.getAvatarExitEvent(self.busy))
        self.busy = 0

    def __getItem(self, av, index):
        """The client lists award items first, then catalogue deliveries."""
        awards = av.awardMailboxContents
        if 0 <= index < len(awards):
            return 'award', index, awards[index]
        mailIndex = index - len(awards)
        if 0 <= mailIndex < len(av.mailboxContents):
            return 'mail', mailIndex, av.mailboxContents[mailIndex]
        return None, None, None

    def __removeItem(self, av, source, index):
        if source == 'award':
            items = CatalogItemList(list(av.awardMailboxContents), store=CatalogItem.Customization)
            del items[index]
            av.b_setAwardMailboxContents(items)
        else:
            items = CatalogItemList(list(av.mailboxContents), store=CatalogItem.Customization)
            del items[index]
            av.b_setMailboxContents(items)

    # ---- client messages ------------------------------------------------------
    def avatarEnter(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        if self.busy and self.busy != avId:
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return
        if avId != self.ownerId:
            self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_NOT_OWNER, avId)
            self.__clearMovieLater()
            return
        if len(av.mailboxContents) + len(av.awardMailboxContents) == 0:
            if len(av.onOrder):
                self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_WAITING, avId)
            else:
                self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_EMPTY, avId)
            self.__clearMovieLater()
            return
        self.busy = avId
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__stopUsing)
        self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_READY, avId)

    def avatarExit(self):
        avId = self.air.getAvatarIdFromSender()
        if avId != self.busy:
            return
        self.d_setMovie(MailboxGlobals.MAILBOX_MOVIE_EXIT, avId)
        self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
        self.__stopUsing()
        self.__clearMovieLater()
        av = self.air.doId2do.get(avId)
        if av is not None:
            av.b_setCatalogNotify(av.catalogNotify, ToontownGlobals.NoItems if not len(av.mailboxContents) else ToontownGlobals.OldItems)

    def acceptItemMessage(self, context, blob, index, optional):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        retcode = ToontownGlobals.P_NotAtMailbox
        if av is not None and avId == self.busy:
            source, listIndex, item = self.__getItem(av, index)
            if item is None or item != CatalogItem.getItem(blob, store=CatalogItem.Customization):
                retcode = ToontownGlobals.P_InvalidIndex
            else:
                try:
                    retcode = item.recordPurchase(av, optional)
                except Exception as e:
                    self.notify.warning('Could not accept %s for %s: %s' % (item, avId, e))
                    retcode = ToontownGlobals.P_NoPurchaseMethod
                if retcode >= 0:
                    self.__removeItem(av, source, listIndex)
                    self.air.writeServerEvent('mailbox-accept', avId, '%s' % item)
        self.sendUpdateToAvatarId(avId, 'acceptItemResponse', [context, retcode])

    def discardItemMessage(self, context, blob, index, optional):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        retcode = ToontownGlobals.P_NotAtMailbox
        if av is not None and avId == self.busy:
            source, listIndex, item = self.__getItem(av, index)
            if item is None or item != CatalogItem.getItem(blob, store=CatalogItem.Customization):
                retcode = ToontownGlobals.P_InvalidIndex
            else:
                self.__removeItem(av, source, listIndex)
                retcode = ToontownGlobals.P_ItemAvailable
        self.sendUpdateToAvatarId(avId, 'discardItemResponse', [context, retcode])

    # Party invites are not supported yet.
    def acceptInviteMessage(self, context, inviteKey):
        pass

    def rejectInviteMessage(self, context, inviteKey):
        pass

    def markInviteReadButNotReplied(self, inviteKey):
        pass
