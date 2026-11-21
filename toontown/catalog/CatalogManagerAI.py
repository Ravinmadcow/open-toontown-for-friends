import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from panda3d.core import ConfigVariableInt

from toontown.catalog.CatalogGenerator import CatalogGenerator
from toontown.toonbase import ToontownGlobals

MINUTES_PER_WEEK = 7 * 24 * 60


class CatalogManagerAI(DistributedObjectAI):
    """
    Hands out the Clarabelle catalogue. Each toon gets a new week's catalogue
    when their current one is a week old (or straight away the first time).

    'catalog-week-minutes' in etc/Configrc.prc sets how long a catalogue
    week lasts, in minutes (default: a real week).
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('CatalogManagerAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.generator = CatalogGenerator()
        self.weekLength = ConfigVariableInt('catalog-week-minutes', MINUTES_PER_WEEK).value

    def startCatalog(self):
        pass

    def isItemReleased(self, item):
        return True

    def deliverCatalogFor(self, av):
        if av is None or not hasattr(av, 'getCatalogSchedule'):
            return
        now = int(time.time() / 60 + 0.5)
        currentWeek, nextTime = av.getCatalogSchedule()
        if nextTime and now < nextTime:
            # Not due yet; the toon's own timer will call us again.
            return

        newWeek = currentWeek + 1
        try:
            monthly = self.generator.generateMonthlyCatalog(av, now)
            weekly = self.generator.generateWeeklyCatalog(av, newWeek, monthly)
            back = self.generator.generateBackCatalog(av, newWeek, currentWeek, weekly)
        except Exception as e:
            self.notify.warning('Could not make a catalogue for %s: %s' % (av.getDoId(), e))
            return

        av.b_setCatalog(monthly, weekly, back)
        av.b_setCatalogNotify(ToontownGlobals.NewItems, av.mailboxNotify)
        av.b_setCatalogSchedule(newWeek, now + self.weekLength)
        self.notify.info('Delivered catalogue week %s to %s (%s items)' % (
            newWeek, av.getDoId(), len(monthly) + len(weekly) + len(back)))
