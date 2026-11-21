"""The game's ctx drawing calls, drawn with Badgeware v3's `screen` (Tufty 2350).

The game draws with the Tildagon's ctx: a 240 x 240 canvas, origin in the middle.
Ctx takes the same calls and draws them on the Tufty's 320 x 240 screen with
ctx (0, 0) at pixel (ox, oy), which the layout moves (layout_tufty.py).

Only the calls the game makes: rgb, rgba, begin_path, move_to, line_to,
rectangle, arc, fill, stroke, text, save, restore, and font_size, line_width,
text_align, text_baseline. Badgeware v3 (picovector, bw-1.29): screen.pen =
color.rgb(r, g, b, a); screen.rectangle(x, y, w, h); screen.line(x0, y0, x1, y1);
screen.circle(x, y, r); screen.shape(shape...) for wide lines and filled
outlines (shape.custom with one outline, a list of vec2 points; the Tufty's
v3.1.1 takes neither a list of outlines nor a flat array('f') yet); screen.text(s, x, y) (plain x, y, as
its own apps: a (x, y) point was ignored and the text went to the top left). Its fonts are all pixel fonts,
so each text size picks a font (FONTS, heights measured on the Tufty) at scale 1.
Moved from Corteil/tufty_ace_commarder's ctx_badgeware.py (Badgeware v2) in
build 109 and brought to v3.
"""
import math

try:
    _vec2 = vec2            # Badgeware's (a builtin there)
except NameError:           # a PC (the tests): the stand-in sets it
    _vec2 = None

# (largest game text size, font name): measured line heights on the Tufty,
# 2026-11-21: desert 10, sins 12, badgeware 14, smart 16, badgewaremax 20, ignore 28
FONTS = ((10, "desert"), (12, "sins"), (15, "badgeware"), (18, "smart"), (23, "badgewaremax"),
         (999, "ignore"))


