import datetime

from panda3d.core import ConfigVariableBool, ConfigVariableString
from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI
from toontown.toonbase import ToontownGlobals

# Holidays that switch on automatically by date: (holidayId, start (month, day), end (month, day))
# The winter season runs across New Year, so it is checked specially below.
AUTO_HOLIDAYS = [
    (ToontownGlobals.WINTER_DECORATIONS, (12, 1), (1, 2)),
    (ToontownGlobals.WINTER_CAROLING, (12, 14), (1, 4)),
]


class NewsManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('NewsManagerAI')
    CHECK_INTERVAL = 3600  # re-check the date every hour

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.holidayIdList = []

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.updateHolidays()
        taskMgr.doMethodLater(self.CHECK_INTERVAL, self.__checkHolidays, self.uniqueName('checkHolidays'))

    def delete(self):
        taskMgr.remove(self.uniqueName('checkHolidays'))
        DistributedObjectAI.delete(self)

    @staticmethod
    def __inRange(today, start, end):
        key = (today.month, today.day)
        if start <= end:
            return start <= key <= end
        return key >= start or key <= end  # wraps over New Year

    def getActiveHolidayIds(self):
        ids = []
        # Holidays forced on in etc/Configrc.prc, e.g.  force-holidays 4
        for part in ConfigVariableString('force-holidays', '').value.replace(',', ' ').split():
            try:
                ids.append(int(part))
            except ValueError:
                self.notify.warning('Ignoring bad force-holidays value: %s' % part)
        # Holidays switched on by the calendar
        if ConfigVariableBool('want-auto-holidays', True).value:
            today = datetime.date.today()
            for holidayId, start, end in AUTO_HOLIDAYS:
                if self.__inRange(today, start, end):
                    ids.append(holidayId)
        return sorted(set(ids))

    def updateHolidays(self):
        ids = self.getActiveHolidayIds()
        if ids == self.holidayIdList:
            return
        self.holidayIdList = ids
        manager = getattr(self.air, 'holidayManager', None)
        if manager is not None:
            manager.currentHolidays = {holidayId: True for holidayId in ids}
        self.__updateWinterCaroling(ids)
        self.notify.warning('Active holidays: %s' % (ids or 'none'))
        self.sendUpdate('setHolidayIdList', [ids])

    def __updateWinterCaroling(self, ids):
        from toontown.ai.WinterCarolingMgrAI import WinterCarolingMgrAI
        if getattr(self.air, 'winterCarolingMgr', None) is None:
            self.air.winterCarolingMgr = WinterCarolingMgrAI(self.air)
        caroling = ToontownGlobals.WINTER_CAROLING in ids or ToontownGlobals.WACKY_WINTER_CAROLING in ids
        try:
            if caroling:
                self.air.winterCarolingMgr.start()
            else:
                self.air.winterCarolingMgr.stop()
        except Exception as e:
            self.notify.warning('Could not update Winter Caroling: %s' % e)

    def __checkHolidays(self, task):
        self.updateHolidays()
        return task.again

    def getHolidayIdList(self):
        return self.holidayIdList

    def getWeeklyCalendarHolidays(self):
        return []

    def getYearlyCalendarHolidays(self):
        return []

    def getOncelyCalendarHolidays(self):
        return []

    def getRelativelyCalendarHolidays(self):
        return []

    def getMultipleStartHolidays(self):
        return []
