from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectAI import DistributedObjectAI

LEADERBOARD_SIZE = 10


class DistributedTrophyMgrAI(DistributedObjectAI):
    """
    Building trophies. A toon's trophy score is the total number of floors in
    the Toon buildings they've won back that are still standing (Cogs taking a
    building back takes the floors away again). The score earns stars above
    the toon's head, and the top 10 show on the leaderboard in every Toon HQ.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedTrophyMgrAI')

    def __init__(self, air):
        DistributedObjectAI.__init__(self, air)
        self.scores = {}   # avId -> floors
        self.names = {}    # avId -> name
        self.leaderInfo = ([], [], [])

    def getScore(self, avId):
        return self.scores.get(avId, 0)

    def requestTrophyScore(self):
        avId = self.air.getAvatarIdFromSender()
        self.__sendScore(avId)

    def __sendScore(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None and hasattr(av, 'd_setTrophyScore'):
            av.d_setTrophyScore(self.getScore(avId))

    def getLeaderInfo(self):
        return self.leaderInfo

    def addTrophy(self, avId, name, numFloors):
        self.scores[avId] = self.scores.get(avId, 0) + numFloors
        self.names[avId] = name
        self.__changed(avId)

    def removeTrophy(self, avId, numFloors):
        if avId not in self.scores:
            return
        self.scores[avId] -= numFloors
        if self.scores[avId] <= 0:
            del self.scores[avId]
            self.names.pop(avId, None)
        self.__changed(avId)

    def __changed(self, avId):
        self.__sendScore(avId)
        ranked = sorted(self.scores.items(), key=lambda item: -item[1])[:LEADERBOARD_SIZE]
        leaderInfo = ([avId for avId, score in ranked],
                      [self.names.get(avId, '') for avId, score in ranked],
                      [score for avId, score in ranked])
        if leaderInfo != self.leaderInfo:
            self.leaderInfo = leaderInfo
            messenger.send('leaderboardChanged')
            messenger.send('leaderboardFlush')
