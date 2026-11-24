from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI
from direct.distributed.MsgTypes import CLIENTAGENT_DECLARE_OBJECT, CLIENTAGENT_UNDECLARE_OBJECT
from direct.distributed.PyDatagram import PyDatagram
from otp.otpbase import OTPGlobals

# friendConsidering codes the client understands (see FriendInviter.__friendConsidering)
CONSIDER_NO = 0            # not available / busy
CONSIDER_YES = 1           # invitee is looking at the request
CONSIDER_ALREADY = 2       # already friends
CONSIDER_SELF = 3          # tried to befriend yourself
CONSIDER_IGNORED = 4       # invitee is ignoring the inviter
CONSIDER_NOT_ACCEPTING = 6 # invitee has friend requests turned off
CONSIDER_TOO_MANY = 13     # invitee's friends list is full

# friendResponse / inviteeFriendResponse codes
RESPONSE_NO = 0
RESPONSE_YES = 1
RESPONSE_TOO_MANY = 3

# Friend code stored with each friend in the toon's friends list
FRIEND_CODE = 0


class FriendManagerAI(DistributedObjectGlobalAI):
    """
    Handles making friends between two toons in the same district.

    Flow:
      inviter  -> friendQuery(inviteeId)
      AI       -> invitee: inviteeFriendQuery(inviterId, name, dna, context)
      invitee  -> inviteeFriendConsidering(yesNo, context)
      AI       -> inviter: friendConsidering(yesNo, context)
      invitee  -> inviteeFriendResponse(yesNoMaybe, context)
      AI       -> saves the friendship on both toons, then
                  inviter: friendResponse(yesNoMaybe, context)
    """
    notify = DirectNotifyGlobal.directNotify.newCategory('FriendManagerAI')

    def __init__(self, air):
        DistributedObjectGlobalAI.__init__(self, air)
        self.nextContext = 1
        self.requests = {}  # context -> [inviterId, inviteeId]
        self.online = set()  # toons that have logged in and asked for their friends list

    # ---- helpers ------------------------------------------------------------
    def __getToon(self, avId):
        av = self.air.doId2do.get(avId)
        if av is not None and hasattr(av, 'getFriendsList'):
            return av
        return None

    @staticmethod
    def __isFriend(av, otherId):
        for entry in av.getFriendsList():
            if entry[0] == otherId:
                return True
        return False

    def __getRequest(self, context, senderId, role):
        request = self.requests.get(context)
        if request is None:
            return None
        # role 0 = inviter, 1 = invitee: only the right toon may answer
        if request[role] != senderId:
            self.air.writeServerEvent('suspicious', senderId, 'FriendManagerAI: wrong toon for context %s' % context)
            return None
        return request

    # ---- inviter ------------------------------------------------------------
    def friendQuery(self, inviteeId):
        inviterId = self.air.getAvatarIdFromSender()
        inviter = self.__getToon(inviterId)
        if inviter is None:
            return

        context = self.nextContext
        self.nextContext += 1

        if inviteeId == inviterId:
            self.sendUpdateToAvatarId(inviterId, 'friendConsidering', [CONSIDER_SELF, context])
            return

        invitee = self.__getToon(inviteeId)
        if invitee is None:
            self.sendUpdateToAvatarId(inviterId, 'friendConsidering', [CONSIDER_NO, context])
            return

        if self.__isFriend(inviter, inviteeId):
            self.sendUpdateToAvatarId(inviterId, 'friendConsidering', [CONSIDER_ALREADY, context])
            return

        if len(invitee.getFriendsList()) >= OTPGlobals.MaxFriends:
            self.sendUpdateToAvatarId(inviterId, 'friendConsidering', [CONSIDER_TOO_MANY, context])
            return

        self.requests[context] = [inviterId, inviteeId]
        self.sendUpdateToAvatarId(inviteeId, 'inviteeFriendQuery',
                                  [inviterId, inviter.getName(), inviter.getDNAString(), context])

    def cancelFriendQuery(self, context):
        request = self.__getRequest(context, self.air.getAvatarIdFromSender(), 0)
        if request is None:
            return
        self.sendUpdateToAvatarId(request[1], 'inviteeCancelFriendQuery', [context])

    # ---- invitee ------------------------------------------------------------
    def inviteeFriendConsidering(self, yesNo, context):
        request = self.__getRequest(context, self.air.getAvatarIdFromSender(), 1)
        if request is None:
            return
        if yesNo != CONSIDER_YES:
            del self.requests[context]
        self.sendUpdateToAvatarId(request[0], 'friendConsidering', [yesNo, context])

    def inviteeFriendResponse(self, yesNoMaybe, context):
        request = self.__getRequest(context, self.air.getAvatarIdFromSender(), 1)
        if request is None:
            return
        del self.requests[context]
        inviterId, inviteeId = request

        if yesNoMaybe == RESPONSE_YES:
            inviter = self.__getToon(inviterId)
            invitee = self.__getToon(inviteeId)
            if inviter is None or invitee is None:
                yesNoMaybe = RESPONSE_NO
            elif len(inviter.getFriendsList()) >= OTPGlobals.MaxFriends or \
                    len(invitee.getFriendsList()) >= OTPGlobals.MaxFriends:
                yesNoMaybe = RESPONSE_TOO_MANY
            else:
                self.__makeFriends(inviter, invitee)

        self.sendUpdateToAvatarId(inviterId, 'friendResponse', [yesNoMaybe, context])

    def inviteeAcknowledgeCancel(self, context):
        request = self.__getRequest(context, self.air.getAvatarIdFromSender(), 1)
        if request is not None:
            del self.requests[context]

    # ---- saving -------------------------------------------------------------
    def __makeFriends(self, av1, av2):
        for av, other in ((av1, av2), (av2, av1)):
            av.extendFriendsList(other.getDoId(), FRIEND_CODE)
            # Saves to the database and tells the toon's own client.
            av.d_setFriendsList(av.getFriendsList())
            questManager = getattr(self.air, 'questManager', None)
            if questManager is not None:
                try:
                    questManager.toonMadeFriend(av, other)
                except Exception as e:
                    self.notify.warning('Friend quest update failed: %s' % e)
        self.air.writeServerEvent('friends-made', av1.getDoId(), av2.getDoId())
        self.notify.info('%s and %s are now friends' % (av1.getDoId(), av2.getDoId()))
        # Let both toons see each other in their friends lists straight away.
        for av in (av1, av2):
            if av.getDoId() in self.online:
                self.__sendFriendsList(av.getDoId())

    # ---- secret friends (not supported yet) --------------------------------
    def requestSecret(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'requestSecretResponse', [0, ''])

    def submitSecret(self, secret):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'submitSecretResponse', [0, 0])

    # ==== friends list, online status, whispers and teleporting ================
    # The client can only send messages to toons it knows about, so we
    # 'declare' each online friend's toon to it. That is what makes whispers
    # and teleport requests to friends in other places work.

    def __declare(self, toClientAvId, objectId, declare=True):
        obj = self.air.doId2do.get(objectId)
        if obj is None or not hasattr(obj, 'dclass'):
            return
        dg = PyDatagram()
        msgType = CLIENTAGENT_DECLARE_OBJECT if declare else CLIENTAGENT_UNDECLARE_OBJECT
        dg.addServerHeader(self.GetPuppetConnectionChannel(toClientAvId), self.air.ourChannel, msgType)
        dg.addUint32(objectId)
        if declare:
            dg.addUint16(obj.dclass.getNumber())
        self.air.send(dg)

    def __isOnline(self, avId):
        return avId in self.online and avId in self.air.doId2do

    def __getInfo(self, avIds, callback):
        """Looks up name and look for each toon; calls back with a list of entries."""
        entries = {}
        pending = set()
        for avId in avIds:
            av = self.air.doId2do.get(avId)
            if av is not None and hasattr(av, 'getDNAString'):
                entries[avId] = [avId, av.getName(), av.getDNAString(), getattr(av, 'petId', 0) or 0,
                                 1 if self.__isOnline(avId) else 0]
            else:
                pending.add(avId)

        def finish():
            callback([entries[avId] for avId in avIds if avId in entries])

        if not pending:
            finish()
            return
        for avId in list(pending):
            def gotToon(dclass, fields, avId=avId):
                try:
                    entries[avId] = [avId, fields['setName'][0], fields['setDNAString'][0],
                                     (fields.get('setPetId') or [0])[0], 0]
                except Exception:
                    pass  # not a toon any more (deleted)
                pending.discard(avId)
                if not pending:
                    finish()
            self.air.dbInterface.queryObject(self.air.dbId, avId, gotToon)

    def __sendFriendsList(self, avId):
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        friendIds = [entry[0] for entry in av.getFriendsList()]
        for friendId in friendIds:
            if self.__isOnline(friendId):
                self.__declare(avId, friendId)
                self.__declare(friendId, avId)
        self.__getInfo(friendIds, lambda entries: self.sendUpdateToAvatarId(avId, 'friendsListResponse', [entries]))

    def requestFriendsList(self):
        avId = self.air.getAvatarIdFromSender()
        av = self.air.doId2do.get(avId)
        if av is None:
            return
        firstTime = avId not in self.online
        self.online.add(avId)
        self.__sendFriendsList(avId)
        if firstTime:
            self.acceptOnce(self.air.getAvatarExitEvent(avId), self.__avatarOffline, [avId])
            for entry in av.getFriendsList():
                friendId = entry[0]
                if self.__isOnline(friendId):
                    self.sendUpdateToAvatarId(friendId, 'friendOnline', [avId])

    def __avatarOffline(self, avId):
        self.online.discard(avId)
        for friendId in list(self.online):
            friend = self.air.doId2do.get(friendId)
            if friend is None:
                continue
            if any(entry[0] == avId for entry in friend.getFriendsList()):
                self.sendUpdateToAvatarId(friendId, 'friendOffline', [avId])

    def requestAvatarInfo(self, avIds):
        avId = self.air.getAvatarIdFromSender()
        avIds = list(avIds)[:50]
        self.__getInfo(avIds, lambda entries: self.sendUpdateToAvatarId(avId, 'avatarInfoResponse', [entries]))

    def requestPetInfo(self, petId):
        """A doodle's details (name, look, traits, mood) for the doodle panel
        and the pet shop, packed the way the client's PetDetail expects."""
        avId = self.air.getAvatarIdFromSender()

        def reply(fields):
            data = self.__packPetFields(fields) if fields else None
            if data is None:
                self.sendUpdateToAvatarId(avId, 'petInfoResponse', [petId, 1, b''])
            else:
                self.sendUpdateToAvatarId(avId, 'petInfoResponse', [petId, 0, data])

        pet = self.air.doId2do.get(petId)
        petMgr = getattr(self.air, 'petMgr', None)
        if pet is not None and pet.__class__.__name__ == 'DistributedPetAI' and petMgr is not None:
            reply(petMgr.getPetFields(pet))
            return

        def gotPet(dclass, fields):
            if dclass is None or dclass.getName() != 'DistributedPet':
                fields = None
            reply(fields)
        self.air.dbInterface.queryObject(self.air.dbId, petId, gotPet)

    def __packPetFields(self, fields):
        from panda3d.direct import DCPacker
        dclass = self.air.dclassesByName['DistributedPetAI']
        packer = DCPacker()
        try:
            for i in range(dclass.getNumInheritedFields()):
                field = dclass.getInheritedField(i)
                if not field.isRequired() or field.asMolecularField():
                    continue
                args = fields.get(field.getName())
                packer.beginPack(field)
                if args is not None:
                    field.packArgs(packer, list(args))
                else:
                    packer.packLiteralValue(field.getDefaultValue())
                if not packer.endPack():
                    raise ValueError('could not pack %s' % field.getName())
        except Exception as e:
            self.notify.warning('Could not pack doodle details: %s' % e)
            return None
        return packer.getBytes()

    def requestRemoveFriend(self, friendId):
        avId = self.air.getAvatarIdFromSender()
        for a, b in ((avId, friendId), (friendId, avId)):
            av = self.air.doId2do.get(a)
            if av is not None:
                newList = [entry for entry in av.getFriendsList() if entry[0] != b]
                av.setFriendsList(newList)
                av.d_setFriendsList(newList)
            else:
                self.__removeOffline(a, b)
        if self.__isOnline(friendId):
            self.sendUpdateToAvatarId(friendId, 'friendOffline', [avId])
            self.__sendFriendsList(friendId)
        self.__sendFriendsList(avId)

    def __removeOffline(self, avId, friendId):
        """The other toon is offline: update their saved friends list in the database."""
        def gotToon(dclass, fields):
            try:
                friends = [entry for entry in fields['setFriendsList'][0] if entry[0] != friendId]
            except Exception:
                return
            self.air.dbInterface.updateObject(self.air.dbId, avId, dclass, {'setFriendsList': (friends,)})
        self.air.dbInterface.queryObject(self.air.dbId, avId, gotToon)
