"""The mission messages shown on docking (see missions.py): INCOMING MESSAGE
for two seconds, then the text as one column you scroll through, with the
Constrictor turning above its briefing as in the original (BRIEF, PAUSE).
Joystick up / down scrolls; C goes down a screenful, and at the end goes on
(it also skips the two seconds); F skips the rest.
"""
import math

from . import cockpit, describe

INCOMING_TIME = 2.0     # seconds of INCOMING MESSAGE, as the original's BRIS
SIZE = 13               # text size (10 was too small to read on the badge)
LINE = 15               # pixels from one line of text to the next
PARA = 5                # and the extra space between paragraphs
PAGE_GAP = 14           # and between the parts the original showed as separate screens
CHAR_W = SIZE * 0.62    # about how wide a character of that size is
VIEW_TOP = -66          # text is shown between these heights on the screen
VIEW_BOTTOM = 66
WIDTH = 22              # characters to a line: they fit anywhere in the view
SCROLL_SPEED = 130.0    # pixels a second while the joystick is held
SHIP_H = 64             # room for the ship above the text
SHIP_TOP_SPACE = 22     # the ship goes once its centre is scrolled this near the view's top
SHIP_Z = 580.0          # how far away the ship is (it comes in from SHIP_FAR)
SHIP_FAR = 6000.0
SHIP_IN = 1.2           # seconds it takes to come in
SPIN = (0.9, 0.55)      # radians a second it rolls and pitches


def _lines(words, width=WIDTH):
    """A paragraph's lines, each at most width characters."""
    out = []
    line = ""
    for w in words.split():
        if line and len(line) + 1 + len(w) <= width:
            line += " " + w
            continue
        if line:
            out.append(line)
        line = w[:width]
    if line:
        out.append(line)
    return out


def layout(pages, ship=False):
    """Pages ((text, ship) from describe.mission_pages) as one column:
    [(line, y), ...] with y from the top of the column, and the last line's
    y. ship: leave room for the ship at the top."""
    out = []
    y = SHIP_H if ship else 0
    first = True
    for words, _ in pages:
        if not first:
            y += PAGE_GAP
        first = False
        for p in words.split("\n"):
            if not p:               # an empty line between paragraphs
                y += LINE
                continue
            for line in _lines(p):
                out.append((line, y))
                y += LINE
            y += PARA
    return out, max(0, y - PARA - LINE)


class Briefing:
    def __init__(self, game_data, token, cmdr_name, galaxy, ship_bp=None, pages=None):
        """pages: the message itself, (text, shows the ship) for each part,
        in place of a mission's (token)."""
        if pages is None:
            pages = describe.mission_pages(game_data, token, cmdr_name, galaxy)
        self.ship = ship_bp if pages and pages[0][1] else None
        self.lines, last = layout(pages, self.ship is not None)
        self.most = max(0.0, float(last - (VIEW_BOTTOM - VIEW_TOP)))  # furthest it scrolls
        self.scroll = 0.0
        self.incoming = True
        self.t = 0.0
        self.ship_t = 0.0
        self.done = not self.lines

    def tick(self, dt, move=0):
        """move: -1 joystick up (back), 1 down (on), 0 neither."""
        self.t += dt
        self.ship_t += dt
        if self.incoming:
            if self.t >= INCOMING_TIME:
                self.incoming = False
            return
        if move:
            self.scroll = max(0.0, min(self.most, self.scroll + move * SCROLL_SPEED * dt))

    def at_end(self):
        return self.scroll >= self.most

    def next(self):
        """C: past INCOMING MESSAGE, down a screenful, or at the end, done."""
        if self.incoming:
            self.incoming = False
        elif self.at_end():
            self.done = True
        else:
            self.scroll = min(self.most, self.scroll + (VIEW_BOTTOM - VIEW_TOP) - LINE)

    def skip(self):
        self.done = True

    def draw(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        if self.incoming or self.done:
            if int(self.t * 3) % 3 != 2:        # flashing gently
                text(ctx, "INCOMING MESSAGE", 0, 0, 16, cockpit.WHITE)
            return
        top = VIEW_TOP - self.scroll
        ship_y = top + SHIP_H // 2 - 6
        if self.ship is not None and ship_y >= VIEW_TOP + SHIP_TOP_SPACE:
            self._draw_ship(ctx, ship_y)    # until it would stick out above the view
        for line, y in self.lines:
            sy = top + y
            if sy < VIEW_TOP - 1:
                continue
            if sy > VIEW_BOTTOM + 1:
                break
            text(ctx, line, 0, int(sy), SIZE, cockpit.WHITE)
        # more above / below
        if self.scroll > 0:
            ctx.rgb(*cockpit.GREY).rectangle(-8, VIEW_TOP - 12, 16, 2).fill()
        end = self.at_end()
        if not end:
            ctx.rgb(*cockpit.GREY).rectangle(-8, VIEW_BOTTOM + 10, 16, 2).fill()
        text(ctx, "C: continue" if end else "stick: scroll  C: more", 0, 86, 11, cockpit.GREY)
        if not end:
            text(ctx, "F: skip", 0, 100, 10, cockpit.GREY)

    def _draw_ship(self, ctx, y):
        from .docked import _Show
        o = _Show(self.ship)
        k = min(1.0, self.ship_t / SHIP_IN)
        z = SHIP_FAR + (SHIP_Z - SHIP_FAR) * (1 - (1 - k) * (1 - k))
        o.z = z
        o.y = -y * z / cockpit.FOCAL
        a = self.ship_t * SPIN[0]
        b = self.ship_t * SPIN[1]
        ca, sa = math.cos(a), math.sin(a)
        cb, sb = math.cos(b), math.sin(b)
        # rolled by a about the nose, then pitched by b
        o.m = [ca, sa, 0.0, -sa * cb, ca * cb, sb, sa * sb, -ca * sb, cb]
        cockpit.draw_ship(ctx, o, cockpit.WHITE, 3, True)
