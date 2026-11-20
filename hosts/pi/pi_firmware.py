"""Stand-ins for the Tildagon firmware modules the game imports, so the real
ace.py runs unchanged on a Raspberry Pi (or any computer with Python 3).

install() puts them in sys.modules; it must run before the game is imported.
They copy the firmware's behaviour where the game depends on it (the app base
class, the LED ring), written afresh from what the game uses: no firmware code
is copied. Input doesn't come through here: since the platform layer's step 2
the Pi sends the game control names itself (controls_pi.py), so the firmware's
buttons and button events have no stand-ins.

What the firmware gives and the Pi doesn't: no IMU (no tilt steering), no
scheduler shortcut (run.py has its own loop), no hexpansion manager, no
firmware text dialog (with a keyboard the game uses its own typing pages).
"""
import sys
import types


class Bus:
    """The event bus, as far as the game still uses it: LED pattern events
    (emit), which the Pi has nothing to do for."""

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
