import math
import random

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.fishing import FishingTargetGlobals


class DistributedFishingTargetAI(DistributedObjectAI):
    """A fish shadow that wanders around the pond. Casting onto it gets a bite."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedFishingTargetAI')

    def __init__(self, air, pond):
        DistributedObjectAI.__init__(self, air)
        self.pond = pond
        self.pondDoId = pond.getDoId()
        self.maxRadius = FishingTargetGlobals.getTargetRadius(pond.getArea())
        self.stateIndex = FishingTargetGlobals.MOVING
        self.angle = 0.0
        self.radius = 0.0
        self.time = FishingTargetGlobals.StepTime
        self.timestamp = globalClockDelta.getRealNetworkTime()
        self.__pickDestination()

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        taskMgr.doMethodLater(self.time, self.__move, self.uniqueName('move'))

    def delete(self):
        taskMgr.remove(self.uniqueName('move'))
        DistributedObjectAI.delete(self)

    def __pickDestination(self):
        self.angle = random.random() * 2.0 * math.pi
        self.radius = random.random() * self.maxRadius
        self.time = FishingTargetGlobals.StepTime + random.random() * 3.0
        self.timestamp = globalClockDelta.getRealNetworkTime()

    def __move(self, task):
        self.__pickDestination()
        self.sendUpdate('setState', self.getState())
        task.delayTime = self.time
        return task.again

    def getPondDoId(self):
        return self.pondDoId

    def getState(self):
        return [self.stateIndex, self.angle, self.radius, self.time, self.timestamp]
