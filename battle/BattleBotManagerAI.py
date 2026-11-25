"""
Battle bots: AI-controlled helper toons for street battles.

When a player starts or joins a street battle, the server spawns up to
N helper toons for them (default 2). The helpers run into the battle like
any other toon, pick their own gags each round, heal hurt teammates, and
teleport out when the battle ends, when they go sad, or when their owner
leaves the battle.

Helpers copy their owner's laff, gag tracks and gag experience, so they
grow with you. They get a random look and a random name.

Config (in your .prc file, e.g. etc/Configrc.prc):
    want-battle-bots #t             turn the feature on or off
    battle-bots-per-toon 2          default number of helpers per player (0-3)
    battle-bots-infinite-gags #t    refill helpers' gags every round
    battle-bots-heal-threshold 0.5  heal a teammate below this fraction of laff

Magic word (if your copy has the spellbook):
    ~bots 3        set how many helpers you get (0 turns them off for you)
"""

import random

from direct.directnotify import DirectNotifyGlobal
from direct.showbase.DirectObject import DirectObject
from direct.distributed.ClockDelta import globalClockDelta
from direct.task import Task
from panda3d.core import ConfigVariableBool, ConfigVariableInt, ConfigVariableDouble
from panda3d.direct import DCPacker

from otp.otpbase import OTPGlobals
from toontown.toon import ToonDNA
from toontown.toon.DistributedToonAI import DistributedToonAI
from toontown.toonbase import ToontownGlobals
from toontown.toonbase.ToontownBattleGlobals import (
    HEAL_TRACK, LURE_TRACK, SOUND_TRACK, THROW_TRACK, SQUIRT_TRACK, DROP_TRACK,
    LAST_REGULAR_GAG_LEVEL, getAvPropDamage)
from toontown.battle.BattleBase import (
    getToonAttack, attackAffectsGroup,
    TOON_TRACK_COL, TOON_LVL_COL, TOON_TGT_COL)

BOT_CLASS_NAME = 'DistributedBattleBotAI'
MAX_BOTS_PER_TOON = 3
DAMAGE_TRACKS = (SOUND_TRACK, THROW_TRACK, SQUIRT_TRACK, DROP_TRACK)
BOT_GAG_TRACKS = (THROW_TRACK, SQUIRT_TRACK, HEAL_TRACK, SOUND_TRACK, DROP_TRACK)

BOT_NAMES = [
    'Pickles', 'Noodle', 'Sparky', 'Biscuit', 'Waffles', 'Doodle', 'Ziggy',
    'Bubbles', 'Pip', 'Muffin', 'Gizmo', 'Jellybean', 'Scooter', 'Sprocket',
    'Taffy', 'Wiggles', 'Fizz', 'Clunk', 'Bonkers', 'Puddles']

# Fields the AI keeps live on the bot (we call the real setter).
# Every other required field is copied from the owner as a frozen value.
LIVE_FIELDS = (
    'setName', 'setDNAString', 'setMaxHp', 'setHp', 'setExperience',
    'setTrackAccess', 'setTrackBonusLevel', 'setMaxCarry', 'setInventory',
    'setCogMerits', 'setQuests', 'setBattleId', 'setNPCFriendsDict')

# Frozen values that must not be copied from the owner.
FROZEN_OVERRIDES = {
    'getFriendsList': [],
    'getCheesyEffect': (ToontownGlobals.CENormal, 0, 0),
    'getHouseId': 0,
    'getPetId': 0,
    'getAccountName': '',
    'getGM': 0,
    'getAsGM': False,
    'getTeleportAccess': [],
}


