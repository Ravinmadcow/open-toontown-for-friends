from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta

from toontown.estate import ClosetGlobals
from toontown.estate.DistributedFurnitureItemAI import DistributedFurnitureItemAI
from toontown.toon import ToonDNA


def _inList(itemList, item, size):
    item = list(item)
    for i in range(0, len(itemList), size):
        if list(itemList[i:i + size]) == item:
            return True
    return False


class DistributedClosetAI(DistributedFurnitureItemAI):
    """
    The wardrobe: the house owner can change into clothes they own, and
    throw clothes away. Other toons just get the 'not your wardrobe' message.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedClosetAI')

    def __init__(self, air, furnitureMgr, item, posHpr):
        DistributedFurnitureItemAI.__init__(self, air, furnitureMgr, item, posHpr)
        self.busy = 0
        self.originalDNA = None
        self.deletedWorn = set()

    def delete(self):
        self._stopUsing()
        taskMgr.remove(self.uniqueName('clearMovie'))
        DistributedFurnitureItemAI.delete(self)

    # ---- helpers ------------------------------------------------------------
    def getOwnerId(self):
        return self.furnitureMgr.ownerId

    def _getGender(self, av):
        owner = self.air.doId2do.get(self.getOwnerId())
        style = (owner or av).getStyle()
        return style.gender

    def d_setMovie(self, mode, avId):
        self.sendUpdate('setMovie', [mode, avId, globalClockDelta.getRealNetworkTime()])

    def _clearMovieLater(self):
        taskMgr.remove(self.uniqueName('clearMovie'))
        taskMgr.doMethodLater(3.0, self._clearMovie, self.uniqueName('clearMovie'))

    def _clearMovie(self, task):
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_CLEAR, 0)
        return task.done

    def _startUsing(self, av):
        self.busy = av.getDoId()
        self.deletedWorn = set()
        self.acceptOnce(self.air.getAvatarExitEvent(self.busy), self._stopUsing)
        taskMgr.doMethodLater(ClosetGlobals.TIMEOUT_TIME, self._timeout, self.uniqueName('timeout'))

    def _stopUsing(self):
        if self.busy:
            self.ignore(self.air.getAvatarExitEvent(self.busy))
        taskMgr.remove(self.uniqueName('timeout'))
        taskMgr.remove(self.uniqueName('forceClose'))
        self.busy = 0
        self.originalDNA = None
        self.deletedWorn = set()

    def _timeout(self, task):
        if self.busy:
            # The client answers with setDNA(..., finished=1), which closes up.
            self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_TIMEOUT, self.busy)
            taskMgr.doMethodLater(10.0, self._forceClose, self.uniqueName('forceClose'))
        return task.done

    def _forceClose(self, task):
        if self.busy:
            self._finish(self.busy)
        return task.done

    def _finish(self, avId):
        self.d_setMovie(ClosetGlobals.CLOSET_MOVIE_COMPLETE, avId)
        av = self.air.doId2do.get(avId)
        self.d_setClosedState(av)
        self._stopUsing()
        self._clearMovieLater()

    def _busyCheck(self, avId):
        if self.busy and self.busy != avId:
            self.sendUpdateToAvatarId(avId, 'freeAvatar', [])
            return False
        return True

    # ---- wardrobe specifics (the trunk overrides these) ---------------------
    def d_setOpenState(self, av, isOwner):
        if isOwner:
            tops = list(av.getClothesTopsList())
            bottoms = list(av.getClothesBottomsList())
        else:
            tops, bottoms = [], []
        self.sendUpdate('setState', [ClosetGlobals.OPEN, av.getDoId(), self.getOwnerId(),
                                     self._getGender(av), tops, bottoms])

    def d_setClosedState(self, av):
        gender = self._getGender(av) if av is not None else 'm'
        self.sendUpdate('setState', [ClosetGlobals.CLOSED, 0, self.getOwnerId(), gender, [], []])

    # ---- client messages ------------------------------------------------------
    def enterAvatar(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self._busyCheck(avId):
            return
        self._startUsing(av)
        self.originalDNA = av.getDNAString()
        self.d_setOpenState(av, avId == self.getOwnerId())

    def removeItem(self, dnaBlob, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.busy or avId != self.getOwnerId():
            return
        dna = ToonDNA.ToonDNA()
        dna.makeFromNetString(dnaBlob)
        original = ToonDNA.ToonDNA()
        original.makeFromNetString(self.originalDNA)
        if which == ClosetGlobals.SHIRT:
            item = (dna.topTex, dna.topTexColor, dna.sleeveTex, dna.sleeveTexColor)
            worn = (original.topTex, original.topTexColor, original.sleeveTex, original.sleeveTexColor)
            if av.removeItemInClothesTopsList(*item):
                av.b_setClothesTopsList(av.getClothesTopsList())
            elif item == worn:
                self.deletedWorn.add(ClosetGlobals.SHIRT)
        elif which == ClosetGlobals.SHORTS:
            item = (dna.botTex, dna.botTexColor)
            worn = (original.botTex, original.botTexColor)
            if av.removeItemInClothesBottomsList(*item):
                av.b_setClothesBottomsList(av.getClothesBottomsList())
            elif item == worn:
                self.deletedWorn.add(ClosetGlobals.SHORTS)

    def setDNA(self, dnaBlob, finished, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.busy:
            return

        if finished == 0:
            # Just previewing: show the other toons nearby.
            self.sendUpdate('setCustomerDNA', [avId, dnaBlob])
            return

        if finished == 2 and avId == self.getOwnerId():
            self._applyClothes(av, dnaBlob, which)
        else:
            # Cancelled (or not the owner): put the original outfit back.
            self.sendUpdate('setCustomerDNA', [avId, self.originalDNA])
            av.b_setDNAString(self.originalDNA)
        self._finish(avId)

    def _applyClothes(self, av, dnaBlob, which):
        new = ToonDNA.ToonDNA()
        new.makeFromNetString(dnaBlob)
        old = ToonDNA.ToonDNA()
        old.makeFromNetString(self.originalDNA)
        result = ToonDNA.ToonDNA()
        result.makeFromNetString(self.originalDNA)

        if which & ClosetGlobals.SHIRT:
            newTop = (new.topTex, new.topTexColor, new.sleeveTex, new.sleeveTexColor)
            oldTop = (old.topTex, old.topTexColor, old.sleeveTex, old.sleeveTexColor)
            if newTop != oldTop and _inList(av.getClothesTopsList(), newTop, 4):
                if ClosetGlobals.SHIRT in self.deletedWorn:
                    av.removeItemInClothesTopsList(*newTop)
                else:
                    av.replaceItemInClothesTopsList(*(newTop + oldTop))
                result.topTex, result.topTexColor, result.sleeveTex, result.sleeveTexColor = newTop
                av.b_setClothesTopsList(av.getClothesTopsList())

        if which & ClosetGlobals.SHORTS:
            newBot = (new.botTex, new.botTexColor)
            oldBot = (old.botTex, old.botTexColor)
            if newBot != oldBot and _inList(av.getClothesBottomsList(), newBot, 2):
                if ClosetGlobals.SHORTS in self.deletedWorn:
                    av.removeItemInClothesBottomsList(*newBot)
                else:
                    av.replaceItemInClothesBottomsList(*(newBot + oldBot))
                result.botTex, result.botTexColor = newBot
                # Girls switch body shape between shorts and skirts.
                if len(old.torso) == 2 and len(new.torso) == 2 and new.torso[0] == old.torso[0]:
                    result.torso = new.torso
                av.b_setClothesBottomsList(av.getClothesBottomsList())

        av.b_setDNAString(result.makeNetString())
        self.sendUpdate('setCustomerDNA', [av.getDoId(), result.makeNetString()])
