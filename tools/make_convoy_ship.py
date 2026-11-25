#!/usr/bin/env python3
"""Make convoy_ship.py: the big freighter that multiplayer's convoy modes protect
(duel.py, plans/MULTIPLAYER.md). An original design, so it is there whichever
content the game uses (Elite's or its own): a wedge of a bow with a bridge on top,
three cargo containers on a spine, and an engine block with two exhausts. About
seven times a Cobra Mk III's length.

Usage:  python3 tools/make_convoy_ship.py [-o convoy_ship.py]
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shipmaker import HIDES_ALWAYS, HIDES_NEVER, Ship


def _mirror(points):
    out = []
    for x, y, z in points:
        out.append((x, y, z))
        if x:
            out.append((-x, y, z))
    return out


def _box(s, x0, x1, y0, y1, z0, z1):
    return s.hull([(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)])


def hauler():
    s = Ship("CONVOY", "HAULER")
    # the bow: a blunt wedge, the bridge a ridge on its back
    s.part(HIDES_ALWAYS)
    s.hull(_mirror([(36, -28, 430), (36, 18, 420), (120, -56, 290), (120, 56, 290),
                    (48, 96, 300), (40, 80, 360)]))
    # three containers, wider than the spine
    for z0, z1 in ((160, 270), (30, 140), (-100, 10)):
        s.part(HIDES_ALWAYS)
        _box(s, -126, 126, -52, 52, z0, z1)
    # the spine they hang on, seen in the gaps
    s.part(HIDES_NEVER)
    _box(s, -30, 30, -26, 26, -210, 290)
    # the engine block, narrowing to the back, two exhausts on it
    s.part(HIDES_ALWAYS)
    faces = s.hull(_mirror([(104, -48, -210), (104, 48, -210), (80, -36, -330), (80, 36, -330)]))
    back = [f for f in faces if s.faces[f][1][2] < 0][0]
    for cx in (-44, 44):
        c = [s.vertex((cx + dx, dy, -330)) for dx, dy in ((-24, -18), (24, -18), (24, 18), (-24, 18))]
        for k in range(4):
            s.line(c[k], c[(k + 1) % 4], back)
    size = max(math.sqrt(x * x + y * y + z * z) for x, y, z in s.verts)
    area = int((size * 0.45) ** 2) // 25 * 25      # hit anywhere along its length
    gun = max(range(len(s.verts)), key=lambda i: s.verts[i][2])
    # (canisters, hit area, gun, explosions, bounty, visibility, energy, speed, laser, missiles)
    return s.blueprint((0, area, gun, 14, 0, 120, 255, 6, 0, 0))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-o", "--output", default="convoy_ship.py")
    args = ap.parse_args()
    e = hauler()
    out = ['"""The convoy\'s freighter (multiplayer: duel.py), made by tools/make_convoy_ship.py.',
           "",
           "An original design, free to use with the game: (role, vertices, edges, face",
           "normals, stats, title, parts), see tools/shipmaker.py.",
           '"""',
           "SHIP = %r" % (e,)]
    with open(args.output, "w") as f:
        f.write("\n".join(out) + "\n")
    print("Wrote %s: %d vertices, %d edges, %d parts" % (args.output, len(e[1]), len(e[2]),
                                                       len(e[6]) if len(e) > 6 else 0))


if __name__ == "__main__":
    main()
