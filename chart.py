"""The two charts: the local chart (the star systems round the one you are
in, with a ring for how far the fuel in the tank will take you) and the
galactic chart (all 256 systems). Each has a cursor that selects the system
nearest to it.

They are only on screen while the game is paused or docked, so they can
afford a few pieces of text and some float maths.
"""
from . import cockpit, config

# The galaxy chart is twice as wide as it is tall for the same distance, so on
# the local chart a step across is 5 pixels and a step down is 2.5. That makes
# a light year 12.5 pixels in every direction, and a full tank (7 light years)
# 87.5.
SX2 = 10            # pixels per chart unit across, times 2
SY2 = 5             # pixels per chart unit down, times 2
PX_PER_FUEL = 1.25  # pixels per tenth of a light year
EDGE = 100          # systems further than this from the centre are off the chart
CURSOR_SPEED = 75.0  # pixels per second while the joystick is held

# The galactic chart squeezes 256 x 256 chart units into 204 x 102 pixels, so
# a light year is 2 pixels and a full tank 14.
GX5 = 4             # pixels per chart unit across, times 5
GY5 = 2             # pixels per chart unit down, times 5
G_PX_PER_FUEL = 0.2
G_HALF_W = 102
G_HALF_H = 51
G_CURSOR_SPEED = 45.0