class DistributedBattleBotAI(DistributedToonAI):
    """A server-owned toon with no client behind it.

    On the wire it is a normal DistributedToon, so every client already
    knows how to draw and animate it.
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedBattleBotAI')

    def __init__(self, air, ownerId):
        # The AI looks up a class's dclass by its Python class name.
        # Point our name at DistributedToon's dclass.
        air.dclassesByName.setdefault(BOT_CLASS_NAME, air.dclassesByName['DistributedToonAI'])
        DistributedToonAI.__init__(self, air)
        self.ownerId = ownerId
        self.gameAccess = OTPGlobals.AccessFull

    # --- Not a player: skip population counts, district announcements,
    # --- location checks and the avatarEntered/avatarExited events.
    def isPlayerControlled(self):
        return False

    def _doPlayerEnter(self):
        pass

    def _doPlayerExit(self):
        pass

    def _announceArrival(self):
        pass

    def _announceExit(self):
        pass

    def isBattleBot(self):
        return True

    def getGameAccess(self):
        return OTPGlobals.AccessFull

    # --- Build the bot from its owner before it is generated.
    def setupFromOwner(self, owner, name, dnaString):
        dclass = self.dclass

        # 1. Frozen copies of everything we don't manage ourselves.
        for field in self._requiredFields():
            setterName = field.getName()
            if setterName in LIVE_FIELDS:
                continue
            getterName = 'get' + setterName[3:]
            if getterName in FROZEN_OVERRIDES:
                value = FROZEN_OVERRIDES[getterName]
            else:
                getter = getattr(owner, getterName, None)
                if getter is None:
                    continue  # the packer will use the .dc default
                try:
                    value = getter()
                except Exception:
                    continue
            setattr(self, getterName, (lambda v=value: v))

        # 2. Live fields the battle system reads and writes.
        self.setName(name)
        self.setDNAString(dnaString)
        self.setMaxHp(owner.getMaxHp())
        self.setHp(owner.getMaxHp())
        self.setExperience(owner.getExperience())
        self.setTrackAccess(owner.getTrackAccess())
        self.setTrackBonusLevel(owner.getTrackBonusLevel())
        self.setMaxCarry(owner.getMaxCarry())
        self.setInventory(owner.getInventory())
        self.setCogMerits(list(owner.getCogMerits()))
        self.setQuests([])
        self.setBattleId(0)
        self.setNPCFriendsDict([])
        self.restockGags()

        # 3. Make sure every required field can actually be sent.
        # Anything that won't pack falls back to its .dc default.
        for field in self._requiredFields():
            if not self._fieldPacks(dclass, field):
                getterName = 'get' + field.getName()[3:]
                default = self._defaultFor(field)
                setattr(self, getterName, (lambda v=default: v))
                self.notify.debug('using .dc default for %s' % field.getName())

    def getNPCFriendsDict(self):
        # The base class returns a dict, which can't be sent over the wire.
        return [(k, v) for k, v in self.NPCFriendsDict.items()]

    def restockGags(self):
        # The stock maxOutInv fills tracks in order, so with a small gag
        # pouch Toon-Up, Trap and Lure eat it all. Bots don't use Trap or
        # Lure, so fill the tracks they do use, highest gags first.
        inv = self.inventory
        inv.zeroInv(1)
        tracks = [t for t in BOT_GAG_TRACKS if self.hasTrackAccess(t)]
        # Mix big and small gags so small pouches still get both.
        levelOrder = (5, 2, 4, 1, 3, 0)
        added = True
        while added:
            added = False
            for level in levelOrder:
                for track in tracks:
                    if inv.addItem(track, level) > 0:
                        added = True
        inv.calcTotalProps()

    def _requiredFields(self):
        fields = []
        dclass = self.dclass
        for i in range(dclass.getNumInheritedFields()):
            field = dclass.getInheritedField(i)
            if field.asMolecularField() is not None:
                continue
            if field.asAtomicField() is None or not field.isRequired():
                continue
            fields.append(field)
        return fields

    def _fieldPacks(self, dclass, field):
        packer = DCPacker()
        packer.beginPack(field)
        try:
            ok = dclass.packRequiredField(packer, self, field)
        except Exception:
            ok = False
        return packer.endPack() and ok

    @staticmethod
    def _defaultFor(field):
        packer = DCPacker()
        packer.setUnpackData(field.getDefaultValue())
        packer.beginUnpack(field)
        args = field.unpackArgs(packer)
        packer.endUnpack()
        if len(args) == 1:
            return args[0]
        return args


class BattleBotBrain:
    """Picks a gag for a bot each round."""

    def __init__(self, healThreshold):
        self.healThreshold = healThreshold

    @staticmethod
    def has(toon, track, level):
        return toon.hasTrackAccess(track) and toon.inventory.numItem(track, level) > 0

    @staticmethod
    def amount(toon, track, level):
        return getAvPropDamage(track, level, toon.experience.getExp(track))

    def pick(self, battle, bot, planned, lurePlanned):
        botId = bot.doId
        suits = [s for s in battle.activeSuits if s.getHP() > 0]
        if not suits:
            return getToonAttack(botId)

        heal = self._pickHeal(battle, bot)
        if heal is not None:
            return heal

        lured = set(s.doId for s in battle.luredSuits)
        remaining = dict((s.doId, s.getHP() - planned.get(s.doId, 0)) for s in suits)
        alive = [s for s in suits if remaining[s.doId] > 0]
        if not alive:
            # Teammates should finish everything. Back them up cheaply.
            alive = suits
        target = min(alive, key=lambda s: remaining[s.doId])
        targetHp = max(1, remaining[target.doId])
        targetLured = target.doId in lured or lurePlanned

        options = []
        for track in (THROW_TRACK, SQUIRT_TRACK, DROP_TRACK, SOUND_TRACK):
            if track == DROP_TRACK and targetLured:
                continue  # drops miss lured cogs
            if track == SOUND_TRACK and (lured or lurePlanned or len(alive) < 2):
                continue  # sound wakes lured cogs; only worth it on groups
            for level in range(LAST_REGULAR_GAG_LEVEL + 1):
                if self.has(bot, track, level):
                    options.append((track, level, self.amount(bot, track, level)))

        if not options:
            return getToonAttack(botId)

        single = [o for o in options if o[0] != SOUND_TRACK]
        killers = [o for o in single if o[2] >= targetHp]
        if killers:
            # Cheapest gag that finishes the target.
            track, level, dmg = min(killers, key=lambda o: (o[1], o[2]))
        else:
            def value(o):
                return o[2] * len(alive) * 0.8 if o[0] == SOUND_TRACK else o[2]
            track, level, dmg = max(options, key=value)

        if attackAffectsGroup(track, level):
            return getToonAttack(botId, track=track, level=level, target=-1)
        return getToonAttack(botId, track=track, level=level, target=target.doId)

    def _pickHeal(self, battle, bot):
        if not bot.hasTrackAccess(HEAL_TRACK):
            return None
        mates = []
        for avId in battle.activeToons:
            if avId == bot.doId:
                continue  # toon-up can't target yourself
            toon = battle.getToon(avId)
            if toon and toon.maxHp > 0 and toon.hp > 0:
                mates.append(toon)
        hurt = [t for t in mates if float(t.hp) / t.maxHp < self.healThreshold]
        if not hurt:
            return None
        target = min(hurt, key=lambda t: float(t.hp) / t.maxHp)
        missing = target.maxHp - target.hp
        levels = [lvl for lvl in range(LAST_REGULAR_GAG_LEVEL + 1) if self.has(bot, HEAL_TRACK, lvl)]
        if not levels:
            return None
        enough = [lvl for lvl in levels if self.amount(bot, HEAL_TRACK, lvl) >= missing]
        level = min(enough) if enough else max(levels)
        if attackAffectsGroup(HEAL_TRACK, level):
            return getToonAttack(bot.doId, track=HEAL_TRACK, level=level, target=-1)
        return getToonAttack(bot.doId, track=HEAL_TRACK, level=level, target=target.doId)


class BattleBotManagerAI(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('BattleBotManagerAI')

    def __init__(self, air):
        DirectObject.__init__(self)
        self.air = air
        self.enabled = ConfigVariableBool('want-battle-bots', True).getValue()
        self.defaultCount = max(0, min(MAX_BOTS_PER_TOON, ConfigVariableInt('battle-bots-per-toon', 2).getValue()))
        self.infiniteGags = ConfigVariableBool('battle-bots-infinite-gags', True).getValue()
        self.brain = BattleBotBrain(ConfigVariableDouble('battle-bots-heal-threshold', 0.5).getValue())
        self.countByOwner = {}   # ownerId -> helpers wanted (set by ~bots)
        self.bots = {}           # botId -> bot
        self.ownerBots = {}      # ownerId -> [botId]
        self.spawned = set()     # (battleDoId, ownerId) already given helpers
        self.notify.info('battle bots %s, %d per toon' % ('on' if self.enabled else 'off', self.defaultCount))

    # ---------------------------------------------------------------- queries
    def isBot(self, avId):
        return avId in self.bots

    def getBotCount(self, ownerId):
        return self.countByOwner.get(ownerId, self.defaultCount)

    def setBotCount(self, ownerId, count):
        self.countByOwner[ownerId] = max(0, min(MAX_BOTS_PER_TOON, count))

    # ------------------------------------------------------- battle hooks
    def handleWaitForInput(self, battle):
        """Called each time a battle starts a new round of gag picking."""
        if not self.enabled or not self._battleAllowed(battle):
            return
        for avId in list(battle.toons):
            if self.isBot(avId):
                continue
            key = (battle.doId, avId)
            if key in self.spawned or self.getBotCount(avId) <= 0:
                continue
            self.spawned.add(key)
            # Spawn on the next frame, outside the battle's state change.
            taskMgr.doMethodLater(0.1, self.__spawnForOwner, 'battleBots-spawn-%s-%s' % key,
                                  extraArgs=[battle, avId])
        if self.infiniteGags:
            for avId in battle.toons:
                bot = self.bots.get(avId)
                if bot:
                    bot.restockGags()
        self.chooseAttacks(battle, final=False)

    def chooseAttacks(self, battle, final=True):
        """Pick gags for every active bot. final=True runs just before the
        round's movie is made, once the players have chosen."""
        botIds = [t for t in battle.activeToons if self.isBot(t)]
        if not botIds:
            return
        if not [t for t in battle.toons if not self.isBot(t)]:
            return  # no players left; the bots are about to leave

        planned = {}
        lurePlanned = False
        for avId in battle.activeToons:
            if self.isBot(avId):
                continue
            attack = battle.toonAttacks.get(avId)
            toon = battle.getToon(avId)
            if not attack or not toon:
                continue
            track, level, target = attack[TOON_TRACK_COL], attack[TOON_LVL_COL], attack[TOON_TGT_COL]
            if track == LURE_TRACK:
                lurePlanned = True
            elif track in DAMAGE_TRACKS and 0 <= level <= LAST_REGULAR_GAG_LEVEL + 1:
                self.__addPlanned(battle, planned, track, level, target, toon)

        for botId in botIds:
            bot = self.bots[botId]
            attack = self.brain.pick(battle, bot, planned, lurePlanned)
            battle.toonAttacks[botId] = attack
            track, level, target = attack[TOON_TRACK_COL], attack[TOON_LVL_COL], attack[TOON_TGT_COL]
            if track in DAMAGE_TRACKS:
                self.__addPlanned(battle, planned, track, level, target, bot)

        if not final:
            battle.d_setChosenToonAttacks()

    def __addPlanned(self, battle, planned, track, level, target, toon):
        try:
            dmg = getAvPropDamage(track, level, toon.experience.getExp(track))
        except Exception:
            return
        if attackAffectsGroup(track, level):
            for s in battle.activeSuits:
                planned[s.doId] = planned.get(s.doId, 0) + dmg
        else:
            planned[target] = planned.get(target, 0) + dmg

    # ----------------------------------------------------------- spawning
    def _battleAllowed(self, battle):
        # Street battles only for now (not buildings, Cog HQ or bosses).
        return battle.__class__.__name__ == 'DistributedBattleAI' and getattr(battle, 'streetBattle', 0)

    def __spawnForOwner(self, battle, ownerId):
        if battle.doId not in self.air.doId2do or ownerId not in battle.toons:
            return Task.done
        owner = self.air.doId2do.get(ownerId)
        if owner is None:
            return Task.done
        have = len([b for b in self.ownerBots.get(ownerId, []) if b in battle.toons])
        for i in range(self.getBotCount(ownerId) - have):
            if not battle.toonCanJoin():
                break
            self.__spawnBot(owner, battle, i)
        return Task.done

    def __spawnBot(self, owner, battle, index):
        dna = ToonDNA.ToonDNA()
        dna.newToonRandom(gender=random.choice(['m', 'f']))
        taken = set(self.bots[b].getName() for b in self.ownerBots.get(owner.doId, []) if b in self.bots)
        names = [n for n in BOT_NAMES if n not in taken] or BOT_NAMES
        name = random.choice(names)

        bot = DistributedBattleBotAI(self.air, owner.doId)
        try:
            bot.setupFromOwner(owner, name, dna.makeNetString())
            bot.generateWithRequired(battle.zoneId)
        except Exception:
            self.notify.warning('could not create a battle bot for %s' % owner.doId)
            import traceback
            traceback.print_exc()
            return None

        self.bots[bot.doId] = bot
        self.ownerBots.setdefault(owner.doId, []).append(bot.doId)
        self.accept('Battle releasing toon %s' % bot.doId, self.__botReleased, [bot.doId])
        self.accept('Battle releasing toon %s' % owner.doId, self.__ownerReleased, [owner.doId])
        self.accept(self.air.getAvatarExitEvent(owner.doId), self.__ownerReleased, [owner.doId])

        # Put it on the street a little behind its owner, then join.
        x, y, z = owner.getX(), owner.getY(), owner.getZ()
        side = -1 if index % 2 == 0 else 1
        x += side * (3 + 2 * (index // 2))
        y -= 2
        h = owner.getH()
        bot.setPosHpr(x, y, z, h, 0, 0)
        bot.sendUpdate('setParent', [ToontownGlobals.SPRender])
        bot.sendUpdate('setSmPosHpr', [x, y, z, h, 0, 0, globalClockDelta.getFrameNetworkTime(bits=16)])
        bot.b_setAnimState('neutral', 1.0)
        battle.signupToon(bot.doId, x, y, z)
        self.notify.info('%s brought helper %s (%s) into battle %s' % (owner.doId, name, bot.doId, battle.doId))
        return bot

    # ----------------------------------------------------------- cleanup
    def __ownerReleased(self, ownerId):
        # The owner left the battle (finished, died, ran, or logged off).
        for key in [k for k in self.spawned if k[1] == ownerId]:
            self.spawned.discard(key)
        for botId in list(self.ownerBots.get(ownerId, [])):
            bot = self.bots.get(botId)
            if bot is None:
                continue
            battle = self.air.doId2do.get(bot.battleId)
            if battle is not None and hasattr(battle, 'removeBotToon'):
                # Next frame, so we don't change the battle mid-update.
                taskMgr.doMethodLater(0.1, self.__removeFromBattle, 'battleBots-remove-%s' % botId,
                                      extraArgs=[battle, botId])
            else:
                self.__botReleased(botId)

    def __removeFromBattle(self, battle, botId):
        if botId in self.bots and battle.doId in self.air.doId2do:
            battle.removeBotToon(botId)
        if botId in self.bots and self.bots[botId].battleId == 0:
            self.__botReleased(botId)
        return Task.done

    def __botReleased(self, botId):
        bot = self.bots.get(botId)
        if bot is None or getattr(bot, '_leaving', False):
            return
        bot._leaving = True
        self.ignore('Battle releasing toon %s' % botId)
        try:
            bot.b_setAnimState('TeleportOut', 1.0)
        except Exception:
            pass
        taskMgr.doMethodLater(3.5, self.__deleteBot, 'battleBots-delete-%s' % botId, extraArgs=[botId])

    def __deleteBot(self, botId):
        bot = self.bots.pop(botId, None)
        if bot is None:
            return Task.done
        ownerId = bot.ownerId
        if ownerId in self.ownerBots and botId in self.ownerBots[ownerId]:
            self.ownerBots[ownerId].remove(botId)
            if not self.ownerBots[ownerId]:
                del self.ownerBots[ownerId]
                self.ignore('Battle releasing toon %s' % ownerId)
                self.ignore(self.air.getAvatarExitEvent(ownerId))
        bot.requestDelete()
        return Task.done
