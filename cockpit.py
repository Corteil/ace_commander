"""Cockpit view for the flight game: ships, radar and gauges on the round
240x240 screen (origin at the centre, y down).

Measured on the badge, a filled rectangle costs about 0.03 ms, a line about
0.35 ms and a piece of text about 4 ms. So everything that is drawn every
frame is built from rectangles where it can be, including the numbers, and
text is kept for messages that only show now and then.
"""
import math

FOCAL = 208.0    # pixels; gives a field of view of about 60 degrees
VIEW_NAMES = ("FRONT", "REAR", "LEFT", "RIGHT")   # as game.VIEW_NAMES; this module imports no game
NEAR = 30.0      # nothing closer than this is drawn
TAU = 2 * math.pi
WIRE_MIN = 8.0   # ships that look smaller than this (pixels) are drawn as a marker
STREAK_MIN = 300  # world units: the shortest stardust streak with the jump drive on

RADAR_Y = 88
RADAR_RX = 58
RADAR_RY = 24
RADAR_RANGE = 10000.0
_RADAR = tuple(
    (RADAR_RX * math.cos(i * TAU / 24) - 0.75, RADAR_Y + RADAR_RY * math.sin(i * TAU / 24) - 0.75)
    for i in range(24)
)

_RADAR_R = int(RADAR_RANGE)
_RADAR_R2 = _RADAR_R * _RADAR_R

WHITE = (1, 1, 1)
DIM = (0.2, 0.2, 0.26)
GREEN = (0.3, 1, 0.4)
YELLOW = (1, 0.85, 0.2)
RED = (1, 0.25, 0.2)
ORANGE = (1, 0.55, 0.1)
CYAN = (0.3, 0.9, 1)
MAGENTA = (1, 0.3, 1)
LIGHT_PURPLE = (0.75, 0.6, 1)
POLICE_BLUE = (0.35, 0.5, 1)
GREY = (0.7, 0.7, 0.75)
# your laser's beam, by type (game.LASERS); the LEDs flash the same colour on
# each shot. Enemy lasers are ORANGE, which none of these is.
LASER_COLOURS = {
    "pulse": MAGENTA,
    "beam": (0.25, 0.5, 1),
    "military": GREEN,
    "mining": YELLOW,
}
# enemy missiles are orange like enemy lasers (all enemy fire), yours light purple
COLOUR = {"ship": WHITE, "rock": GREY, "can": YELLOW, "missile": ORANGE, "pmissile": LIGHT_PURPLE,
          "station": WHITE}
PLANET = (0.35, 0.6, 1)
# each system's planet is one of these, picked from its number (Space.planet):
# (the disc's colour, its outline's)
PLANET_COLOURS = (
    ((0.12, 0.25, 0.55), (0.35, 0.6, 1)),       # ocean blue
    ((0.12, 0.4, 0.18), (0.4, 0.9, 0.45)),      # green
    ((0.5, 0.38, 0.2), (0.95, 0.75, 0.45)),     # desert
    ((0.5, 0.18, 0.12), (1, 0.45, 0.3)),        # red
    ((0.32, 0.32, 0.36), (0.75, 0.75, 0.8)),    # grey
    ((0.32, 0.16, 0.45), (0.75, 0.5, 1)),       # purple
    ((0.1, 0.38, 0.4), (0.4, 0.9, 0.9)),        # teal
)
SUN = (1, 0.8, 0.25)
# each system's sun is one of these, picked from its number (Space.sun)
SUN_COLOURS = (
    (1, 0.35, 0.2),     # red
    (1, 0.6, 0.2),      # orange
    (1, 0.8, 0.25),     # yellow
    (1, 0.95, 0.8),     # white
    (0.7, 0.85, 1),     # blue-white
)

# seven-segment digits: which of the segments a-g are lit for 0-9
_SEGS = ("abcdef", "bc", "abged", "abgcd", "fgbc", "afgcd", "afgedc", "abc", "abcdefg", "abcdfg")


def _digit_rects(w, h, t):
    """For each digit, the rectangles (x, y, w, h) that draw it in a w by h cell."""
    half = (h - t) / 2.0
    seg = {
        "a": (0, 0, w, t),
        "b": (w - t, 0, t, half + t),
        "c": (w - t, half, t, half + t),
        "d": (0, h - t, w, t),
        "e": (0, half, t, half + t),
        "f": (0, 0, t, half + t),
        "g": (0, half, w, t),
    }
    return tuple(tuple(seg[c] for c in segs) for segs in _SEGS)


_BIG = (7, 11, 2, _digit_rects(7, 11, 2))      # (width, height, thickness, rectangles)
_SMALL = (4, 7, 1, _digit_rects(4, 7, 1))


def number(ctx, value, x, y, font=_BIG, align=0):
    """Draw a whole number out of rectangles in the current colour. (x, y) is
    the top of the number: its centre for align 0, its left edge for align -1,
    its right edge for align 1. Returns the width drawn."""
    w, h, t, rects = font
    s = str(int(value))
    step = w + t + 1
    width = len(s) * step - (t + 1)
    if align == 0:
        x -= width / 2.0
    elif align > 0:
        x -= width
    for ch in s:
        if ch != "-":
            for rx, ry, rw, rh in rects[ord(ch) - 48]:
                ctx.rectangle(x + rx, y + ry, rw, rh).fill()
        x += step
    return width


def text(ctx, s, x, y, size, rgb, align=0):
    """Text centred on (x, y), or with align -1 starting at x, 1 ending at x."""
    ctx.font_size = size
    ctx.text_align = ctx.CENTER if align == 0 else (ctx.LEFT if align < 0 else ctx.RIGHT)
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


# On the badge every float result is a new 16-byte object on the heap, and a
# frame that makes many of them soon has to stop for a garbage collection.
# Small whole numbers cost nothing, so the loops below work in whole numbers:
# positions in world units, directions times 4096, and screen positions in
# whole pixels.
IFOCAL = int(FOCAL)
INEAR = int(NEAR)
_PX = [0] * 96      # screen x of each vertex of the ship being drawn
_PY = [0] * 96      # screen y
_OK = [False] * 96  # False if the vertex is behind the viewer
_VIS = [False] * 64  # which faces of the ship being drawn can be seen
_PZ = [0] * 96      # how far away each vertex is
_VX = [0] * 96      # and where it is across and up, before the perspective
_VY = [0] * 96


