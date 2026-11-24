"""
Fish Bingo at one pond.

Everyone fishing at the pond plays the same card layout. Catch a fish (or a
boot, which counts as anything) and mark a matching square. The first toon to
complete the card's pattern and press BINGO wins the jackpot for everybody
sitting at the pond.

Game cycle (times from BingoGlobals, matching the original game):
    Intro (5 s) -> WaitCountdown (15 s) -> Playing (90-180 s) -> Reward or GameOver (5 s) -> WaitCountdown ...
From :55 past each hour there's a 5-minute Intermission; the first game of each
hour is Blockout, whose jackpot grows by 100 every time nobody wins it.
"""
import random
import time

from direct.directnotify import DirectNotifyGlobal
from direct.distributed.ClockDelta import globalClockDelta
from direct.distributed.DistributedObjectAI import DistributedObjectAI

from toontown.fishing import BingoGlobals, FishGlobals
from toontown.fishing.BlockoutBingo import BlockoutBingo
from toontown.fishing.DiagonalBingo import DiagonalBingo
from toontown.fishing.FourCornerBingo import FourCornerBingo
from toontown.fishing.NormalBingo import NormalBingo
from toontown.fishing.ThreewayBingo import ThreewayBingo

CARD_CLASSES = {BingoGlobals.NORMAL_CARD: NormalBingo,
                BingoGlobals.FOURCORNER_CARD: FourCornerBingo,
                BingoGlobals.DIAGONAL_CARD: DiagonalBingo,
                BingoGlobals.THREEWAY_CARD: ThreewayBingo,
                BingoGlobals.BLOCKOUT_CARD: BlockoutBingo}
REGULAR_CARDS = [BingoGlobals.NORMAL_CARD, BingoGlobals.FOURCORNER_CARD,
                 BingoGlobals.DIAGONAL_CARD, BingoGlobals.THREEWAY_CARD]
FISH_CODES = (FishGlobals.FishItem, FishGlobals.FishItemNewEntry, FishGlobals.FishItemNewRecord)


