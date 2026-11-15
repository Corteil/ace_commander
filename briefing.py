"""The mission messages shown on docking (see missions.py): INCOMING MESSAGE
for two seconds, then the text a screen at a time, with the Constrictor
turning above its briefing as in the original (BRIEF, PAUSE). C goes on to
the next screen (and skips the two seconds), F skips to the end.
"""
import math

from . import cockpit, describe

INCOMING_TIME = 2.0     # seconds of INCOMING MESSAGE, as the original's BRIS
SIZE = 14               # text size (10 was too small to read on the badge)
LINE = 16               # pixels from one line of text to the next
PARA = 5                # and the extra space between paragraphs
CHAR_W = SIZE * 0.62    # about how wide a character of that size is
TOP = -84               # where the text starts on a screen without the ship
SHIP_TOP = -38          # and with it
BOTTOM = 72             # the last line's lowest place
SHIP_Y = 76             # the ship's centre: this many pixels above the middle
SHIP_Z = 580.0          # and this far away (it comes in from SHIP_FAR)
SHIP_FAR = 6000.0
SHIP_IN = 1.2           # seconds it takes to come in
SPIN = (0.9, 0.55)      # radians a second it rolls and pitches


def _width(y):
    """Characters that fit on a line at height y of the round screen."""
    h = abs(y) + 6
    if h >= 114:
        return 10
    return max(10, int(2 * math.sqrt(114 * 114 - h * h) / CHAR_W))


def _lines(words, y):
    """A paragraph's lines from height y down: [(line, y), ...]."""
    out = []
    line = ""
    for w in words.split():
        if line and len(line) + 1 + len(w) <= _width(y):
            line += " " + w
            continue
        if line:
            out.append((line, y))
            y += LINE
        line = w[:_width(y)]
    if line:
        out.append((line, y))
    return out


def layout(pages):
    """Split pages ((text, ship) from describe.mission_pages) into screens
    that fit: each a (ship, [(line, y), ...]). A paragraph that doesn't fit
    in what is left of a screen starts the next one (and is split only if
    it is longer than a whole screen). The ship is shown on the first
    screen of its page only, leaving the rest more room."""
    screens = []
    for words, ship in pages:
        show = ship
        lines = []
        y = SHIP_TOP if show else TOP
        for p in words.split("\n"):
            if not p:               # an empty line between paragraphs
                y += LINE
                continue
            got = _lines(p, y)
            if got[-1][1] > BOTTOM and lines:       # on to the next screen
                screens.append((show, lines))
                show = False
                lines = []
                y = TOP
                got = _lines(p, y)
            while got[-1][1] > BOTTOM:              # longer than a whole screen
                fit = [l for l in got if l[1] <= BOTTOM]
                screens.append((show, lines + fit))
                show = False
                lines = []
                rest = " ".join(l[0] for l in got[len(fit):])
                got = _lines(rest, TOP)
            lines += got
            y = got[-1][1] + LINE + PARA
        if lines:
            screens.append((show, lines))
    return screens


class Briefing:
    def __init__(self, game_data, token, cmdr_name, galaxy, ship_bp=None):
        pages = describe.mission_pages(game_data, token, cmdr_name, galaxy)
        self.screens = layout(pages)
        self.ship = ship_bp
        self.at = -1            # -1: INCOMING MESSAGE
        self.t = 0.0
        self.ship_t = 0.0
        self.done = not self.screens

    def tick(self, dt):
        self.t += dt
        self.ship_t += dt
        if self.at < 0 and self.t >= INCOMING_TIME:
            self.next()

    def next(self):
        self.at += 1
        self.t = 0.0
        if self.at >= len(self.screens):
            self.done = True

    def skip(self):
        self.done = True

    def draw(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        if self.at < 0 or self.done:
            if int(self.t * 3) % 3 != 2:        # flashing gently
                text(ctx, "INCOMING MESSAGE", 0, 0, 16, cockpit.WHITE)
            return
        ship, lines = self.screens[self.at]
        if ship and self.ship is not None:
            self._draw_ship(ctx)
        for line, y in lines:
            text(ctx, line, 0, y, SIZE, cockpit.WHITE)
        last = self.at == len(self.screens) - 1
        text(ctx, "C: continue" if last else "C: more   F: skip", 0, 94, 11, cockpit.GREY)

    def _draw_ship(self, ctx):
        from .docked import _Show
        o = _Show(self.ship)
        k = min(1.0, self.ship_t / SHIP_IN)
        z = SHIP_FAR + (SHIP_Z - SHIP_FAR) * (1 - (1 - k) * (1 - k))
        o.z = z
        o.y = SHIP_Y * z / cockpit.FOCAL
        a = self.ship_t * SPIN[0]
        b = self.ship_t * SPIN[1]
        ca, sa = math.cos(a), math.sin(a)
        cb, sb = math.cos(b), math.sin(b)
        # rolled by a about the nose, then pitched by b
        o.m = [ca, sa, 0.0, -sa * cb, ca * cb, sb, sa * sb, -ca * sb, cb]
        cockpit.draw_ship(ctx, o, cockpit.WHITE, 3, True)