class Ctx:
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"

    def __init__(self, screen, color, shape, font, ox=160, oy=120):
        self.screen = screen
        self.color = color
        self.shape_mod = shape
        self.ox = ox
        self.oy = oy
        self.font_size = 14
        self.line_width = 1.5
        self.text_align = "center"
        self.text_baseline = "middle"
        self._rgba = (255, 255, 255, 255)
        self._pen_dirty = True
        self._path = []
        self._shape = None
        self._cx = 0.0
        self._cy = 0.0
        self._stack = []
        self._fonts = []
        for size, name in FONTS:
            f = getattr(font, name, None)
            if f is not None:
                self._fonts.append((size, f))
        self._font = None

    # state ---------------------------------------------------------------
    def save(self):
        self._stack.append((self._rgba, self.font_size, self.line_width, self.text_align,
                            self.text_baseline))
        return self

    def restore(self):
        if self._stack:
            (self._rgba, self.font_size, self.line_width,
             self.text_align, self.text_baseline) = self._stack.pop()
            self._pen_dirty = True
        return self

    def rgb(self, r, g, b):
        return self.rgba(r, g, b, 1.0)

    def rgba(self, r, g, b, a):
        self._rgba = (int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5),
                      int(a * 255 + 0.5))
        self._pen_dirty = True
        return self

    def _pen(self):
        if self._pen_dirty:
            self.screen.pen = self.color.rgb(*self._rgba)
            self._pen_dirty = False

    # paths ---------------------------------------------------------------
    def begin_path(self):
        self._path = []
        self._shape = None
        return self

    def move_to(self, x, y):
        self._cx = x
        self._cy = y
        self._path.append([x, y])
        return self

    def line_to(self, x, y):
        if not self._path:
            self._path.append([self._cx, self._cy])
        self._path[-1].append(x)
        self._path[-1].append(y)
        self._cx = x
        self._cy = y
        return self

    def rectangle(self, x, y, w, h):
        self._shape = ("rect", x, y, w, h)
        return self

    def arc(self, x, y, r, a0, a1, d):
        self._shape = ("arc", x, y, r, a0, a1)
        return self

    # painting ------------------------------------------------------------
    def fill(self):
        sh = self._shape
        ox = self.ox
        oy = self.oy
        if sh is not None and sh[0] == "rect":
            self._fill_rect(sh[1], sh[2], sh[3], sh[4])
        elif sh is not None and sh[0] == "arc":
            self._pen()
            v = _vec2 if _vec2 is not None else _builtin_vec2()
            self.screen.circle(v(ox + sh[1], oy + sh[2]), int(sh[3] + 0.5))    # as its examples
        else:
            v = _vec2 if _vec2 is not None else _builtin_vec2()
            for sub in self._path:
                if len(sub) >= 6:       # at least a triangle; one outline per shape
                    pts = [v(ox + sub[i], oy + sub[i + 1]) for i in range(0, len(sub), 2)]
                    self._pen()
                    self.screen.shape(self.shape_mod.custom(pts))
        self._shape = None
        self._path = []
        return self

    def _fill_rect(self, x, y, w, h):
        if w < 0:
            x += w
            w = -w
        if h < 0:
            y += h
            h = -h
        x0 = int(self.ox + x + 0.5)
        y0 = int(self.oy + y + 0.5)
        x1 = int(self.ox + x + w + 0.5)
        y1 = int(self.oy + y + h + 0.5)
        if w > 0 and x1 <= x0:      # a thin rectangle (the radar's 1 px axes sit on half
            x1 = x0 + 1             # pixels) must still cover a pixel, not round away
        if h > 0 and y1 <= y0:
            y1 = y0 + 1
        if x1 > x0 and y1 > y0:
            self._pen()
            self.screen.rectangle(x0, y0, x1 - x0, y1 - y0)

    def _seg(self, x0, y0, x1, y1):
        ox = self.ox
        oy = self.oy
        self._pen()
        if self.line_width <= 1.5:
            self.screen.line(int(ox + x0 + 0.5), int(oy + y0 + 0.5),
                             int(ox + x1 + 0.5), int(oy + y1 + 0.5))
        else:
            self.screen.shape(self.shape_mod.line(ox + x0, oy + y0, ox + x1, oy + y1,
                                                  self.line_width))

    def stroke(self):
        sh = self._shape
        if sh is not None and sh[0] == "rect":
            _, x, y, w, h = sh
            self._seg(x, y, x + w, y)
            self._seg(x + w, y, x + w, y + h)
            self._seg(x + w, y + h, x, y + h)
            self._seg(x, y + h, x, y)
        elif sh is not None and sh[0] == "arc":
            _, cx, cy, r, a0, a1 = sh
            full = abs(a1 - a0) >= 2 * math.pi - 1e-6
            n = max(8, min(48, int(r * 0.9)))
            sweep = (2 * math.pi) if full else (a1 - a0)
            px = cx + r * math.cos(a0)
            py = cy + r * math.sin(a0)
            for i in range(1, n + 1):
                a = a0 + sweep * i / n
                qx = cx + r * math.cos(a)
                qy = cy + r * math.sin(a)
                self._seg(px, py, qx, qy)
                px = qx
                py = qy
        for sub in self._path:
            for i in range(0, len(sub) - 2, 2):
                self._seg(sub[i], sub[i + 1], sub[i + 2], sub[i + 3])
        self._shape = None
        self._path = []
        return self

    # text ----------------------------------------------------------------
    def _pick_font(self):
        size = self.font_size
        for top, f in self._fonts:
            if size <= top:
                return f
        return self._fonts[-1][1] if self._fonts else None

    def text(self, s):
        s = str(s)
        f = self._pick_font()
        scr = self.screen
        if f is not None and f is not self._font:
            scr.font = f
            self._font = f
        w, h = scr.measure_text(s)
        x = self.ox + self._cx
        y = self.oy + self._cy
        if self.text_align == "center":
            x -= w / 2
        elif self.text_align == "right":
            x -= w
        if self.text_baseline == "middle":
            y -= h / 2
        elif self.text_baseline in ("bottom", "alphabetic"):
            y -= h
        self._pen()
        scr.text(s, int(x + 0.5), int(y + 0.5))
        self._path = []
        return self


def _builtin_vec2():
    import builtins
    return builtins.vec2
