"""Stand-ins for the Tildagon firmware modules the game imports, so the real
ace.py runs unchanged on a Raspberry Pi (or any computer with Python 3).

install() puts them in sys.modules; it must run before the game is imported.
They copy the firmware's behaviour where the game depends on it (button
matching through parents, events delivered to handlers, the LED ring), written
afresh from what the game uses: no firmware code is copied.

What the firmware gives and the Pi doesn't: no IMU (no tilt steering), no
scheduler shortcut (run.py has its own loop), no hexpansion manager, no
firmware text dialog (with a keyboard the game uses its own typing pages).
"""
import sys
import types


class Button:
    """A button, matched as the firmware does: a physical button counts as
    each of its parents (the badge's A is also UP and Frontboard A)."""

    def __init__(self, name, group, parent=None):
        self.name = name
        self.group = group
        if isinstance(parent, Button):
            self.parents = [parent]
        elif parent is None:
            self.parents = []
        else:
            self.parents = list(parent)
        self._all = None

    def __hash__(self):
        return hash((self.name, self.group))

    def __eq__(self, other):
        return isinstance(other, Button) and self.name == other.name and self.group == other.group

    @property
    def all_parents(self):
        if self._all is None:
            out = []
            for p in self.parents:
                out.append(p)
                out += p.all_parents
            self._all = out
        return self._all

    def __contains__(self, other):
        return other == self or any(other == p for p in self.all_parents)

    def find_parent_in_group(self, group):
        for b in [self] + self.all_parents:
            if b.group == group:
                return b
        return None

    def __repr__(self):
        return "%s.%s" % (self.group, self.name)


SYSTEM = {n: Button(n, "System") for n in
          ("UNDEFINED", "CANCEL", "CONFIRM", "UP", "DOWN", "LEFT", "RIGHT")}
FRONTBOARD = {c: Button(c, "Frontboard") for c in "ABCDEF"}
JOYSTICK = {n: Button(n, "Joystick") for n in
            ("UP", "DOWN", "LEFT", "RIGHT", "A", "B", "C", "X", "Y", "Z", "SELECT")}

# the keyboard, named as the Keyboard Hexpansion's keys (the firmware's
# events/keyboard.py): letters, digits, symbols and the modifiers
KEYBOARD = {c: Button(c, "Keyboard") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
for _c in """!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~""":
    KEYBOARD[_c] = Button(_c, "Keyboard")
for _n in ("SPACE", "SHIFT", "CTRL", "ALT", "BACKSPACE"):
    KEYBOARD[_n] = Button(_n, "Keyboard")
KEYBOARD["ESCAPE"] = Button("ESCAPE", "Keyboard", SYSTEM["CANCEL"])
KEYBOARD["ENTER"] = Button("ENTER", "Keyboard", SYSTEM["CONFIRM"])
for _n in ("UP", "DOWN", "LEFT", "RIGHT"):
    KEYBOARD[_n] = Button(_n, "Keyboard", SYSTEM[_n])
TAB = Button("TAB", "Keyboard")         # not in the firmware's table: the game matches it by name

# the 2026 front board's physical buttons, each a lettered button and a system
# direction at once, as the badge sends them
_BOARD = (("A", "UP"), ("B", "RIGHT"), ("C", "CONFIRM"), ("D", "DOWN"), ("E", "LEFT"), ("F", "CANCEL"))
BADGE = {c: Button(c, "TwentyTwentySix", [SYSTEM[s], FRONTBOARD[c]]) for c, s in _BOARD}
STICK = {n: Button("JOY" + n, "TwentyTwentySix", [SYSTEM[n], JOYSTICK[n]])
         for n in ("UP", "DOWN", "LEFT", "RIGHT")}
STICK["SELECT"] = Button("JOYSELECT", "TwentyTwentySix", [SYSTEM["CONFIRM"], JOYSTICK["SELECT"]])


class ButtonDownEvent:
    requires_focus = True

    def __init__(self, button):
        self.button = button


class ButtonUpEvent:
    requires_focus = True

    def __init__(self, button):
        self.button = button


class Bus:
    """The event bus: handlers by event type. There is one app, always in
    focus, so every handler gets every event."""

    def __init__(self):
        self.handlers = {}

    def on(self, event_type, handler, app):
        self.handlers.setdefault(event_type, []).append(handler)

    def on_async(self, event_type, handler, app):
        pass

    def remove(self, event_type, handler, app):
        hs = self.handlers.get(event_type, [])
        if handler in hs:
            hs.remove(handler)

    def emit(self, event):
        """Events the game sends to the firmware (LED patterns): nothing to do."""

    def send(self, event):
        """Deliver a button event to the game's handlers."""
        for h in list(self.handlers.get(type(event), [])):
            h(event)


class App:
    """The firmware's app base class, as far as the game uses it."""

    def __init__(self):
        self.overlays = []
        self._focused = True
        self.quit = False

    def minimise(self):
        self.quit = True        # leaving the game ends the Pi program


class Leds:
    """The badge's LEDs (19, 1-12 the front ring): run.py draws the ring."""

    def __init__(self):
        self.values = [(0, 0, 0)] * 19

    def __setitem__(self, i, rgb):
        self.values[i] = tuple(rgb)

    def __getitem__(self, i):
        return self.values[i]

    def __len__(self):
        return len(self.values)

    def write(self):
        pass


class PatternDisable:
    pass


class PatternEnable:
    pass


bus = None
leds = None


def _module(name, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def install():
    """Put the stand-ins in sys.modules. Returns (bus, leds)."""
    global bus, leds
    bus = Bus()
    leds = Leds()
    _module("app", App=App)
    _module("events")
    _module("events.input", Button=Button, BUTTON_TYPES=SYSTEM,
            ButtonDownEvent=ButtonDownEvent, ButtonUpEvent=ButtonUpEvent)
    _module("events.joystick", JOYSTICK_BUTTON_TYPES=JOYSTICK)
    _module("events.keyboard", KEYBOARD_BUTTONS=KEYBOARD)
    _module("frontboards")
    _module("frontboards.common", FRONTBOARD_BUTTON_TYPES=FRONTBOARD)
    _module("system")
    _module("system.eventbus", eventbus=bus)
    _module("system.patterndisplay")
    _module("system.patterndisplay.events", PatternDisable=PatternDisable,
            PatternEnable=PatternEnable)
    tos = types.SimpleNamespace(leds=leds, set_led_power=lambda on: None)
    _module("tildagonos", tildagonos=tos)
    for name in ("imu", "system.scheduler", "settings", "app_components",
                 "app_components.dialog", "system.hexpansion", "system.hexpansion.app"):
        sys.modules.pop(name, None)     # not on a Pi: the game copes without them
    return bus, leds
