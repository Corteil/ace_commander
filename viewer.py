"""Ship viewer: one ship at a time, spinning, with hidden lines removed."""
import math

CAM_DIST = 380.0
FOCAL = 300.0
FIT_RADIUS = 85.0   # every ship is scaled so its furthest vertex is this far out


def _rotation(yaw, pitch, roll):
    """Return a flat 3x3 matrix equal to Rz(roll) * Rx(pitch) * Ry(yaw)."""
    sy, cy = math.sin(yaw), math.cos(yaw)
    sp, cp = math.sin(pitch), math.cos(pitch)
    sr, cr = math.sin(roll), math.cos(roll)
    a0 = (cy, 0.0, sy)
    a1 = (sp * sy, cp, -sp * cy)
    a2 = (-cp * sy, sp, cp * cy)
    return (
        cr * a0[0] - sr * a1[0], cr * a0[1] - sr * a1[1], cr * a0[2] - sr * a1[2],
        sr * a0[0] + cr * a1[0], sr * a0[1] + cr * a1[1], sr * a0[2] + cr * a1[2],
        a2[0], a2[1], a2[2],
    )


def _fill_hull(ctx, pts):
    """Fill black the outline round pts (the smallest convex shape holding them)."""
    pts = sorted(pts)
    hull = []
    for half in (pts, pts[::-1]):       # Andrew's monotone chain, as cockpit._fill_hull
        start = len(hull)
        for p in half:
            while len(hull) >= start + 2:
                ax, ay = hull[-2]
                bx, by = hull[-1]
                if (bx - ax) * (p[1] - ay) - (by - ay) * (p[0] - ax) > 0:
                    break
                hull.pop()
            hull.append(p)
        hull.pop()
    if len(hull) < 3:
        return
    ctx.rgb(0, 0, 0)
    ctx.begin_path()
    ctx.move_to(*hull[-1])
    for p in hull:
        ctx.line_to(*p)
    ctx.fill()


def with_convoy(ships):
    """The ships to show: the game's, then the convoy's hauler (multiplayer, duel.py),
    which is the game's own design whichever content is used."""
    try:
        from . import convoy_ship
    except ImportError:
        return ships
    return tuple(ships) + (convoy_ship.SHIP,)


class Viewer:
    def __init__(self, ships):
        self.ships = ships   # entries from ship_data.SHIPS
        self.idx = 0
        self.yaw = 2.6
        self.pitch = 0.35
        self.roll = 0.0
        self._load()

    def _load(self):
        e = self.ships[self.idx]
        name, verts, edges, normals = e[:4]
        name = e[5] if len(e) > 5 else name     # the name shown
        r = max(math.sqrt(x * x + y * y + z * z) for x, y, z in verts) or 1.0
        s = FIT_RADIUS / r
        self.name = name
        self.verts = [(x * s, y * s, z * s) for x, y, z in verts]
        self.edges = edges
        self.normals = normals
        # convex parts, for a shape that isn't convex (the ring station, the convoy's
        # hauler): drawn back to front, each nearer one blacking out what is behind
        self.parts = e[6] if len(e) > 6 else None

    def switch(self, step):
        self.idx = (self.idx + step) % len(self.ships)
        self._load()

    def step(self, dt, jx, jy):
        """jx and jy are -1..1: roll and pitch the ship."""
        self.yaw += 0.8 * dt
        self.pitch += jy * 2.0 * dt
        self.roll += jx * 2.0 * dt

    def draw(self, ctx):
        m00, m01, m02, m10, m11, m12, m20, m21, m22 = _rotation(
            self.yaw, self.pitch, self.roll)
        screen = []
        for x, y, z in self.verts:
            k = FOCAL / (m20 * x + m21 * y + m22 * z + CAM_DIST)
            screen.append(((m00 * x + m01 * y + m02 * z) * k,
                           -(m10 * x + m11 * y + m12 * z) * k))

        # Elite's own rule: the ship sits straight ahead, so a face is visible
        # when its normal points back towards the camera. A face with no
        # normal (face-less edges, as on the plate) is always drawn.
        visible = []
        for nx, ny, nz in self.normals:
            visible.append(
                (nx == 0 and ny == 0 and nz == 0)
                or m20 * nx + m21 * ny + m22 * nz < 0
            )

        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.line_width = 1.5
        if self.parts:
            depth = [m20 * x + m21 * y + m22 * z for x, y, z in self.verts]
            order = sorted(self.parts, key=lambda p: -sum(depth[v] for v in p[0]) / len(p[0]))
            side_on = -0.5 < m22 < 0.5      # the nose across the view more than along it
            for vs, es, hides in order:
                d = sum(depth[v] for v in vs) / len(vs)
                if d < 0 and (hides == 1 or (hides == 2 and side_on)):
                    _fill_hull(ctx, [screen[v] for v in vs])
                ctx.rgb(1, 1, 1)
                ctx.begin_path()
                for i in es:
                    a, b, f1, f2 = self.edges[i]
                    if visible[f1] or visible[f2]:
                        ctx.move_to(screen[a][0], screen[a][1])
                        ctx.line_to(screen[b][0], screen[b][1])
                ctx.stroke()
        else:
            ctx.rgb(1, 1, 1)
            ctx.begin_path()
            for a, b, f1, f2 in self.edges:
                if visible[f1] or visible[f2]:
                    ctx.move_to(screen[a][0], screen[a][1])
                    ctx.line_to(screen[b][0], screen[b][1])
            ctx.stroke()

        ctx.font_size = 13
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.rgb(0.4, 1, 0.4).move_to(0, 103).text(self.name)
        ctx.rgb(0.7, 0.7, 0.75).move_to(0, -106).text(
            "%d/%d" % (self.idx + 1, len(self.ships)))
