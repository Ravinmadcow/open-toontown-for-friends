"""
One toon's garden on an estate: the flower boxes, the empty planting spots
and the flowers growing in them. Gardens are saved on the server under
<server-data-folder>/gardens/<toonId>.json, and plants keep growing while
nobody is around ('garden-day-minutes' in etc/Configrc.prc sets how long a
garden day is; the default is a real day).
"""
import json
import os
import time

from direct.directnotify import DirectNotifyGlobal
from panda3d.core import ConfigVariableInt

from toontown.estate import GardenGlobals

notify = DirectNotifyGlobal.directNotify.newCategory('GardenAI')

MAX_CATCH_UP_DAYS = 14


def _dayLength():
    return max(1, ConfigVariableInt('garden-day-minutes', 24 * 60).value)


def _today():
    return int(time.time() / 60 / _dayLength())


def _folder(air):
    return os.path.join(getattr(air, 'dataFolder', '') or '', 'gardens')


def gardenExists(air, ownerId):
    return bool(ownerId) and os.path.exists(os.path.join(_folder(air), '%d.json' % ownerId))


class GardenAI:
    def __init__(self, air, estate, slot, ownerId):
        self.air = air
        self.estate = estate
        self.slot = slot
        self.ownerId = ownerId
        self.zoneId = estate.zoneId
        self.boxes = []
        self.objects = {}   # plot index -> plot or plant object
        self.lastDay = _today()

    # ---- loading / saving -----------------------------------------------------
    def __path(self):
        return os.path.join(_folder(self.air), '%d.json' % self.ownerId)

    def __loadData(self):
        try:
            with open(self.__path(), 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def save(self):
        plants = []
        for plot, obj in self.objects.items():
            if hasattr(obj, 'species'):
                plants.append({'plot': plot, 'species': obj.species, 'variety': obj.variety,
                               'water': obj.waterLevel, 'growth': obj.growthLevel})
        try:
            os.makedirs(_folder(self.air), exist_ok=True)
            tmp = self.__path() + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({'plants': plants, 'lastDay': self.lastDay}, f)
            os.replace(tmp, self.__path())
        except Exception as e:
            notify.warning('Could not save garden for %s: %s' % (self.ownerId, e))

    # ---- building ---------------------------------------------------------------
    def create(self):
        from toontown.estate.DistributedGardenBoxAI import DistributedGardenBoxAI

        data = self.__loadData()
        saved = {p['plot']: p for p in data.get('plants', [])}
        self.lastDay = data.get('lastDay', _today())
        missedDays = min(max(0, _today() - self.lastDay), MAX_CATCH_UP_DAYS)
        self.lastDay = _today()

        for x, y, h, boxType in GardenGlobals.estateBoxes[self.slot]:
            box = DistributedGardenBoxAI(self.air, self, x, y, h, boxType)
            box.generateWithRequired(self.zoneId)
            self.boxes.append(box)

        for plot, hardPoint in enumerate(GardenGlobals.estatePlots[self.slot]):
            x, y, h, plotType = hardPoint[:4]
            if plotType not in (GardenGlobals.FLOWER_TYPE, GardenGlobals.GAG_TREE_TYPE):
                continue  # statues come in a later round
            plant = saved.get(plot)
            attributes = GardenGlobals.PlantAttributes.get(plant['species']) if plant else None
            if attributes and attributes['plantType'] == plotType:
                obj = self.__makePlant(plot, x, y, h, plant['species'], plant.get('variety', 0),
                                       plant.get('water', 0), plant.get('growth', 0))
                for i in range(missedDays):
                    obj.growOneDay()
                if hasattr(obj, 'lastWilted'):
                    obj.lastWilted = obj.isWilted()
                obj.generateWithRequired(self.zoneId)
                self.objects[plot] = obj
            else:
                self.__makePlot(plot)

        self.save()
        self.updateTrackBonus()
        taskMgr.doMethodLater(60, self.__checkDay, 'garden-day-%d' % id(self))

    def __makePlant(self, plot, x, y, h, species, variety, water=0, growth=0):
        if GardenGlobals.PlantAttributes[species]['plantType'] == GardenGlobals.GAG_TREE_TYPE:
            from toontown.estate.DistributedGagTreeAI import DistributedGagTreeAI
            return DistributedGagTreeAI(self.air, self, plot, x, y, h, species, water, growth)
        from toontown.estate.DistributedFlowerAI import DistributedFlowerAI
        return DistributedFlowerAI(self.air, self, plot, x, y, h, species, variety, water, growth)

    def __makePlot(self, plot):
        from toontown.estate.DistributedGardenPlotAI import DistributedGardenPlotAI
        x, y, h = GardenGlobals.estatePlots[self.slot][plot][:3]
        obj = DistributedGardenPlotAI(self.air, self, plot, x, y, h)
        obj.generateWithRequired(self.zoneId)
        self.objects[plot] = obj
        return obj

    def __checkDay(self, task):
        today = _today()
        if today > self.lastDay:
            days = min(today - self.lastDay, MAX_CATCH_UP_DAYS)
            self.lastDay = today
            for obj in self.objects.values():
                if hasattr(obj, 'growOneDay'):
                    for i in range(days):
                        obj.growOneDay()
                    obj.b_setWaterLevel(obj.waterLevel)
                    obj.b_setGrowthLevel(obj.growthLevel)
                    if hasattr(obj, 'lastWilted'):
                        obj.lastWilted = obj.isWilted()
            self.save()
            self.updateTrackBonus()
        return task.again

    def cleanup(self):
        taskMgr.remove('garden-day-%d' % id(self))
        self.save()
        for obj in list(self.objects.values()) + self.boxes:
            obj.requestDelete()
        self.objects = {}
        self.boxes = []

    # ---- planting and picking -------------------------------------------------
    def plantFlower(self, plotObj, species, variety, avId):
        from toontown.estate.DistributedFlowerAI import DistributedFlowerAI
        plot = plotObj.plot
        x, y, _ = plotObj.position
        h = plotObj.heading
        plotObj.requestDelete()
        flower = DistributedFlowerAI(self.air, self, plot, x, y, h, species, variety)
        flower.generateWithRequired(self.zoneId)
        self.objects[plot] = flower
        flower.movieAvId = avId
        flower.d_setMovie(GardenGlobals.MOVIE_FINISHPLANTING, avId)
        self.save()

    def plantGagTree(self, plotObj, typeIndex, avId):
        from toontown.estate.DistributedGagTreeAI import DistributedGagTreeAI
        plot = plotObj.plot
        x, y, _ = plotObj.position
        h = plotObj.heading
        plotObj.requestDelete()
        tree = DistributedGagTreeAI(self.air, self, plot, x, y, h, typeIndex)
        tree.generateWithRequired(self.zoneId)
        self.objects[plot] = tree
        tree.movieAvId = avId
        tree.d_setMovie(GardenGlobals.MOVIE_FINISHPLANTING, avId)
        self.save()

    def removePlant(self, plant, avId):
        plot = plant.plot
        plant.requestDelete()
        newPlot = self.__makePlot(plot)
        newPlot.movieAvId = avId
        newPlot.d_setMovie(GardenGlobals.MOVIE_FINISHREMOVING, avId)
        self.save()
        self.updateTrackBonus()

    # ---- gag trees ------------------------------------------------------------
    def getTree(self, track, level):
        for obj in self.objects.values():
            if getattr(obj, 'track', None) == track and getattr(obj, 'level', None) == level:
                return obj
        return None

    def hasRequiredTrees(self, track, level, fullGrown=False):
        """A tree needs a tree for every lower gag in its track (full grown, to harvest)."""
        for lower in range(level):
            tree = self.getTree(track, lower)
            if tree is None or (fullGrown and not tree.isGTEFullGrown()):
                return False
        return True

    def updateTrackBonus(self):
        """Organic gags: each track is boosted up to its highest unbroken run of
        full-grown, watered trees, starting from the first gag."""
        av = self.air.doId2do.get(self.ownerId)
        if av is None or not hasattr(av, 'b_setTrackBonusLevel'):
            return
        from toontown.toonbase import ToontownBattleGlobals
        bonus = []
        for track in range(ToontownBattleGlobals.NUM_GAG_TRACKS):
            best = -1
            for level in range(ToontownBattleGlobals.UBER_GAG_LEVEL_INDEX + 1):
                tree = self.getTree(track, level)
                if tree is None or not tree.isGTEFullGrown() or tree.isWilted():
                    break
                best = level
            bonus.append(best)
        if list(av.getTrackBonusLevel()) != bonus:
            av.b_setTrackBonusLevel(bonus)
