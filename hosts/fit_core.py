"""Fitting the badge's 240 x 240 screens to a wider screen: the part every host
shares (the Pi and the CardputerZero through fit_pygame.py, the Tufty through its
host). Plain Python that runs on MicroPython too: no re, no f-strings.

A whole-frame screen (screen_key: the title, docked tabs, Options, the in-flight
screens) is drawn into a Recorder in canvas units; its grey hint lines (is_hint)
come out into one row along the bottom; the rest is spread over the screen's width
and the height left (fit), text keeping its pixel size, at most `aspect` times
wider than tall (the game's config.wide, so ships and charts keep their shape);
lines of text that would still overlap are nudged down (nudges). A Placer keeps
each screen's placement and only ever brings it closer, so a screen doesn't jump.
replay() draws the recorded frame through any ctx with the standard calls.
"""
import math

GREY = (0.7, 0.7, 0.75)         # cockpit.GREY: hints are drawn in it
MARGIN = 3                      # pixels kept clear round the edge
MAX_X = 2.4                     # spread across at most this many times the plain scale
MAX_Y = 1.7                     # and down at most this many times
MAX_ASPECT = 1.5                # and across at most this many times more than down
OVERLAP = 0.25                  # lines of text may overlap by this much of their height
GAP = "    "                    # between hints in the row
FLIGHT_MODES = ("flight", "launch", "docking", "mlaunch")
SCREENS = ("status", "inventory", "market", "chart", "data")   # ace.SCREENS: whole-frame in flight
_LETTERS = "ABCDEF"
_JOINS = (", ", " or ", " / ", "/")


def screen_key(app):
    """Which whole-frame screen the game shows, as a key to remember its placement
    by, or None: flight's own frames (the 3D view and dashboard, the pause menu
    over them, the tunnels) and the speed test."""
    mode = getattr(app, "mode", "")
    if mode == "flight":
        if getattr(app, "fsub", None) in SCREENS and not getattr(app, "paused", False):
            return (mode, app.fsub)
        return None
    if mode in FLIGHT_MODES or mode == "bench":
        return None
    dock = getattr(app, "dock", None)
    return (mode, dock.name() if mode == "docked" and dock is not None else None)


def is_hint(s):
    """A hint naming buttons: a badge letter (or a list of them) before a colon
    ("C: buy", "C or F: back", "C, D or F: back"), or "< >", "up / down",
    "UP/DOWN", "stick:"."""
    if "< >" in s or "up / down" in s or "up/down" in s or "UP/DOWN" in s or "stick:" in s:
        return True
    n = len(s)
    for i in range(n):
        if s[i] not in _LETTERS or (i > 0 and s[i - 1].isalpha()) or (i > 0 and s[i - 1].isdigit()):
            continue
        j = i + 1
        while True:
            if j < n and s[j] == ":":
                return True
            for w in _JOINS:
                if s[j:j + len(w)] == w and j + len(w) < n and s[j + len(w)] in _LETTERS:
                    j += len(w) + 1
                    break
            else:
                break
    return False


def is_hint_op(op):
    """A recorded text op that is a hint (grey, opaque)."""
    return op[0] == "text" and op[7] == GREY and op[8] >= 1 and is_hint(op[1])


class Recorder:
    """Stands in for a ctx while a screen draws: every call the game makes
    (rgb, rgba, rectangle, arc, begin_path, move_to, line_to, fill, stroke, text,
    save, restore; font_size, text_align, text_baseline, line_width) is kept, in
    canvas units. ops: ("fill" | "stroke", shape, paths, rgb, alpha, line_width)
    and ("text", s, x, y, size, align, baseline, rgb, alpha)."""
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"
    TOP = "top"
    BOTTOM = "bottom"
    ALPHABETIC = "alphabetic"

    def __init__(self):
        self.labels = None
        self.a11y = None
        self.start()

    def start(self):
        self.ops = []
        self.rgb_ = (1, 1, 1)
        self.alpha = 1
        self.font_size = 14
        self.text_align = "center"
        self.text_baseline = "middle"
        self.line_width = 1.5
        self.paths = []
        self.shape = None
        self.cx = 0
        self.cy = 0
        self.stack = []

    def save(self):
        self.stack.append((self.rgb_, self.alpha, self.font_size, self.text_align,
                           self.text_baseline, self.line_width))
        return self

    def restore(self):
        if self.stack:
            (self.rgb_, self.alpha, self.font_size, self.text_align,
             self.text_baseline, self.line_width) = self.stack.pop()
        return self

    def rgb(self, r, g, b):
        self.rgb_ = (r, g, b)
        self.alpha = 1
        return self

    def rgba(self, r, g, b, a):
        self.rgb_ = (r, g, b)
        self.alpha = a
        return self

    def begin_path(self):
        self.paths = []
        self.shape = None
        return self

    def move_to(self, x, y):
        self.cx = x
        self.cy = y
        self.paths.append([(x, y)])
        return self

    def line_to(self, x, y):
        if not self.paths:
            self.paths.append([(self.cx, self.cy)])
        self.paths[-1].append((x, y))
        self.cx = x
        self.cy = y
        return self

    def close_path(self):
        if self.paths and len(self.paths[-1]) > 1:
            self.paths[-1].append(self.paths[-1][0])
        return self

    def rectangle(self, x, y, w, h):
        self.shape = ("rect", x, y, w, h)
        return self

    def arc(self, x, y, r, a0, a1, d=0):
        self.shape = ("arc", x, y, r, a0, a1)
        return self

    def fill(self):
        self.ops.append(("fill", self.shape, self.paths, self.rgb_, self.alpha, 0))
        self.shape = None
        self.paths = []
        return self

    def stroke(self):
        self.ops.append(("stroke", self.shape, self.paths, self.rgb_, self.alpha, self.line_width))
        self.shape = None
        self.paths = []
        return self

    def text(self, s):
        self.ops.append(("text", str(s), self.cx, self.cy, self.font_size, self.text_align,
                         self.text_baseline, self.rgb_, self.alpha))
        self.paths = []
        return self


