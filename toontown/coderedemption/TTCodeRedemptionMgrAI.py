"""
Code redemption (Options page > Codes in the Shticker Book).

Codes live in etc/redeem_codes.txt, one per line:
    CODE   reward [reward ...]   [expires=YYYY-MM-DD]
Rewards are delivered to the toon's mailbox:
    beans:500                       a jar of 500 jellybeans
    item:CatalogFurnitureItem(100)  any catalogue item, written the way the
                                    catalogue code writes it
Each toon can use each code once. Codes aren't case-sensitive.
Which toons have used which codes is saved in <server-data-folder>/redeemed_codes.json.
The file is re-read whenever it changes, so new codes work without a restart.
"""
import json
import os
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.toonbase import ToontownGlobals

# Result codes understood by the client (TTCodeRedemptionConsts.RedeemErrors).
SUCCESS, NO_SUCH_CODE, EXPIRED, ALREADY_USED, AWARD_FAILED, TOO_MANY_ATTEMPTS, UNAVAILABLE = range(7)
# AwardManagerConsts.GiveAwardErrors values used here.
AWARD_OK, AWARD_MAILBOX_FULL, AWARD_ALREADY_HAVE, AWARD_UNKNOWN = 0, 3, 15, 16
MAX_FAILURES = 5
FAILURE_WINDOW = 10 * 60  # seconds


def _catalogNamespace():
    from toontown.catalog import (CatalogAccessoryItem, CatalogAnimatedFurnitureItem, CatalogBeanItem,
                                  CatalogChatItem, CatalogClothingItem, CatalogEmoteItem, CatalogFlooringItem,
                                  CatalogFurnitureItem, CatalogGardenItem, CatalogGardenStarterItem,
                                  CatalogMouldingItem, CatalogNametagItem, CatalogPetTrickItem, CatalogPoleItem,
                                  CatalogRentalItem, CatalogToonStatueItem, CatalogWainscotingItem,
                                  CatalogWallpaperItem, CatalogWindowItem)
    names = {}
    for module in (CatalogAccessoryItem, CatalogAnimatedFurnitureItem, CatalogBeanItem, CatalogChatItem,
                   CatalogClothingItem, CatalogEmoteItem, CatalogFlooringItem, CatalogFurnitureItem,
                   CatalogGardenItem, CatalogGardenStarterItem, CatalogMouldingItem, CatalogNametagItem,
                   CatalogPetTrickItem, CatalogPoleItem, CatalogRentalItem, CatalogToonStatueItem,
                   CatalogWainscotingItem, CatalogWallpaperItem, CatalogWindowItem):
        name = module.__name__.split('.')[-1]
        names[name] = getattr(module, name)
    return names


class TTCodeRedemptionMgrAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('TTCodeRedemptionMgrAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.codes = {}
        self.codesMtime = None
        self.redeemed = None
        self.failures = {}  # avId -> [timestamps]

    # ---- files ------------------------------------------------------------------
    def codesPath(self):
        return os.path.join('etc', 'redeem_codes.txt')

    def __redeemedPath(self):
        return os.path.join(getattr(self.air, 'dataFolder', '') or '', 'redeemed_codes.json')

    def loadCodes(self):
        path = self.codesPath()
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self.codes = {}
            return self.codes
        if mtime == self.codesMtime:
            return self.codes
        self.codesMtime = mtime
        codes = {}
        with open(path, 'r', encoding='utf-8') as f:
            for lineNo, line in enumerate(f, 1):
                line = line.split('#', 1)[0].strip()
                if not line:
                    continue
                parts = line.split()
                code, rewards, expires = parts[0].upper(), [], None
                for part in parts[1:]:
                    if part.startswith('expires='):
                        expires = part[len('expires='):]
                    else:
                        rewards.append(part)
                if not rewards:
                    self.notify.warning('redeem_codes.txt line %d: %s has no reward' % (lineNo, code))
                    continue
                codes[code] = {'rewards': rewards, 'expires': expires}
        self.codes = codes
        self.notify.info('Loaded %d redeemable codes' % len(codes))
        return codes

    def __loadRedeemed(self):
        if self.redeemed is None:
            try:
                with open(self.__redeemedPath(), 'r') as f:
                    self.redeemed = json.load(f)
            except Exception:
                self.redeemed = {}
        return self.redeemed

    def __saveRedeemed(self):
        try:
            folder = os.path.dirname(self.__redeemedPath())
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = self.__redeemedPath() + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.redeemed, f)
            os.replace(tmp, self.__redeemedPath())
        except Exception as e:
            self.notify.warning('Could not save redeemed codes: %s' % e)

    # ---- rewards ----------------------------------------------------------------
    def makeItems(self, rewards):
        items = []
        namespace = None
        for reward in rewards:
            kind, _, value = reward.partition(':')
            kind = kind.lower()
            if kind == 'beans':
                from toontown.catalog.CatalogBeanItem import CatalogBeanItem
                items.append(CatalogBeanItem(int(value)))
            elif kind == 'item':
                if namespace is None:
                    namespace = _catalogNamespace()
                items.append(eval(value, {'__builtins__': {}}, namespace))
            else:
                raise ValueError('unknown reward %s' % reward)
        return items

    def __deliver(self, av, items):
        from toontown.catalog import CatalogItem
        from toontown.catalog.CatalogItemList import CatalogItemList
        if len(av.onOrder) + len(av.mailboxContents) + len(items) > ToontownGlobals.MaxMailboxContents:
            return AWARD_MAILBOX_FULL
        for item in items:
            if item.reachedPurchaseLimit(av):
                return AWARD_ALREADY_HAVE
        now = int(time.time() / 60 + 0.5)
        for item in items:
            item.deliveryDate = now
        onOrder = CatalogItemList(list(av.onOrder) + items, store=CatalogItem.Customization | CatalogItem.DeliveryDate)
        av.b_setDeliverySchedule(onOrder)
        return AWARD_OK

    # ---- client request ---------------------------------------------------------
    def redeemCode(self, context, code):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        result, awardResult = self.__redeem(av, code.strip().upper())
        if result in (NO_SUCH_CODE, EXPIRED):
            now = time.time()
            recent = [t for t in self.failures.get(avId, []) if now - t < FAILURE_WINDOW] + [now]
            self.failures[avId] = recent
        self.sendUpdateToAvatarId(avId, 'redeemCodeResult', [context, result, awardResult])

    def __redeem(self, av, code):
        avId = av.getDoId()
        now = time.time()
        if len([t for t in self.failures.get(avId, []) if now - t < FAILURE_WINDOW]) >= MAX_FAILURES:
            return TOO_MANY_ATTEMPTS, 0
        try:
            codes = self.loadCodes()
        except Exception as e:
            self.notify.warning('Could not read %s: %s' % (self.codesPath(), e))
            return UNAVAILABLE, 0
        entry = codes.get(code)
        if entry is None:
            return NO_SUCH_CODE, 0
        if entry['expires'] and time.strftime('%Y-%m-%d') > entry['expires']:
            return EXPIRED, 0
        redeemed = self.__loadRedeemed()
        if avId in redeemed.get(code, []):
            return ALREADY_USED, 0
        try:
            items = self.makeItems(entry['rewards'])
        except Exception as e:
            self.notify.warning('Code %s has a bad reward: %s' % (code, e))
            return AWARD_FAILED, AWARD_UNKNOWN
        awardResult = self.__deliver(av, items)
        if awardResult != AWARD_OK:
            return AWARD_FAILED, awardResult
        redeemed.setdefault(code, []).append(avId)
        self.__saveRedeemed()
        self.failures.pop(avId, None)
        self.notify.info('%s redeemed %s' % (avId, code))
        return SUCCESS, 0
