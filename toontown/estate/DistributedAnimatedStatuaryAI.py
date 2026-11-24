from direct.directnotify import DirectNotifyGlobal

from toontown.estate.DistributedStatuaryAI import DistributedStatuaryAI


class DistributedAnimatedStatuaryAI(DistributedStatuaryAI):
    """A moving statue, like the Flappy Cog. The client plays the animation."""
    notify = DirectNotifyGlobal.directNotify.newCategory('DistributedAnimatedStatuaryAI')
