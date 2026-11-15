#!/usr/bin/env python3
"""Make original_ships.py: the game's own ships, designed for Ace Commander,
so it runs without anything from Elite. (With your own ship_data.py from
tools/import_ships.py the game uses that instead.)

Each ship takes a role the game knows by the first name (game.py's lists);
the second is the name shown on screen.

Usage:  python3 tools/make_original_ships.py [-o original_ships.py]
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shipmaker import Ship


def ring_station():
    """A ring on three spokes round a hub; you dock through the slot in the
    hub's front (+z), which is the station's furthest point forward."""
    s = Ship("DODO", "HALO STATION")
    n = 6                       # sides of the ring (each one costs the badge 8 lines)
    r, w, d = 200, 24, 26       # the ring's middle radius, half its width and half its depth
    rings = []
    for k in range(n):
        a = 2 * math.pi * k / n        # corners between the spokes; flat sides meet them
        c, sn = math.cos(a), math.sin(a)
        rings.append([s.vertex((rr * c, rr * sn, z))
                      for rr, z in ((r + w, d), (r + w, -d), (r - w, -d), (r - w, d))])
    for k in range(n):
        p, q = rings[k], rings[(k + 1) % n]
        corners = [s.verts[i] for i in p + q]
        mid = tuple(sum(v[j] for v in corners) / 8.0 for j in range(3))   # inside the tube
        for j in range(4):
            s.face([p[j], p[(j + 1) % 4], q[(j + 1) % 4], q[j]], mid)
    # the hub: a hexagonal drum, longer than the ring is deep
    hr, back, front = 62, -64, 96
    hub = [(hr * math.cos(math.pi / 3 * k), hr * math.sin(math.pi / 3 * k), z)
           for z in (back, front) for k in range(6)]
    faces = s.hull(hub)
    front_face = [f for f in faces if s.faces[f][1][2] > 0][0]
    # the docking slot: a 2:1 letterbox in the front face
    sw, sh = 34, 17
    corners = [s.vertex((x, y, front)) for x, y in ((-sw, -sh), (sw, -sh), (sw, sh), (-sw, sh))]
    for k in range(4):
        s.line(corners[k], corners[(k + 1) % 4], front_face)
    # three spokes, from the hub's flat sides out to the ring: flat panels,
    # seen from either side (a zero normal), 4 lines each
    t, inner, outer = 10, hr * math.cos(math.pi / 6), r - w
    for k in range(3):
        a = math.pi / 6 + 2 * math.pi / 3 * k      # through the middle of a hub side
        c, sn = math.cos(a), math.sin(a)
        ox, oy = -sn * t, c * t                    # across the spoke
        p = [s.vertex((rr * c + u * ox, rr * sn + u * oy, 0))
             for rr, u in ((inner, 1), (outer, 1), (outer, -1), (inner, -1))]
        s.faces.append((p, (0, 0, 0)))
    return s.blueprint(_stats(s, 0, 11, 0, 115, 255, 0, 0, 0, gun=0))


def _mirror(points):
    """The points and their mirror images across the middle (x to -x)."""
    out = []
    for x, y, z in points:
        out.append((x, y, z))
        if x:
            out.append((-x, y, z))
    return out


def _gun(s):
    """The vertex furthest forward: where its laser fires from."""
    return max(range(len(s.verts)), key=lambda i: s.verts[i][2])


def _stats(s, canisters, explosions, bounty, vis, energy, speed, laser, missiles, gun=None):
    size = max(math.sqrt(x * x + y * y + z * z) for x, y, z in s.verts)
    area = min(9800, int((size * 0.7) ** 2) // 25 * 25)    # how easily it is hit
    return (canisters, area, _gun(s) if gun is None else gun, explosions, bounty, vis,
            energy, speed, laser, missiles)


def _hull_ship(key, title, points, stats, engines=None):
    """A convex ship round points (mirrored), with engine slits on its
    back: engines is a list of (x, y, half width, half height) at the
    furthest-back z."""
    s = Ship(key, title)
    faces = s.hull(_mirror(points))
    if engines:
        back = min(z for _, _, z in s.verts)
        bf = [f for f in faces if s.faces[f][1][2] < 0 and
              all(s.verts[i][2] == back for i in s.faces[f][0])]
        if bf:
            for x, y, hw, hh in engines:
                for cx in ((x, -x) if x else (x,)):
                    c = [s.vertex((cx + dx, y + dy, back)) for dx, dy in
                         ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
                    for k in range(4):
                        s.line(c[k], c[(k + 1) % 4], bf[0])
    return s, s.blueprint(_stats(s, *stats))


# (key, title, half the points (x >= 0; mirrored), (canisters, explosions,
#  bounty in tenths of a credit, visibility, energy, speed, laser, missiles),
#  engines)
HULLS = [
    # your ship, and traders': a broad wedge with swept wingtips
    ("COBRA MK III", "KESTREL",
     [(22, 0, 84), (0, 20, 28), (118, -4, -26), (72, 18, -40), (112, -10, -40),
      (0, 22, -40), (30, -20, -40)],
     (3, 9, 0, 50, 160, 27, 2, 3), [(40, 0, 10, 6)]),
    ("COBRA MK III P", "KESTREL RAIDER",
     [(22, 0, 84), (0, 20, 28), (118, -4, -26), (72, 18, -40), (112, -10, -40),
      (0, 22, -40), (30, -20, -40)],
     (1, 9, 180, 50, 160, 27, 2, 2), [(40, 0, 10, 6)]),
    # police: an arrowhead with a raised spine
    ("VIPER", "WARDEN",
     [(0, 0, 76), (14, 8, 16), (44, 0, -26), (20, 14, -26), (0, 18, -26), (20, -10, -26),
      (0, -12, -26)],
     (0, 9, 0, 24, 110, 33, 2, 1), [(14, 2, 6, 4)]),
    # small pirate craft
    ("SIDEWINDER", "GNAT",
     [(0, 0, 40), (58, -2, -26), (0, 14, -26), (14, -10, -26)],
     (0, 6, 60, 20, 75, 36, 2, 0)),
    ("MAMBA", "HORNET",
     [(0, 0, 70), (10, 6, 30), (58, -2, -30), (18, 8, -34), (18, -8, -34)],
     (1, 7, 140, 25, 95, 31, 2, 2), [(10, 0, 5, 3)]),
    ("KRAIT", "STINGER",
     [(20, 0, 96), (84, 0, -6), (40, 0, -48), (0, 16, 10), (0, -14, 0)],
     (1, 3, 110, 25, 85, 29, 2, 0)),
    ("ADDER", "MULE",
     [(18, 6, 44), (18, -6, 44), (30, 8, 20), (30, -8, 20), (28, 8, -40), (28, -8, -40)],
     (0, 4, 45, 23, 90, 23, 2, 0), [(12, 0, 6, 4)]),
    ("GECKO", "SKINK",
     [(14, 0, 46), (62, -2, -16), (24, 8, -24), (24, -6, -24)],
     (0, 5, 60, 18, 75, 31, 2, 0)),
    ("COBRA MK I", "KITE",
     [(0, 0, 62), (62, 0, -4), (0, 12, 0), (0, -10, 0), (22, 0, -38)],
     (3, 5, 80, 19, 95, 25, 2, 2)),
    ("WORM", "GRUB",
     [(10, 8, 34), (10, -8, 34), (24, 12, -24), (24, -12, -24), (0, 16, -24), (0, -16, -24)],
     (0, 3, 0, 19, 32, 22, 1, 0)),
    # bounty hunters
    ("ASP MK II", "HARRIER",
     [(0, 2, 82), (16, 10, 20), (70, -2, -44), (28, 12, -44), (28, -10, -44)],
     (0, 5, 210, 42, 155, 39, 5, 1), [(20, 0, 7, 4)]),
    ("FER DE LANCE", "LANCET",
     [(0, 0, 106), (14, 8, 30), (38, 0, -50), (16, 16, -50), (16, -12, -50)],
     (0, 5, 0, 40, 165, 31, 2, 2), [(12, 2, 5, 4)]),
    # big traders
    ("PYTHON", "BULWARK",
     [(0, 0, 220), (40, 30, 40), (92, 0, 0), (40, -26, 40), (60, 40, -110), (60, -36, -110)],
     (5, 8, 0, 38, 260, 19, 3, 3), [(30, 0, 14, 10)]),
    ("PYTHON P", "BULWARK RAIDER",
     [(0, 0, 220), (40, 30, 40), (92, 0, 0), (40, -26, 40), (60, 40, -110), (60, -36, -110)],
     (2, 8, 210, 38, 260, 19, 3, 3), [(30, 0, 14, 10)]),
    ("BOA", "BARGE",
     [(30, 20, 92), (30, -20, 92), (60, 38, 0), (60, -38, 0), (50, 34, -104), (50, -34, -104)],
     (5, 7, 0, 42, 240, 23, 3, 4), [(24, 0, 12, 10)]),
    ("ANACONDA", "LEVIATHAN",
     [(0, 10, 250), (34, 28, 120), (66, 0, 80), (34, -30, 100), (60, 50, -56), (66, -48, -56)],
     (6, 11, 0, 48, 250, 15, 6, 7), [(30, 0, 16, 14)]),
    ("MORAY", "EEL",
     [(0, 2, 64), (24, 6, 30), (58, -2, -30), (20, 16, -40), (20, -12, -40)],
     (1, 5, 55, 40, 105, 24, 2, 0)),
    # mission 1's prototype: low, wide and sharp
    ("CONSTRICTOR", "PHANTOM",
     [(0, 0, 84), (16, 10, 30), (54, 0, -36), (24, 14, -40), (24, -10, -40), (40, 0, -40)],
     (3, 9, 0, 44, 250, 35, 6, 4), [(14, 2, 6, 4)]),
    # aliens: a six-pointed saucer and its drone
    ("THARGOID", "VORN MOTHERSHIP",
     [(150, 0, 86), (150, 0, -86), (0, 0, 172), (0, 0, -172), (48, 36, 0), (0, 40, 30),
      (40, -30, 0), (0, -34, -24)],
     (0, 9, 520, 52, 245, 38, 2, 6)),
    ("THARGON", "VORN DRONE",
     [(0, 0, 40), (24, 0, -28), (0, 20, -28), (0, -16, -28)],
     (0, 3, 45, 20, 22, 31, 2, 0)),
    # station shuttles
    ("SHUTTLE", "SHUTTLE",
     [(12, 10, 34), (12, -10, 34), (20, 18, -26), (20, -18, -26)],
     (14, 8, 0, 22, 34, 9, 0, 0), [(0, 0, 8, 6)]),
    ("TRANSPORTER", "HAULER",
     [(20, 8, 30), (20, -8, 30), (32, 10, -26), (32, -10, -26)],
     (0, 5, 0, 16, 34, 9, 0, 0), [(16, 0, 6, 4)]),
    # odds and ends
    ("MISSILE", "MISSILE",
     [(0, 0, 66), (6, 6, 30), (6, -6, 30), (6, 6, -40), (6, -6, -40), (14, 0, -44),
      (0, 14, -44), (0, -14, -44)],
     (0, 1, 0, 15, 2, 43, 0, 0)),
    ("ESCAPE POD", "ESCAPE POD",
     [(0, 0, 34), (18, -10, -12), (0, 14, -12)],
     (0, 4, 0, 8, 18, 9, 0, 0)),
]


def canister():
    s = Ship("CANISTER", "CANISTER")
    pts = [(18 * math.cos(math.pi / 3 * k), 18 * math.sin(math.pi / 3 * k), z)
           for z in (-14, 14) for k in range(6)]
    s.hull(pts)
    return s.blueprint(_stats(s, 0, 3, 0, 12, 18, 14, 0, 0))


def _rock(key, title, radius, seed, n, stats):
    """A lumpy rock: points on a sphere, pushed in and out a little."""
    s = Ship(key, title)
    rnd = seed
    pts = []
    golden = math.pi * (3 - math.sqrt(5))
    for k in range(n):
        rnd = (rnd * 1103515245 + 12345) & 0x7FFFFFFF
        r = radius * (0.75 + 0.25 * (rnd % 1000) / 1000.0)
        y = 1 - 2 * (k + 0.5) / n
        rr = math.sqrt(1 - y * y)
        a = golden * k
        pts.append((r * rr * math.cos(a), r * y, r * rr * math.sin(a)))
    s.hull(pts)
    return s.blueprint(_stats(s, *stats))


def plate():
    """A bent strip of hull: one flat piece, seen from either side."""
    s = Ship("PLATE", "ALLOY PLATE")
    p = [s.vertex(v) for v in ((-16, -34, -6), (14, -30, 8), (18, 36, 4), (-12, 30, -8))]
    s.faces.append((p, (0, 0, 0)))
    return s.blueprint(_stats(s, 0, 1, 0, 5, 16, 15, 0, 0))


def coriolis():
    """The smaller stations: an octagonal drum, end on to you, with a 3:1
    slot in its front."""
    s = Ship("CORIOLIS", "DRUM STATION")
    r = 150
    pts = [(r * math.cos(math.pi / 4 * (k + 0.5)), r * math.sin(math.pi / 4 * (k + 0.5)), z)
           for z in (-150, 150) for k in range(8)]
    faces = s.hull(pts)
    front = [f for f in faces if s.faces[f][1][2] > 0][0]
    c = [s.vertex((x, y, 150)) for x, y in ((-36, -12), (36, -12), (36, 12), (-36, 12))]
    for k in range(4):
        s.line(c[k], c[(k + 1) % 4], front)
    return s.blueprint(_stats(s, 0, 11, 0, 110, 255, 0, 0, 5, gun=0))


def _all():
    out = [b for _, b in (_hull_ship(k, t, p, st, en if len(h) > 4 else None)
                          for h in HULLS for k, t, p, st, *rest in [h]
                          for en in [rest[0] if rest else None])]
    out += [canister(), plate(),
            _rock("ASTEROID", "ASTEROID", 76, 7, 12, (0, 6, 5, 45, 65, 28, 0, 0)),
            _rock("BOULDER", "BOULDER", 36, 3, 8, (0, 3, 2, 18, 24, 28, 0, 0)),
            _rock("SPLINTER", "SPLINTER", 18, 5, 5, (0, 3, 0, 9, 18, 12, 0, 0)),
            coriolis(), ring_station()]
    return out




def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("-o", "--output", default="original_ships.py")
    args = ap.parse_args()
    entries = _all()
    out = ['"""Ace Commander\'s own ships, made by tools/make_original_ships.py.',
           "",
           "Original designs, free to use with the game. Each entry is (role, vertices,",
           "edges, face normals, stats, title): see tools/shipmaker.py.",
           '"""',
           "SHIPS = ("]
    for e in entries:
        out.append("    %r," % (e,))
    out.append(")")
    with open(args.output, "w") as f:
        f.write("\n".join(out) + "\n")
    print("Wrote %s: %d ships" % (args.output, len(entries)))


if __name__ == "__main__":
    main()
