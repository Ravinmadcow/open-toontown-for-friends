from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI


class DistributedChangingStatuaryAI(DistributedStatuaryAI):
    """A statue that changes over the days, like the melting snowman."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedChangingStatuaryAI')

    def growOneDay(self):
        lastStage = self.attributes.get('growthThresholds', (1,))[-1]
        self.growthLevel = min(self.growthLevel + 1, lastStage)
