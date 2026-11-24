"""
'jellybean-multiplier' in etc/Configrc.prc changes how many jellybeans toons
earn from trolley games, fishing and ToonTask rewards. 1 is normal Toontown,
2 is twice as many. Server side only.
"""
from panda3d.core import ConfigVariableDouble


def getMultiplier():
    return max(0.0, ConfigVariableDouble('jellybean-multiplier', 1.0).value)


def scale(amount):
    return int(amount * getMultiplier() + 0.5)