def _ly(d):
    return "%d.%d LY" % (d // 10, d % 10)


class _Cursor:
    """What both charts share: dots, a cursor and the dot nearest to it.
    Each dot is (x, y, system index, distance), in pixels from the centre of
    the screen and tenths of a light year from where you are."""

    speed = CURSOR_SPEED

    def __init__(self, gal, here, fuel, sel, verb):
        self.gal = gal
        self.here = here
        self.fuel = fuel
        self.verb = verb    # what C does with a system in range: "JUMP" or "TARGET"
        self.marked = None  # in flight: the target, labelled TARGET when selected
        self.active = True  # the joystick moves the cursor (docked: only after C)
        self.docked = False # on a docked tab (the hints: before C the joystick changes tabs)
        self.dots = []
        self.sel = None     # the dot nearest the cursor
        self.info = None    # its galaxy.System
        self.cx = 0.0
        self.cy = 0.0
        self.kx = 1             # across, things are drawn this many times narrower (the
                                # local chart on a wide screen: the host stretches it back)

    def _start(self, sel):
        """Put the cursor on system sel if it is on the chart, else on you."""
        for dot in self.dots:
            if dot[2] == sel:
                self.cx = float(dot[0])
                self.cy = float(dot[1])
                break
        else:
            for dot in self.dots:
                if dot[2] == self.here:
                    self.cx = float(dot[0])
                    self.cy = float(dot[1])
        self._select()

    def _select(self):
        # whole numbers: on the badge every float result is a new heap object
        cx = int(self.cx)
        cy = int(self.cy)
        here = self.here
        best = None
        best_d = 1 << 30
        for dot in self.dots:
            dx = dot[0] - cx
            dy = dot[1] - cy
            d = dx * dx + dy * dy
            if d < best_d or (d == best_d and dot[2] == here):
                best_d = d
                best = dot
        if best is not self.sel:
            self.sel = best
            self.info = self.gal.system(best[2]) if best is not None else None

    def _inside(self, x, y):
        return x * x + y * y <= EDGE * EDGE

    def move(self, jx, jy, dt):
        """Move the cursor: jx and jy are -1..1, jy negative for up."""
        if not jx and not jy:
            return
        if dt > 0.1:
            dt = 0.1
        x = self.cx + jx * self.speed * dt
        y = self.cy + jy * self.speed * dt
        if self._inside(x, y):
            self.cx = x
            self.cy = y
            self._select()

    def goto(self, i):
        """Put the cursor on system i and select it (a search found it: build
        88), even where dots overlap."""
        for dot in self.dots:
            if dot[2] == i:
                self.cx = float(dot[0])
                self.cy = float(dot[1])
                self.sel = dot
                self.info = self.gal.system(i)
                return True
        return False

    def picked(self):
        """The selected system's index, or None."""
        return self.sel[2] if self.sel is not None else None

    def target(self):
        """(system index, distance) of the selected system if a jump can
        reach it, else None."""
        s = self.sel
        if s is None or s[2] == self.here or not 0 < s[3] <= self.fuel:
            return None
        return s[2], s[3]

    def _box(self, ctx, x, y, h, rgb):
        k = self.kx
        hx = h if k == 1 else h * k
        ctx.rgb(*rgb)
        ctx.rectangle(x - hx, y - h, 2 * hx + 1, 1).fill()
        ctx.rectangle(x - hx, y + h, 2 * hx + 1, 1).fill()
        ctx.rectangle(x - hx, y - h, 1, 2 * h + 1).fill()
        ctx.rectangle(x + hx, y - h, 1, 2 * h + 1).fill()

    def _cursor(self, ctx, gap, arm):
        """A cross with a gap in the middle: yellow while the joystick moves
        it, grey while (docked) it changes tabs."""
        x = int(self.cx)
        y = int(self.cy)
        ctx.rgb(*(cockpit.YELLOW if self.active else cockpit.GREY))
        k = self.kx
        if k != 1:                  # drawn narrower across (a wide screen's local chart)
            x = x * k
            ctx.rectangle(x - (gap + arm) * k, y, arm * k, 1).fill()
            ctx.rectangle(x + (gap + 1) * k, y, arm * k, 1).fill()
            ctx.rectangle(x, y - gap - arm, 1, arm).fill()
            ctx.rectangle(x, y + gap + 1, 1, arm).fill()
            return
        ctx.rectangle(x - gap - arm, y, arm, 1).fill()
        ctx.rectangle(x + gap + 1, y, arm, 1).fill()
        ctx.rectangle(x, y - gap - arm, 1, arm).fill()
        ctx.rectangle(x, y + gap + 1, 1, arm).fill()

    def _you(self, ctx, x, y, arm):
        ctx.rgb(*cockpit.GREEN)
        ax = arm if self.kx == 1 else arm * self.kx
        ctx.rectangle(x - ax, y, 2 * ax + 1, 1).fill()
        ctx.rectangle(x, y - arm, 1, 2 * arm + 1).fill()

    def _texts(self, ctx, name_y, line_y, fuel_y):
        """The selected system and how far it is, and your range. No hints:
        while the joystick changes tabs (docked, before C) the name has
        arrows round it, "< LAVE >"."""
        text = cockpit.text
        s = self.sel
        lx, la = 0, 0               # the line under the name: centred, RANGE below it
        if config.wide:             # a wide screen: that line ending left of the middle,
            lx, la = -6, 1          # RANGE starting right of it (Brian)
        if s is not None:
            name = self.info.name if self.active else "< %s >" % self.info.name
            text(ctx, name, 0, name_y, 15, cockpit.WHITE)
            mark = "TARGET  " if s[2] == self.marked and s[2] != self.here else ""
            if s[2] == self.here:
                text(ctx, "YOU ARE HERE", lx, line_y, 12, cockpit.GREEN, la)
            elif self.target() is not None:
                text(ctx, mark + _ly(s[3]), lx, line_y, 12, cockpit.GREEN, la)
            elif s[3] == 0:
                text(ctx, "TOO CLOSE TO JUMP", lx, line_y, 12, cockpit.RED, la)
            elif mark:          # the longest line: smaller, to fit low on the local chart
                text(ctx, "TARGET %s TOO FAR" % _ly(s[3]), lx, line_y, 10, cockpit.RED, la)
            else:
                text(ctx, "%s  TOO FAR" % _ly(s[3]), lx, line_y, 12, cockpit.RED, la)
        if config.wide and s is not None:
            text(ctx, "RANGE %s" % _ly(self.fuel), 6, line_y, 10, cockpit.YELLOW, -1)
        else:
            text(ctx, "RANGE %s" % _ly(self.fuel), 0, fuel_y, 10, cockpit.YELLOW)

    def _hint(self, ctx, y):
        """A hint line, only where the screen's corners show (config.more_hints:
        the Tufty, the Pi's Elite layout); the host names its own buttons."""
        if self.docked and not self.active:
            s = "C: cursor   < > screens   F: status"
        elif hasattr(self, "number"):
            s = "C: target  D: data  B: find  F: back"
        else:
            s = "C: target   D: data   F: back"
        cockpit.text(ctx, s, 0, y, 10, cockpit.GREY)


class Chart(_Cursor):
    """The local chart, centred on where you are: a system (here), or a
    chart position between systems (at, in witchspace; here is then None)."""

    def __init__(self, gal, here, fuel, sel=None, verb="JUMP", at=None):
        if at is not None:
            here = None
            x0, y0 = at
        else:
            x0 = gal.xs[here]
            y0 = gal.ys[here]
        _Cursor.__init__(self, gal, here, fuel, sel, verb)
        # a wide screen (config.wide, Brian: "the range should be round but the star field
        # should fill out the sides"): systems out to wide times further left and right,
        # all drawn wide times narrower, so the host's stretch leaves the range round
        self.wide = config.wide or 0
        if self.wide:
            self.kx = 1.0 / self.wide
        for i in range(len(gal.xs)):
            px = (gal.xs[i] - x0) * SX2 // 2
            py = (gal.ys[i] - y0) * SY2 // 2
            if self._inside(px, py):
                d = gal.distance(here, i) if at is None else gal.distance_xy(x0, y0, i)
                self.dots.append((px, py, i, d))
        self._start(sel)

    def _inside(self, x, y):
        if self.wide:           # the whole width of a wide screen
            return -EDGE * self.wide <= x <= EDGE * self.wide and -EDGE <= y <= EDGE
        return x * x + y * y <= EDGE * EDGE

    def draw(self, ctx):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.line_width = 1.5
        k = self.kx
        if self.fuel > 0:       # how far a jump can go
            r = self.fuel * PX_PER_FUEL
            ctx.rgb(*cockpit.DIM)
            if k == 1:
                ctx.arc(0, 0, r, 0, cockpit.TAU, 0).stroke()
            else:               # an oval wide times narrower: round once stretched
                import math
                ctx.begin_path()
                n = 48
                for j in range(n + 1):
                    a = cockpit.TAU * j / n
                    (ctx.move_to if j == 0 else ctx.line_to)(r * k * math.cos(a), r * math.sin(a))
                ctx.stroke()
        fuel = self.fuel
        for px, py, i, d in self.dots:
            if i == self.here:
                continue
            if k != 1:
                px = px * k
            if 0 < d <= fuel:
                ctx.rgb(*cockpit.WHITE).rectangle(px - 1, py - 1, 3, 3).fill()
            else:
                ctx.rgb(*cockpit.GREY).rectangle(px, py, 2, 2).fill()
        self._you(ctx, 0, 0, 4)
        s = self.sel
        if s is not None:
            ok = self.target() is not None or s[2] == self.here
            self._box(ctx, s[0] * k if k != 1 else s[0], s[1], 5, cockpit.GREEN if ok else cockpit.RED)
        if config.more_hints:
            self._texts(ctx, -100, 88, 100)
            self._hint(ctx, 113)
        else:
            self._texts(ctx, -100, 97, 110)
        self._cursor(ctx, 4, 5)


class GalChart(_Cursor):
    """The galactic chart: all 256 systems, in a band across the middle."""

    speed = G_CURSOR_SPEED

    def __init__(self, gal, here, fuel, sel=None, verb="TARGET", number=1):
        _Cursor.__init__(self, gal, here, fuel, sel, verb)
        self.number = number    # which galaxy, 1 to 8, for the title
        for i in range(len(gal.xs)):
            self.dots.append(((gal.xs[i] - 128) * GX5 // 5, (gal.ys[i] - 128) * GY5 // 5,
                              i, gal.distance(here, i)))
        self._start(sel)

    def _inside(self, x, y):
        return -G_HALF_W <= x <= G_HALF_W and -G_HALF_H <= y <= G_HALF_H

    def draw(self, ctx):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.line_width = 1.5
        ctx.rgb(*cockpit.DIM)       # the edge of the chart, top and bottom
        ctx.rectangle(-G_HALF_W - 3, -G_HALF_H - 4, 2 * G_HALF_W + 7, 1).fill()
        ctx.rectangle(-G_HALF_W - 3, G_HALF_H + 4, 2 * G_HALF_W + 7, 1).fill()
        fuel = self.fuel
        ctx.rgb(*cockpit.GREY)
        for px, py, i, d in self.dots:
            if not 0 < d <= fuel:
                ctx.rectangle(px, py, 1.5, 1.5).fill()
        ctx.rgb(*cockpit.WHITE)
        for px, py, i, d in self.dots:
            if 0 < d <= fuel:
                ctx.rectangle(px, py, 2, 2).fill()
        here = self.dots[self.here]
        if fuel > 0:
            ctx.rgb(*cockpit.DIM).arc(here[0], here[1], fuel * G_PX_PER_FUEL,
                                      0, cockpit.TAU, 0).stroke()
        self._you(ctx, here[0], here[1], 3)
        s = self.sel
        if s is not None:
            ok = self.target() is not None or s[2] == self.here
            self._box(ctx, s[0], s[1], 4, cockpit.GREEN if ok else cockpit.RED)
        cockpit.text(ctx, "GALAXY %d" % self.number, 0, -96, 10, cockpit.GREY)
        self._texts(ctx, -76, 74, 92)
        if config.more_hints:
            self._hint(ctx, 108)
        self._cursor(ctx, 3, 4)
