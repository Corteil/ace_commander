"""Cockpit view for the flight game: ships, radar and gauges on the round
240x240 screen (origin at the centre, y down).

Measured on the badge, a filled rectangle costs about 0.03 ms, a line about
0.35 ms and a piece of text about 4 ms. So everything that is drawn every
frame is built from rectangles where it can be, including the numbers, and
text is kept for messages that only show now and then.
"""
import math

FOCAL = 208.0    # pixels; gives a field of view of about 60 degrees
NEAR = 30.0      # nothing closer than this is drawn
TAU = 2 * math.pi
WIRE_MIN = 8.0   # ships that look smaller than this (pixels) are drawn as a marker

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
GREY = (0.7, 0.7, 0.75)
COLOUR = {"ship": WHITE, "rock": GREY, "can": YELLOW, "missile": MAGENTA, "pmissile": CYAN}

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


def text(ctx, s, x, y, size, rgb):
    ctx.font_size = size
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


# On the badge every float result is a new 16-byte object on the heap, and a
# frame that makes many of them soon has to stop for a garbage collection.
# Small whole numbers cost nothing, so the loops below work in whole numbers:
# positions in world units, directions times 4096, and screen positions in
# whole pixels.
IFOCAL = int(FOCAL)
INEAR = int(NEAR)
_PX = [0] * 48      # screen x of each vertex of the ship being drawn
_PY = [0] * 48      # screen y
_OK = [False] * 48  # False if the vertex is behind the viewer
_VIS = [False] * 24  # which faces of the ship being drawn can be seen


