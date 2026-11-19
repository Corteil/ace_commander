"""A game controller (Raspberry Pi host, P2).

Any pad SDL knows as a game controller (Xbox, PlayStation, 8BitDo, ...): its
controls are named by position (Xbox names: A south, B east, X west, Y north),
so the tables here serve them all. Pads can be plugged in and out while the
game runs; unplugging lets go of whatever the pad held.

Two maps (Brian, 2026-11-19):
- Flying (looking at space): FLIGHT. Analogue sticks: left up / down the
  power (where the stick sits is the speed: top full, bottom stopped, centre
  half), left left / right yaw; right up / down pitch, left / right roll.
  Left trigger missile, left bumper E.C.M. (Hardcore; otherwise it is
  automatic), right trigger fire, right bumper energy bomb, D-pad the views,
  Start the pause menu, the Xbox button held 1 s the escape pod. A held: jump
  drive; B: docking computer on / off; X: hyperspace (held 1 s: galactic);
  Y: the in-flight screens in turn, then back to space; left stick click: arm
  the missile (Hardcore); right stick click: the next view.
- Everywhere else (title, docked, the pause menu, the in-flight screens):
  BADGE, the pad as the badge's buttons and joystick, so every screen works as
  on the badge; Y still steps through the in-flight screens.
"""
import math

import pygame

from pi_firmware import BADGE, KEYBOARD, STICK, ButtonDownEvent, ButtonUpEvent

try:
    from pygame._sdl2 import controller as sdl_controller
except ImportError:         # an old pygame: no pads
    sdl_controller = None

# off the flight: the pad is the badge
BADGE_MAP = {
    "dpup": STICK["UP"], "dpdown": STICK["DOWN"],
    "dpleft": STICK["LEFT"], "dpright": STICK["RIGHT"],
    "stickup": STICK["UP"], "stickdown": STICK["DOWN"],         # the left stick
    "stickleft": STICK["LEFT"], "stickright": STICK["RIGHT"],
    "a": BADGE["C"],            # south: choose, buy
    "x": BADGE["D"],            # west: sell, D's things
    "y": "screens",             # north: the in-flight screens in turn (B docked)
    "b": BADGE["F"],            # east: back
    "start": BADGE["A"],        # launch, the pause menu
    "rightshoulder": BADGE["F"], "righttrigger": BADGE["F"],
    "leftshoulder": BADGE["E"], "lefttrigger": BADGE["E"],
    "leftstick": STICK["SELECT"],
}

# flying: a button the control holds, or a special action (a name)
FLIGHT_MAP = {
    "lefttrigger": BADGE["D"],      # missile (Hardcore: arms, then fires, as the badge's D)
    "leftshoulder": "ecm",          # Hardcore's E.C.M. (otherwise automatic)
    "righttrigger": KEYBOARD["SPACE"],  # fire
    "rightshoulder": BADGE["B"],    # energy bomb
    "dpup": KEYBOARD["1"], "dpdown": KEYBOARD["2"],     # views: front, rear,
    "dpleft": KEYBOARD["3"], "dpright": KEYBOARD["4"],  # left, right
    "start": BADGE["A"],            # the pause menu
    "guide": "escape",              # held HOLD_ESCAPE: the escape pod
    "a": KEYBOARD["J"],             # held: the jump drive
    "b": "dock",                    # the docking computer on / off
    "x": "hyper",                   # hyperspace; held HOLD_GALACTIC: galactic
    "y": "screens",                 # the in-flight screens in turn
    "leftstick": KEYBOARD["T"],     # arm the missile (Hardcore)
    "rightstick": KEYBOARD["V"],    # the next view
}

HOLD_ESCAPE = 1.0           # seconds the Xbox button is held for the escape pod
HOLD_GALACTIC = 1.0         # seconds X is held for the galactic hyperdrive
DEAD = 0.12                 # analogue dead zone, of full travel
CURVE = 1.6                 # > 1: finer near the centre
STICK_ON = 0.5              # off the flight the left stick is the joystick: on past half
STICK_OFF = 0.35            # and off below this (a gap, so it doesn't chatter)
TRIGGER_ON = 0.5
# Y steps through the in-flight screens in this order (the game's number keys)
SCREEN_ORDER = (("local", "6"), ("galactic", "5"), ("status", "9"),
                ("inventory", "0"), ("market", "8"))

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
    pygame.CONTROLLER_AXIS_RIGHTX: "rightx", pygame.CONTROLLER_AXIS_RIGHTY: "righty",
    pygame.CONTROLLER_AXIS_TRIGGERLEFT: "lefttrigger",
    pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "righttrigger",
}


