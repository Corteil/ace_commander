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
        _mkdirs(data_dir)
        config = _module("config")
        config.data_dir = data_dir
        config.platform = platform_tufty
        self.feed = controls_tufty.Feed()
        config.input = self.feed.attach
        ck = _module("cockpit")
        config.layout = TuftyLayout(screen, rect, ck)
        self.ace = _module("ace")
        self.app = self.ace.AceCommander()
        self.ctx = Ctx(screen, color, shape, font, SCREEN_W // 2, SCREEN_H // 2)
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

    def update(self):
        """One frame, for Badgeware's run(update): None to carry on, True to
        leave (the game's QUIT or F on the title screen)."""
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
    """ns: the app's globals. Badgeware's names come from there or builtins."""
    import builtins

    def get(name):
        if name in ns:
            return ns[name]
        return getattr(builtins, name)
    try:
        get("badge").mode(get("HIRES"))     # 320 x 240
    except Exception:
        pass
    buttons = {"A": get("BUTTON_A"), "B": get("BUTTON_B"), "C": get("BUTTON_C"),
               "UP": get("BUTTON_UP"), "DOWN": get("BUTTON_DOWN")}
    return Host(get("screen"), get("badge"), get("color"), get("shape"), get("font"),
                get("rect"), buttons, _pad())
