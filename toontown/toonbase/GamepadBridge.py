"""
GamepadBridge: makes a game controller drive Toontown's keyboard controls.

The game's minigames, golf, racing and walking all listen for keyboard
events ('arrow_up', 'control', 'delete' and so on). This bridge reads the
first connected gamepad every frame and sends those same events, so every
game that works with the keyboard works with a pad, with no changes to the
games themselves.

It also exposes analog values (getSteer / getThrottle) so racing can steer
smoothly instead of only full-left / full-right.

Config (.prc):
    want-gamepad                 #t     turn the bridge on
    gamepad-deadzone             0.2    stick values below this count as centred
    gamepad-stick-threshold      0.5    how far the stick must move to "press" an arrow
    gamepad-invert-y             #f     flip the left stick's up/down
    gamepad-analog-racing        #t     smooth stick/trigger driving in karts
    gamepad-map-<button>  <key>         remap a button, e.g. gamepad-map-face_b insert
"""

from panda3d.core import (ConfigVariableBool, ConfigVariableDouble,
                          ConfigVariableString, InputDevice, GamepadButton)
from direct.showbase.DirectObject import DirectObject
from direct.directnotify import DirectNotifyGlobal


# Default button -> keyboard key. Button names are Panda3D GamepadButton names.
DEFAULT_BUTTON_MAP = {
    'face_a': 'control',      # jump / golf swing / throw / kart gag
    'face_b': 'delete',       # throw pie / flip card in Match Minnie
    'face_x': 'insert',       # alternate pie throw
    'face_y': 'tab',          # golf & racing view toggle
    'lshoulder': 'page_up',   # camera view up
    'rshoulder': 'page_down', # camera view down
    'start': 'escape',        # Options page
    'back': 'f8',             # Shticker Book
}

DIRECTION_KEYS = ('arrow_up', 'arrow_down', 'arrow_left', 'arrow_right')