def draw_ship(ctx, o, rgb=None, wire_min=WIRE_MIN, solid=False):
    """Draw one object, in its kind's colour or rgb, as a wireframe if it looks
    at least wire_min pixels across. With solid, its outline is filled black
    first, hiding whatever was drawn behind it. Returns True if any of it was
    on screen."""
    z = int(o.z)
    if z < INEAR:
        return False
    bp = o.bp
    x = int(o.x)
    y = int(o.y)
    sx = x * IFOCAL // z
    sy = -(y * IFOCAL // z)
    pr = bp.isize * IFOCAL // z     # how big it looks, in pixels
    if sx - pr > 120 or sx + pr < -120 or sy - pr > 120 or sy + pr < -120:
        return False
    ctx.rgb(*(RED if o.hit > 0 else rgb or COLOUR[o.kind]))
    if pr < 3 and wire_min > 0:     # too far away to make out: a dot (wire_min 0: never)
        ctx.rectangle(sx - 1, sy - 1, 2, 2).fill()
        return True
    if pr < wire_min:   # middle distance: a small marker, much cheaper than lines
        ctx.rectangle(sx - pr, sy - 1, 2 * pr, 1.5).fill()
        h = pr // 2
        ctx.rectangle(sx - 1, sy - h, 1.5, 2 * h).fill()
        return True

    m = o.m
    m0 = int(m[0] * 4096)
    m1 = int(m[1] * 4096)
    m2 = int(m[2] * 4096)
    m3 = int(m[3] * 4096)
    m4 = int(m[4] * 4096)
    m5 = int(m[5] * 4096)
    m6 = int(m[6] * 4096)
    m7 = int(m[7] * 4096)
    m8 = int(m[8] * 4096)
    px = _PX
    py = _PY
    ok = _OK
    dz = _PZ
    wx = _VX
    wy = _VY
    i = 0
    for vx, vy, vz in bp.verts:
        pz = z + ((vx * m2 + vy * m5 + vz * m8) >> 12)
        qx = x + ((vx * m0 + vy * m3 + vz * m6) >> 12)
        qy = y + ((vx * m1 + vy * m4 + vz * m7) >> 12)
        dz[i] = pz
        wx[i] = qx
        wy[i] = qy
        if pz < INEAR:
            ok[i] = False   # behind the viewer
        else:
            ok[i] = True
            px[i] = qx * IFOCAL // pz
            py[i] = -(qy * IFOCAL // pz)
        i += 1

    # A face shows if its normal points back towards you from a point on the
    # face. (Elite judged it from the ship's middle, which is the same far off
    # but shows the far side of a big ship you are close to, such as a
    # station's back rim as you fly in.) A zero normal always shows.
    vis = _VIS
    fv = bp.face_vert
    i = 0
    for nx, ny, nz in bp.normals:
        if nx == 0 and ny == 0 and nz == 0:
            vis[i] = True
        else:
            v = fv[i]
            if v < 0:
                ax, ay, az = x, y, z
            else:
                ax, ay, az = wx[v], wy[v], dz[v]
            vis[i] = (((nx * m0 + ny * m3 + nz * m6) >> 8) * ax
                      + ((nx * m1 + ny * m4 + nz * m7) >> 8) * ay
                      + ((nx * m2 + ny * m5 + nz * m8) >> 8) * az < 0)
        i += 1

    col = RED if o.hit > 0 else rgb or COLOUR[o.kind]
    if bp.parts:    # not convex: its convex parts back to front, each hiding what is behind
        order = []
        for vs, es, hides in bp.parts:
            d = 0
            for v in vs:
                d += dz[v]
            order.append((d // len(vs), vs, es, hides))
        order.sort(key=lambda t: -t[0])
        edges = bp.edges
        side_on = -2048 < m8 < 2048     # the nose more across the view than along it
        for d, vs, es, hides in order:
            # blacking out costs about 2 ms: only a part nearer than the middle
            # can hide another, and some only when seen side-on
            if d < z and (hides == 1 or (hides == 2 and side_on)):
                _fill_hull(ctx, vs)
            ctx.rgb(*col)
            ctx.begin_path()
            for e in es:
                a, b, f1, f2 = edges[e]
                if (vis[f1] or vis[f2]) and ok[a] and ok[b]:
                    ctx.move_to(px[a], py[a])
                    ctx.line_to(px[b], py[b])
            ctx.stroke()
        return True
    if solid:
        _fill_hull(ctx, range(len(bp.verts)))
    ctx.rgb(*col)
    ctx.begin_path()
    for a, b, f1, f2 in bp.edges:
        if (vis[f1] or vis[f2]) and ok[a] and ok[b]:
            ctx.move_to(px[a], py[a])
            ctx.line_to(px[b], py[b])
    ctx.stroke()
    return True


def _fill_hull(ctx, idx):
    """Fill black the outline round the projected vertices numbered in idx
    (the smallest convex shape holding them all), if none is behind the viewer."""
    px = _PX
    py = _PY
    pts = []
    for i in idx:
        if not _OK[i]:
            return
        pts.append((px[i], py[i]))
    pts.sort()
    # Andrew's monotone chain: the lower then the upper half of the outline
    hull = []
    for half in (pts, pts[::-1]):
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


def _enemy_beam(ctx, o):
    """An enemy laser: from the ship's gun to your cockpit, which is just
    below the view, so the beam runs off the bottom of the screen."""
    bp = o.bp
    m = o.m
    vx, vy, vz = bp.verts[bp.gun] if bp.gun < len(bp.verts) else (0, 0, 0)
    pz = o.z + vx * m[2] + vy * m[5] + vz * m[8]
    if pz < NEAR:
        return
    k = FOCAL / pz
    gx = (o.x + vx * m[0] + vy * m[3] + vz * m[6]) * k
    gy = -(o.y + vx * m[1] + vy * m[4] + vz * m[7]) * k
    if gy > 120:
        return
    ctx.line_width = 2.5
    ctx.rgb(*ORANGE)
    ctx.begin_path()
    ctx.move_to(gx, gy)
    ctx.line_to(gx * 0.25, 126)
    ctx.stroke()
    ctx.line_width = 1.5


# the hyperspace streaks: (direction x, y times 256, starting radius in pixels)
_WARP_T = 1.2       # the same as game.WARP_TIME
_STREAKS = tuple(
    (int(256 * math.cos(i * TAU / 18 + 0.2)), int(256 * math.sin(i * TAU / 18 + 0.2)),
     8 + (i * 29) % 34)
    for i in range(18))


# A station's colour says what kind of government runs the system, warm for
# the dangerous ones and cool for the safe ones, in the order of
# galaxy.GOVERNMENTS. It is used for the tunnel's mouth and the badge's LEDs as
# you launch. No red (the LEDs flash red when you are hit) and no white (the
# tunnel is white).
STATION_COLOURS = (
    ORANGE,             # Anarchy
    YELLOW,             # Feudal
    MAGENTA,            # Multi-government
    (1, 0.5, 0.75),     # Dictatorship: pink
    (0.65, 0.4, 1),     # Communist: violet
    (0.4, 0.55, 1),     # Confederacy: blue
    CYAN,               # Democracy
    GREEN,              # Corporate State
)


def station_colour(government):
    """The colour of a station in a system with this government (0 to 7), or
    green if it isn't known."""
    if government is None:
        return GREEN
    return STATION_COLOURS[government & 7]


# ---- the station's tunnel, for launching and docking --------------------
#
# Each station has its own tunnel (Tunnel): every ring is the shape of the
# station's slot (a flat letterbox, level as you come in), and the gaps
# between the rings follow a pattern of the station's own. At the end it
# opens into a bigger docking bay of the same shape, with the doors at the back.
TUNNEL_RINGS = 12
TUNNEL_FOCAL = 62.0     # pixels across a ring of radius 1 at distance 1
SLOT_ASPECT = {"CORIOLIS": 3.0, "DODO": 2.0}    # from their slots' vertices: 20 x 60 and 32 x 64
# the tunnel opens into the docking bay: the same shape, this much bigger and
# this deep, whatever the spacing; its far wall is the bay doors
BAY_SCALE = 3.0
BAY_DEPTH = 3.6
# ships parked in the bay: ship units to a tunnel unit (a slot is 2 units
# wide), and only ships that would fit through the slot
SHIP_SCALE = 150.0
SLOT_ROOM = 0.95        # how much of the slot a ship may fill
# where they park: either side of the way in, two rows deep (x, depth into
# the bay), in tunnel units
PARK_SPOTS = ((-1.6, 1.3), (1.6, 1.3), (-1.6, 2.7), (1.6, 2.7))
PARKED_RGB = (0.75, 0.75, 0.75)
# your own ship, seen from behind as it flies through the tunnel: this far
# ahead of the view (tunnel units), a little below the middle of the slot
# (a fraction of its half height), in your ship's colour
ME_AHEAD = 2.0
ME_LOW = 0.35
ME_RGB = (0.3, 0.9, 1)
# Taking off and landing in the bay: on launch the ship rises off the bay floor
# over the first ME_LIFT of the scene before flying out (the view closing in
# on it meanwhile); on docking it settles onto the floor over the last ME_LAND.
ME_LIFT = 0.3
ME_LAND = 0.3
# the colours a ship can be painted at the Repair Shop: (name, rgb)
SHIP_COLOURS = (
    ("CYAN", (0.3, 0.9, 1)),
    ("WHITE", (1, 1, 1)),
    ("RED", (1, 0.25, 0.2)),
    ("ORANGE", (1, 0.55, 0.1)),
    ("YELLOW", (1, 0.9, 0.2)),
    ("GREEN", (0.3, 1, 0.35)),
    ("BLUE", (0.35, 0.5, 1)),
    ("PURPLE", (0.75, 0.4, 1)),
)


def ship_rgb(i):
    """The colour of paint number i (SHIP_COLOURS), cyan if unknown."""
    return SHIP_COLOURS[i][1] if isinstance(i, int) and 0 <= i < len(SHIP_COLOURS) else ME_RGB
# lit windows along both side walls of the bay, high up, overlooking the ships:
# how many a side, how high on the wall (fractions of its half height) and
# how long each is (tunnel units), and the colour of their frames (only the
# frames are drawn)
BAY_WINDOWS = 3
WINDOW_Y = (0.3, 0.7)
WINDOW_LEN = 0.7
WINDOW_FRAME = (1.0, 1.0, 1.0)

# the gaps between rings, from the mouth inwards, before they are scaled to
# add up to TUNNEL_RINGS - 1 (so a tunnel is always the same length)
TUNNEL_SPACINGS = (
    ("EVEN", (1,) * 11),
    ("WIDENING", tuple(0.4 + 0.12 * i for i in range(11))),
    ("NARROWING", tuple(1.6 - 0.12 * i for i in range(11))),
    ("PAIRS", tuple(0.45 if i % 2 else 1.55 for i in range(11))),
    ("THREES", tuple(2.0 if i % 3 == 2 else 0.5 for i in range(11))),
)


class Tunnel:
    """One station's tunnel. Ring 0 is the mouth; the last ring before the
    bay is where the tunnel opens into it, and the last ring of all is the
    bay doors, BAY_SCALE times the slot's size. depth[j] is ring j's distance in from the mouth (0 to
    TUNNEL_RINGS - 1); pts the slot's four corners, the same for every ring,
    as whole numbers, 16ths of a pixel at distance 1. seed (the system's
    number) picks the spacing; station (its ship name) the slot's shape."""

    def __init__(self, seed=0, station="CORIOLIS"):
        seed = int(seed) & 0xFF
        sp = (seed // 4 + seed // 17) % len(TUNNEL_SPACINGS)
        self.names = ("SLOT", TUNNEL_SPACINGS[sp][0])
        last = TUNNEL_RINGS - 1
        gaps = TUNNEL_SPACINGS[sp][1][:last - 1]    # between the rings; then the bay
        k = (last - BAY_DEPTH) / sum(gaps)
        self.depth = []
        d = 0.0
        for j in range(last):
            if j:
                d += gaps[j - 1] * k
            self.depth.append(d)
        self.depth[last - 1] = last - BAY_DEPTH
        self.depth.append(float(last))              # the doors, at the back of the bay
        aspect = SLOT_ASPECT.get(station, 3.0)
        w = int(TUNNEL_FOCAL * 16)
        h = int(TUNNEL_FOCAL * 16 / aspect)
        self.pts = ((w, h), (-w, h), (-w, -h), (w, -h))
        self.mouth_in = 1.0 / aspect    # the slot's half height, for the stars beyond
        self.aspect = aspect
        self.parked = []                # ships in the bay (_Parked): see park
        self.me = None                  # your ship, drawn flying through (see _draw_me)
        self.me_rgb = ME_RGB            # and its paint

    def fits(self, bp):
        """True if this ship would fit through the slot, level."""
        hw = max([abs(v[0]) for v in bp.verts] or [0])
        hh = max([abs(v[1]) for v in bp.verts] or [0])
        room = SHIP_SCALE * SLOT_ROOM
        return hw <= room and hh <= room / self.aspect

    def fly(self, bp, rgb=ME_RGB):
        """Show this ship (your own, painted rgb) flying through the tunnel. One
        too big for the slot (a Boa, Python or Anaconda in a Coriolis, whose slot
        is three times as wide as high) is drawn shrunk to just fit (Brian: the
        ship you fly was missing from the scene)."""
        self.me_rgb = rgb
        if bp is None:
            self.me = None
            return
        k = 1.0
        if not self.fits(bp):
            hw = max([abs(v[0]) for v in bp.verts] or [1])
            hh = max([abs(v[1]) for v in bp.verts] or [1])
            room = SHIP_SCALE * SLOT_ROOM
            k = 0.95 * min(room / hw, room / self.aspect / hh)
        self.me = _MeInTunnel(bp, k)

    def park(self, bps, rnd):
        """Park these ships (blueprints) in the bay, the ones that fit the
        slot, one to a spot, each facing in or out, a little askew."""
        spots = list(PARK_SPOTS)
        self.parked = []
        floor = BAY_SCALE / self.aspect
        for bp in bps:
            if not spots or not self.fits(bp):
                continue
            x, d = spots.pop(rnd.randrange(len(spots)))
            hh = max([abs(v[1]) for v in bp.verts] or [0])
            a = rnd.uniform(-0.3, 0.3) + (math.pi if rnd.random() < 0.5 else 0.0)
            self.parked.append(_Parked(bp, x, -floor + hh / SHIP_SCALE,
                                       TUNNEL_RINGS - 1 - BAY_DEPTH + d, a))


class _MeInTunnel:
    """Your ship in the tunnel: what draw_ship needs, facing straight ahead."""
    kind = "ship"
    hit = 0.0

    def __init__(self, bp, k=1.0):
        self.bp = bp
        self.m = [k, 0.0, 0.0, 0.0, k, 0.0, 0.0, 0.0, k]      # k < 1: shrunk to fit the slot
        self.x = self.y = self.z = 0.0
        self.hh = k * max([abs(v[1]) for v in bp.verts] or [0])    # how far down its hull goes


class _Parked:
    """A ship parked in the bay: tunnel units across (x), up (y) and its
    depth in from the mouth; turned by a about the vertical. Has what
    draw_ship needs."""
    kind = "ship"
    hit = 0.0

    def __init__(self, bp, x, y, depth, a):
        self.bp = bp
        self.tx = x
        self.ty = y
        self.depth = depth
        c = math.cos(a)
        sn = math.sin(a)
        # side, roof, nose: level, the nose a round from straight ahead
        self.m = [c, 0.0, -sn, 0.0, 1.0, 0.0, sn, 0.0, c]
        self.x = self.y = self.z = 0.0


_TUNNEL0 = None


def _tunnel(tun):
    global _TUNNEL0
    if tun is not None:
        return tun
    if _TUNNEL0 is None:
        _TUNNEL0 = Tunnel(0)
    return _TUNNEL0


# where each corner of each ring lands on the screen, while drawing
_SX = [0] * (TUNNEL_RINGS * 4)
_SY = [0] * (TUNNEL_RINGS * 4)


def _draw_rings(ctx, tun, zs, rgb, doors):
    """Draw the rings at distances zs[j] (None if not drawn): the mouth in
    the station's colour, the tunnel's rings and its four long edges, the
    wall where it opens into the bay, and (if doors) the bay's edges and its
    doors, filled dimly, in the station's colour."""
    ctx.line_width = 1.5
    sx = _SX
    sy = _SY
    last = TUNNEL_RINGS - 1
    shown = []
    for j in range(TUNNEL_RINGS):
        z = zs[j]
        if z is None:
            continue
        shown.append(j)
        kk = int(1024 / z)
        if j == last:
            kk = int(kk * BAY_SCALE)
        base = j * 4
        for i in range(4):
            x, y = tun.pts[i]       # the tunnel doesn't turn: each ring is a scale of these
            sx[base + i] = x * kk >> 14
            sy[base + i] = y * kk >> 14
    # far to near, so the doors are filled before anything is drawn over them
    shown.sort(key=lambda j: -zs[j])
    for j in shown:
        z = zs[j]
        b = 1.0 if z < 2 else 2.0 / z      # dimmer further in
        base = j * 4
        if j == last:
            ctx.rgb(rgb[0] * 0.25, rgb[1] * 0.25, rgb[2] * 0.25)
            _ring_path(ctx, base)
            ctx.fill()
        if j == 0 or j == last:
            ctx.rgb(rgb[0] * b, rgb[1] * b, rgb[2] * b)
        else:
            ctx.rgb(b, b, b)
        _ring_path(ctx, base)
        ctx.stroke()
    tube = [j for j in shown if j < last]
    if len(tube) > 1:       # the rings are all the same shape, so these are straight
        near = tube[-1] * 4
        far = tube[0] * 4
        ctx.rgb(*GREY)
        ctx.begin_path()
        for i in range(4):
            ctx.move_to(sx[near + i], sy[near + i])
            ctx.line_to(sx[far + i], sy[far + i])
        ctx.stroke()
    # the bay: its front wall (round the tunnel's end) and its four edges back
    # to the doors, from the nearest point still in front of you
    zo = zs[last - 1] if zs[last - 1] is not None else (0.4 if zs[last] is not None else None)
    if zo is None:
        return
    ko = int(1024 * BAY_SCALE / zo)
    ox = [x * ko >> 14 for x, y in tun.pts]
    oy = [y * ko >> 14 for x, y in tun.pts]
    b = 1.0 if zo < 2 else 2.0 / zo
    ctx.rgb(b, b, b)
    if zs[last - 1] is not None:
        ctx.begin_path()
        ctx.move_to(ox[3], oy[3])
        for i in range(4):
            ctx.line_to(ox[i], oy[i])
        ctx.stroke()
    if zs[last] is not None:
        d = last * 4
        ctx.rgb(*GREY)
        ctx.begin_path()
        for i in range(4):
            ctx.move_to(ox[i], oy[i])
            ctx.line_to(sx[d + i], sy[d + i])
        ctx.stroke()


def _ring_path(ctx, base):
    sx = _SX
    sy = _SY
    ctx.begin_path()
    ctx.move_to(sx[base + 3], sy[base + 3])
    for p in range(base, base + 4):
        ctx.line_to(sx[p], sy[p])


def _pulse(s, passes, mouth_flash):
    """How bright the LEDs are when s has gone past the first few of passes
    (the s at which each ring goes by, in order): a fading pulse after each
    ring, and after the mouth (the ring passes[mouth_flash], if any) a full
    flash fading to 0.4."""
    last = None
    for n, p in enumerate(passes):
        if s >= p:
            last = n
    if last is None:
        return 0.0
    p = s - passes[last]
    if last == mouth_flash:
        return 1.0 - 0.6 * min(1.0, p)
    return 0.5 * (1 - p) * (1 - p) if p < 1 else 0.0


def tunnel_glow(f, tun=None):
    """How bright the LEDs are at point f (0 to 1) of the launch: a pulse as
    each ring goes by, then full once you are out of the mouth."""
    tun = _tunnel(tun)
    last = TUNNEL_RINGS - 1
    s = (TUNNEL_RINGS + 1) * f * f
    if s >= last + 0.2:                 # out of the mouth
        return 1.0
    # ring j goes by when last - depth[j] + 0.6 - s = 0.4; the doors behind you don't
    passes = [last - tun.depth[j] + 0.2 for j in range(last - 1, -1, -1)]
    return _pulse(s, passes, None)


# Docking is the launch the other way round: in through the mouth, the rings
# coming at you more and more slowly, to a stop at the bay doors at the back.
DOCK_START = 3.0        # the mouth starts this far ahead
DOCK_END = BAY_DEPTH + 0.2     # and you stop with the doors this far ahead: at the way into the bay


def _dock_depth(f):
    """How far into the tunnel you are at point f (0 to 1) of docking:
    quick through the mouth, slowing to a stop."""
    g = 1.0 - f
    return (DOCK_START + TUNNEL_RINGS - 1 - DOCK_END) * (1.0 - g * g)


def dock_glow(f, tun=None):
    """How bright the LEDs are at point f (0 to 1) of docking: rising as the
    mouth comes up, a flash going through it, then a pulse for each ring."""
    tun = _tunnel(tun)
    s = _dock_depth(f)
    first = DOCK_START - 0.4            # the mouth goes by when s reaches this
    if s < first:
        return 0.4 * s / first
    return _pulse(s, [d + first for d in tun.depth], 0)


# stars seen through the mouth of the tunnel: (x, y, distance from the centre)
def _scatter(n):
    out = []
    v = 12345
    for _ in range(n):
        v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        x = (v >> 8) % 221 - 110
        v = (v * 1103515245 + 12345) & 0x7FFFFFFF
        y = (v >> 8) % 221 - 110
        out.append((x, y, int(math.sqrt(x * x + y * y))))
    return tuple(out)


_STARS = _scatter(40)
_ZS = [None] * TUNNEL_RINGS


def draw_tunnel(ctx, f, t, rgb=GREEN, inward=False, tun=None):
    """The launch: flying out along the station's tunnel (tun, a Tunnel). f
    goes from 0 at the start to 1 at the mouth; t is the time in seconds
    (unused: the tunnel doesn't turn); rgb is the station's colour, for the mouth. With inward,
    docking instead: f goes from 0 outside the mouth to 1 stopped at the
    doors."""
    tun = _tunnel(tun)
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
    zs = _ZS
    last = TUNNEL_RINGS - 1
    if inward:
        s = _dock_depth(f)
        for j in range(TUNNEL_RINGS):
            z = tun.depth[j] + DOCK_START - s
            zs[j] = z if z >= 0.4 else None
        _draw_rings(ctx, tun, zs, rgb, True)
        _draw_windows(ctx, tun, DOCK_START - s, zs[TUNNEL_RINGS - 2])
        _draw_parked(ctx, tun, DOCK_START - s, zs[TUNNEL_RINGS - 2])
        k = (f - (1.0 - ME_LAND)) / ME_LAND       # landing: 0 to 1 over the last part
        _draw_me(ctx, tun, ME_AHEAD, _ease(k))
        return
    s = (TUNNEL_RINGS + 1) * f * f      # slow at first, then faster
    # space, through the mouth: as far out as the circle inside it
    z = 0.6 - s + last
    seen = 170 if z < 0.4 else int(tun.mouth_in * TUNNEL_FOCAL / z)
    if seen > 4:
        ctx.rgb(*GREY)
        for x, y, r in _STARS:
            if r < seen:
                ctx.rectangle(x, y, 1.5, 1.5).fill()
    for j in range(TUNNEL_RINGS):
        z = last - tun.depth[j] + 0.6 - s
        zs[j] = z if z >= 0.4 and j < last else None    # the doors are behind you
    _draw_rings(ctx, tun, zs, rgb, False)
    _draw_windows(ctx, tun, None, None, last + 0.6 - s)
    _draw_parked(ctx, tun, None, None, last + 0.6 - s)
    # taking off: it rises from the floor where it stands while the view
    # closes in, then flies out ME_AHEAD in front
    s_lift = (TUNNEL_RINGS + 1) * ME_LIFT * ME_LIFT
    _draw_me(ctx, tun, ME_AHEAD + s_lift - min(s, s_lift), 1.0 - _ease(f / ME_LIFT))


def _ease(k):
    """0 to 1, smoothly (k is clipped to 0..1)."""
    if k <= 0:
        return 0.0
    if k >= 1:
        return 1.0
    return k * k * (3.0 - 2.0 * k)


def _draw_me(ctx, tun, ahead, down):
    """Your ship, ahead tunnel units in front of the view, level and flying
    the way you look: in from the mouth when docking, out to it on launch.
    down is 0 at its flying height in the slot, 1 standing on the bay floor.
    Filled black inside its outline so the tunnel behind it doesn't show
    through; the rings nearer than it are all bigger than it, so none would
    cross it."""
    o = tun.me
    if o is None:
        return
    fly = -ME_LOW / tun.aspect
    floor = -BAY_SCALE / tun.aspect + o.hh / SHIP_SCALE
    o.x = 0.0
    o.y = (fly + (floor - fly) * down) * SHIP_SCALE
    o.z = ahead * FOCAL / TUNNEL_FOCAL * SHIP_SCALE
    draw_ship(ctx, o, tun.me_rgb, 3, True)


def _draw_windows(ctx, tun, ahead, gate, back=None):
    """Lit windows along the bay's side walls (see BAY_WINDOWS). Distances
    and gate as for _draw_parked."""
    if BAY_WINDOWS <= 0:
        return
    last = TUNNEL_RINGS - 1
    start = last - BAY_DEPTH
    step = (BAY_DEPTH - 0.4) / BAY_WINDOWS
    wall = BAY_SCALE                        # the side walls, in tunnel units
    half = BAY_SCALE / tun.aspect           # the bay's half height
    ylo = WINDOW_Y[0] * half
    yhi = WINDOW_Y[1] * half
    f = TUNNEL_FOCAL
    for k in range(BAY_WINDOWS):
        d1 = start + 0.3 + k * step
        d2 = d1 + WINDOW_LEN
        if back is None:
            z1 = d1 + ahead
            z2 = d2 + ahead
        else:
            z1 = back - d1
            z2 = back - d2
        if z1 > z2:
            z1, z2 = z2, z1
        if z2 < 0.3:
            continue                        # behind you
        if z1 < 0.3:
            z1 = 0.3                        # cut off where it passes you
        if gate is not None:                # in the tunnel still: seen through the opening?
            zc = (z1 + z2) / 2
            if wall / zc > 1.0 / gate or yhi / zc > 1.0 / tun.aspect / gate:
                continue
        for side in (-1, 1):
            x1 = int(side * f * wall / z1)
            x2 = int(side * f * wall / z2)
            pts = ((x1, int(-f * yhi / z1)), (x2, int(-f * yhi / z2)),
                   (x2, int(-f * ylo / z2)), (x1, int(-f * ylo / z1)))
            ctx.rgb(*WINDOW_FRAME)
            ctx.begin_path()
            ctx.move_to(*pts[3])
            for p in pts:
                ctx.line_to(*p)
            ctx.stroke()


def _draw_parked(ctx, tun, ahead, gate, back=None):
    """The ships parked in the bay. A ship at depth d is d + ahead away
    (docking), or back - d (launching, looking out). gate is how far
    ahead the tunnel opens into the bay, or None once you are in it: until
    then only ships seen through the opening are drawn."""
    zk = FOCAL / TUNNEL_FOCAL * SHIP_SCALE      # tunnel distance to world units
    for o in tun.parked:
        z = o.depth + ahead if back is None else back - o.depth
        if z < 0.2:
            continue
        o.x = o.tx * SHIP_SCALE
        o.y = o.ty * SHIP_SCALE
        o.z = z * zk
        if gate is not None:    # in the tunnel still: is it in sight through the opening?
            sx = TUNNEL_FOCAL * o.tx / z
            sy = TUNNEL_FOCAL * o.ty / z
            if (abs(sx) > TUNNEL_FOCAL / gate
                    or abs(sy) > TUNNEL_FOCAL / tun.aspect / gate):
                continue
        draw_ship(ctx, o, PARKED_RGB, 3)    # never a marker: these are close


def draw(ctx, g, ms=None, ring=True):
    """Draw the whole cockpit for Game g. ms is the frame time to show, or None."""
    draw_world(ctx, g)
    draw_hud(ctx, g, ms, ring)


# While the docking computer flies, the view is from behind and above your own
# ship (Brian's idea): the camera sits CHASE_BACK behind you and CHASE_UP above.
CHASE_BACK = 760
CHASE_UP = 130
CHASE_DOCK = 220        # docking: the camera closes in to this far outside the slot's face
CHASE_CLOSE = 0.5       # as you dock (Brian: the station bigger before the tunnel),
                        # coming this much closer for each unit you do
_auto_in = None
PLAYER_NOSE = 40        # your ship's nose is in the slot this far before its middle


def chase_back(g):
    """How far behind your ship the chase camera is: CHASE_BACK, closing in
    on the docking computer's final approach so that when the ship is
    game.AUTO_IN inside the slot (docked) the camera is CHASE_DOCK outside
    the slot's face, the station filling the screen."""
    global _auto_in
    sp = g.space
    st = sp.station if sp is not None else None
    if st is None or getattr(g, "auto_phase", 0) != 2:
        return float(CHASE_BACK)
    if _auto_in is None:        # looked up once (cockpit doesn't import game at start)
        from . import game
        _auto_in = game.AUTO_IN
    d = sp.d_station - st.bp.front + _auto_in     # 0 when docked
    near = CHASE_DOCK + _auto_in
    return max(float(near), min(float(CHASE_BACK), near + d * CHASE_CLOSE))
_me = None      # your ship, for that view: [Obj, the Game whose blueprint it is]


def _chase_shift(g, dy, dz):
    """Move everything drawn by (0, dy, dz): into the chase camera's view and
    back out again (only while drawing; the rules never see it)."""
    for o in g.objs:
        o.y += dy
        o.z += dz
    idy = int(dy)
    idz = int(dz)
    for p in g.dust:
        p[1] += idy
        p[2] += idz
    for boom in g.booms:
        for p in boom.parts:
            p[1] += idy
            p[2] += idz
    sp = g.space
    if sp is not None:
        sp.py += dy
        sp.pz += dz
        sp.sy += dy
        sp.sz += dz
        if sp.station is not None:
            sp.station.y += dy
            sp.station.z += dz


class _Me:
    """Your own ship, as draw_ship wants it: straight ahead of the chase
    camera, facing the way you fly."""

    def __init__(self, bp):
        self.bp = bp
        self.kind = "ship"
        self.x = 0.0
        self.y = -float(CHASE_UP)
        self.z = float(CHASE_BACK)      # draw_world moves it in as the camera closes in
        self.m = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.hit = 0.0


def _my_ship(g):
    global _me
    if _me is None or _me[1] is not g:
        bp = g.types.get(getattr(g, "ship_name", "COBRA MK III"))   # the ship you fly
        if bp is None:
            return None
        _me = [_Me(bp), g, 0.0, 0.0]
    # bank and pitch with the docking computer's stick, eased, so you can see it fly
    p, r = getattr(g, "auto_stick", (0.0, 0.0))
    _me[2] += (r * 0.5 - _me[2]) * 0.2
    _me[3] += (p * 0.25 - _me[3]) * 0.2
    b, a = _me[2], _me[3]
    cb, sb, ca, sa = math.cos(b), math.sin(b), math.cos(a), math.sin(a)
    # side, roof, nose: rolled by b (right wing down), then nose up by a
    _me[0].m = [cb, -sb, 0.0, sb * ca, cb * ca, sa, -sb * sa, -cb * sa, ca]
    return _me[0]


def _streak_tail(view, tail):
    """Where a speck of stardust was, from where it is now, in the view's
    frame (x, z), with the jump drive on: the dust rushes at you from the
    front, away from you at the back and across the side views (left: from
    the right; right: from the left), so each streak trails the way it came
    (game.Game.view_dust)."""
    if view == 1:
        return 0, -tail
    if view == 2:
        return tail, 0
    if view == 3:
        return -tail, 0
    return 0, tail


def draw_world(ctx, g):
    """Space, ships, explosions and laser beams; from behind your ship while
    the docking computer flies."""
    if getattr(g, "autodock", False):
        me = _my_ship(g)
        if me is not None:
            back = chase_back(g)
            up = CHASE_UP * back / CHASE_BACK       # the ship stays where it is on screen
            me.y = -up
            me.z = back
            _chase_shift(g, -up, back)
            try:
                sp = g.space
                st = sp.station if sp is not None else None
                inside = st is not None and sp.d_station < st.bp.front + PLAYER_NOSE
                if inside:      # going into the slot: drawn first, so the station hides it
                    draw_ship(ctx, me, getattr(g, "ship_rgb", CYAN), 0, True)
                _draw_world(ctx, g, 0)     # the station in 3D however far off it is
                if not inside:
                    draw_ship(ctx, me, getattr(g, "ship_rgb", CYAN), 0, True)
            finally:
                _chase_shift(g, up, -back)
            return
    if g.view:      # rear, left or right: the world turned into that view (Game.enter_view)
        dust = g.dust
        g.dust = g.view_dust()
        g.enter_view()
        try:
            _draw_world(ctx, g)
        finally:
            g.leave_view()
            g.dust = dust
        text(ctx, VIEW_NAMES[g.view] + " VIEW", 0, -96, 11, GREY)
        return
    _draw_world(ctx, g)


def _draw_world(ctx, g, station_wire=WIRE_MIN):
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
    ctx.line_width = 1.5

    if g.warp > 0:      # just out of hyperspace: streaks rushing out from the centre
        k = 256 - int(g.warp * 256 / _WARP_T)       # 0 at the start to 256 at the end
        if k < 0:
            k = 0
        ctx.rgb(*CYAN)
        ctx.begin_path()
        for dx, dy, r0 in _STREAKS:
            a = r0 + (k * 40 >> 8)
            b = a + 12 + (k * 110 >> 8)
            ctx.move_to(dx * a >> 8, dy * a >> 8)
            ctx.line_to(dx * b >> 8, dy * b >> 8)
        ctx.stroke()

    sp = g.space
    if sp is not None:
        _draw_space(ctx, sp, station_wire)

    # stardust, so speed and turning can be seen (close to you, so drawn over the
    # planet and sun); with the jump drive on, each speck is a streak back to
    # where it was two steps ago
    if g.jumping:
        ctx.rgb(*WHITE)
        tail = 2 * g.fwd
        if tail < STREAK_MIN:
            tail = STREAK_MIN
        tx, tz = _streak_tail(g.view, int(tail))
        ctx.begin_path()
        for p in g.dust:
            z = int(p[2])
            if z > INEAR:
                x = int(p[0])
                y = int(p[1])
                ctx.move_to(x * IFOCAL // z, -(y * IFOCAL // z))
                x += tx
                z += tz
                if z <= INEAR:      # rear view: where it was is behind the screen
                    z = INEAR + 1
                ctx.line_to(x * IFOCAL // z, -(y * IFOCAL // z))
        ctx.stroke()
    else:
        ctx.rgb(*GREY)
        for p in g.dust:
            z = int(p[2])
            if z > INEAR:
                ctx.rectangle(int(p[0]) * IFOCAL // z, -(int(p[1]) * IFOCAL // z), 1.5, 1.5).fill()


    for o in g.objs:
        draw_ship(ctx, o)
        if o.beam > 0:
            _enemy_beam(ctx, o)

    for boom in g.booms:
        fade = 1.0 - boom.t / boom.life
        if fade <= 0:
            continue
        ctx.rgb(1, 0.5 + 0.5 * fade, 0.2 * fade)
        for p in boom.parts:
            z = int(p[2])
            if z > INEAR:
                ctx.rectangle(int(p[0]) * IFOCAL // z - 1,
                              -(int(p[1]) * IFOCAL // z) - 1, 2.5, 2.5).fill()

    if g.beam > 0:      # the player's twin lasers meet at the crosshair
        ctx.rgb(*LASER_COLOURS.get(g.laser, RED))
        ctx.begin_path()
        ctx.move_to(-60, 100)
        ctx.line_to(0, 0)
        ctx.move_to(60, 100)
        ctx.line_to(0, 0)
        ctx.stroke()

    t = g.lock
    if t is not None and t.z > NEAR:    # missile sights: a diamond round the ship, red
        k = FOCAL / t.z                 # (white for a low-risk ship) until the missile has locked on, then green
        h = int(t.bp.size * k) + 5
        if h < 9:
            h = 9
        elif h > 48:
            h = 48
        bx = int(t.x * k)
        by = -int(t.y * k)
        ctx.rgb(*(GREEN if g.locked else RED if hostile(t) else WHITE))
        ctx.begin_path()
        ctx.move_to(bx, by - h)
        ctx.line_to(bx + h, by)
        ctx.line_to(bx, by + h)
        ctx.line_to(bx - h, by)
        ctx.line_to(bx, by - h)
        ctx.stroke()


def hostile(o):
    """A ship that is a danger to you: a pirate, or anything attacking you
    (red on the radar and in the missile sights). A hull left adrift after
    its crew bailed out isn't (build 92: low-risk ships' sights are white)."""
    if o.state == "drift":
        return False
    return o.role == "pirate" or o.state == "attack" or o.state == "break"


def _sphere(x, y, z, r):
    """Where a sphere is on screen: (x, y, radius) in pixels, or None if it is
    behind you, too close to draw as a circle, or off screen."""
    if z < r * 0.5:
        return None
    k = FOCAL / z
    x *= k
    y *= -k
    r *= k
    if x - r > 120 or x + r < -120 or y - r > 120 or y + r < -120:
        return None
    return x, y, r


def _covers(c):
    """True if the circle (x, y, r) covers the whole screen."""
    x = abs(c[0]) + 120
    y = abs(c[1]) + 120
    return x * x + y * y < c[2] * c[2]


MAX_ARC = 2000      # pixels: circles bigger than this that don't cover the screen are left out


def _sun(ctx, sp, sun):
    if sun is None:
        return
    ctx.rgb(*SUN_COLOURS[sp.sun % len(SUN_COLOURS)])
    if _covers(sun):
        ctx.rectangle(-120, -120, 240, 240).fill()
    elif sun[2] < MAX_ARC:
        ctx.arc(sun[0], sun[1], sun[2], 0, TAU, 0).fill()


def _planet(ctx, sp, planet):
    """The planet: a disc in its colour with a brighter outline."""
    if planet is None:
        return
    fill, edge = PLANET_COLOURS[sp.planet % len(PLANET_COLOURS)]
    ctx.rgb(*fill)
    if _covers(planet):
        ctx.rectangle(-120, -120, 240, 240).fill()
        return
    if planet[2] >= MAX_ARC:
        return
    x, y, r = planet
    ctx.arc(x, y, r, 0, TAU, 0).fill()
    ctx.rgb(*edge).arc(x, y, r, 0, TAU, 0).stroke()


def _draw_space(ctx, sp, wire=WIRE_MIN):
    """The sun (filled), the planet (an outline, filled black if it is in
    front of the sun) and the station, in its government's colour."""
    sun = _sphere(sp.sx, sp.sy, sp.sz, sp.sr)
    planet = _sphere(sp.px, sp.py, sp.pz, sp.pr)
    # whichever is nearer is drawn last, over the other
    sun_near = (sp.sx * sp.sx + sp.sy * sp.sy + sp.sz * sp.sz
                < sp.px * sp.px + sp.py * sp.py + sp.pz * sp.pz)
    if sun_near:
        _planet(ctx, sp, planet)
        _sun(ctx, sp, sun)
    else:
        _sun(ctx, sp, sun)
        _planet(ctx, sp, planet)
    st = sp.station
    if st is not None:
        # in front of the planet and over its outline: the station hides it
        solid = False
        if (planet is not None and st.z > NEAR
                and st.x * st.x + st.y * st.y + st.z * st.z
                < sp.px * sp.px + sp.py * sp.py + sp.pz * sp.pz):
            k = FOCAL / st.z
            dx = st.x * k - planet[0]
            dy = -st.y * k - planet[1]
            pr = st.bp.size * k
            d = math.sqrt(dx * dx + dy * dy)
            solid = abs(d - planet[2]) < pr
        # wire 0 (the docking computer's view): a wireframe at its true size
        # however far off, never a dot or marker
        draw_ship(ctx, st, station_colour(sp.gov), wire, solid)


# the compass, right of the radar: a ring with a dot that points to the planet,
# or to the station in the safe zone; bright if it is ahead, dim behind
COMPASS_X = 80
COMPASS_Y = 60
COMPASS_R = 9
_COMPASS = tuple(
    (COMPASS_X + COMPASS_R * math.cos(i * TAU / 16) - 0.75,
     COMPASS_Y + COMPASS_R * math.sin(i * TAU / 16) - 0.75)
    for i in range(16)
)


COOL_CABIN = 30         # the same as game.COOL_CABIN
SCOOP_TEMP = 224        # the same as game.SCOOP_TEMP
SUN_HEAT = 36.0         # the same as game.SUN_HEAT
# the altitude gauge is full where the cabin starts to warm, empty at the
# sun's surface: in sun radii above it, so it fits every sun's size
SUN_GAUGE_ALT = math.sqrt((285 - COOL_CABIN) / SUN_HEAT) - 1.0
# the cabin temperature gauge's colour, from cool to too hot: green while it
# is safe, through yellow and orange to red near the surface
CT_COLOURS = ((0.0, (0.2, 1.0, 0.3)), (0.45, (1.0, 0.9, 0.1)), (0.7, (1.0, 0.55, 0.1)),
              (0.86, (1.0, 0.15, 0.1)))
MAX_FUEL = 70           # the Cobra's full tank, tenths of a light year (Game.fuel_max: the ship's)


def ct_colour(cabin):
    """The cabin temperature gauge's colour (see CT_COLOURS), blended."""
    f = (cabin - COOL_CABIN) / (255.0 - COOL_CABIN)
    last = CT_COLOURS[0]
    for at, rgb in CT_COLOURS:
        if f <= at:
            if at == last[0]:
                return rgb
            k = (f - last[0]) / (at - last[0])
            a = last[1]
            return (a[0] + (rgb[0] - a[0]) * k, a[1] + (rgb[1] - a[1]) * k,
                    a[2] + (rgb[2] - a[2]) * k)
        last = (at, rgb)
    return last[1]


def _sun_gauges(ctx, g, sp):
    """Near the sun: cabin temperature (CT) and altitude above the sun (AL),
    two bars across the top of the screen, and the fuel (FU) under them. CT
    goes from green through yellow and orange to red near the surface; AL is
    full where the cabin starts to warm and empty at the sun's surface; FU is
    red below a quarter of a tank."""
    ctx.rgba(0, 0, 0, 0.6).rectangle(-74, -99, 148, 19).fill()    # readable against the sun
    text(ctx, "CT", -66, -92, 9, GREY)
    text(ctx, "AL", 66, -92, 9, GREY)
    ctx.rgb(*DIM).rectangle(-58, -94, 50, 4).fill()
    ctx.rgb(*DIM).rectangle(8, -94, 50, 4).fill()
    t = (g.cabin - COOL_CABIN) * 50 // (255 - COOL_CABIN)
    ctx.rgb(*ct_colour(g.cabin))
    ctx.rectangle(-58, -94, t, 4).fill()
    d = math.sqrt(sp.sx * sp.sx + sp.sy * sp.sy + sp.sz * sp.sz) - sp.sr
    a = int(50 * d / (SUN_GAUGE_ALT * sp.sr))
    a = 0 if a < 0 else 50 if a > 50 else a
    ctx.rgb(*CYAN).rectangle(8, -94, a, 4).fill()
    full = getattr(g, "fuel_max", MAX_FUEL)     # the ship's own tank (ships.tank)
    if g.fuel is not None and full:     # the fuel, under them: watch it fill as you skim
        text(ctx, "FU", -66, -83, 9, GREY)
        ctx.rgb(*DIM).rectangle(-58, -85, 116, 4).fill()
        f = min(g.fuel, full) * 116 // full
        ctx.rgb(*(RED if g.fuel < full // 4 else GREEN)).rectangle(-58, -85, f, 4).fill()


def _compass(ctx, sp):
    ctx.rgb(0.38, 0.38, 0.48)
    for px, py in _COMPASS:
        ctx.rectangle(px, py, 1.5, 1.5).fill()
    st = sp.station
    if sp.safe and st is not None:
        x, y, z = st.x, st.y, st.z
        rgb = station_colour(sp.gov)
    else:
        x, y, z = sp.px, sp.py, sp.pz
        rgb = PLANET
    d = math.sqrt(x * x + y * y + z * z)
    if d < 1:
        return
    k = (COMPASS_R - 2) / d
    dx = COMPASS_X + int(x * k)
    dy = COMPASS_Y - int(y * k)
    if z >= 0:
        ctx.rgb(*rgb).rectangle(dx - 1.5, dy - 1.5, 3, 3).fill()
    else:
        ctx.rgb(rgb[0] * 0.4, rgb[1] * 0.4, rgb[2] * 0.4).rectangle(dx - 1, dy - 1, 2, 2).fill()


def _vbar(ctx, x, frac, rgb):
    ctx.rgb(*DIM).rectangle(x, -30, 6, 60).fill()
    if frac > 0:
        if frac > 1:
            frac = 1
        h = 60 * frac
        ctx.rgb(*rgb).rectangle(x, 30 - h, 6, h).fill()


def draw_hud(ctx, g, ms=None, ring=True):
    """Crosshair, gauges, radar and numbers. ring: flash a red ring when hit
    (for badges where the LEDs can't be used for that)."""
    # crosshair (not in the docking computer's view from behind your ship)
    if not getattr(g, "autodock", False) and g.laser is not None:      # as Elite: only with a laser here
        ctx.rgb(*GREEN)
        ctx.rectangle(6, -0.75, 8, 1.5).fill()
        ctx.rectangle(-14, -0.75, 8, 1.5).fill()
        ctx.rectangle(-0.75, 6, 1.5, 8).fill()
        ctx.rectangle(-0.75, -14, 1.5, 8).fill()

    # gauges: speed and laser heat on the left, shield and energy on the right
    _vbar(ctx, -112, g.speed / getattr(g, "max_speed", 40.0), CYAN if g.jumping else GREEN)
    _vbar(ctx, -103, g.heat, RED if g.hot else YELLOW)
    _vbar(ctx, 97, g.shield / 100.0, CYAN)
    _vbar(ctx, 106, g.hull / 100.0, GREEN if g.hull > 30 else RED)

    # missiles left, one slot for each of the ship's pylons (build 82)
    for i in range(getattr(g, "max_missiles", 4)):
        ctx.rgb(*(GREEN if i < g.missiles else DIM)).rectangle(-70 + i * 9, 56, 6, 4).fill()

    # radar: across is left-right, up the ellipse is ahead, sticks show height
    ctx.rgb(0.38, 0.38, 0.48)
    for px, py in _RADAR:
        ctx.rectangle(px, py, 1.5, 1.5).fill()
    ctx.rectangle(-RADAR_RX, RADAR_Y - 0.5, 2 * RADAR_RX, 1).fill()
    ctx.rectangle(-0.5, RADAR_Y - RADAR_RY, 1, 2 * RADAR_RY).fill()
    for o in g.objs:        # in whole numbers, like draw_ship
        x = int(o.x)
        z = int(o.z)
        if x * x + z * z > _RADAR_R2:
            continue
        bx = x * RADAR_RX // _RADAR_R
        by = RADAR_Y - z * RADAR_RY // _RADAR_R
        h = int(o.y) * 22 // _RADAR_R
        if h > 22:
            h = 22
        elif h < -6:
            h = -6
        if o.kind == "ship":    # hostile ships red, the police blue, traders white
            if hostile(o):
                ctx.rgb(*RED)
            elif o.role == "police":
                ctx.rgb(*POLICE_BLUE)
            else:
                ctx.rgb(*WHITE)
        else:
            ctx.rgb(*COLOUR[o.kind])
        if h >= 0:
            ctx.rectangle(bx, by - h, 1, h).fill()
        else:
            ctx.rectangle(bx, by, 1, -h).fill()
        ctx.rectangle(bx - 1, by - h - 1, 3, 3).fill()
    sp = g.space
    if sp is not None:
        st = sp.station     # far off it is beyond cheap whole numbers, so check first
        if st is not None and -_RADAR_R < st.x < _RADAR_R and -_RADAR_R < st.z < _RADAR_R:
            x = int(st.x)
            z = int(st.z)
            if x * x + z * z <= _RADAR_R2:
                bx = x * RADAR_RX // _RADAR_R
                by = RADAR_Y - z * RADAR_RY // _RADAR_R
                h = int(max(-6000.0, min(22000.0, st.y))) * 22 // _RADAR_R
                ctx.rgb(*station_colour(sp.gov))
                if h >= 0:
                    ctx.rectangle(bx, by - h, 1, h).fill()
                else:
                    ctx.rectangle(bx, by, 1, -h).fill()
                ctx.rectangle(bx - 2, by - h - 2, 5, 5).fill()
        if not sp.witch:        # nothing to point at in witchspace
            _compass(ctx, sp)
        if g.cabin > COOL_CABIN:
            _sun_gauges(ctx, g, sp)

    # combat practice: wave (yellow) and score (white), as one centred row of
    # digits; a commander's flight has neither
    if sp is None:
        wave = str(g.wave)
        score = str(g.score)
        width = (len(wave) + len(score)) * 10 - 6 + 9
        x = -width / 2.0
        ctx.rgb(*YELLOW)
        x += number(ctx, g.wave, x, -102, _BIG, -1) + 9
        ctx.rgb(*WHITE)
        number(ctx, g.score, x, -102, _BIG, -1)
    if ms is not None:      # frame time in ms, small, just above
        ctx.rgb(*GREY)
        number(ctx, ms, 0, -114, _SMALL)

    if g.bomb_t > 0:    # the energy bomb: the screen flashes white
        ctx.rgba(1, 1, 1, min(1.0, g.bomb_t * 2.0)).rectangle(-120, -120, 240, 240).fill()
    if g.over and g.ejected:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -42, 200, 100).fill()
        text(ctx, "ESCAPE POD", 0, -22, 24, YELLOW)
        text(ctx, "ship and cargo lost", 0, 6, 13, WHITE)
        text(ctx, "C: to the station" if g.again.endswith("station") else g.again,
             0, 30, 12, GREY)
        text(ctx, "F: title screen", 0, 46, 12, GREY)
    elif g.over:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -42, 200, 100).fill()
        text(ctx, "GAME OVER", 0, -22, 26, RED)
        text(ctx, "SCORE %d   KILLS %d" % (g.score, g.kills), 0, 6, 14, WHITE)
        text(ctx, g.again, 0, 30, 12, GREY)
        text(ctx, "F: title screen", 0, 46, 12, GREY)
    elif g.msg_t > 0:
        # a dark band behind it, so it can be read against the sun
        ctx.rgba(0, 0, 0, 0.6).rectangle(-78, -75, 156, 18).fill()
        text(ctx, g.msg, 0, -66, 14, YELLOW)

    if ring and g.flash > 0:     # just been hit
        ctx.line_width = 6
        ctx.rgb(*RED).arc(0, 0, 116, 0, TAU, 0).stroke()
        ctx.line_width = 1.5
