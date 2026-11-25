"""Title screen: the name in block letters, a ship tumbling under it, and one
line of menu.

Text is the slow thing to draw on the badge (about 4 ms a piece), so the name
is built from rectangles and only the menu line is text. The ship is drawn
the way the ship viewer draws one, turning on three axes at once so that it
tumbles. Every few seconds it flies off past the camera and the next ship
comes in from the distance.
"""
from .viewer import _rotation
from . import config

FOCAL = 300.0
CAM_DIST = 380.0     # where the ship sits while it tumbles
FAR_DIST = 4000.0    # where it comes in from
FIT_RADIUS = 78.0    # every ship is scaled so its furthest vertex is this far out
NEAR = 40.0          # nothing closer to the camera than this is drawn
SHIP_Y = 8.0         # screen y of the ship's centre

T_IN = 1.2           # seconds flying in
T_HOLD = 8.0         # seconds tumbling
T_OUT = 0.9          # seconds flying off towards the viewer

FIRST = ("COBRA MK III", "MAMBA")   # the original showed these two
# not ships, or too small to be worth a turn
SKIP = ("MISSILE", "CANISTER", "PLATE", "SPLINTER", "BOULDER", "ASTEROID",
        "ESCAPE POD", "THARGON")

from .letters import block_rects, ACE as _ACE, COMMANDER as _COMMANDER, draw_name, face_dots, draw_edges



def _order(ships):
    """Indexes into ships in the order they take their turn."""
    names = [entry[0] for entry in ships]
    order = [names.index(n) for n in FIRST if n in names]
    for i, n in enumerate(names):
        if i not in order and n not in SKIP:
            order.append(i)
    return order or list(range(len(ships)))


class Title:
    def __init__(self, ships):
        self.ships = ships
        self.order = _order(ships)
        self.turn = 0
        self.yaw = 2.6
        self.pitch = 0.35
        self.roll = 0.0
        self._load()

    def _load(self):
        e = self.ships[self.order[self.turn]]
        name, verts, edges, normals = e[:4]
        self.key = name             # the role (FIRST names roles)
        name = e[5] if len(e) > 5 else name     # the name shown
        r2 = 1.0
        for x, y, z in verts:
            d = x * x + y * y + z * z
            if d > r2:
                r2 = d
        s = FIT_RADIUS / (r2 ** 0.5)
        self.name = name
        self.verts = [(x * s, y * s, z * s) for x, y, z in verts]
        self.edges = edges
        self.normals = normals
        self.entry = e
        self.dots = face_dots(e, s)     # for hidden lines in perspective (letters.face_dots)
        self.t = 0.0
        self.dist = FAR_DIST

    def step(self, dt):
        self.yaw += 0.7 * dt
        self.pitch += 0.45 * dt
        self.roll += 0.25 * dt
        self.t += dt
        t = self.t
        if t < T_IN:
            k = 1.0 - t / T_IN          # 1 far away, 0 arrived; slows as it arrives
            self.dist = CAM_DIST + (FAR_DIST - CAM_DIST) * k * k
        elif t < T_IN + T_HOLD:
            self.dist = CAM_DIST
        elif t < T_IN + T_HOLD + T_OUT:
            k = (t - T_IN - T_HOLD) / T_OUT     # speeds up towards the viewer
            self.dist = CAM_DIST - (CAM_DIST + FIT_RADIUS) * k * k
        else:
            self.turn = (self.turn + 1) % len(self.order)
            self._load()

    def draw(self, ctx, label):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()

        m00, m01, m02, m10, m11, m12, m20, m21, m22 = _rotation(
            self.yaw, self.pitch, self.roll)
        dist = self.dist
        screen = []
        depth = []
        for x, y, z in self.verts:
            dz = m20 * x + m21 * y + m22 * z
            depth.append(dz)
            d = dz + dist
            if d < NEAR:
                screen.append(None)
            else:
                k = FOCAL / d
                screen.append(((m00 * x + m01 * y + m02 * z) * k,
                               SHIP_Y - (m10 * x + m11 * y + m12 * z) * k))
        # a face shows when its normal points back at the camera from a point on it
        # (in perspective: letters.face_dots); a face with no normal is always drawn
        visible = []
        dots = self.dots
        i = 0
        for nx, ny, nz in self.normals:
            visible.append((nx == 0 and ny == 0 and nz == 0)
                           or dots[i] + dist * (m20 * nx + m21 * ny + m22 * nz) < 0)
            i += 1
        ctx.line_width = 1.5
        draw_edges(ctx, self.entry, screen, visible, depth, (1, 1, 1), -0.5 < m22 < 0.5)

        # the name goes on last, so a ship flying past the camera passes behind it
        draw_name(ctx)

        ctx.font_size = 13
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.rgb(0.3, 1, 0.4).move_to(0, 84).text("< %s >" % label)
        if config.more_hints:   # the corners show (the Tufty, the Pi's Elite layout)
            ctx.font_size = 10
            ctx.rgb(0.6, 0.6, 0.6).move_to(0, 108).text("< > choose   C: select")
