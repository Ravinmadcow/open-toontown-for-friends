"""
Switches Fish Bingo on and off at every pond, for the Fish Bingo holidays.
Ponds register themselves here when they're created (playgrounds and estates).
"""
from direct.directnotify import DirectNotifyGlobal


class FishBingoMgrAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('FishBingoMgrAI')

    def __init__(self, air):
        self.air = air
        self.running = False
        self.ponds = set()

    def addPond(self, pond):
        self.ponds.add(pond)
        if self.running:
            self.__startAt(pond)

    def removePond(self, pond):
        self.ponds.discard(pond)
        mgr = getattr(pond, 'bingoMgr', None)
        if mgr is not None:
            pond.bingoMgr = None
            mgr.requestDelete()

    def __startAt(self, pond):
        from toontown.fishing.DistributedPondBingoManagerAI import DistributedPondBingoManagerAI
        if getattr(pond, 'bingoMgr', None) is not None:
            return
        mgr = DistributedPondBingoManagerAI(self.air, pond)
        mgr.generateWithRequired(pond.zoneId)
        pond.bingoMgr = mgr
        for spot in getattr(pond, 'spots', []):
            if spot.avId:
                mgr.addToon(spot.avId)
        mgr.startBingo()

    def start(self):
        if self.running:
            return
        self.running = True
        for pond in list(self.ponds):
            try:
                self.__startAt(pond)
            except Exception as e:
                self.notify.warning('Could not start bingo at pond %s: %s' % (pond.getDoId(), e))
        self.notify.info('Fish Bingo started at %d ponds' % len(self.ponds))

    def stop(self):
        if not self.running:
            return
        self.running = False
        for pond in list(self.ponds):
            mgr = getattr(pond, 'bingoMgr', None)
            if mgr is not None:
                mgr.stopBingo()
        self.notify.info('Fish Bingo stopping')