def extents(ops, measure):
    """Each thing's anchor in canvas units and how far it reaches round it in
    pixels: (x, y, left, right, up, down, op number or -1). measure(s, size) gives
    a text's (w, h) in pixels. A background (a fill over most of the canvas)
    doesn't count; nor do hints."""
    out = []
    for n, op in enumerate(ops):
        if op[0] == "text":
            _, s, x, y, size, align, base, _, _ = op
            w, h = measure(s, size)
            l = -w / 2.0 if align == "center" else (-w if align == "right" else 0)
            if base == "middle":
                t = -h / 2.0
            elif base == "top":
                t = 0
            else:
                t = -h * 0.8
            out.append((x, y, l, l + w, t, t + h, n))
            continue
        shape, paths = op[1], op[2]
        if shape is not None and shape[0] == "rect":
            _, x, y, w, h = shape
            if abs(w) >= 200 and abs(h) >= 200:
                continue            # the screen's background
            out.append((x, y, 0, 0, 0, 0, -1))
            out.append((x + w, y + h, 0, 0, 0, 0, -1))
        elif shape is not None and shape[0] == "arc":
            x, y, r = shape[1], shape[2], shape[3]
            out.append((x - r, y - r, 0, 0, 0, 0, -1))
            out.append((x + r, y + r, 0, 0, 0, 0, -1))
        for pts in paths:
            for p in pts:
                out.append((p[0], p[1], 0, 0, 0, 0, -1))
    return out


def fit(ext, base, w, h, aspect=MAX_ASPECT):
    """The scales across and down and the canvas's 0 in pixels (sx, sy, y0) that put
    the things in ext inside a w x h area, centred across on x = 0."""
    if not ext:
        return base, base, h / 2.0
    half = w / 2.0 - MARGIN
    sx = base * MAX_X
    for e in ext:
        x = e[0]
        if x > 0.5:
            sx = min(sx, (half - e[3]) / x)
        elif x < -0.5:
            sx = min(sx, (half + e[2]) / -x)
    sx = max(base, sx)
    ymin = min(e[1] for e in ext)
    ymax = max(e[1] for e in ext)
    room = h - 2 * MARGIN
    sy = base * MAX_Y
    if ymax > ymin:
        for _ in range(4):          # the text's own height doesn't scale: settle on sy
            top = min(e[1] * sy + e[4] for e in ext)
            bot = max(e[1] * sy + e[5] for e in ext)
            if bot - top <= room + 0.5:
                break
            fixed = (bot - top) - (ymax - ymin) * sy
            sy = max(base * 0.8, (room - fixed) / (ymax - ymin))
    sy = min(sy, base * MAX_Y)
    sx = max(min(sx, sy * aspect), min(base, sy))
    return sx, sy, centre(ext, sy, h)


def centre(ext, sy, area):
    """The canvas's 0 in pixels that centres ext down an area that high."""
    if not ext:
        return area / 2.0
    top = min(e[1] * sy + e[4] for e in ext)
    bot = max(e[1] * sy + e[5] for e in ext)
    return MARGIN + (area - 2 * MARGIN - (bot - top)) / 2.0 - top


def fits(ext, sx, sy, y0, w, h):
    """Whether everything in ext lands inside w x h with this placement."""
    for e in ext:
        X = w / 2.0 + e[0] * sx
        Y = y0 + e[1] * sy
        if X + e[2] < -1 or X + e[3] > w + 1 or Y + e[4] < -1 or Y + e[5] > h + 1:
            return False
    return True


