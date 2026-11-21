from direct.directnotify import DirectNotifyGlobal
from direct.distributed.DistributedObjectGlobalAI import DistributedObjectGlobalAI
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

    # ---- secret friends (not supported yet) --------------------------------
    def requestSecret(self):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'requestSecretResponse', [0, ''])

    def submitSecret(self, secret):
        avId = self.air.getAvatarIdFromSender()
        self.sendUpdateToAvatarId(avId, 'submitSecretResponse', [0, 0])
