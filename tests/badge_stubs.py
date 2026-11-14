"""Stand-ins for the badge firmware, for running the app on a PC."""
import math
import sys
import types


class App:
    minimised = 0

    def __init__(self):
        self.overlays = []      # the real base class sets this up

    def minimise(self):
        App.minimised += 1


class Button:
    """Same matching rules as the firmware's events.input.Button."""

    def __init__(self, name, group, parent=None):
        self.name = name
        self.group = group
        if isinstance(parent, Button):
            self.parents = [parent]
        elif parent is None:
            self.parents = []
        else:
            self.parents = parent

    def __hash__(self):
        return hash((self.name, self.group))

    def __eq__(self, other):
        return self.name == other.name and self.group == other.group

    @property
    def all_parents(self):
        out = []
        for p in self.parents:
            out.append(p)
            out += p.all_parents
        return out

    def __contains__(self, other):
        return other == self or any(other == p for p in self.all_parents)

    def __repr__(self):
        return "%s.%s" % (self.group, self.name)


NAMES = ["UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "CANCEL"]
TYPES = {k: Button(k, "System") for k in NAMES}
FB = {k: Button(k, "Frontboard") for k in "ABCDEF"}
JOY = {k: Button(k, "Joystick") for k in ("UP", "DOWN", "LEFT", "RIGHT", "SELECT")}
KEYS = {c: Button(c, "Keyboard") for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"}
KEYS["SPACE"] = Button("SPACE", "Keyboard")
KEYS["ENTER"] = Button("ENTER", "Keyboard", TYPES["CONFIRM"])
KEYS["ESCAPE"] = Button("ESCAPE", "Keyboard", TYPES["CANCEL"])
for _k in ("UP", "DOWN", "LEFT", "RIGHT"):
    KEYS[_k] = Button(_k, "Keyboard", TYPES[_k])

# what a test can hold down, by name
PHYSICAL = {
    "A": Button("A", "TwentyTwentySix", [TYPES["UP"], FB["A"]]),
    "B": Button("B", "TwentyTwentySix", [TYPES["RIGHT"], FB["B"]]),
    "C": Button("C", "TwentyTwentySix", [TYPES["CONFIRM"], FB["C"]]),
    "D": Button("D", "TwentyTwentySix", [TYPES["DOWN"], FB["D"]]),
    "E": Button("E", "TwentyTwentySix", [TYPES["LEFT"], FB["E"]]),
    "F": Button("F", "TwentyTwentySix", [TYPES["CANCEL"], FB["F"]]),
    "JOYUP": Button("JOYUP", "TwentyTwentySix", [TYPES["UP"], JOY["UP"]]),
    "JOYDOWN": Button("JOYDOWN", "TwentyTwentySix", [TYPES["DOWN"], JOY["DOWN"]]),
    "JOYLEFT": Button("JOYLEFT", "TwentyTwentySix", [TYPES["LEFT"], JOY["LEFT"]]),
    "JOYRIGHT": Button("JOYRIGHT", "TwentyTwentySix", [TYPES["RIGHT"], JOY["RIGHT"]]),
    "JOYFIRE": Button("JOYFIRE", "TwentyTwentySix", [TYPES["CONFIRM"], JOY["SELECT"]]),
    # plain system buttons, as a USB keyboard's arrows, Enter and Escape send
    "UP": KEYS["UP"], "DOWN": KEYS["DOWN"], "LEFT": KEYS["LEFT"], "RIGHT": KEYS["RIGHT"],
    "CONFIRM": KEYS["ENTER"], "CANCEL": KEYS["ESCAPE"],
}
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    PHYSICAL["KEY_" + _c] = KEYS[_c]
PHYSICAL["KEY_SPACE"] = KEYS["SPACE"]


class ButtonDownEvent:
    requires_focus = True

    def __init__(self, button):
        self.button = button


class ButtonUpEvent:
    requires_focus = True

    def __init__(self, button):
        self.button = button


class Bus:
    """Stand-in for system.eventbus.eventbus."""

    def __init__(self):
        self.handlers = {}
        self.events = []     # names of events the app emitted

    def on(self, event_type, handler, app):
        assert hasattr(app, "overlays"), "App.__init__ must run first"
        self.handlers.setdefault(event_type, []).append(handler)

    def remove(self, event_type, handler, app):
        self.handlers[event_type].remove(handler)

    def emit(self, event):
        self.events.append(type(event).__name__)

    def send(self, event):
        """Deliver an event to the app, as the badge does for a button."""
        for h in self.handlers.get(type(event), []):
            h(event)


bus = Bus()
_down = set()


def press(names):
    """Make exactly these buttons be down, sending events for what changed."""
    global _down
    names = set(names)
    for n in sorted(_down - names):
        bus.send(ButtonUpEvent(PHYSICAL[n]))
    for n in sorted(names - _down):
        bus.send(ButtonDownEvent(PHYSICAL[n]))
    _down = names


def choose(a, label):
    """Pick a title screen choice by name."""
    assert a.mode == "menu", a.mode
    a.menu = a.choices().index(label)
    tick(a, fresh=["CONFIRM"])


def tick(a, held=(), fresh=(), ms=40):
    """One update with these buttons down. `fresh` ones are let go straight after."""
    press(set(held) | set(fresh))
    a.update(ms)
    if fresh:
        press(held)
        a.update(0)


class Imu:
    reading = [0.0, 0.0, 9.81]
    fail = False

    @staticmethod
    def acc_read():
        if Imu.fail:
            raise OSError("no sensor")
        return tuple(Imu.reading)


def install(imu=True, keyboard=True, joystick=True):
    global bus, _down
    for name in list(sys.modules):
        if name == "ace_commander" or name.startswith("ace_commander."):
            del sys.modules[name]
    bus = Bus()
    _down = set()
    app = types.ModuleType("app")
    app.App = App
    inp = types.ModuleType("events.input")
    inp.BUTTON_TYPES = TYPES
    inp.ButtonDownEvent = ButtonDownEvent
    inp.ButtonUpEvent = ButtonUpEvent
    for n in ("imu", "events.keyboard", "events.joystick", "frontboards", "frontboards.common",
              "system.scheduler"):
        sys.modules.pop(n, None)
    remove_leds()
    eb = types.ModuleType("system.eventbus")
    eb.eventbus = bus
    sys.modules.update({"app": app, "events": types.ModuleType("events"), "events.input": inp,
                        "system": types.ModuleType("system"), "system.eventbus": eb})
    if imu:
        m = types.ModuleType("imu")
        m.acc_read = Imu.acc_read
        sys.modules["imu"] = m
    if keyboard:
        kb = types.ModuleType("events.keyboard")
        kb.KEYBOARD_BUTTONS = KEYS
        sys.modules["events.keyboard"] = kb
    if joystick:
        j = types.ModuleType("events.joystick")
        j.JOYSTICK_BUTTON_TYPES = JOY
        fb = types.ModuleType("frontboards.common")
        fb.FRONTBOARD_BUTTON_TYPES = FB
        sys.modules.update({"events.joystick": j, "frontboards": types.ModuleType("frontboards"),
                            "frontboards.common": fb})
    Imu.reading = [0.0, 0.0, 9.81]
    Imu.fail = False
    App.minimised = 0


# The drawing calls the user's own working badge app (file_explorer) uses,
# plus begin_path. Anything else is treated as a mistake.
METHODS = {"rgb", "rgba", "rectangle", "fill", "stroke", "arc", "move_to", "line_to",
           "begin_path", "close_path", "text", "save", "restore"}
ATTRS = {"font_size", "text_align", "text_baseline", "line_width"}


class CountCtx:
    """Checks every call is a known one with finite numbers, and counts them."""
    CENTER = "center"
    LEFT = "left"
    MIDDLE = "middle"

    def __init__(self):
        object.__setattr__(self, "calls", {})
        object.__setattr__(self, "texts", [])
        object.__setattr__(self, "pos", (0, 0))
        object.__setattr__(self, "depth", 0)

    def __setattr__(self, name, value):
        if name not in ATTRS:
            raise AttributeError("unknown ctx attribute " + name)
        object.__setattr__(self, name, value)

    def __getattr__(self, name):
        if name not in METHODS:
            raise AttributeError("unknown ctx method " + name)

        def call(*args):
            for a in args:
                if isinstance(a, float) and not math.isfinite(a):
                    raise ValueError("%s got %r" % (name, args))
            self.calls[name] = self.calls.get(name, 0) + 1
            if name == "move_to":
                object.__setattr__(self, "pos", args)
            elif name == "text":
                self.texts.append((args[0], self.pos, self.font_size))
            elif name == "save":
                object.__setattr__(self, "depth", self.depth + 1)
            elif name == "restore":
                object.__setattr__(self, "depth", self.depth - 1)
            return self
        return call


class PilCtx:
    """Draws to a PIL image, to look at a frame. scale 3 = 720 x 720."""
    CENTER = "center"
    LEFT = "left"
    MIDDLE = "middle"

    def __init__(self, scale=3):
        from PIL import Image, ImageDraw
        self.s = scale
        self.img = Image.new("RGB", (240 * scale, 240 * scale), (0, 0, 0))
        self.d = ImageDraw.Draw(self.img, "RGBA")
        self.col = (255, 255, 255, 255)
        self.path = []      # list of sub-paths, each a list of points
        self.shape = None
        self.font_size = 14
        self.line_width = 1.5
        self.text_align = "center"
        self.text_baseline = "middle"
        self.cur = (0, 0)

    def _p(self, x, y):
        return ((x + 120) * self.s, (y + 120) * self.s)

    def save(self): return self
    def restore(self): return self

    def rgb(self, r, g, b):
        self.col = (int(r * 255), int(g * 255), int(b * 255), 255)
        return self

    def rgba(self, r, g, b, a):
        self.col = (int(r * 255), int(g * 255), int(b * 255), int(a * 255))
        return self

    def begin_path(self):
        self.path = []
        self.shape = None
        return self

    def move_to(self, x, y):
        self.cur = (x, y)
        self.path.append([self._p(x, y)])
        return self

    def line_to(self, x, y):
        if not self.path:
            self.path.append([self._p(*self.cur)])
        self.path[-1].append(self._p(x, y))
        self.cur = (x, y)
        return self

    def rectangle(self, x, y, w, h):
        self.shape = ("rect", x, y, w, h)
        return self

    def arc(self, x, y, r, a0, a1, d):
        self.shape = ("arc", x, y, r)
        return self

    def fill(self):
        if self.shape and self.shape[0] == "rect":
            _, x, y, w, h = self.shape
            a, b = self._p(x, y), self._p(x + w, y + h)
            self.d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])],
                             fill=self.col)
        elif self.shape and self.shape[0] == "arc":
            _, x, y, r = self.shape
            self.d.ellipse([self._p(x - r, y - r), self._p(x + r, y + r)], fill=self.col)
        self.shape = None
        self.path = []
        return self

    def stroke(self):
        w = max(1, int(self.line_width * self.s))
        if self.shape and self.shape[0] == "rect":
            _, x, y, wd, h = self.shape
            self.d.rectangle([self._p(x, y), self._p(x + wd, y + h)], outline=self.col, width=w)
        elif self.shape and self.shape[0] == "arc":
            _, x, y, r = self.shape
            self.d.ellipse([self._p(x - r, y - r), self._p(x + r, y + r)], outline=self.col, width=w)
        for sub in self.path:
            if len(sub) > 1:
                self.d.line(sub, fill=self.col, width=w)
        self.shape = None
        self.path = []
        return self

    def text(self, s):
        from PIL import ImageFont
        try:
            font = ImageFont.truetype("DejaVuSans.ttf", int(self.font_size * self.s))
        except OSError:
            font = ImageFont.load_default()
        x, y = self._p(*self.cur)
        self.d.text((x, y), s, fill=self.col, font=font, anchor="mm")
        self.path = []
        return self

    def finish(self, path):
        """Black out everything outside the round screen and save."""
        from PIL import Image, ImageDraw
        mask = Image.new("L", self.img.size, 0)
        ImageDraw.Draw(mask).ellipse([0, 0, self.img.size[0] - 1, self.img.size[1] - 1], fill=255)
        out = Image.new("RGB", self.img.size, (40, 40, 48))
        out.paste(self.img, (0, 0), mask)
        out.save(path)


class Leds:
    """Stand-in for tildagonos.leds."""
    count = 19
    def __init__(self):
        self.values = {}
        self.writes = 0
        self.fail = False

    def __setitem__(self, i, rgb):
        if self.fail:
            raise OSError("led failure")
        self.values[i] = rgb

    def write(self):
        self.writes += 1

    def __len__(self):
        return Leds.count


class PatternDisable:
    pass


class PatternEnable:
    pass


def install_leds():
    """Call after install(). Returns (leds, bus)."""
    leds = Leds()
    t = types.ModuleType("tildagonos")
    power = []
    t.tildagonos = types.SimpleNamespace(leds=leds, set_led_power=power.append)
    leds.power = power
    pd = types.ModuleType("system.patterndisplay")
    ev = types.ModuleType("system.patterndisplay.events")
    ev.PatternDisable = PatternDisable
    ev.PatternEnable = PatternEnable
    sys.modules.update({"tildagonos": t, "system.patterndisplay": pd,
                        "system.patterndisplay.events": ev})
    return leds, bus


def remove_leds():
    for n in ("tildagonos", "system.patterndisplay", "system.patterndisplay.events"):
        sys.modules.pop(n, None)
