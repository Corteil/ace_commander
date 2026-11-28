"""The badge's 240 x 240 screens fitted to a wide screen: the CardputerZero's
320 x 170 LCD (always), and the Pi's Elite layout with --wide.

A screen (the title, docked tabs, Options, an in-flight screen: anything drawn
as one whole frame on the 240 canvas) is drawn once into a list (FitCtx in
record mode), then:

- its hint lines (grey text naming buttons, "C: buy   D: sell", "< > screens")
  come out and are joined into one row along the bottom of the LCD;
- the rest is spread to fill the LCD's width and the height left: whole
  pixels of text stay the size they are (Ctx.text_k), only the spacing
  between things grows, so lines stop crowding; where lines of text would
  still overlap (a full screen), its text is made a little smaller, down to
  MIN_TEXT_K, and any still overlapping are moved down out of the way;
- the spread is kept per screen (the mode, tab and hints), and only made
  smaller when something no longer fits, so a screen doesn't jump about.

Flight's own frames (the 3D view, dashboard, pause menu) are drawn as before
(screen_key says which frames are whole screens).
"""
import os
import sys

import pygame

from ctx_pygame import Ctx, relabel

_HOSTS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _HOSTS not in sys.path:
    sys.path.insert(0, _HOSTS)
import fit_core     # noqa: E402  (the placing shared with the Tufty)
from fit_core import (MAX_ASPECT, FLIGHT_MODES, SCREENS, OVERLAP, clear, fits, screen_key,  # noqa: E402,F401
                      fit as _fit, nudges, centre as _centre)

GREY = (179, 179, 191)          # cockpit.GREY, (0.7, 0.7, 0.75), as Ctx stores it
HINT_SIZE = 11                  # the hint row's font size (canvas points, times Ctx.text_k)
GAP = fit_core.GAP
MARGIN = fit_core.MARGIN
MIN_TEXT_K = 1.3                # a full screen's text is made smaller, down to this


class FitCtx(Ctx):
    """A Ctx that can record a frame in canvas units and draw it back fitted."""

    def __init__(self, surface, scale=2):
        super().__init__(surface, scale)
        self.rec = None             # the ops of the frame being recorded, or None
        self.hints = None
        self._sizes = {}            # (text, px) -> rendered (w, h)

    # ---- recording ------------------------------------------------------------
    def start(self):
        self.rec = []
        self.hints = []

    def stop(self):
        ops, hints = self.rec, self.hints
        self.rec = self.hints = None
        return ops, hints

    def _p(self, x, y):
        if self.rec is not None:
            return (x, y)           # canvas units, placed when drawn back
        return Ctx._p(self, x, y)

    def fill(self):
        if self.rec is None:
            return Ctx.fill(self)
        self.rec.append(("fill", self.shape, self.paths, self.col, self.alpha, 0))
        self.shape = None
        self.paths = []
        return self

    def stroke(self):
        if self.rec is None:
            return Ctx.stroke(self)
        self.rec.append(("stroke", self.shape, self.paths, self.col, self.alpha, self.line_width))
        self.shape = None
        self.paths = []
        return self

    def text(self, s):
        if self.rec is None:
            return Ctx.text(self, s)
        s = str(s)
        if self.col == GREY and self.alpha >= 255 and fit_core.is_hint(s):
            self.hints.append(s)
        else:
            self.rec.append(("text", s, self.cur, self.font_size, self.text_align,
                             self.text_baseline, self.col, self.alpha))
        self.paths = []
        return self

    # ---- measuring --------------------------------------------------------------
    def px(self, size, k=None):
        """A canvas font size in pixels, as Ctx.text draws it (base scale), with
        text k times bigger (Ctx.text_k)."""
        return max(6, int(size * self.base * (self.text_k if k is None else k)))

    def text_size(self, s, px):
        k = (s, px)
        wh = self._sizes.get(k)
        if wh is None:
            if len(self._sizes) > 2000:
                self._sizes.clear()
            wh = self._sizes[k] = self._font(px).size(relabel(s, self.labels) if self.labels else s)
        return wh

    def extents(self, ops, k=None):
        """Each thing's anchor in canvas units and how far it reaches round it in
        pixels: (x, y, left, right, up, down, op number or -1), its text k times bigger.
        A background (a fill over most of the canvas) doesn't count."""
        out = []
        for n, op in enumerate(ops):
            if op[0] == "text":
                _, s, (x, y), size, align, base, _, _ = op
                w, h = self.text_size(s, self.px(size, k))
                l = -w / 2.0 if align == self.CENTER else (-w if align == self.RIGHT else 0)
                if base == self.MIDDLE:
                    t = -h / 2.0
                elif base == self.TOP:
                    t = 0
                else:
                    t = -h * 0.8
                out.append((x, y, l, l + w, t, t + h, n))
                continue
            _, shape, paths, _, _, _ = op
            if shape and shape[0] == "rect":
                _, x, y, w, h = shape
                if abs(w) >= 200 and abs(h) >= 200:
                    continue        # the screen's background
                out.append((x, y, 0, 0, 0, 0, -1))
                out.append((x + w, y + h, 0, 0, 0, 0, -1))
            elif shape and shape[0] == "circle":
                _, x, y, r = shape
                out.append((x - r, y - r, 0, 0, 0, 0, -1))
                out.append((x + r, y + r, 0, 0, 0, 0, -1))
            for pts in paths:
                for (x, y) in pts:
                    out.append((x, y, 0, 0, 0, 0, -1))
        return out


