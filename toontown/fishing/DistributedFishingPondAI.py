from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.fishing import FishingTargetGlobals


class DistributedFishingPondAI(DistributedObjectAI):
    """A pond: owns the fish shadows swimming in it and the spots around it."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingPondAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.area = None
        self.targets = []
        self.spots = []

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        from toontown.fishing.DistributedFishingTargetAI import DistributedFishingTargetAI
        for i in range(FishingTargetGlobals.getNumTargets(self.area)):
            target = DistributedFishingTargetAI(self.air, self)
            target.generateWithRequired(self.zoneId)
            self.targets.append(target)

    def cleanup(self):
        """Removes the pond with its spots and fish shadows (used by estates)."""
        for obj in self.spots + self.targets:
            obj.requestDelete()
        self.spots = []
        self.targets = []
        self.requestDelete()

    def setArea(self, area):
        self.area = area

    def getArea(self):
        return self.area

    def addSpot(self, spot):
        self.spots.append(spot)

    def hitTarget(self, targetId):
        avId = self.air.getAvatarIdFromSender()
        if not any(target.getDoId() == targetId for target in self.targets):
            return
        for spot in self.spots:
            if spot.avId == avId:
                spot.rewardIfValid()
                return
