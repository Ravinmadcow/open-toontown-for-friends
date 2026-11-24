"""
Winter Caroling: sing any carol from the Winter > Caroling SpeedChat menu inside
each of the six caroling shops.

- Each shop gives a stocking of jellybeans, once per toon per season.
- Caroling at all six gives a Snowman head until the caroling season ends.
- If a toon who finished loses the Snowman head, singing at any of the shops
  again gives it back (as in the original game).

Progress is saved on the server in <server-data-folder>/winter_caroling.json.
"""
import datetime
import json
import os
import time

from direct.directnotify import DirectNotifyGlobal

from toontown.toonbase import ToontownGlobals

# The six shopkeepers from Disney's Toontown, one in each playground's area.
CAROLING_ZONES = {
    2659: 'Joy Buzzers to the World (Silly Street, Toontown Central)',
    1707: "Gifts With a Porpoise (Seaweed Street, Donald's Dock)",
    5626: 'Pine Needle Crafts (Elm Street, Daisy Gardens)',
    4614: "Shave and a Haircut for a Song (Alto Avenue, Minnie's Melodyland)",
    3828: "Snowman's Land (Polar Place, The Brrrgh)",
    9720: "Talking In Your Sleep Voice Training (Pajama Place, Donald's Dreamland)",
}
BEANS_PER_SHOP = 100
SEASON_END = (1, 4)  # the Snowman head lasts until the end of 4 January


class WinterCarolingMgrAI:
    notify = DirectNotifyGlobal.directNotify.newCategory('WinterCarolingMgrAI')

    def __init__(self, air):
        self.air = air
        self.targets = []
        self.progress = None   # {season: {avId: [zones]}}

    # ---- holiday on / off -------------------------------------------------------------
    def isRunning(self):
        return bool(self.targets)

    def start(self):
        if self.targets:
            return
        from toontown.ai.DistributedWinterCarolingTargetAI import DistributedWinterCarolingTargetAI
        for zoneId in CAROLING_ZONES:
            target = DistributedWinterCarolingTargetAI(self.air, self)
            target.generateWithRequired(zoneId)
            self.targets.append(target)
        self.notify.info('Winter Caroling started in %d shops' % len(self.targets))

    def stop(self):
        for target in self.targets:
            target.requestDelete()
        self.targets = []
        self.notify.info('Winter Caroling stopped')

    # ---- seasons --------------------------------------------------------------------------
    @staticmethod
    def season(today=None):
        today = today or datetime.date.today()
        return str(today.year if today.month >= 7 else today.year - 1)

    def seasonEndMinutes(self):
        """When the Snowman head runs out: the end of 4 January after this season."""
        endYear = int(self.season()) + 1
        end = datetime.datetime(endYear, SEASON_END[0], SEASON_END[1], 23, 59)
        return int(time.mktime(end.timetuple()) // 60)

    # ---- saving ---------------------------------------------------------------------------
    def __path(self):
        return os.path.join(getattr(self.air, 'dataFolder', '') or '', 'winter_caroling.json')

    def __load(self):
        if self.progress is None:
            try:
                with open(self.__path(), 'r') as f:
                    self.progress = json.load(f)
            except Exception:
                self.progress = {}
            # Keep only this season.
            self.progress = {self.season(): self.progress.get(self.season(), {})}
        return self.progress[self.season()]

    def __save(self):
        try:
            folder = os.path.dirname(self.__path())
            if folder:
                os.makedirs(folder, exist_ok=True)
            tmp = self.__path() + '.tmp'
            with open(tmp, 'w') as f:
                json.dump(self.progress, f)
            os.replace(tmp, self.__path())
        except Exception as e:
            self.notify.warning('Could not save caroling progress: %s' % e)

    def getProgress(self, avId):
        return list(self.__load().get(str(avId), []))

    # ---- singing ------------------------------------------------------------------------------
    def attemptTarget(self, avId, target):
        av = self.air.doId2do.get(avId)
        if av is None or target.zoneId not in CAROLING_ZONES:
            return
        if getattr(av, 'zoneId', None) != target.zoneId:
            return  # must be inside the shop
        seasonProgress = self.__load()
        done = seasonProgress.setdefault(str(avId), [])
        if target.zoneId not in done:
            done.append(target.zoneId)
            self.__save()
            av.addMoney(BEANS_PER_SHOP)
            av.sendUpdate('winterCarolingTargetMet', [BEANS_PER_SHOP])
            self.notify.info('%s caroled at %s (%d of %d)' % (avId, CAROLING_ZONES[target.zoneId], len(done),
                                                             len(CAROLING_ZONES)))
            if len(done) >= len(CAROLING_ZONES):
                self.giveSnowmanHead(av)
        elif len(done) >= len(CAROLING_ZONES) and av.getCheesyEffect()[0] != ToontownGlobals.CESnowMan:
            self.giveSnowmanHead(av)

    def giveSnowmanHead(self, av):
        av.b_setCheesyEffect(ToontownGlobals.CESnowMan, 0, self.seasonEndMinutes())