class Fitter:
    """Draws whole-frame screens fitted, remembering each screen's placement."""

    def __init__(self):
        self.places = {}            # screen key -> (sx, sy, y0, text k)

    def draw(self, ctx, window, draw, key, labels, base):
        W, H = window.get_size()
        ctx.base = base
        ctx.labels = labels
        ctx.start()
        ctx.ox, ctx.oy, ctx.sx, ctx.s = 0.0, 0.0, base, base
        draw(ctx)
        ops, hints = ctx.stop()
        ops, tabs = fit_core.split_tabs(ops)    # drawn apart: one size on every screen
        top = fit_core.tab_band(base) if tabs else 0
        # the hint row along the bottom (each hint's own wide gaps made two spaces)
        row = GAP.join(_squeeze(h) for h in hints)
        if labels and row:
            row = relabel(row, labels)
        hh = 0
        img = None
        if row:
            px = ctx.px(HINT_SIZE)
            f = ctx._font(px)
            while f.size(row)[0] > W - 2 * MARGIN and px > 7:
                px -= 1
                f = ctx._font(px)
            img = f.render(row, True, GREY)
            hh = img.get_height() + 1
        # the rest, spread over what is left
        area = H - hh - top
        k = (key, row)
        place = self.places.get(k)
        ext = ctx.extents(ops, place[3]) if place is not None else None
        if place is None or not fits(ext, place[0], place[1], place[2], W, area):
            tk = ctx.text_k if place is None else place[3]
            while True:             # the biggest text whose lines don't overlap
                ext = ctx.extents(ops, tk)
                sx, sy, y0 = _fit(ext, base, W, area, MAX_ASPECT)
                if place is not None:   # only ever closer together: no jumping about
                    sx, sy = min(sx, place[0]), min(sy, place[1])
                    y0 = _centre(ext, sy, area)
                if tk <= MIN_TEXT_K + 1e-6 or (clear(ext, sx, sy) and fits(ext, sx, sy, y0, W, area)):
                    break
                tk = max(MIN_TEXT_K, tk - 0.1)
            if len(self.places) > 200:
                self.places.clear()
            place = self.places[k] = (sx, sy, y0, tk)
        sx, sy, y0, tk = place
        nudge = nudges(ctx.extents(ops, tk), sx, sy, y0, area)
        y0 += top
        window.set_clip(None)
        window.fill((0, 0, 0))
        ctx.ox, ctx.oy, ctx.sx, ctx.s = W / 2.0, y0, sx, sy
        keep_k = ctx.text_k
        ctx.text_k = tk * base / sy            # text in pixels at tk, whatever the spread
        try:
            for i, op in enumerate(ops):
                if op[0] == "text":
                    _, s, cur, size, align, bl, col, alpha = op
                    d = nudge.get(i)
                    if d:
                        cur = (cur[0], cur[1] + d / sy)
                    ctx.cur, ctx.font_size, ctx.text_align, ctx.text_baseline = cur, size, align, bl
                    ctx.col, ctx.alpha = col, alpha
                    Ctx.text(ctx, s)
                else:
                    kind, shape, paths, col, alpha, lw = op
                    ctx.shape = shape
                    ctx.paths = [[Ctx._p(ctx, x, y) for (x, y) in pts] for pts in paths]
                    ctx.col, ctx.alpha = col, alpha
                    if kind == "fill":
                        Ctx.fill(ctx)
                    else:
                        ctx.line_width = lw
                        Ctx.stroke(ctx)
            if tabs:                # the tab dots: one size and place on every screen
                kt = fit_core.TAB_K * base
                ctx.ox, ctx.oy, ctx.sx, ctx.s = W / 2.0, fit_core.tab_offset(base), kt, kt
                for op in tabs:
                    ctx.shape, ctx.paths, ctx.col, ctx.alpha = op[1], [], op[3], op[4]
                    Ctx.fill(ctx)
        finally:
            ctx.text_k = keep_k
            ctx.ox, ctx.oy, ctx.sx, ctx.s = W / 2.0, H / 2.0, base, base
        if img is not None:
            window.blit(img, ((W - img.get_width()) // 2, H - img.get_height()))
        return place


def _squeeze(h):
    """A hint with its own wide gaps made two spaces."""
    h = h.strip()
    while "   " in h:
        h = h.replace("   ", "  ")
    return h