class DistributedPondBingoManagerAI(DistributedObjectAI):
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedPondBingoManagerAI')

    def __init__(self, air, pond):
        DistributedObjectAI.__init__(self, air)
        self.pond = pond
        self.state = 'Off'
        self.stateTime = 0
        self.cardId = 0
        self.typeId = BingoGlobals.NORMAL_CARD
        self.tileSeed = 0
        self.jackpot = 0
        self.superJackpot = BingoGlobals.MIN_SUPER_JACKPOT
        self.nextIsBlockout = True
        self.closing = False
        self.cards = {}       # avId -> that toon's card for the current game
        self.lastCatch = {}   # avId -> (genus, species) waiting to be marked
        self.players = set()  # toons sitting at this pond's fishing spots

    def getPondDoId(self):
        return self.pond.getDoId()

    def __taskName(self):
        return self.uniqueName('bingo')

    def __later(self, delay, func):
        taskMgr.remove(self.__taskName())
        taskMgr.doMethodLater(delay, lambda task: func(), self.__taskName())

    # ---- sending ------------------------------------------------------------------
    def __sendState(self, avId):
        self.sendUpdateToAvatarId(avId, 'setState', [self.state, self.stateTime])

    def __sendCard(self, avId):
        card = self.cards.get(avId)
        gameState = card.getGameState() if card else 1 << (BingoGlobals.CARD_SIZE // 2)
        self.sendUpdateToAvatarId(avId, 'setCardState', [self.cardId, self.typeId, self.tileSeed, gameState])
        self.sendUpdateToAvatarId(avId, 'setJackpot', [self.jackpot])

    def __setState(self, state):
        self.state = state
        self.stateTime = globalClockDelta.getRealNetworkTime()
        for avId in list(self.players):
            self.__sendState(avId)

    def __newCard(self):
        card = CARD_CLASSES[self.typeId]()
        card.generateCard(self.tileSeed, self.pond.getArea())
        return card

    # ---- players ------------------------------------------------------------------
    def addToon(self, avId):
        if avId in self.players:
            return
        self.players.add(avId)
        if self.state == 'Off':
            return
        if self.state in ('WaitCountdown', 'Playing'):
            self.cards[avId] = self.__newCard()
            self.__sendCard(avId)
        self.__sendState(avId)

    def removeToon(self, avId):
        self.players.discard(avId)
        self.cards.pop(avId, None)
        self.lastCatch.pop(avId, None)

    def recordCatch(self, avId, code, item1, item2):
        if code in FISH_CODES:
            self.lastCatch[avId] = (item1, item2)
        elif code == FishGlobals.BootItem:
            self.lastCatch[avId] = FishGlobals.BingoBoot

    # ---- game cycle ---------------------------------------------------------------
    def startBingo(self):
        self.closing = False
        # Blockout opens each hour; a session starting mid-hour begins with a regular card.
        self.nextIsBlockout = time.localtime().tm_min < 5
        self.__setState('Intro')
        self.__later(BingoGlobals.INTRO_SESSION, self.__startWait)

    def stopBingo(self):
        """The bingo holiday ended. Finish politely, then remove this manager."""
        self.closing = True
        if self.state in ('Intro', 'WaitCountdown', 'Off'):
            self.__finish()
        elif self.state in ('GameOver', 'Reward', 'Intermission'):
            self.__close()
        # While Playing, the game runs to its end and then closes.

    def __startWait(self):
        if self.closing:
            self.__close()
            return
        if time.localtime().tm_min >= BingoGlobals.HOUR_BREAK_MIN and not self.nextIsBlockout:
            self.nextIsBlockout = True
            self.__setState('Intermission')
            self.__later(BingoGlobals.HOUR_BREAK_SESSION, self.__startWait)
            return
        self.cardId = (self.cardId + 1) % 65536
        if self.nextIsBlockout:
            self.typeId = BingoGlobals.BLOCKOUT_CARD
            self.jackpot = self.superJackpot
            self.nextIsBlockout = False
        else:
            self.typeId = random.choice(REGULAR_CARDS)
            self.jackpot = BingoGlobals.getJackpot(self.typeId)
        self.tileSeed = random.randint(0, 65535)
        self.cards = {}
        self.lastCatch = {}
        for avId in list(self.players):
            self.cards[avId] = self.__newCard()
            self.__sendCard(avId)
        self.__setState('WaitCountdown')
        self.__later(BingoGlobals.TIMEOUT_SESSION, self.__startGame)

    def __startGame(self):
        for avId in list(self.players):
            if avId not in self.cards:
                self.cards[avId] = self.__newCard()
                self.__sendCard(avId)
        self.__setState('Playing')
        self.__later(BingoGlobals.getGameTime(self.typeId), self.__gameOver)

    def __gameOver(self):
        if self.typeId == BingoGlobals.BLOCKOUT_CARD:
            self.superJackpot = min(self.superJackpot + BingoGlobals.ROLLOVER_AMOUNT, BingoGlobals.MAX_SUPER_JACKPOT)
        self.__setState('GameOver')
        self.__later(BingoGlobals.REWARD_TIMEOUT, self.__startWait)

    def __close(self):
        self.__setState('CloseEvent')
        self.__later(BingoGlobals.CLOSE_EVENT_TIMEOUT, self.__finish)

    def __finish(self):
        taskMgr.remove(self.__taskName())
        self.__setState('Off')
        self.players = set()
        if getattr(self.pond, 'bingoMgr', None) is self:
            self.pond.bingoMgr = None
        self.requestDelete()

    def delete(self):
        taskMgr.remove(self.__taskName())
        DistributedObjectAI.delete(self)

    # ---- client messages ------------------------------------------------------------
    def cardUpdate(self, cardId, cellId, genus, species):
        avId = self.air.getAvatarIdFromSender()
        card = self.cards.get(avId)
        if self.state != 'Playing' or cardId != self.cardId or card is None:
            return
        if not 0 <= cellId < BingoGlobals.CARD_SIZE:
            return
        catch = (genus, species)
        if self.lastCatch.get(avId) != catch:
            self.notify.warning('%s marked a square without catching %s' % (avId, catch))
            return
        if card.cellUpdateCheck(cellId, genus, species) != BingoGlobals.NO_UPDATE:
            del self.lastCatch[avId]
            self.sendUpdateToAvatarId(avId, 'updateGameState', [card.getGameState(), cellId])

    def handleBingoCall(self, cardId):
        avId = self.air.getAvatarIdFromSender()
        card = self.cards.get(avId)
        if self.state != 'Playing' or cardId != self.cardId or card is None:
            return
        if not card.checkForBingo():
            self.notify.warning('%s called bingo without a winning card' % avId)
            return
        self.notify.info('%s won a %s bingo for %s jellybeans' % (avId, BingoGlobals.getGameName(self.typeId), self.jackpot))
        for playerId in list(self.players):
            av = self.air.doId2do.get(playerId)
            if av is not None:
                self.giveBeans(av, self.jackpot)
        if self.typeId == BingoGlobals.BLOCKOUT_CARD:
            self.superJackpot = BingoGlobals.MIN_SUPER_JACKPOT
        self.__setState('Reward')
        self.__later(BingoGlobals.REWARD_TIMEOUT, self.__startWait)

    @staticmethod
    def giveBeans(av, amount):
        """Pocket first; anything that doesn't fit goes to the bank."""
        room = max(0, av.getMaxMoney() - av.getMoney())
        pocket = min(room, amount)
        if pocket:
            av.b_setMoney(av.getMoney() + pocket)
        rest = amount - pocket
        if rest:
            av.b_setBankMoney(min(av.getBankMoney() + rest, av.getMaxBankMoney()))
