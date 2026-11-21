from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

HIT_TIME = 30      # seconds to land the next hit before your streak resets
MAX_LEVEL = 10     # most jellybeans a single hit can be worth


class DistributedTargetAI(DistributedObjectAI):
    """
    The target that floats over the estate pond while cannons are rented.
    Hitting it with a cannon shot earns jellybeans; each hit in a row is worth
    one more (up to 10) as long as you land the next one before the timer runs out.
    It also keeps the estate's pinball high score.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTargetAI')

    def __init__(self, air, x, y, z):
        DistributedObjectAI.__init__(self, air)
        self.position = (x, y, z)
        self.level = 1
        self.pinballHiScore = 0
        self.pinballHiScorer = ''

    def announceGenerate(self):
        DistributedObjectAI.announceGenerate(self)
        self.d_setState()

    def delete(self):
        taskMgr.remove(self.uniqueName('streak'))
        DistributedObjectAI.delete(self)

    def getPosition(self):
        return self.position

    def getPinballHiScore(self):
        return self.pinballHiScore

    def getPinballHiScorer(self):
        return self.pinballHiScorer

    def d_setState(self):
        self.sendUpdate('setState', [1, self.level, HIT_TIME])

    def __streakOver(self, task):
        self.level = 1
        self.d_setState()
        return task.done

    # ---- client messages ------------------------------------------------------
    def setResult(self, avId):
        senderId = self.air.getAvatarIdFromSender()
        if not avId or avId != senderId:
            return  # a miss, or someone reporting for someone else
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        reward = self.level
        av.addMoney(reward)
        self.sendUpdate('setReward', [reward])
        self.level = min(self.level + 1, MAX_LEVEL)
        self.d_setState()
        taskMgr.remove(self.uniqueName('streak'))
        taskMgr.doMethodLater(HIT_TIME, self.__streakOver, self.uniqueName('streak'))

    def setBonus(self, bonus):
        pass

    def setCurPinballScore(self, avId, score, multiplier):
        senderId = self.air.getAvatarIdFromSender()
        if avId != senderId:
            return
        total = score * multiplier
        if total > self.pinballHiScore:
            av = self.air.doId2do.get(avId)
            self.pinballHiScore = total
            self.pinballHiScorer = av.getName() if av is not None else ''
            self.sendUpdate('setPinballHiScore', [self.pinballHiScore])
            self.sendUpdate('setPinballHiScorer', [self.pinballHiScorer])