def draw_ship(ctx, o):
    """Draw one object. Returns True if any of it was on screen."""
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
    ctx.rgb(*(RED if o.hit > 0 else COLOUR[o.kind]))
    if pr < 3:          # too far away to make out: a dot
        ctx.rectangle(sx - 1, sy - 1, 2, 2).fill()
        return True
    if pr < WIRE_MIN:   # middle distance: a small marker, much cheaper than lines
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
    i = 0
    for vx, vy, vz in bp.verts:
        pz = z + ((vx * m2 + vy * m5 + vz * m8) >> 12)
        if pz < INEAR:
            ok[i] = False   # behind the viewer
        else:
            ok[i] = True
            px[i] = (x + ((vx * m0 + vy * m3 + vz * m6) >> 12)) * IFOCAL // pz
            py[i] = -((y + ((vx * m1 + vy * m4 + vz * m7) >> 12)) * IFOCAL // pz)
        i += 1

    # Elite's hidden-line rule: a face shows if its normal points back along
    # the line from the viewer to the ship. A zero normal always shows.
    vis = _VIS
    i = 0
    for nx, ny, nz in bp.normals:
        vis[i] = ((nx == 0 and ny == 0 and nz == 0)
                  or ((nx * m0 + ny * m3 + nz * m6) >> 8) * x
                  + ((nx * m1 + ny * m4 + nz * m7) >> 8) * y
                  + ((nx * m2 + ny * m5 + nz * m8) >> 8) * z < 0)
        i += 1

    ctx.begin_path()
    for a, b, f1, f2 in bp.edges:
        if (vis[f1] or vis[f2]) and ok[a] and ok[b]:
            ctx.move_to(px[a], py[a])
            ctx.line_to(px[b], py[b])
    ctx.stroke()
    return True


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


# the launch tunnel: hexagonal rings one unit apart, the way out of the station
TUNNEL_RINGS = 12
TUNNEL_FOCAL = 62.0     # pixels across a ring of radius 1 at distance 1
TUNNEL_SPIN = 0.5       # radians per second: the station turns as you leave
_HEX = tuple((math.cos(k * TAU / 6), math.sin(k * TAU / 6)) for k in range(6))
# each station has its own colour, for the tunnel's mouth and the badge's LEDs
# as you launch. No red (the LEDs flash red when you are hit) and no white (the
# tunnel is white).
STATION_COLOURS = (GREEN, CYAN, YELLOW, MAGENTA, ORANGE, (0.4, 0.55, 1), (1, 0.5, 0.75),
                   (0.65, 0.4, 1))


def station_colour(system):
    """The colour of the station at this system (an index, or None)."""
    if system is None:
        return GREEN
    return STATION_COLOURS[((system * 40503) & 0xFFFF) >> 13]     # mixed, 0 to 7


def tunnel_glow(f):
    """How bright the LEDs are at point f (0 to 1) of the launch: a pulse as
    each ring goes by, then full once you are out of the mouth."""
    p = (TUNNEL_RINGS + 1) * f * f - 0.2    # ring i goes past when this reaches i
    if p < 0:
        return 0.0
    n = int(p)
    if n >= TUNNEL_RINGS - 1:
        return 1.0
    p -= n
    return 0.5 * (1 - p) * (1 - p)


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


def draw_tunnel(ctx, f, t, rgb=GREEN):
    """The launch: flying out along a tunnel of hexagons. f goes from 0 at the
    start to 1 at the mouth; t is the time in seconds, for the spin; rgb is
    the station's colour, for the mouth."""
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
    ctx.line_width = 1.5
    s = (TUNNEL_RINGS + 1) * f * f      # slow at first, then faster
    a = t * TUNNEL_SPIN
    ca = math.cos(a)
    sa = math.sin(a)
    corners = [(TUNNEL_FOCAL * (x * ca - y * sa), TUNNEL_FOCAL * (x * sa + y * ca))
               for x, y in _HEX]
    # space, through the mouth: as far out as the circle inside the last hexagon
    z = TUNNEL_RINGS - 1 + 0.6 - s
    seen = 170 if z < 0.4 else int(0.87 * TUNNEL_FOCAL / z)
    if seen > 4:
        ctx.rgb(*GREY)
        for x, y, r in _STARS:
            if r < seen:
                ctx.rectangle(x, y, 1.5, 1.5).fill()
    near = far = None
    for i in range(TUNNEL_RINGS):
        z = i + 0.6 - s
        if z < 0.4:
            continue
        k = 1.0 / z
        if near is None:
            near = k
        far = k
        b = 1.0 if z < 2 else 2.0 / z      # dimmer further in
        if i == TUNNEL_RINGS - 1:           # the mouth, with space beyond
            ctx.rgb(rgb[0] * b, rgb[1] * b, rgb[2] * b)
        else:
            ctx.rgb(b, b, b)
        ctx.begin_path()
        x, y = corners[5]
        ctx.move_to(int(x * k), int(y * k))
        for x, y in corners:
            ctx.line_to(int(x * k), int(y * k))
        ctx.stroke()
    if near is not None and far != near:    # the tunnel's six long edges
        ctx.rgb(*GREY)
        ctx.begin_path()
        for x, y in corners:
            ctx.move_to(int(x * near), int(y * near))
            ctx.line_to(int(x * far), int(y * far))
        ctx.stroke()


def draw(ctx, g, ms=None, ring=True):
    """Draw the whole cockpit for Game g. ms is the frame time to show, or None."""
    draw_world(ctx, g)
    draw_hud(ctx, g, ms, ring)


def draw_world(ctx, g):
    """Space, ships, explosions and laser beams."""
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
    ctx.line_width = 1.5

    # stardust, so speed and turning can be seen
    ctx.rgb(*GREY)
    for p in g.dust:
        z = int(p[2])
        if z > INEAR:
            ctx.rectangle(int(p[0]) * IFOCAL // z, -(int(p[1]) * IFOCAL // z), 1.5, 1.5).fill()

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
        ctx.rgb(*RED)
        ctx.begin_path()
        ctx.move_to(-60, 100)
        ctx.line_to(0, 0)
        ctx.move_to(60, 100)
        ctx.line_to(0, 0)
        ctx.stroke()

    t = g.lock
    if t is not None and t.z > NEAR:    # missile sights: a diamond round the ship,
        k = FOCAL / t.z                 # red until the missile has locked on, then green
        h = int(t.bp.size * k) + 5
        if h < 9:
            h = 9
        elif h > 48:
            h = 48
        bx = int(t.x * k)
        by = -int(t.y * k)
        ctx.rgb(*(GREEN if g.locked else RED))
        ctx.begin_path()
        ctx.move_to(bx, by - h)
        ctx.line_to(bx + h, by)
        ctx.line_to(bx, by + h)
        ctx.line_to(bx - h, by)
        ctx.line_to(bx, by - h)
        ctx.stroke()


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
    # crosshair
    ctx.rgb(*GREEN)
    ctx.rectangle(6, -0.75, 8, 1.5).fill()
    ctx.rectangle(-14, -0.75, 8, 1.5).fill()
    ctx.rectangle(-0.75, 6, 1.5, 8).fill()
    ctx.rectangle(-0.75, -14, 1.5, 8).fill()

    # gauges: speed and laser heat on the left, shield and energy on the right
    _vbar(ctx, -112, g.speed / 40.0, GREEN)
    _vbar(ctx, -103, g.heat, RED if g.hot else YELLOW)
    _vbar(ctx, 97, g.shield / 100.0, CYAN)
    _vbar(ctx, 106, g.hull / 100.0, GREEN if g.hull > 30 else RED)

    # missiles left
    for i in range(4):
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
        ctx.rgb(*(RED if o.kind == "ship" else COLOUR[o.kind]))   # hostile ships in red
        if h >= 0:
            ctx.rectangle(bx, by - h, 1, h).fill()
        else:
            ctx.rectangle(bx, by, 1, -h).fill()
        ctx.rectangle(bx - 1, by - h - 1, 3, 3).fill()

    # wave (yellow) and score (white), as one centred row of digits
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

    if g.over:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -42, 200, 100).fill()
        text(ctx, "GAME OVER", 0, -22, 26, RED)
        text(ctx, "SCORE %d   KILLS %d" % (g.score, g.kills), 0, 6, 14, WHITE)
        text(ctx, g.again, 0, 30, 12, GREY)
        text(ctx, "F: title screen", 0, 46, 12, GREY)
    elif g.msg_t > 0:
        text(ctx, g.msg, 0, -66, 14, YELLOW)

    if ring and g.flash > 0:     # just been hit
        ctx.line_width = 6
        ctx.rgb(*RED).arc(0, 0, 116, 0, TAU, 0).stroke()
        ctx.line_width = 1.5
