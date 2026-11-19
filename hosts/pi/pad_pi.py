"""A game controller as the badge's buttons and joystick (Raspberry Pi host, P2).

Any pad SDL knows as a game controller (Xbox, PlayStation, 8BitDo, ...): its
buttons are named by position, so one table (MAP) serves them all. The pad is
the badge: its buttons send the badge's own A-F and joystick, so every screen
works as it does on the badge. The left stick is the joystick too, pushed past
STICK_ON (let go below STICK_OFF); the triggers count as buttons past TRIGGER_ON.
Pads can be plugged in and out while the game runs.
"""
import pygame

from pi_firmware import BADGE, STICK, ButtonDownEvent, ButtonUpEvent

try:
    from pygame._sdl2 import controller as sdl_controller
except ImportError:         # an old pygame: no pads
    sdl_controller = None

# pad control -> the badge's button (Brian can change this table)
MAP = {
    "dpup": STICK["UP"], "dpdown": STICK["DOWN"],
    "dpleft": STICK["LEFT"], "dpright": STICK["RIGHT"],
    "stickup": STICK["UP"], "stickdown": STICK["DOWN"],         # the left stick
    "stickleft": STICK["LEFT"], "stickright": STICK["RIGHT"],
    "a": BADGE["C"],            # south: fire, choose, buy
    "x": BADGE["D"],            # west: missile, sell
    "y": BADGE["B"],            # north: energy bomb, next tab, search
    "b": BADGE["F"],            # east: back (faster in flight, as the badge's F)
    "start": BADGE["A"],        # the in-flight menu, launch
    "rightshoulder": BADGE["F"], "righttrigger": BADGE["F"],    # faster
    "leftshoulder": BADGE["E"], "lefttrigger": BADGE["E"],      # slower
    "leftstick": STICK["SELECT"],
}

STICK_ON = 0.5              # of full travel: the stick counts as pushed
STICK_OFF = 0.35            # and as let go (a gap, so it doesn't chatter)
TRIGGER_ON = 0.5

_BUTTONS = {
    pygame.CONTROLLER_BUTTON_A: "a", pygame.CONTROLLER_BUTTON_B: "b",
    pygame.CONTROLLER_BUTTON_X: "x", pygame.CONTROLLER_BUTTON_Y: "y",
    pygame.CONTROLLER_BUTTON_BACK: "back", pygame.CONTROLLER_BUTTON_GUIDE: "guide",
    pygame.CONTROLLER_BUTTON_START: "start",
    pygame.CONTROLLER_BUTTON_LEFTSTICK: "leftstick",
    pygame.CONTROLLER_BUTTON_RIGHTSTICK: "rightstick",
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "leftshoulder",
    pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "rightshoulder",
    pygame.CONTROLLER_BUTTON_DPAD_UP: "dpup", pygame.CONTROLLER_BUTTON_DPAD_DOWN: "dpdown",
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: "dpleft", pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "dpright",
}
_AXES = {
    pygame.CONTROLLER_AXIS_LEFTX: "leftx", pygame.CONTROLLER_AXIS_LEFTY: "lefty",
    pygame.CONTROLLER_AXIS_TRIGGERLEFT: "lefttrigger",
    pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "righttrigger",
}


class Pads:
    """Game controller events in, the badge's button events out. Two controls
    can send the same button (the D-pad and the stick, a shoulder and a
    trigger): it goes down with the first and up with the last."""

    def __init__(self, bus, log=False):
        self.bus = bus
        self.log = log
        self.pads = {}          # instance id -> Controller
        self.on = set()         # (instance id, control) held down
        self.count = {}         # badge button -> how many controls hold it
        if sdl_controller is not None:
            sdl_controller.init()
            for i in range(pygame.joystick.get_count()):
                self._open(i)

    def _open(self, index):
        if sdl_controller is None or not sdl_controller.is_controller(index):
            return
        c = sdl_controller.Controller(index)
        jid = c.as_joystick().get_instance_id()
        self.pads[jid] = c
        if self.log:
            print("PAD", c.name, "plugged in", flush=True)

    def names(self):
        return [c.name for c in self.pads.values()]

    def _set(self, pid, control, down):
        b = MAP.get(control)
        key = (pid, control)
        if b is None or (key in self.on) == down:
            return
        if self.log:
            print("PAD", control, "down" if down else "up", "->", b, flush=True)
        if down:
            self.on.add(key)
            self.count[b] = self.count.get(b, 0) + 1
            if self.count[b] == 1:
                self.bus.send(ButtonDownEvent(b))
        else:
            self.on.discard(key)
            self.count[b] -= 1
            if self.count[b] == 0:
                self.bus.send(ButtonUpEvent(b))

    def handle(self, event):
        """Pass a pygame event on. True if it was a pad's."""
        t = event.type
        if t == pygame.CONTROLLERDEVICEADDED:
            if event.device_index not in [c.id for c in self.pads.values()]:
                self._open(event.device_index)
            return True
        if t == pygame.CONTROLLERDEVICEREMOVED:
            pid = event.instance_id
            for key in [k for k in self.on if k[0] == pid]:
                self._set(pid, key[1], False)       # let go of what it held
            self.pads.pop(pid, None)
            return True
        if t in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP):
            name = _BUTTONS.get(event.button)
            if name is not None:
                self._set(event.instance_id, name, t == pygame.CONTROLLERBUTTONDOWN)
            return True
        if t == pygame.CONTROLLERAXISMOTION:
            name = _AXES.get(event.axis)
            v = event.value / 32767.0
            pid = event.instance_id
            if name == "leftx" or name == "lefty":
                neg, pos = ("stickleft", "stickright") if name == "leftx" else ("stickup", "stickdown")
                for stick, sign in ((neg, -1), (pos, 1)):
                    held = (pid, stick) in self.on
                    push = v * sign
                    if not held and push >= STICK_ON:
                        self._set(pid, stick, True)
                    elif held and push < STICK_OFF:
                        self._set(pid, stick, False)
            elif name is not None:                      # a trigger
                held = (pid, name) in self.on
                if not held and v >= TRIGGER_ON:
                    self._set(pid, name, True)
                elif held and v < TRIGGER_ON * 0.7:
                    self._set(pid, name, False)
            return True
        return False

    def release_all(self):
        for pid, control in list(self.on):
            self._set(pid, control, False)
