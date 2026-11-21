"""
Controller (gamepad) support for Open Toontown.

Feeds the gamepad into the same input system the keyboard uses, so walking,
jumping, cranes, camera views and Esc menus all work without changing the
rest of the game. Client-side only.

Layout (Xbox names):
    Left stick ........ walk / turn
    A ................. jump (Ctrl)
    B ................. Esc (exit/back)
    X ................. Delete
    Y ................. Esc
    LB / RB ........... previous / next camera view (Shift+Tab / Tab)
    D-pad up / down ... look up / look down (Page Up / Page Down)
    Right stick ....... move the mouse pointer
    RT / LT ........... left click (Windows only)
    Back / View ....... F9

Turn it off by adding  want-gamepad #f  to etc/Configrc.prc.
"""

import sys

from panda3d.core import ConfigVariableBool, InputDevice
from direct.showbase.DirectObject import DirectObject
from direct.showbase.InputStateGlobal import inputState
from direct.directnotify import DirectNotifyGlobal
from direct.task import Task

# ---- Tweak these if something feels off -----------------------------------
STICK_DEADZONE = 0.35      # how far the stick must move before it counts
TRIGGER_THRESHOLD = 0.5    # how far a trigger must be pulled to click
POINTER_SPEED = 900.0      # pixels per second at full right-stick tilt
INVERT_LEFT_Y = False      # set True if forward/back are the wrong way round
INVERT_RIGHT_Y = False     # set True if the pointer moves the wrong way up/down

# Button -> keyboard event the game already listens for
BUTTON_EVENTS = {
    'face_b': 'escape',
    'face_y': 'escape',
    'face_x': 'delete',
    'lshoulder': 'shift-tab',
    'rshoulder': 'tab',
    'dpad_up': 'page_up',
    'dpad_down': 'page_down',
    'back': 'f9',
}

INPUT_SOURCE = 'gamepad'
PREFIX = 'gamepad'


class GamepadSupport(DirectObject):
    notify = DirectNotifyGlobal.directNotify.newCategory('GamepadSupport')

    def __init__(self):
        DirectObject.__init__(self)
        self.device = None
        self.held = {}          # inputState name -> bool we last set
        self.triggerDown = False
        self.pointerX = None
        self.pointerY = None
        self.accept('connect-device', self.__onConnect)
        self.accept('disconnect-device', self.__onDisconnect)
        allDevices = list(base.devices.getDevices())
        self.notify.warning('Input devices found: %s' % ', '.join('%s [%s]' % (d.name, d.device_class) for d in allDevices) or 'none')
        for device in base.devices.getDevices(InputDevice.DeviceClass.gamepad):
            self.__attach(device)
            break
        taskMgr.add(self.__update, 'gamepadUpdate')

    # ---- connecting -------------------------------------------------------
    def __onConnect(self, device):
        if self.device is None and device.device_class == InputDevice.DeviceClass.gamepad:
            self.__attach(device)

    def __onDisconnect(self, device):
        if device == self.device:
            self.__detach()

    def __attach(self, device):
        self.device = device
        base.attachInputDevice(device, prefix=PREFIX)
        for button, event in BUTTON_EVENTS.items():
            self.accept('%s-%s' % (PREFIX, button), messenger.send, [event])
            self.accept('%s-%s-up' % (PREFIX, button), messenger.send, [event + '-up'])
        self.accept('%s-face_a' % PREFIX, self.__setHeld, ['jump', True])
        self.accept('%s-face_a-up' % PREFIX, self.__setHeld, ['jump', False])
        self.notify.warning('Controller connected: %s' % device.name)

    def __detach(self):
        for button in list(BUTTON_EVENTS) + ['face_a']:
            self.ignore('%s-%s' % (PREFIX, button))
            self.ignore('%s-%s-up' % (PREFIX, button))
        for name in list(self.held):
            self.__setHeld(name, False)
        try:
            base.detachInputDevice(self.device)
        except Exception:
            pass
        self.notify.warning('Controller disconnected')
        self.device = None

    # ---- helpers ----------------------------------------------------------
    def __setHeld(self, name, active):
        if self.held.get(name) == active:
            return
        self.held[name] = active
        inputState.set(name, active, inputSource=INPUT_SOURCE)

    def __axis(self, axis):
        found = self.device.findAxis(axis)
        return found.value if found else 0.0

    # ---- every frame ------------------------------------------------------
    def __update(self, task):
        if self.device is None or base.win is None:
            return Task.cont

        # Left stick (and d-pad left/right) -> walk and turn
        x = self.__axis(InputDevice.Axis.left_x)
        y = self.__axis(InputDevice.Axis.left_y)
        if INVERT_LEFT_Y:
            y = -y
        self.__setHeld('forward', y > STICK_DEADZONE)
        self.__setHeld('reverse', y < -STICK_DEADZONE)
        self.__setHeld('turnLeft', x < -STICK_DEADZONE)
        self.__setHeld('turnRight', x > STICK_DEADZONE)

        # Right stick -> mouse pointer
        rx = self.__axis(InputDevice.Axis.right_x)
        ry = self.__axis(InputDevice.Axis.right_y)
        if INVERT_RIGHT_Y:
            ry = -ry
        if abs(rx) > STICK_DEADZONE or abs(ry) > STICK_DEADZONE:
            pointer = base.win.getPointer(0)
            if self.pointerX is None:
                self.pointerX, self.pointerY = pointer.getX(), pointer.getY()
            step = POINTER_SPEED * globalClock.getDt()
            w, h = base.win.getXSize(), base.win.getYSize()
            self.pointerX = min(max(self.pointerX + rx * step, 0), w - 1)
            self.pointerY = min(max(self.pointerY - ry * step, 0), h - 1)
            base.win.movePointer(0, int(self.pointerX), int(self.pointerY))
        else:
            self.pointerX = self.pointerY = None

        # Triggers -> left click
        trigger = max(self.__axis(InputDevice.Axis.left_trigger),
                      self.__axis(InputDevice.Axis.right_trigger))
        pressed = trigger > TRIGGER_THRESHOLD
        if pressed != self.triggerDown:
            self.triggerDown = pressed
            self.__click(pressed)

        return Task.cont

    def __click(self, down):
        # Send a real mouse click so menus and battle buttons respond.
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            flag = 0x0002 if down else 0x0004  # MOUSEEVENTF_LEFTDOWN / LEFTUP
            ctypes.windll.user32.mouse_event(flag, 0, 0, 0, 0)
        except Exception as e:
            self.notify.warning('Could not click: %s' % e)


def start():
    if not ConfigVariableBool('want-gamepad', True).value:
        return None
    try:
        return GamepadSupport()
    except Exception as e:
        GamepadSupport.notify.warning('Gamepad support disabled: %s' % e)
        return None
