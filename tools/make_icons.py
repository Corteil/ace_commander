#!/usr/bin/env python3
"""Make the app icons from one of the game's own ships, the Kestrel (Brian,
2026-11-21: the ship on the Tufty's loading screen): dark space with a few
stars, the ship from just above behind, its hull filled dark blue under bright
cyan edges, in a light rounded frame.

    python3 tools/make_icons.py

writes hosts/tufty/app/icon.png (24 x 24 pixel art, as the Tufty's own apps'
icons) and hosts/pi/icon.png (256 x 256, drawn at 4 times and scaled down,
for the Pi's desktop and menu entries). Needs Pillow.
"""
import math
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import original_ships   # noqa: E402

SHIP = "COBRA MK III"       # its role: the game's own design for it is the Kestrel
TURN, TIP = math.pi, 0.75   # seen from behind, from a little above
SPACE = (8, 10, 20, 255)
FRAME = (235, 240, 250, 255)
STAR = (150, 150, 170, 255)
EDGE = (90, 225, 255, 255)
HULL = (20, 70, 110, 255)
STARS = ((4, 4), (19, 5), (5, 19), (19, 18), (11, 3), (14, 20))     # on 24 x 24


def _hull(pts):
    pts = sorted(set(pts))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and cross(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and cross(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def icon(size, line=1, frame=1, radius=3, star=1, scale=10.0, dy=0.5):
    """The icon at size x size; line, frame and star are pixel widths."""
    e = [s for s in original_ships.SHIPS if s[0] == SHIP][0]
    verts, edges = e[1], e[2]
    span = max(abs(c) for v in verts for c in v)
    k = size / 24.0
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=SPACE, outline=FRAME,
                        width=frame)
    for x, y in STARS:
        d.rectangle((x * k, y * k, x * k + star - 1, y * k + star - 1), fill=STAR)
    ca, sa = math.cos(TURN), math.sin(TURN)
    cb, sb = math.cos(TIP), math.sin(TIP)
    pts = []
    for x, y, z in verts:
        x, z = x * ca + z * sa, -x * sa + z * ca
        y, z = y * cb - z * sb, y * sb + z * cb
        f = scale * k / span
        pts.append((size / 2 - 0.5 + x * f, size / 2 - 0.5 + dy * k - y * f))
    d.polygon(_hull(pts), fill=HULL)
    for a, b, *_ in edges:
        d.line((pts[a], pts[b]), fill=EDGE, width=line)
    return im


def main():
    tufty = os.path.join(REPO, "hosts", "tufty", "app", "icon.png")
    icon(24).save(tufty)
    big = icon(1024, line=10, frame=24, radius=120, star=24)
    pi = os.path.join(REPO, "hosts", "pi", "icon.png")
    big.resize((256, 256), Image.LANCZOS).save(pi)
    print("wrote", tufty, "and", pi)


if __name__ == "__main__":
    main()
