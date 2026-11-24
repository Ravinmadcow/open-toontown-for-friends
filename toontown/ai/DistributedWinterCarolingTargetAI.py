from direct.directnotify import DirectNotifyGlobal

from toontown.ai.DistributedScavengerHuntTargetAI import DistributedScavengerHuntTargetAI


class DistributedWinterCarolingTargetAI(DistributedScavengerHuntTargetAI):
    """A caroling shopkeeper. Sing any carol inside the shop to get a stocking of
    jellybeans; see WinterCarolingMgrAI."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedWinterCarolingTargetAI')
