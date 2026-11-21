from direct.directnotify import DirectNotifyGlobal

from toontown.building.DistributedDoorAI import DistributedDoorAI


class DistributedHouseDoorAI(DistributedDoorAI):
    """
    A house's front door. The 'block' sent to the client is the house's doId,
    which is how the client finds the house model the door belongs to.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedHouseDoorAI')

    def __init__(self, air, houseId, doorType, doorIndex=0, lockValue=0, swing=3):
        DistributedDoorAI.__init__(self, air, houseId, doorType, doorIndex, lockValue, swing)