class GamepadBridge(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('GamepadBridge')
    TASK_NAME = 'gamepadBridgePoll'

    def __init__(self):
        DirectObject.__init__(self)
        self.deadzone = ConfigVariableDouble('gamepad-deadzone', 0.2).value
        self.threshold = ConfigVariableDouble('gamepad-stick-threshold', 0.5).value
        self.invertY = ConfigVariableBool('gamepad-invert-y', False).value
        self.analogRacing = ConfigVariableBool('gamepad-analog-racing', True).value

        self.buttonMap = {}
        for buttonName, key in DEFAULT_BUTTON_MAP.items():
            key = ConfigVariableString('gamepad-map-' + buttonName, key).value
            if key and key != 'none':
                self.buttonMap[buttonName] = key

        self.device = None
        self._buttonHandles = {}
        self._held = set()     # keyboard keys we are currently "holding"
        self._steer = 0.0
        self._throttle = 0.0

        self.accept('connect-device', self.__onConnect)
        self.accept('disconnect-device', self.__onDisconnect)
        self.__pickDevice()
        taskMgr.add(self.__poll, self.TASK_NAME, sort=-45)

    # ------------------------------------------------------------ public

    def isActive(self):
        return self.device is not None

    def getSteer(self):
        """Left stick X, -1 (left) to 1 (right), 0 inside the deadzone."""
        return self._steer

    def getThrottle(self):
        """-1 (reverse) to 1 (full gas). Triggers if the pad has them, else stick Y."""
        return self._throttle

    def destroy(self):
        taskMgr.remove(self.TASK_NAME)
        self.__releaseAll()
        self.ignoreAll()
        self.device = None

    # ------------------------------------------------------- device setup

    def __pickDevice(self):
        devices = base.devices.getDevices(InputDevice.DeviceClass.gamepad)
        if not devices:
            devices = base.devices.getDevices(InputDevice.DeviceClass.flight_stick)
        if devices:
            self.__setDevice(devices[0])

    def __setDevice(self, device):
        self.device = device
        self._buttonHandles = {}
        for buttonName in self.buttonMap:
            getter = getattr(GamepadButton, buttonName, None)
            if getter is not None:
                self._buttonHandles[buttonName] = getter()
        for name in ('dpad_up', 'dpad_down', 'dpad_left', 'dpad_right'):
            self._buttonHandles[name] = getattr(GamepadButton, name)()
        self.notify.info('Using controller: %s' % device.name)

    def __onConnect(self, device):
        if self.device is None and device.device_class in (
                InputDevice.DeviceClass.gamepad, InputDevice.DeviceClass.flight_stick):
            self.__setDevice(device)

    def __onDisconnect(self, device):
        if device == self.device:
            self.notify.info('Controller disconnected')
            self.__releaseAll()
            self.device = None
            self.__pickDevice()

    # ------------------------------------------------------------ polling

    def __axis(self, axis):
        state = self.device.findAxis(axis)
        if not state.known:
            return None
        return state.value

    def __button(self, buttonName):
        handle = self._buttonHandles.get(buttonName)
        if handle is None:
            return False
        state = self.device.findButton(handle)
        return state.known and state.pressed

    def __applyDeadzone(self, value):
        if value is None or abs(value) < self.deadzone:
            return 0.0
        # Rescale so movement starts at 0 just outside the deadzone.
        sign = 1.0 if value > 0 else -1.0
        return sign * min(1.0, (abs(value) - self.deadzone) / (1.0 - self.deadzone))

    def __poll(self, task):
        if self.device is None:
            return task.cont
        if not self.device.connected:
            self.__onDisconnect(self.device)
            return task.cont
        self.device.poll()

        rawX = self.__axis(InputDevice.Axis.left_x) or 0.0
        rawY = self.__axis(InputDevice.Axis.left_y) or 0.0
        if self.invertY:
            rawY = -rawY

        # Digital arrows: stick past threshold, or the d-pad.
        wanted = set()
        if rawY > self.threshold or self.__button('dpad_up'):
            wanted.add('arrow_up')
        if rawY < -self.threshold or self.__button('dpad_down'):
            wanted.add('arrow_down')
        if rawX < -self.threshold or self.__button('dpad_left'):
            wanted.add('arrow_left')
        if rawX > self.threshold or self.__button('dpad_right'):
            wanted.add('arrow_right')

        for buttonName, key in self.buttonMap.items():
            if self.__button(buttonName):
                wanted.add(key)

        for key in list(self._held - wanted):
            self.__release(key)
        for key in wanted - self._held:
            self.__press(key)

        # Analog values for racing.
        self._steer = self.__applyDeadzone(rawX)
        dpadSteer = (1.0 if self.__button('dpad_right') else 0.0) - (1.0 if self.__button('dpad_left') else 0.0)
        if dpadSteer:
            self._steer = dpadSteer

        gas = self.__axis(InputDevice.Axis.right_trigger)
        brake = self.__axis(InputDevice.Axis.left_trigger)
        triggerThrottle = 0.0
        if gas is not None or brake is not None:
            triggerThrottle = self.__applyDeadzone(gas or 0.0) - self.__applyDeadzone(brake or 0.0)
        if triggerThrottle:
            self._throttle = triggerThrottle
        else:
            self._throttle = self.__applyDeadzone(rawY)
            if self.__button('dpad_up'):
                self._throttle = 1.0
            elif self.__button('dpad_down'):
                self._throttle = -1.0
        return task.cont

    # ------------------------------------------------------ event sending

    def __press(self, key):
        self._held.add(key)
        t = globalClock.getFrameTime()
        messenger.send(key)
        messenger.send('time-' + key, [t])

    def __release(self, key):
        self._held.discard(key)
        t = globalClock.getFrameTime()
        messenger.send(key + '-up')
        messenger.send('time-' + key + '-up', [t])

    def __releaseAll(self):
        for key in list(self._held):
            self.__release(key)
        self._steer = 0.0
        self._throttle = 0.0
