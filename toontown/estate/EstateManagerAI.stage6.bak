from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.estate.DistributedEstateAI import DistributedEstateAI
from toontown.estate.DistributedHouseAI import DistributedHouseAI

NUM_HOUSES = 6


class EstateInstance:
    """One live estate: its zone, the estate object, its six houses and who is in it."""

    def __init__(self, accountId, ownerId, zoneId):
        self.accountId = accountId
        self.ownerId = ownerId
        self.zoneId = zoneId
        self.estate = None
        self.houses = []
        self.visitors = set()
        self.ready = False
        self.waiting = []  # avIds waiting for this estate to finish loading
        self.ponds = []


class EstateManagerAI(DistributedObjectAI):
    """
    Stage 1 estates: pressing Go Home loads your account's estate in its own
    zone, with a house for each toon slot. The estate is unloaded again when
    everyone has left.

    Houses that belong to a toon get a working front door and an interior
    with starting furniture. Everything is created fresh each visit.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('EstateManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.accountId2estate = {}
        self.zoneId2estate = {}
        self.avId2estate = {}   # which estate each toon is currently in
        self.estate = {}        # ownerAvId -> DistributedEstateAI (used by catalog code)
        self.pondGroups = None  # fishing pond layout from the estate DNA, loaded once

    # ---- client requests ----------------------------------------------------
    def getEstateZone(self, avId, name):
        senderId = self.air.getAvatarIdFromSender()
        accountId = self.air.getAccountIdFromSender()
        sender = self.air.doId2do.get(senderId)
        if sender is None:
            return

        if avId and avId != senderId:
            # Visiting someone else's estate: only if it is already loaded (stage 3 adds more).
            target = self.air.doId2do.get(avId)
            instance = None
            for inst in self.accountId2estate.values():
                if avId == inst.ownerId or (target is not None and avId in inst.visitors):
                    instance = inst
                    break
            if instance is None or not instance.ready:
                self.sendUpdateToAvatarId(senderId, 'setEstateZone', [0, 0])
                return
            self.__enter(instance, senderId)
            return

        instance = self.accountId2estate.get(accountId)
        if instance is not None:
            instance.ownerId = senderId
            if instance.ready:
                self.__enter(instance, senderId)
            else:
                instance.waiting.append(senderId)
            return

        zoneId = self.air.allocateZone()
        instance = EstateInstance(accountId, senderId, zoneId)
        instance.waiting.append(senderId)
        self.accountId2estate[accountId] = instance
        self.zoneId2estate[zoneId] = instance
        self.air.dbInterface.queryObject(self.air.dbId, accountId,
                                         lambda dclass, fields: self.__gotAccount(instance, fields))

    def exitEstate(self):
        avId = self.air.getAvatarIdFromSender()
        self.__leave(avId)

    def removeFriend(self, ownerId, avId):
        # Friends removal is handled by the friends system, not estates.
        pass

    # ---- loading --------------------------------------------------------------
    def __gotAccount(self, instance, fields):
        if self.accountId2estate.get(instance.accountId) is not instance:
            return  # unloaded while we were waiting
        avList = list((fields or {}).get('ACCOUNT_AV_SET', []))
        avList = (avList + [0] * NUM_HOUSES)[:NUM_HOUSES]
        names = {}
        pending = set(avId for avId in avList if avId)

        def finish():
            self.__buildEstate(instance, avList, names)

        if not pending:
            finish()
            return

        for avId in list(pending):
            online = self.air.doId2do.get(avId)
            if online is not None and hasattr(online, 'getName'):
                names[avId] = online.getName()
                pending.discard(avId)
        if not pending:
            finish()
            return

        for avId in list(pending):
            def gotToon(dclass, toonFields, avId=avId):
                try:
                    names[avId] = toonFields['setName'][0]
                except Exception:
                    names[avId] = ''
                pending.discard(avId)
                if not pending:
                    finish()
            self.air.dbInterface.queryObject(self.air.dbId, avId, gotToon)

    def __buildEstate(self, instance, avList, names):
        if self.accountId2estate.get(instance.accountId) is not instance:
            return

        estate = DistributedEstateAI(self.air)
        estate.generateWithRequired(instance.zoneId)
        instance.estate = estate

        try:
            self.__createPonds(instance)
        except Exception as e:
            self.notify.warning('Could not set up the estate fishing pond: %s' % e)

        for slot in range(NUM_HOUSES):
            avId = avList[slot]
            house = DistributedHouseAI(self.air)
            house.setHousePos(slot)
            house.setGardenPos(slot)
            house.setColor(slot)
            house.setAvatarId(avId)
            house.setName(names.get(avId, '') if avId else '')
            house.generateWithRequired(instance.zoneId)
            house.d_setHouseReady()
            instance.houses.append(house)
            if avId:
                try:
                    house.setupInterior(instance.zoneId)
                except Exception as e:
                    self.notify.warning('Could not set up interior for house %s: %s' % (slot, e))

            # Let each online toon on this account know which house is theirs.
            toon = self.air.doId2do.get(avId) if avId else None
            if toon is not None and hasattr(toon, 'b_setHouseId'):
                toon.b_setHouseId(house.getDoId())

        instance.ready = True
        self.estate[instance.ownerId] = estate
        self.notify.info('Loaded estate for account %s in zone %s' % (instance.accountId, instance.zoneId))

        waiting, instance.waiting = instance.waiting, []
        for avId in waiting:
            if avId in self.air.doId2do:
                self.__enter(instance, avId)
        if not instance.visitors:
            self.__unload(instance)

    # ---- visitors -----------------------------------------------------------
    def __enter(self, instance, avId):
        old = self.avId2estate.get(avId)
        if old is not None and old is not instance:
            self.__leave(avId)
        instance.visitors.add(avId)
        self.avId2estate[avId] = instance
        self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__leave, [avId])
        self.sendUpdateToAvatarId(avId, 'setEstateZone', [instance.ownerId, instance.zoneId])

    def __leave(self, avId):
        instance = self.avId2estate.pop(avId, None)
        self.ignore(self.air.getAvatarExitEvent(avId))
        if instance is None:
            return
        instance.visitors.discard(avId)
        if not instance.visitors and instance.ready:
            self.__unload(instance)

    # ---- fishing ------------------------------------------------------------
    def __findPondGroups(self, dnaData, found):
        if 'fishing_pond' in dnaData.getName():
            found.append(dnaData)
            return
        for i in range(dnaData.getNumChildren()):
            self.__findPondGroups(dnaData.at(i), found)

    def __createPonds(self, instance):
        from panda3d.toontown import DNAStorage
        from toontown.fishing.DistributedFishingPondAI import DistributedFishingPondAI
        from toontown.toonbase import ToontownGlobals
        if self.pondGroups is None:
            self.pondGroups = []
            dnaFile = self.air.lookupDNAFileName('estate_1.dna')
            self.dnaStore = DNAStorage()
            self.dnaData = self.air.loadDNAFileAI(self.dnaStore, dnaFile)
            self.__findPondGroups(self.dnaData, self.pondGroups)
        for group in self.pondGroups:
            pond = DistributedFishingPondAI(self.air)
            pond.setArea(ToontownGlobals.MyEstate)
            pond.generateWithRequired(instance.zoneId)
            self.air.findFishingSpots(group, pond)
            instance.ponds.append(pond)

    def __unload(self, instance):
        for pond in instance.ponds:
            try:
                pond.cleanup()
            except Exception as e:
                self.notify.warning('Could not clean up pond: %s' % e)
        instance.ponds = []
        for house in instance.houses:
            try:
                house.cleanupInterior()
            except Exception as e:
                self.notify.warning('Could not clean up house interior: %s' % e)
            house.requestDelete()
        instance.houses = []
        if instance.estate is not None:
            instance.estate.requestDelete()
            instance.estate = None
        if self.estate.get(instance.ownerId) is not None:
            del self.estate[instance.ownerId]
        self.accountId2estate.pop(instance.accountId, None)
        self.zoneId2estate.pop(instance.zoneId, None)
        self.air.deallocateZone(instance.zoneId)
        self.notify.info('Unloaded estate for account %s' % instance.accountId)
