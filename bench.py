"""Speed test: times different kinds of drawing on the real badge, to show
what makes a frame slow. Results go on screen and to the serial console as
lines starting with BENCH."""

import time

try:
    _us = time.ticks_us
    _diff = time.ticks_diff
except AttributeError:   # off the badge (tests)
    def _us():
        return int(time.perf_counter() * 1000000)

    def _diff(a, b):
        return a - b

FRAMES = 25    # frames timed per test
SKIP = 4       # frames ignored after switching test


def _segments(n, length):
    """n line segments of about the given length, spread over the screen."""
    out = []
    x, y = 17, 43
    for i in range(n):
        x = (x * 73 + 31) % 151
        y = (y * 57 + 11) % 151
        ax, ay = x - 75, y - 75
        if i % 2:
            out.append((ax, ay, ax + length, ay + length * 0.4))
        else:
            out.append((ax, ay, ax + length * 0.4, ay - length))
    return out


SHORT = _segments(60, 30)
LONG = _segments(20, 110)


def _clear(ctx):
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()


def _lines(ctx, segs, width, per_stroke):
    _clear(ctx)
    ctx.rgb(1, 1, 1)
    ctx.line_width = width
    i = 0
    n = len(segs)
    while i < n:
        ctx.begin_path()
        for ax, ay, bx, by in segs[i:i + per_stroke]:
            ctx.move_to(ax, ay)
            ctx.line_to(bx, by)
        ctx.stroke()
        i += per_stroke


def _text(ctx, n):
    _clear(ctx)
    ctx.font_size = 13
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(1, 1, 1)
    for i in range(n):
        ctx.move_to(0, -50 + i * 20).text("W3  1240")


def t_nothing(ctx):
    pass


def t_clear(ctx):
    _clear(ctx)


def t_lines(ctx):
    _lines(ctx, SHORT, 1.5, 60)


def t_lines_thin(ctx):
    _lines(ctx, SHORT, 1.0, 60)


def t_lines_strokes(ctx):
    _lines(ctx, SHORT, 1.5, 10)


def t_lines_long(ctx):
    _lines(ctx, LONG, 1.5, 20)


def t_dots(ctx):
    _clear(ctx)
    ctx.rgb(1, 1, 1)
    for ax, ay, bx, by in SHORT:
        ctx.rectangle(ax, ay, 2, 2).fill()


def t_bars(ctx):
    _clear(ctx)
    ctx.rgb(0.3, 1, 0.4)
    for x in (-112, -103, 97, 106):
        ctx.rectangle(x, -30, 6, 60).fill()
        ctx.rectangle(x, -10, 6, 40).fill()


def t_text1(ctx):
    _text(ctx, 1)


def t_text6(ctx):
    _text(ctx, 6)


def t_ring(ctx):
    _clear(ctx)
    ctx.line_width = 6
    ctx.rgb(1, 0.25, 0.2).arc(0, 0, 116, 0, 6.2832, 0).stroke()


def t_disc_small(ctx):     # a far sun
    _clear(ctx)
    ctx.rgb(1, 0.8, 0.25).arc(30, -40, 20, 0, 6.2832, 0).fill()


def t_disc_big(ctx):       # a near sun
    _clear(ctx)
    ctx.rgb(1, 0.8, 0.25).arc(0, 0, 100, 0, 6.2832, 0).fill()


def t_circle(ctx):         # a planet
    _clear(ctx)
    ctx.line_width = 1.5
    ctx.rgb(0.35, 0.6, 1).arc(0, 0, 80, 0, 6.2832, 0).stroke()


TESTS = (
    ("nothing", t_nothing),
    ("clear", t_clear),
    ("60 lines", t_lines),
    ("60 thin", t_lines_thin),
    ("60 in 6 strokes", t_lines_strokes),
    ("20 long lines", t_lines_long),
    ("60 dots", t_dots),
    ("8 bars", t_bars),
    ("1 text", t_text1),
    ("6 texts", t_text6),
    ("ring", t_ring),
    ("disc r20", t_disc_small),
    ("disc r100", t_disc_big),
    ("circle r80", t_circle),
)


class Bench:
    def __init__(self):
        self.i = 0
        self.n = 0
        self.total = 0.0     # whole-frame time
        self.drawn = 0.0     # time inside the drawing calls
        self.results = []
        self.done = False
        print("BENCH start (frame ms / of which drawing calls ms)")

    def step(self, delta):
        """Call once per frame with the frame time in ms."""
        if self.done:
            return
        self.n += 1
        if self.n > SKIP:
            self.total += delta
        if self.n >= SKIP + FRAMES:
            name = TESTS[self.i][0]
            avg = self.total / FRAMES
            drawn = self.drawn / FRAMES
            self.results.append((name, avg, drawn))
            print("BENCH %s: %.1f / %.1f" % (name, avg, drawn))
            self.i += 1
            self.n = 0
            self.total = 0.0
            self.drawn = 0.0
            if self.i >= len(TESTS):
                self.done = True
                print("BENCH done")

    def draw(self, ctx):
        if not self.done:
            t0 = _us()
            TESTS[self.i][1](ctx)
            if self.n >= SKIP:
                self.drawn += _diff(_us(), t0) / 1000.0
            return
        _clear(ctx)
        ctx.font_size = 11
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.rgb(1, 1, 1)
        step = 11
        y = -(len(self.results) - 1) * step / 2.0
        for name, avg, drawn in self.results:
            ctx.move_to(0, y).text("%s  %d / %d" % (name, avg, drawn))
            y += step
