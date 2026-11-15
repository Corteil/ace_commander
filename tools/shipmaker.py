"""Build ship blueprints, in the game's format, from shapes described as
corner points. Used by tools/make_original_ships.py to make the game's own
ships (original_ships.py), so the game runs without anything from Elite.

A blueprint (see game.Blueprint) is (name, vertices, edges, face normals,
stats, title):
  - vertices: (x, y, z) whole numbers; +z is the nose, +y the roof, +x right
  - edges: (vertex, vertex, face, face): drawn when either face is seen
  - normals: one per face, pointing out of the ship
  - stats: (canisters, hit area, gun vertex, explosions, bounty, visibility
    distance, energy, speed, laser power, missiles)
  - title: the name shown on screen (the first item is the game's own key)

Shapes are added as parts:
  - hull(points): the smallest convex shape round the points (most ships)
  - face(loop, inside): one flat face from a loop of vertex numbers, its
    normal pointing away from the point inside (for shapes that aren't
    convex, such as a ring)
  - line(a, b, face): a line drawn on a face (a docking slot, engines)

A shape that isn't convex can be split into convex parts (part() before
each): the game then draws the parts back to front, a part nearer than the
middle blacking out its outline first so that it hides what is behind it.
Blacking out costs the badge about 2 ms a part, so each part says when:
HIDES_ALWAYS, HIDES_SIDE_ON (only when seen side-on to the nose, as a
ring's pieces overlap only then) or HIDES_NEVER. The blueprint then has a
seventh item, the parts: (vertex numbers, edge numbers, when) for each.
"""
import math

NORMAL_LEN = 64     # the length the face normals are scaled to
HIDES_NEVER, HIDES_ALWAYS, HIDES_SIDE_ON = 0, 1, 2


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Ship:
    def __init__(self, key, title):
        self.key = key          # the game's name for the role (game.py's lists)
        self.title = title      # what the player sees
        self.verts = []
        self.faces = []         # (loop of vertex numbers, normal)
        self.lines = []         # (a, b, face)
        self.part_of = []       # each face's part (None: no parts)
        self.cur = None         # the part being added to
        self.hides = []         # each part's HIDES_...

    def part(self, hides=HIDES_ALWAYS):
        """Start a new convex part: the faces and lines after this belong to it."""
        self.cur = len(self.hides)
        self.hides.append(hides)

    def vertex(self, p):
        """The number of vertex p, added if it is new."""
        p = (int(round(p[0])), int(round(p[1])), int(round(p[2])))
        if p in self.verts:
            return self.verts.index(p)
        self.verts.append(p)
        return len(self.verts) - 1

    def face(self, loop, inside):
        """A flat face round the vertices in loop (numbers or points), its
        normal pointing away from the point inside. Returns its number."""
        loop = [i if isinstance(i, int) else self.vertex(i) for i in loop]
        pts = [self.verts[i] for i in loop]
        n = (0.0, 0.0, 0.0)
        for k in range(len(pts)):       # Newell's method: fine for any flat loop
            a, b = pts[k], pts[(k + 1) % len(pts)]
            n = (n[0] + (a[1] - b[1]) * (a[2] + b[2]),
                 n[1] + (a[2] - b[2]) * (a[0] + b[0]),
                 n[2] + (a[0] - b[0]) * (a[1] + b[1]))
        c = [sum(p[j] for p in pts) / len(pts) for j in range(3)]
        if _dot(n, _sub(c, inside)) < 0:
            n = (-n[0], -n[1], -n[2])
        self.faces.append((loop, n))
        self.part_of.append(self.cur)
        return len(self.faces) - 1

    def panel(self, loop):
        """A flat piece seen from either side (a zero normal)."""
        loop = [i if isinstance(i, int) else self.vertex(i) for i in loop]
        self.faces.append((loop, (0, 0, 0)))
        self.part_of.append(self.cur)
        return len(self.faces) - 1

    def hull(self, points):
        """The convex shape round points: its faces. Returns their numbers."""
        pts = [tuple(float(v) for v in p) for p in points]
        centre = tuple(sum(p[j] for p in pts) / len(pts) for j in range(3))
        planes = []
        n = len(pts)
        for i in range(n):
            for j in range(i + 1, n):
                for k in range(j + 1, n):
                    nrm = _cross(_sub(pts[j], pts[i]), _sub(pts[k], pts[i]))
                    ln = math.sqrt(_dot(nrm, nrm))
                    if ln < 1e-6:
                        continue
                    nrm = (nrm[0] / ln, nrm[1] / ln, nrm[2] / ln)
                    d = _dot(nrm, pts[i])
                    side = [_dot(nrm, p) - d for p in pts]
                    if max(side) > 1e-6 and min(side) < -1e-6:
                        continue
                    if max(side) > 1e-6:        # all behind: turn it round
                        nrm = (-nrm[0], -nrm[1], -nrm[2])
                        d = -d
                    if any(abs(_dot(nrm, q[0]) - 1) < 1e-6 and abs(d - q[1]) < 1e-3
                           for q in planes):
                        continue
                    planes.append((nrm, d))
        made = []
        for nrm, d in planes:
            on = [p for p in pts if abs(_dot(nrm, p) - d) < 1e-3]
            c = tuple(sum(p[j] for p in on) / len(on) for j in range(3))
            # order the points round the face's middle
            u = _sub(on[0], c)
            ln = math.sqrt(_dot(u, u)) or 1.0
            u = (u[0] / ln, u[1] / ln, u[2] / ln)
            v = _cross(nrm, u)
            on.sort(key=lambda p: math.atan2(_dot(_sub(p, c), v), _dot(_sub(p, c), u)))
            made.append(self.face(on, centre))
        return made

    def line(self, a, b, face):
        a = a if isinstance(a, int) else self.vertex(a)
        b = b if isinstance(b, int) else self.vertex(b)
        self.lines.append((a, b, face))

    def blueprint(self, stats):
        """The game's entry for this ship."""
        owner = {}
        for f, (loop, _) in enumerate(self.faces):
            for k in range(len(loop)):
                a, b = loop[k], loop[(k + 1) % len(loop)]
                key = (min(a, b), max(a, b))
                owner.setdefault(key, []).append(f)
        edges = []
        for (a, b), fs in sorted(owner.items()):
            if len(fs) >= 2:
                # a straight run across two faces that are flat with each
                # other isn't a real edge: leave it out
                n1, n2 = self.faces[fs[0]][1], self.faces[fs[1]][1]
                l1, l2 = math.sqrt(_dot(n1, n1)), math.sqrt(_dot(n2, n2))
                if _dot(n1, n2) / (l1 * l2) > 0.9999:
                    continue
                edges.append((a, b, fs[0], fs[1]))
            else:
                edges.append((a, b, fs[0], fs[0]))
        for a, b, f in self.lines:
            edges.append((a, b, f, f))
        normals = []
        for _, n in self.faces:
            ln = math.sqrt(_dot(n, n)) or 1.0
            normals.append(tuple(int(round(c * NORMAL_LEN / ln)) for c in n))
        entry = (self.key, tuple(self.verts), tuple(edges), tuple(normals), stats, self.title)
        if not self.hides:
            return entry
        parts = []
        for p in range(len(self.hides)):
            vs = set()
            for f, (loop, _) in enumerate(self.faces):
                if self.part_of[f] == p:
                    vs.update(loop)
            es = tuple(i for i, e in enumerate(edges) if self.part_of[e[2]] == p)
            parts.append((tuple(sorted(vs)), es, self.hides[p]))
        return entry + (tuple(parts),)