def shape(v):
    """A stick's -1..1 with the dead zone taken out and the curve put in."""
    a = abs(v)
    if a <= DEAD:
        return 0.0
    a = min(1.0, (a - DEAD) / (1.0 - DEAD)) ** CURVE
    return a if v > 0 else -a


class Analog:
    """What the game reads (AceCommander.analog): roll, pitch, yaw -1..1
    (pitch as the joystick: negative is up), speed 0..1."""

    def __init__(self, roll, pitch, yaw, speed):
        self.roll = roll
        self.pitch = pitch
        self.yaw = yaw
        self.speed = speed


class Pads:
    """Game controller events in, the game's button events out (and its
    analogue controls). Two controls can hold the same button (the D-pad and
    the stick, a shoulder and a trigger): it goes down with the first and up
    with the last. A control lets go of what it pressed, whichever map is in
    use by then."""

    def __init__(self, bus, app=None, log=False):
        self.bus = bus
        self.app = app              # a callable giving the game (AceCommander), or None
        self.log = log
        self.pads = {}              # instance id -> Controller
        self.on = {}                # (instance id, control) -> what it pressed
        self.count = {}             # button -> how many controls hold it
        self.axes = {}              # (instance id, axis name) -> -1..1 (triggers 0..1)
        self.timers = {}            # (instance id, control) -> seconds held (hold actions)
        self.done = set()           # hold actions that have fired
        if sdl_controller is not None:
            sdl_controller.init()
            for i in range(pygame.joystick.get_count()):
                self._open(i)

    # ---- pads coming and going -------------------------------------------------
    def _open(self, index):
        if sdl_controller is None or not sdl_controller.is_controller(index):
            return
        c = sdl_controller.Controller(index)
        jid = c.as_joystick().get_instance_id()
        if jid in self.pads:
            return
        self.pads[jid] = c
        if self.log:
            print("PAD", c.name, "plugged in", flush=True)

    def names(self):
        return [c.name for c in self.pads.values()]

    # ---- where the game is ----------------------------------------------------------
    def _game(self):
        return self.app() if self.app is not None else None

    def flying(self):
        """Looking at space in a flight: the flight map and the sticks."""
        a = self._game()
        return (a is not None and a.mode == "flight" and not a.paused
                and getattr(a, "fsub", None) not in ("status", "inventory", "market", "chart", "data"))

    # ---- buttons -----------------------------------------------------------------------
    def _press(self, b):
        self.count[b] = self.count.get(b, 0) + 1
        if self.count[b] == 1:
            self.bus.send(ButtonDownEvent(b))

    def _release(self, b):
        n = self.count.get(b, 0) - 1
        self.count[b] = max(0, n)
        if n == 0:
            self.bus.send(ButtonUpEvent(b))

    def _tap(self, *buttons):
        """Press and let go at once (the game counts the press next frame)."""
        for b in buttons:
            self._press(b)
        for b in reversed(buttons):
            self._release(b)

    def _set(self, pid, control, down):
        key = (pid, control)
        if down == (key in self.on):
            return
        if not down:
            what = self.on.pop(key)
            if self.log:
                print("PAD", control, "up", flush=True)
            if what == "hyper" and key not in self.done:
                self._tap(KEYBOARD["H"])            # a short press: hyperspace
            if isinstance(what, str):
                self.timers.pop(key, None)
                self.done.discard(key)
            else:
                self._release(what)
            return
        what = (FLIGHT_MAP if self.flying() else BADGE_MAP).get(control)
        if what is None:
            return
        if self.log:
            print("PAD", control, "down ->", what, flush=True)
        self.on[key] = what
        if not isinstance(what, str):
            self._press(what)
        elif what in ("hyper", "escape"):
            self.timers[key] = 0.0                  # tick() fires it when held long enough
        elif what == "dock":
            g = getattr(self._game(), "game", None)
            self._tap(KEYBOARD["P"] if g is not None and g.autodock else KEYBOARD["C"])
        elif what == "ecm":
            g = getattr(self._game(), "game", None)
            if g is not None and g.rules.manual_ecm:
                self._tap(KEYBOARD["E"])
        elif what == "screens":
            self._next_screen()

    def _next_screen(self):
        """Y: the next in-flight screen, and after the last back to space.
        Docked, Y is the badge's B (the next tab)."""
        a = self._game()
        if a is None:
            return
        if a.mode != "flight":
            self._tap(BADGE["B"])
            return
        if a.paused:
            return
        sub = getattr(a, "fsub", None)
        if sub == "chart":
            sub = "galactic" if type(a.chart).__name__ == "GalChart" else "local"
        elif sub == "data":
            sub = "local"
        # Market Prices only in a system (not in witchspace)
        order = [(n, k) for n, k in SCREEN_ORDER
                 if n != "market" or getattr(a, "witch", None) is None]
        names = [n for n, _ in order]
        if sub not in names:            # looking at space: the first
            self._tap(KEYBOARD[order[0][1]])
        elif names.index(sub) + 1 < len(order):
            self._tap(KEYBOARD[order[names.index(sub) + 1][1]])
        else:
            self._tap(KEYBOARD[order[-1][1]])       # the last one's own key closes it

    def tick(self, dt):
        """Once a frame: hold actions, and the analogue controls for the game."""
        for key, t in list(self.timers.items()):
            t += dt
            self.timers[key] = t
            what = self.on.get(key)
            if key in self.done:
                continue
            if what == "hyper" and t >= HOLD_GALACTIC:
                self.done.add(key)
                self._tap(KEYBOARD["SHIFT"], KEYBOARD["H"])     # Shift+H: galactic
            elif what == "escape" and t >= HOLD_ESCAPE:
                self.done.add(key)
                self._tap(KEYBOARD["ESCAPE"])                   # the escape pod
        a = self._game()
        if a is not None and hasattr(a, "analog"):
            a.analog = self.analog() if self.flying() else None

    def analog(self):
        """The sticks of every pad, added together (None with no pad)."""
        if not self.pads:
            return None
        roll = pitch = yaw = 0.0
        speed = None
        for pid in self.pads:
            ax = self.axes
            roll += shape(ax.get((pid, "rightx"), 0.0))
            pitch += shape(ax.get((pid, "righty"), 0.0))
            yaw += shape(ax.get((pid, "leftx"), 0.0))
            y = ax.get((pid, "lefty"))
            if y is not None:
                y = 0.0 if abs(y) <= DEAD else y
                speed = (1.0 - max(-1.0, min(1.0, y))) / 2      # up (negative) is faster
        clamp = lambda v: max(-1.0, min(1.0, v))    # noqa: E731
        return Analog(clamp(roll), clamp(pitch), clamp(yaw), speed)

    # ---- events --------------------------------------------------------------------------
    def handle(self, event):
        """Pass a pygame event on. True if it was a pad's."""
        t = event.type
        if t == pygame.CONTROLLERDEVICEADDED:
            self._open(event.device_index)
            return True
        if t == pygame.CONTROLLERDEVICEREMOVED:
            pid = event.instance_id
            for key in [k for k in self.on if k[0] == pid]:
                self._set(pid, key[1], False)       # let go of what it held
            for key in [k for k in self.axes if k[0] == pid]:
                del self.axes[key]
            self.pads.pop(pid, None)
            return True
        if t in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP):
            name = _BUTTONS.get(event.button)
            if name is not None:
                self._set(event.instance_id, name, t == pygame.CONTROLLERBUTTONDOWN)
            return True
        if t == pygame.CONTROLLERAXISMOTION:
            name = _AXES.get(event.axis)
            if name is None:
                return True
            v = max(-1.0, event.value / 32767.0)
            pid = event.instance_id
            self.axes[(pid, name)] = v
            if name in ("lefttrigger", "righttrigger"):
                held = (pid, name) in self.on
                if not held and v >= TRIGGER_ON:
                    self._set(pid, name, True)
                elif held and v < TRIGGER_ON * 0.7:
                    self._set(pid, name, False)
            elif name in ("leftx", "lefty"):
                # off the flight the left stick is the joystick (on / off);
                # flying it is analogue only, and lets go of any of those
                neg, pos = ("stickleft", "stickright") if name == "leftx" else ("stickup", "stickdown")
                flying = self.flying()
                for stick, sign in ((neg, -1), (pos, 1)):
                    held = (pid, stick) in self.on
                    push = v * sign
                    if not held and push >= STICK_ON and not flying:
                        self._set(pid, stick, True)
                    elif held and (push < STICK_OFF or flying):
                        self._set(pid, stick, False)
            return True
        return False

    def release_all(self):
        """The window lost focus: let go of everything, firing nothing."""
        self.done.update(self.on)       # a held X doesn't jump on its way up
        for pid, control in list(self.on):
            self._set(pid, control, False)
        self.axes = {}
