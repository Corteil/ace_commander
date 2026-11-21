"""Ace Commander on a Tufty 2350 (Badgeware v3): the game, unchanged, on the
Tufty's platform (platform_tufty), controls (controls_tufty), flight layout
(layout_tufty, dash_tufty) and drawing (ctx_tufty). Build 109: this replaces
Corteil/tufty_ace_commarder's vendored copy of the game, its patches and its
firmware stand-ins.

The app folder (/system/apps/ace_commander, made by build_tufty.py) holds
these files and the game as the package ace_commander. Its __init__.py calls
start(globals()) and hands update() to Badgeware's run(). Saves and options go
in DATA_DIR (the app's folder can't be written from MicroPython).
"""
import os
import time

import controls_tufty
import platform_tufty
from ctx_tufty import Ctx
from layout_tufty import TuftyLayout

try:
    _ms = time.ticks_ms
    _diff = time.ticks_diff
except AttributeError:      # a PC (the tests)
    def _ms():
        return int(time.perf_counter() * 1000)

    def _diff(a, b):
        return a - b

GAME = "ace_commander"          # the game's package in the app folder
# the loading screen imports these one a frame, as the badge's app.py does (each
# after the ones it needs; letters first, to draw the name with)
STEPS = ("letters", "original_ships", "ship_data", "game_data", "config", "layout", "content", "commander", "galaxy",
         "market", "ships", "equipment", "rules", "game", "cockpit", "chart", "find", "screens",
         "title", "viewer", "describe", "missions", "briefing", "docked", "controls", "ace")
OPTIONAL = ("ship_data", "game_data")   # made from your own copy of Elite: may be missing
GREEN = (0.3, 1, 0.4)
GREY = (0.6, 0.6, 0.6)
DIM = (0.15, 0.3, 0.18)
# the loading screen's ship, tumbling: one of the game's own designs (Brian), the
# one you start in (the Kestrel, in Elite's Cobra Mk III role), from original_ships
LOAD_SHIP = "COBRA MK III"
SHIP_RGB = (0.3, 0.85, 1.0)
SHIP_Y = -18            # its middle, on the 240 canvas (between the name and the bar)
SHIP_SIZE = 32.0        # half its span on the screen, about
BAR_Y = 42              # the bar, and the module being loaded under it
LOAD_HOLD = 3000        # ms the loading screen stays at least, to see the ship (Brian)
DATA_DIR = "/state/ace_commander"
SCREEN_W, SCREEN_H = 320, 240
# Qw/ST Pad: I2C0 on GP4 / GP5 at 0x21 (G1, 2026-11-19). Never GP6 / GP7: BUTTON_A
# is GPIO7, and opening I2C there dropped the Tufty off USB.
PAD_SDA, PAD_SCL, PAD_ADDR = 4, 5, 0x21


def _module(name):
    return __import__(GAME + "." + name, None, None, ("x",))


def _mkdirs(path):
    part = ""
    for p in path.strip("/").split("/"):
        part += "/" + p
        try:
            os.mkdir(part)
        except OSError:
            pass        # there already


