"""The game's ctx drawing calls on a pygame Surface (Raspberry Pi host).

The game draws a 240 x 240 screen with the origin at its centre, colours as
0-1 floats, through about a dozen calls (rgb, rgba, rectangle, arc, move_to,
line_to, begin_path, close_path, fill, stroke, text, save, restore) and four
attributes (font_size, text_align, text_baseline, line_width). This draws them
at scale S (S = 2: 480 x 480) straight onto the surface, so lines and text are
sharp rather than a scaled-up 240 bitmap.
"""
import math

import re

import pygame

FONT = "DejaVuSans"     # a free font close to the badge's in width


class Ctx:
    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"
    TOP = "top"
    BOTTOM = "bottom"
    ALPHABETIC = "alphabetic"

    def __init__(self, surface, scale=2):
        self.surf = surface
        self.s = scale
        self.ox = surface.get_width() / 2.0
        self.oy = surface.get_height() / 2.0
        self.col = (255, 255, 255)
        self.alpha = 255
        self.font_size = 14
        self.text_align = self.CENTER
        self.text_baseline = self.MIDDLE
        self.line_width = 1.5
        self.paths = []         # sub-paths, each a list of screen points
        self.shape = None       # ("rect", ...) or ("circle", ...): the last shape added
        self.cur = (0.0, 0.0)
        self._stack = []
        self._fonts = {}
        self._texts = {}        # rendered text, kept: the same strings come every frame
        self.a11y = None        # the firmware's screen-reader hook: none here
        self.labels = None      # {"C": "A", ...}: the hints name a pad's buttons (relabel)
        self.line_k = scale     # line widths: times this (the Elite layout draws thinner lines)

    # ---- state ------------------------------------------------------------
    def save(self):
        self._stack.append((self.col, self.alpha, self.font_size, self.text_align,
                            self.text_baseline, self.line_width))
        return self

    def restore(self):
        if self._stack:
            (self.col, self.alpha, self.font_size, self.text_align,
             self.text_baseline, self.line_width) = self._stack.pop()
        return self

    def rgb(self, r, g, b):
        self.col = (_c(r), _c(g), _c(b))
        self.alpha = 255
        return self

    def rgba(self, r, g, b, a):
        self.col = (_c(r), _c(g), _c(b))
        self.alpha = _c(a)
        return self

    def _p(self, x, y):
        return (self.ox + x * self.s, self.oy + y * self.s)

    # ---- paths and shapes ---------------------------------------------------
    def begin_path(self):
        self.paths = []
        self.shape = None
        return self

    def move_to(self, x, y):
        self.cur = (x, y)
        self.paths.append([self._p(x, y)])
        return self

    def line_to(self, x, y):
        if not self.paths:
            self.paths.append([self._p(*self.cur)])
        self.paths[-1].append(self._p(x, y))
        self.cur = (x, y)
        return self

    def close_path(self):
        if self.paths and len(self.paths[-1]) > 1:
            self.paths[-1].append(self.paths[-1][0])
        return self

    def rectangle(self, x, y, w, h):
        self.shape = ("rect", x, y, w, h)
        return self

    def arc(self, x, y, r, a0, a1, direction=0):
        if abs(a1 - a0) >= 2 * math.pi - 1e-6:
            self.shape = ("circle", x, y, r)
            return self
        n = max(4, int(abs(a1 - a0) * r * self.s / 6))
        pts = [self._p(x + r * math.cos(a0 + (a1 - a0) * i / n),
                       y + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]
        self.paths.append(pts)
        self.cur = (x + r * math.cos(a1), y + r * math.sin(a1))
        return self

    def _target(self):
        """Where to draw: the surface, or a see-through layer for a colour
        with alpha (blended on in _done)."""
        if self.alpha >= 255:
            return self.surf
        layer = pygame.Surface(self.surf.get_size(), pygame.SRCALPHA)
        return layer

    def _done(self, target):
        if target is not self.surf:
            target.set_alpha(self.alpha)
            self.surf.blit(target, (0, 0))
        self.shape = None
        self.paths = []
        return self

    def fill(self):
        t = self._target()
        col = self.col
        sh = self.shape
        if sh and sh[0] == "rect":
            _, x, y, w, h = sh
            (ax, ay), (bx, by) = self._p(x, y), self._p(x + w, y + h)
            r = pygame.Rect(round(min(ax, bx)), round(min(ay, by)),
                            max(1, round(abs(bx - ax))), max(1, round(abs(by - ay))))
            t.fill(col, r)
        elif sh and sh[0] == "circle":
            _, x, y, r = sh
            pygame.draw.circle(t, col, self._p(x, y), max(1, r * self.s))
        for pts in self.paths:
            if len(pts) > 2:
                pygame.draw.polygon(t, col, pts)
        return self._done(t)

    def stroke(self):
        t = self._target()
        col = self.col
        w = max(1, round(self.line_width * self.line_k))
        sh = self.shape
        if sh and sh[0] == "rect":
            _, x, y, rw, rh = sh
            (ax, ay), (bx, by) = self._p(x, y), self._p(x + rw, y + rh)
            pygame.draw.rect(t, col, pygame.Rect(round(min(ax, bx)), round(min(ay, by)),
                                                 round(abs(bx - ax)), round(abs(by - ay))), w)
        elif sh and sh[0] == "circle":
            _, x, y, r = sh
            pygame.draw.circle(t, col, self._p(x, y), max(1, r * self.s), w)
        for pts in self.paths:
            if len(pts) > 1:
                pygame.draw.lines(t, col, False, pts, w)
        return self._done(t)

    # ---- text -------------------------------------------------------------
    def _font(self, size):
        f = self._fonts.get(size)
        if f is None:
            path = pygame.font.match_font(FONT) or None
            f = self._fonts[size] = pygame.font.Font(path, size)
        return f

    def text(self, s):
        s = str(s)
        if self.labels:
            s = relabel(s, self.labels)
        size = max(6, int(self.font_size * self.s))
        key = (s, size, self.col)
        img = self._texts.get(key)
        if img is None:
            if len(self._texts) > 400:
                self._texts.clear()
            img = self._texts[key] = self._font(size).render(s, True, self.col)
        x, y = self._p(*self.cur)
        w, h = img.get_size()
        if self.text_align == self.CENTER:
            x -= w / 2
        elif self.text_align == self.RIGHT:
            x -= w
        if self.text_baseline == self.MIDDLE:
            y -= h / 2
        elif self.text_baseline in (self.BOTTOM, self.ALPHABETIC):
            y -= h * 0.8
        if self.alpha < 255:
            img = img.copy()
            img.set_alpha(self.alpha)
        self.surf.blit(img, (round(x), round(y)))
        self.paths = []
        return self


# a hint's button letters: "C: buy", "C or F: back", "C, D or F: back to chart",
# "< > or C: change" (a lone capital A-F, or a list of them, then a colon)
_HINT = re.compile(r"(?<![A-Za-z0-9])[A-F](?:(?:, | or | / |/)[A-F])*(?=:)")
_LETTER = re.compile(r"[A-F]")
_relabelled = {}


def relabel(s, labels):
    """s with the badge's button letters in its hints named as labels has them
    ("C: buy   D: sell" -> "A: buy   X: sell"); other text is left alone."""
    key = (s, id(labels))
    out = _relabelled.get(key)
    if out is None:
        if len(_relabelled) > 2000:
            _relabelled.clear()
        out = _HINT.sub(lambda m: _LETTER.sub(lambda l: labels.get(l.group(0), l.group(0)),
                                              m.group(0)), s)
        _relabelled[key] = out
    return out


def _c(v):
    v = int(v * 255 + 0.5)
    return 0 if v < 0 else 255 if v > 255 else v
