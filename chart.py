"""The local chart: the star systems round the one you are in, a cursor to
pick one with, and a ring showing how far the fuel in the tank will take you.

It is only on screen while the game is paused, so it can afford a few pieces
of text and some float maths.
"""
from . import cockpit

# The galaxy chart is twice as wide as it is tall for the same distance, so a
# step across is 5 pixels and a step down is 2.5. That makes a light year
# 12.5 pixels in every direction, and a full tank (7 light years) 87.5.
SX2 = 10            # pixels per chart unit across, times 2
SY2 = 5             # pixels per chart unit down, times 2
PX_PER_FUEL = 1.25  # pixels per tenth of a light year
EDGE = 100          # systems further than this from the centre are off the chart
CURSOR_SPEED = 75.0  # pixels per second while the joystick is held


class Chart:
    def __init__(self, gal, here, fuel):
        self.gal = gal
        self.here = here
        self.fuel = fuel
        x0 = gal.xs[here]
        y0 = gal.ys[here]
        # every system on the chart: [x, y, index, distance], in pixels from
        # the centre and tenths of a light year
        self.dots = []
        for i in range(len(gal.xs)):
            px = (gal.xs[i] - x0) * SX2 // 2
            py = (gal.ys[i] - y0) * SY2 // 2
            if px * px + py * py <= EDGE * EDGE:
                self.dots.append((px, py, i, gal.distance(here, i)))
        self.cx = 0.0       # the cursor
        self.cy = 0.0
        self.sel = None     # the dot nearest the cursor
        self.info = None    # its galaxy.System
        self._select()

    def _select(self):
        best = None
        best_d = 1 << 30
        for dot in self.dots:
            dx = dot[0] - self.cx
            dy = dot[1] - self.cy
            d = dx * dx + dy * dy
            if d < best_d or (d == best_d and dot[2] == self.here):
                best_d = d
                best = dot
        if best is not self.sel:
            self.sel = best
            self.info = self.gal.system(best[2]) if best is not None else None

    def move(self, jx, jy, dt):
        """Move the cursor: jx and jy are -1..1, jy negative for up."""
        if not jx and not jy:
            return
        if dt > 0.1:
            dt = 0.1
        x = self.cx + jx * CURSOR_SPEED * dt
        y = self.cy + jy * CURSOR_SPEED * dt
        if x * x + y * y <= EDGE * EDGE:
            self.cx = x
            self.cy = y
            self._select()

    def target(self):
        """(system index, distance) of the selected system if a jump can
        reach it, else None."""
        s = self.sel
        if s is None or s[2] == self.here or not 0 < s[3] <= self.fuel:
            return None
        return s[2], s[3]

    def draw(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.line_width = 1.5
        if self.fuel > 0:       # how far a jump can go
            ctx.rgb(*cockpit.DIM).arc(0, 0, self.fuel * PX_PER_FUEL, 0, cockpit.TAU, 0).stroke()
        fuel = self.fuel
        for px, py, i, d in self.dots:
            if i == self.here:
                continue
            if 0 < d <= fuel:
                ctx.rgb(*cockpit.WHITE).rectangle(px - 1, py - 1, 3, 3).fill()
            else:
                ctx.rgb(*cockpit.GREY).rectangle(px, py, 2, 2).fill()
        # you are here
        ctx.rgb(*cockpit.GREEN)
        ctx.rectangle(-4, 0, 9, 1).fill()
        ctx.rectangle(0, -4, 1, 9).fill()

        s = self.sel
        if s is not None:
            ok = self.target() is not None
            here = s[2] == self.here
            rgb = cockpit.GREEN if ok or here else cockpit.RED
            ctx.rgb(*rgb)       # a box round the selected system
            x = s[0] - 5
            y = s[1] - 5
            ctx.rectangle(x, y, 11, 1).fill()
            ctx.rectangle(x, y + 10, 11, 1).fill()
            ctx.rectangle(x, y, 1, 11).fill()
            ctx.rectangle(x + 10, y, 1, 11).fill()
            text(ctx, self.info.name, 0, -100, 15, cockpit.WHITE)
            if here:
                text(ctx, "YOU ARE HERE", 0, 97, 12, cockpit.GREEN)
            elif ok:
                text(ctx, "%d.%d LY   C: JUMP" % (s[3] // 10, s[3] % 10), 0, 97, 12, cockpit.GREEN)
            elif s[3] == 0:
                text(ctx, "TOO CLOSE TO JUMP", 0, 97, 12, cockpit.RED)
            else:
                text(ctx, "%d.%d LY   TOO FAR" % (s[3] // 10, s[3] % 10), 0, 97, 12, cockpit.RED)
        text(ctx, "FUEL %d.%d" % (fuel // 10, fuel % 10), 0, 110, 10, cockpit.YELLOW)

        # the cursor: a cross with a gap in the middle
        x = int(self.cx)
        y = int(self.cy)
        ctx.rgb(*cockpit.YELLOW)
        ctx.rectangle(x - 9, y, 5, 1).fill()
        ctx.rectangle(x + 5, y, 5, 1).fill()
        ctx.rectangle(x, y - 9, 1, 5).fill()
        ctx.rectangle(x, y + 5, 1, 5).fill()