class Host:
    def __init__(self, screen, badge, color, shape, font, rect, buttons, pad=None,
                 data_dir=DATA_DIR):
        """buttons: {"A": BUTTON_A, "B": ..., "C": ..., "UP": ..., "DOWN": ...}
        (Badgeware's constants). pad: a qwstpad.QwSTPad, or None."""
        self.screen = screen
        self.badge = badge
        self.color = color
        self.rect = rect
        self.buttons = buttons
        self.pad = pad
        self.data_dir = data_dir
        self.feed = controls_tufty.Feed()
        self.ctx = Ctx(screen, color, shape, font, SCREEN_W // 2, SCREEN_H // 2)
        self.app = None         # the game, once the loading screen has imported it
        self.done = 0           # modules imported so far
        self.error = None       # why loading failed, if it did
        self.letters = None
        self.ship = None        # the loading screen's ship (an original_ships entry)
        self.loaded = None      # the game, loaded, while the screen is held (LOAD_HOLD)
        self.t_load = _ms()
        self.full = rect(0, 0, SCREEN_W, SCREEN_H)
        self.black = color.rgb(0, 0, 0)     # (color.black came out blue on v3: G1)
        self.last = _ms()
        self.last_level = -1.0
        self.frames = 0

    def _held(self):
        keys = set()
        b = self.badge
        for name, const in self.buttons.items():
            if b.held(const):
                keys.add(controls_tufty.TUFTY_MAP[name])
        if self.pad is not None:
            try:
                for k, v in self.pad.read_buttons().items():
                    if v and k in controls_tufty.PAD_MAP:
                        keys.add(controls_tufty.PAD_MAP[k])
            except Exception:
                self.pad = None             # unplugged: carry on with the Tufty's buttons
        return keys

    def _lights(self):
        """The case lights as bright as the brightest LED the game lit."""
        level = 0
        for rgb in platform_tufty.LEDS:
            for v in rgb:
                if v > level:
                    level = v
        level = level / 255.0
        if level != self.last_level:
            self.last_level = level
            try:
                self.badge.caselights(level)
            except Exception:
                pass

    # ---- the loading screen ---------------------------------------------
    def _load_step(self):
        """Import the next module (STEPS); after config and cockpit, set up
        what the game reads as it loads; after the last, start the game."""
        name = STEPS[self.done]
        try:
            m = _module(name)
        except ImportError:
            if name not in OPTIONAL:
                raise
            m = None
        if name == "letters":
            self.letters = m
        elif name == "original_ships" and m is not None:
            for e in m.SHIPS:
                if e[0] == LOAD_SHIP:
                    self.ship = e
                    break
        elif name == "config":
            _mkdirs(self.data_dir)
            m.data_dir = self.data_dir
            m.platform = platform_tufty
            m.input = self.feed.attach
        elif name == "cockpit":
            _module("config").layout = TuftyLayout(self.screen, self.rect, m)
        self.done += 1
        if self.done == len(STEPS):
            self.ace = _module("ace")
            self.loaded = self.ace.AceCommander()     # started once LOAD_HOLD is up
            print("LOADED in %d ms" % _diff(_ms(), self.t_load))

    def _draw_loading(self):
        """The name where the title screen has it, a bar, the module being
        loaded and LOADING where the menu line will be (as the badge's app.py)."""
        s = self.screen
        s.clip = self.full
        s.pen = self.black
        s.clear()
        ctx = self.ctx
        ctx.ox = SCREEN_W // 2
        ctx.oy = SCREEN_H // 2
        if self.letters is not None:
            self.letters.draw_name(ctx)
        if self.ship is not None:
            self._draw_ship(ctx, _diff(_ms(), self.t_load) / 1000.0)
        n = len(STEPS)
        ctx.rgb(*DIM).rectangle(-70, BAR_Y, 140, 6).fill()
        ctx.rgb(*GREEN).rectangle(-70, BAR_Y, 140 * self.done // n, 6).fill()
        if self.error:
            _text(ctx, "LOAD FAILED", 0, 60, 14, (1, 0.3, 0.2))
            _text(ctx, self.error[:40], 0, 84, 10, GREY)
        else:
            if self.done < n:
                _text(ctx, STEPS[self.done], 0, BAR_Y + 16, 10, GREY)
            _text(ctx, "LOADING", 0, 84, 13, GREEN)

    def _draw_ship(self, ctx, t):
        """The loading screen's ship as a wireframe, turning about two axes."""
        import math
        e = self.ship
        verts = e[1]
        span = 1.0
        for v in verts:
            for c in v:
                if c > span:
                    span = c
                elif -c > span:
                    span = -c
        k = SHIP_SIZE / span
        ca, sa = math.cos(t * 0.9), math.sin(t * 0.9)       # turning round
        cb, sb = math.cos(0.45), math.sin(0.45)             # tipped towards you
        pts = []
        for x, y, z in verts:
            x, z = x * ca + z * sa, -x * sa + z * ca
            y, z = y * cb - z * sb, y * sb + z * cb
            d = 1.0 + z * k / 400.0                         # a little perspective
            pts.append((x * k / d, SHIP_Y - y * k / d))
        ctx.rgb(*SHIP_RGB)
        ctx.begin_path()
        for edge in e[2]:
            a = pts[edge[0]]
            b = pts[edge[1]]
            ctx.move_to(a[0], a[1])
            ctx.line_to(b[0], b[1])
        ctx.stroke()
        title = e[5] if len(e) > 5 else e[0]
        _text(ctx, title, 0, SHIP_Y + SHIP_SIZE + 8, 10, GREY)

    def update(self):
        """One frame, for Badgeware's run(update): None to carry on, True to
        leave (the game's QUIT or F on the title screen)."""
        if self.app is None:        # still loading: a module a frame
            if self.error is None and self.loaded is None:
                try:
                    self._load_step()
                except Exception as e:
                    self.error = "%s: %s" % (STEPS[self.done], e)
                    print("LOAD FAILED", self.error)
            if self.loaded is not None and _diff(_ms(), self.t_load) >= LOAD_HOLD:
                self.app = self.loaded      # held long enough: the game takes over
                self.last = _ms()
            if self.app is None:
                self._draw_loading()
                return None
        now = _ms()
        ms = _diff(now, self.last)
        self.last = now
        if ms < 1:
            ms = 1
        elif ms > 100:
            ms = 100
        self.feed.set_held(self._held())
        self.app.update(ms)
        if self.app.platform.quit:
            return True
        s = self.screen
        s.clip = self.full
        s.pen = self.black
        s.clear()
        ctx = self.ctx
        ctx.ox = SCREEN_W // 2
        ctx.oy = SCREEN_H // 2
        self.app.draw(ctx)
        self._lights()
        self.frames += 1
        return None

    def on_exit(self):
        """HOME pressed (Badgeware calls this, then resets to the launcher)."""
        try:
            self.badge.caselights(0)
        except Exception:
            pass


def _text(ctx, s, x, y, size, rgb):
    ctx.font_size = size
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


def _pad():
    try:
        from machine import I2C, Pin
        import qwstpad
        i2c = I2C(0, sda=Pin(PAD_SDA), scl=Pin(PAD_SCL), freq=400000)
        if PAD_ADDR not in i2c.scan():
            return None
        return qwstpad.QwSTPad(i2c, PAD_ADDR)
    except Exception:
        return None


def start(ns):
    """ns: the app's globals. Badgeware's names come from there or builtins
    (it sets builtins.BUTTON_A and so on: MicroPython keeps those in an override
    table that a plain name finds but getattr(builtins, ...) doesn't, so eval)."""

    def get(name):
        if name in ns:
            return ns[name]
        return eval(name)
    try:
        get("badge").mode(get("HIRES"))     # 320 x 240
    except Exception:
        pass
    buttons = {"A": get("BUTTON_A"), "B": get("BUTTON_B"), "C": get("BUTTON_C"),
               "UP": get("BUTTON_UP"), "DOWN": get("BUTTON_DOWN")}
    return Host(get("screen"), get("badge"), get("color"), get("shape"), get("font"),
                get("rect"), buttons, _pad())