def clear(ext, sx, sy):
    """Whether no two lines of text overlap (by more than OVERLAP of their height)."""
    texts = sorted([e for e in ext if e[6] >= 0], key=lambda e: e[1])
    for i in range(len(texts)):
        ax, ay, al, ar, at, ad, _ = texts[i]
        for b in texts[i + 1:]:
            bx, by, bl, br, bt, bd, _ = b
            if by <= ay:
                continue            # side by side on one line: columns
            if ax * sx + al >= bx * sx + br or bx * sx + bl >= ax * sx + ar:
                continue            # not above one another
            if (ay * sy + ad) - (by * sy + bt) > OVERLAP * min(ad - at, bd - bt):
                return False
    return True


def nudges(ext, sx, sy, y0, bottom):
    """Pixels to move lines of text down by so none overlaps the one above it
    (more than OVERLAP), keyed by op number; nothing goes past bottom."""
    texts = sorted([(y0 + e[1] * sy + e[4], y0 + e[1] * sy + e[5], e[0] * sx + e[2],
                     e[0] * sx + e[3], e[6]) for e in ext if e[6] >= 0])
    out = {}
    placed = []
    for top, bot, left, right, n in texts:
        d = 0.0
        for pt, pb, pl, pr in placed:
            if left >= pr or pl >= right or pt >= top + d:
                continue
            lap = pb - (top + d)
            room = OVERLAP * min(pb - pt, bot - top)
            if lap > room:
                d += lap - room
        d = min(d, max(0.0, bottom - bot))
        if d:
            out[n] = d
        placed.append((top + d, bot + d, left, right))
    return out


def hint_parts(ops):
    """The hints of a recorded screen, each with its wide gaps made two spaces."""
    parts = []
    for op in ops:
        if is_hint_op(op):
            s = op[1].strip()
            while "   " in s:
                s = s.replace("   ", "  ")
            parts.append(s)
    return parts


def hint_row(ops, labels=None, relabel=None):
    """The hints of a recorded screen joined into one row, named by labels if given."""
    row = GAP.join(hint_parts(ops))
    if row and labels and relabel is not None:
        row = relabel(row, labels)
    return row


class Placer:
    """Each screen's placement, kept and only ever brought closer."""

    def __init__(self, aspect=MAX_ASPECT):
        self.aspect = aspect
        self.places = {}

    def place(self, key, ext, base, w, h):
        p = self.places.get(key)
        if p is not None and fits(ext, p[0], p[1], p[2], w, h):
            return p
        sx, sy, y0 = fit(ext, base, w, h, self.aspect)
        if p is not None:
            sx = min(sx, p[0])
            sy = min(sy, p[1])
            y0 = centre(ext, sy, h)
        if len(self.places) > 100:
            self.places.clear()
        p = self.places[key] = (sx, sy, y0)
        return p


def replay(ctx, ops, kx, ky, dy, nudge=None, skip_hints=True):
    """Draw recorded ops through ctx (any ctx with the standard calls), each canvas
    point (x, y) moved to (x * kx, y * ky + dy) on the ctx's own canvas; text keeps
    its size; arcs become outlines (ovals when kx != ky). nudge: {op number: canvas
    units down}."""
    for n, op in enumerate(ops):
        kind = op[0]
        if kind == "text":
            if skip_hints and is_hint_op(op):
                continue
            _, s, x, y, size, align, base, rgb, alpha = op
            if nudge:
                y += nudge.get(n, 0)
            ctx.font_size = size
            ctx.text_align = align
            ctx.text_baseline = base
            ctx.rgba(rgb[0], rgb[1], rgb[2], alpha)
            ctx.move_to(x * kx, y * ky + dy).text(s)
            continue
        _, shape, paths, rgb, alpha, lw = op
        ctx.rgba(rgb[0], rgb[1], rgb[2], alpha)
        if kind == "stroke":
            ctx.line_width = lw
        ctx.begin_path()
        drawn = False
        if shape is not None and shape[0] == "rect":
            _, x, y, w, h = shape
            ctx.rectangle(x * kx, y * ky + dy, w * kx, h * ky)
            drawn = True
        elif shape is not None and shape[0] == "arc":
            _, x, y, r, a0, a1 = shape
            full = abs(a1 - a0) >= 2 * math.pi - 1e-6
            steps = 40
            sweep = 2 * math.pi if full else a1 - a0
            for i in range(steps + 1):
                a = a0 + sweep * i / steps
                px = (x + r * math.cos(a)) * kx
                py = (y + r * math.sin(a)) * ky + dy
                if i == 0:
                    ctx.move_to(px, py)
                else:
                    ctx.line_to(px, py)
            drawn = True
        for pts in paths:
            for i, p in enumerate(pts):
                if i == 0:
                    ctx.move_to(p[0] * kx, p[1] * ky + dy)
                else:
                    ctx.line_to(p[0] * kx, p[1] * ky + dy)
            drawn = True
        if drawn:
            if kind == "fill":
                ctx.fill()
            else:
                ctx.stroke()
