from direct.directnotify import DirectNotifyGlobal

from toontown.estate import ClosetGlobals
from toontown.estate.DistributedClosetAI import DistributedClosetAI
from toontown.toon import ToonDNA

EMPTY = (0, 0, 0)
ACCESSORY_TYPES = (ToonDNA.HAT, ToonDNA.GLASSES, ToonDNA.BACKPACK, ToonDNA.SHOES)


def _getWorn(av, accessoryType):
    return {ToonDNA.HAT: av.getHat,
            ToonDNA.GLASSES: av.getGlasses,
            ToonDNA.BACKPACK: av.getBackpack,
            ToonDNA.SHOES: av.getShoes}[accessoryType]()


def _setWorn(av, accessoryType, item):
    {ToonDNA.HAT: av.b_setHat,
     ToonDNA.GLASSES: av.b_setGlasses,
     ToonDNA.BACKPACK: av.b_setBackpack,
     ToonDNA.SHOES: av.b_setShoes}[accessoryType](*item)


def _sendList(av, accessoryType):
    if accessoryType == ToonDNA.HAT:
        av.b_setHatList(av.getHatList())
    elif accessoryType == ToonDNA.GLASSES:
        av.b_setGlassesList(av.getGlassesList())
    elif accessoryType == ToonDNA.BACKPACK:
        av.b_setBackpackList(av.getBackpackList())
    elif accessoryType == ToonDNA.SHOES:
        av.b_setShoesList(av.getShoesList())


class DistributedTrunkAI(DistributedClosetAI):
    """The accessories trunk: hats, glasses, backpacks and shoes."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrunkAI')

    def __init__(self, air, furnitureMgr, item, posHpr):
        DistributedClosetAI.__init__(self, air, furnitureMgr, item, posHpr)
        self.originalWorn = {}

    def d_setOpenState(self, av, isOwner):
        if isOwner:
            lists = [list(av.getHatList()), list(av.getGlassesList()),
                     list(av.getBackpackList()), list(av.getShoesList())]
        else:
            lists = [[], [], [], []]
        self.sendUpdate('setState', [ClosetGlobals.OPEN, av.getDoId(), self.getOwnerId(),
                                     self._getGender(av)] + lists)

    def d_setClosedState(self, av):
        gender = self._getGender(av) if av is not None else 'm'
        self.sendUpdate('setState', [ClosetGlobals.CLOSED, 0, self.getOwnerId(), gender, [], [], [], []])

    def enterAvatar(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or not self._busyCheck(avId):
            return
        self._startUsing(av)
        self.originalWorn = {t: tuple(_getWorn(av, t)) for t in ACCESSORY_TYPES}
        self.d_setOpenState(av, avId == self.getOwnerId())

    def removeItem(self, geomIdx, texIdx, colorIdx, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.busy or avId != self.getOwnerId():
            return
        if which not in ACCESSORY_TYPES:
            return
        item = (geomIdx, texIdx, colorIdx)
        if av.removeItemInAccessoriesList(which, *item):
            _sendList(av, which)
        elif item == self.originalWorn.get(which):
            self.deletedWorn.add(which)

    def setDNA(self, hatIdx, hatTex, hatColor, glassesIdx, glassesTex, glassesColor,
               backpackIdx, backpackTex, backpackColor, shoesIdx, shoesTex, shoesColor,
               finished, which):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None or avId != self.busy:
            return

        chosen = {ToonDNA.HAT: (hatIdx, hatTex, hatColor),
                  ToonDNA.GLASSES: (glassesIdx, glassesTex, glassesColor),
                  ToonDNA.BACKPACK: (backpackIdx, backpackTex, backpackColor),
                  ToonDNA.SHOES: (shoesIdx, shoesTex, shoesColor)}

        if finished == 0:
            self.d_setCustomerDNA(avId, chosen, which)
            return

        if finished == 2 and avId == self.getOwnerId():
            for accessoryType in ACCESSORY_TYPES:
                if which & accessoryType:
                    self._applyAccessory(av, accessoryType, chosen[accessoryType])
        # Show everyone what the toon is really wearing now.
        worn = {t: tuple(_getWorn(av, t)) for t in ACCESSORY_TYPES}
        self.d_setCustomerDNA(avId, worn, ToonDNA.HAT | ToonDNA.GLASSES | ToonDNA.BACKPACK | ToonDNA.SHOES)
        self._finish(avId)

    def _applyAccessory(self, av, accessoryType, new):
        new = tuple(new)
        old = self.originalWorn.get(accessoryType, EMPTY)
        if new == old:
            return
        if new != EMPTY and not av.hasAccessory(accessoryType, *new):
            self.notify.warning('Toon %s tried to wear an accessory they do not own' % av.getDoId())
            return
        oldDeleted = accessoryType in self.deletedWorn
        if new != EMPTY:
            if old != EMPTY and not oldDeleted:
                av.replaceItemInAccessoriesList(accessoryType, *(new + old))
            else:
                av.removeItemInAccessoriesList(accessoryType, *new)
        elif old != EMPTY and not oldDeleted:
            av.addToAccessoriesList(accessoryType, *old)
        _setWorn(av, accessoryType, new)
        _sendList(av, accessoryType)

    def d_setCustomerDNA(self, avId, items, which):
        args = [avId]
        for accessoryType in ACCESSORY_TYPES:
            args.extend(items[accessoryType])
        args.append(which)
        self.sendUpdate('setCustomerDNA', args)
