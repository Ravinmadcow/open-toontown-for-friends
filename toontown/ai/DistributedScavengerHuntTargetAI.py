from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI


class DistributedScavengerHuntTargetAI(DistributedObjectAI):
    """A spot that toons visit for a holiday hunt. The client sends
    attemptScavengerHunt when the toon says the right phrase here; the hunt's
    manager decides the reward."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedScavengerHuntTargetAI')

    def __init__(self, air, huntMgr=None):
        DistributedObjectAI.__init__(self, air)
        self.huntMgr = huntMgr

    def attemptScavengerHunt(self):
        avId = self.air.getAvatarIdFromSender()
        if self.huntMgr is not None:
            self.huntMgr.attemptTarget(avId, self)
