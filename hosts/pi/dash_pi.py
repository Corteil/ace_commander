"""The Raspberry Pi's Elite-style flight screen (P3): a 3D view over a dashboard.

The Tufty port's layout (Corteil/tufty_ace_commarder, dash_tufty.py) with more of Elite's
dashboard, and as wide as the window: everything is in units of a canvas 240 high, whose
width follows the window's shape (384 on a 16:10 screen, 427 on 16:9, 320 on 4:3).

    +----------------------------------------------------------+
    |                                                          |
    |                 3D view  W x 180                         |   crosshair, messages,
    |                                                          |   view name, hit frame
    +----------------------------------------------------------+
    | SH ====  [m]       .----scanner----.      (o)  SP ====    |   dashboard W x 60:
    | FU ====  [m]      (        +        )   S E  RL --|--    |   left SH FU CT LT AL,
    | CT ====  [m]       '---------------'         DC --|--    |   missiles beside them,
    | LT ====  [m]                                 1  ====     |   scanner, compass and
    | AL ====                                      2..4 ====   |   lamps, right SP RL DC
    +----------------------------------------------------------+   and energy banks 1-4

Elite's details added to the Tufty's: the roll (RL) and dive / climb (DC) indicators, the
energy as four banks (1-4, the bottom one drains last), missile lamps that turn yellow
when armed or seeking and red when locked, one lamp per pylon. The scanner's lines are
nearly white so they show up (Brian). No LED ring on the Pi: being hit flashes a red
frame round the view. The game state comes from game.Game as cockpit.draw_hud reads it.
"""
import math

DASH_H = 60             # the dashboard's height; the view has the rest of the 240
VIEW_H = 240 - DASH_H
ROW0, ROW_STEP, BAR_H = -26, 7.7, 5   # gauge rows: first row's top, step, bar height
LABEL = 7               # gauge label size
SIDE = 84               # width of each gauge block (label, bar)
BAR_W = 58
SC_RY = 20              # scanner: half height; its half width fills the middle
SC_Y = 4                # its centre, below the dashboard's centre
STALK = 13              # tallest blip stalk
COMPASS_R = 9
SCAN_RGB = (0.85, 0.85, 0.9)    # the scanner's lines: near white (Brian); cockpit.RADAR_GRID
                                # is the same, for the badge's and the Tufty's (build 139)
PANEL = (0.04, 0.04, 0.07)
RULE = (0.45, 0.45, 0.55)
ECM_RGB = (0.63, 0.0, 1.0)
TAU = math.pi * 2


class Layout:
    """Where everything goes for a canvas w units wide (the height is always 240)."""

    def __init__(self, w):
        self.w = w
        hw = w / 2.0
        self.hw = hw
        self.left = (-hw + 4, -hw + 18)             # label x, bar x
        self.right = (hw - SIDE + 4, hw - SIDE + 18)
        inner = hw - SIDE - 4                       # room either side of the middle
        self.compass = (inner - COMPASS_R - 2, -14)
        self.lamps = ((inner - 18, 18), (inner - 4, 18))     # S, E
        self.missile_x = -inner + 4
        self.sc_rx = max(40.0, inner - 2 * COMPASS_R - 14)
        self.ring_out = [(self.sc_rx * math.cos(i * TAU / 40), SC_Y + SC_RY * math.sin(i * TAU / 40))
                         for i in range(40)]
        self.ring_in = [(self.sc_rx / 2 * math.cos(i * TAU / 24), SC_Y + SC_RY / 2 * math.sin(i * TAU / 24))
                        for i in range(24)]
        cx, cy = self.compass
        self.compass_ring = [(cx + COMPASS_R * math.cos(i * TAU / 20), cy + COMPASS_R * math.sin(i * TAU / 20))
                             for i in range(20)]


def _row_y(row):
    return ROW0 + row * ROW_STEP


def _bar(ctx, ck, col, row, label, frac, rgb):
    lx, bx = col
    y = _row_y(row)
    ck.text(ctx, label, lx, y + BAR_H / 2.0, LABEL, ck.GREY, -1)
    ctx.rgb(*ck.DIM).rectangle(bx, y, BAR_W, BAR_H).fill()
    if frac > 0:
        ctx.rgb(*rgb).rectangle(bx, y, BAR_W * min(1.0, frac), BAR_H).fill()


def _indicator(ctx, ck, col, row, label, v):
    """Elite's RL / DC: a dim bar with a marker, centre for 0, ends for full."""
    lx, bx = col
    y = _row_y(row)
    ck.text(ctx, label, lx, y + BAR_H / 2.0, LABEL, ck.GREY, -1)
    ctx.rgb(*ck.DIM).rectangle(bx, y, BAR_W, BAR_H).fill()
    ctx.rgb(*RULE).rectangle(bx + BAR_W / 2.0 - 0.5, y, 1, BAR_H).fill()
    v = max(-1.0, min(1.0, v))
    ctx.rgb(*ck.YELLOW).rectangle(bx + BAR_W / 2.0 + v * (BAR_W / 2.0 - 2) - 1.5, y - 1, 3, BAR_H + 2).fill()


def blip_colour(ck, o):
    """The round HUD's rule: hostile ships red, the police blue, other ships white."""
    if o.kind == "ship":
        if ck.hostile(o):
            return ck.RED
        if o.role == "police":
            return ck.POLICE_BLUE
        return ck.WHITE
    return o.rgb or ck.COLOUR[o.kind]


def _stalk(ctx, bx, by, h, size):
    if h >= 0:
        ctx.rectangle(bx - 0.4, by - h, 0.8, h).fill()
    else:
        ctx.rectangle(bx - 0.4, by, 0.8, -h).fill()
    ctx.rectangle(bx - size / 2.0, by - h - size / 2.0, size, size).fill()


def _scanner(ctx, ck, g, L):
    ctx.rgb(*SCAN_RGB)
    for px, py in L.ring_out:
        ctx.rectangle(px - 0.6, py - 0.6, 1.2, 1.2).fill()
    for px, py in L.ring_in:
        ctx.rectangle(px - 0.4, py - 0.4, 0.8, 0.8).fill()
    ctx.rectangle(-L.sc_rx, SC_Y - 0.3, 2 * L.sc_rx, 0.6).fill()
    ctx.rectangle(-0.3, SC_Y - SC_RY, 0.6, 2 * SC_RY).fill()
    R, R2 = ck._RADAR_R, ck._RADAR_R2
    rx = L.sc_rx
    for o in g.objs:
        x, z = o.x, o.z
        if x * x + z * z > R2:
            continue
        bx = x * rx / R
        by = SC_Y - z * SC_RY / R
        h = max(-5.0, min(float(STALK), o.y * STALK / R))
        ctx.rgb(*blip_colour(ck, o))
        _stalk(ctx, bx, by, h, 2.4)
    sp = g.space
    if sp is not None:
        st = sp.station
        if st is not None and -R < st.x < R and -R < st.z < R and st.x * st.x + st.z * st.z <= R2:
            h = max(-5.0, min(float(STALK), max(-6000.0, min(22000.0, st.y)) * STALK / R))
            ctx.rgb(*ck.station_colour(sp.gov))
            _stalk(ctx, st.x * rx / R, SC_Y - st.z * SC_RY / R, h, 4)


def _compass(ctx, ck, sp, L):
    """Elite's compass: the planet (the station in its safe zone), a solid dot when it
    is ahead of you, a dim one when behind."""
    ctx.rgb(*SCAN_RGB)
    for px, py in L.compass_ring:
        ctx.rectangle(px - 0.6, py - 0.6, 1.2, 1.2).fill()
    st = sp.station
    if sp.safe and st is not None:
        x, y, z, rgb = st.x, st.y, st.z, ck.station_colour(sp.gov)
    else:
        x, y, z, rgb = sp.px, sp.py, sp.pz, ck.PLANET
    d = math.sqrt(x * x + y * y + z * z)
    if d < 1:
        return
    cx, cy = L.compass
    k = (COMPASS_R - 2) / d
    dx, dy = cx + x * k, cy - y * k
    if z >= 0:
        ctx.rgb(*rgb).rectangle(dx - 1.5, dy - 1.5, 3, 3).fill()
    else:
        ctx.rgb(rgb[0] * 0.4, rgb[1] * 0.4, rgb[2] * 0.4).rectangle(dx - 1, dy - 1, 2, 2).fill()


ALT_FULL = 2.0           # AL is full this many planet radii above the surface


def altitude(ck, g):
    """(fraction, colour) for AL, as the Tufty: height above the planet (cyan, full at
    ALT_FULL radii) or, while the cabin is warming, above the sun (orange)."""
    sp = g.space
    if sp is None or sp.witch:
        return 0.0, ck.DIM
    if g.cabin > ck.COOL_CABIN:
        d = math.sqrt(sp.sx * sp.sx + sp.sy * sp.sy + sp.sz * sp.sz) - sp.sr
        f, rgb = d / (ck.SUN_GAUGE_ALT * sp.sr), ck.ORANGE
    else:
        d = math.sqrt(sp.px * sp.px + sp.py * sp.py + sp.pz * sp.pz) - sp.pr
        f, rgb = d / (ALT_FULL * sp.pr), ck.CYAN
    return (0.0 if f < 0 else 1.0 if f > 1 else f), rgb


def _lamp(ctx, ck, x, y, letter, on, rgb):
    ctx.rgb(*(rgb if on else ck.DIM)).rectangle(x - 5, y - 5, 10, 10).fill()
    if not on:
        ctx.rgb(*PANEL).rectangle(x - 4, y - 4, 8, 8).fill()
    ck.text(ctx, letter, x, y, 7, PANEL if on else ck.DIM)


def _missiles(ctx, ck, g, L):
    """One lamp per pylon, a column: green ready, yellow armed or seeking, red locked
    (Elite's), the top lamp the one that goes next."""
    n = getattr(g, "max_missiles", 4)
    state = ck.GREEN
    if getattr(g, "locked", False):
        state = ck.RED
    elif getattr(g, "armed", False) or getattr(g, "lock", None) is not None:
        state = ck.YELLOW
    for i in range(n):
        y = _row_y(i)
        if i < g.missiles:
            ctx.rgb(*(state if i == 0 else ck.GREEN))
        else:
            ctx.rgb(*ck.DIM)
        ctx.rectangle(L.missile_x, y, 8, BAR_H).fill()


def draw_dashboard(ctx, ck, g, L, stick=(0.0, 0.0)):
    """ctx origin at the dashboard's centre. stick: (pitch, roll) last flown, -1..1."""
    ctx.rgb(*PANEL).rectangle(-L.hw, -DASH_H / 2.0, L.w, DASH_H).fill()
    ctx.rgb(*RULE).rectangle(-L.hw, -DASH_H / 2.0, L.w, 0.8).fill()
    # left: Elite's shields, fuel, cabin and laser temperature, altitude
    _bar(ctx, ck, L.left, 0, "SH", g.shield / 100.0, ck.CYAN)
    fmax = getattr(g, "fuel_max", 70) or 0
    fuel = (g.fuel / float(fmax)) if (fmax and g.fuel is not None) else 0.0
    _bar(ctx, ck, L.left, 1, "FU", fuel, ck.RED if fuel < 0.25 else ck.GREEN)
    _bar(ctx, ck, L.left, 2, "CT", (g.cabin - ck.COOL_CABIN) / (255.0 - ck.COOL_CABIN), ck.ct_colour(g.cabin))
    _bar(ctx, ck, L.left, 3, "LT", g.heat, ck.RED if g.hot else ck.YELLOW)
    frac, rgb = altitude(ck, g)
    _bar(ctx, ck, L.left, 4, "AL", frac, rgb)
    # right: speed, roll, dive / climb, the four energy banks
    _bar(ctx, ck, L.right, 0, "SP", g.speed / float(getattr(g, "max_speed", 40.0) or 40.0),
         ck.CYAN if g.jumping else ck.GREEN)
    pitch, roll = stick
    _indicator(ctx, ck, L.right, 1, "RL", roll)
    _indicator(ctx, ck, L.right, 2, "DC", pitch)
    low = g.hull <= 30
    for i in range(4):          # bank 1 at the top drains first, bank 4 last
        f = (g.hull - (3 - i) * 25.0) / 25.0
        _bar(ctx, ck, L.right, 3 + i, str(i + 1), f, ck.RED if low else ck.GREEN)
    _missiles(ctx, ck, g, L)
    sp = g.space
    (sx, sy), (ex, ey) = L.lamps
    _lamp(ctx, ck, sx, sy, "S", sp is not None and sp.safe, ck.GREEN)
    _lamp(ctx, ck, ex, ey, "E", g.ecm_t > 0, ECM_RGB)
    _scanner(ctx, ck, g, L)
    if sp is not None and not sp.witch:
        _compass(ctx, ck, sp, L)


def draw_view_overlay(ctx, ck, g, L, ms=None):
    """ctx origin at the view's centre (W x 180): crosshair, view name, wave / score,
    messages, game over, bomb flash, and a red frame when hit (no LEDs on the Pi)."""
    hh = VIEW_H / 2.0
    hw = L.hw
    if not getattr(g, "autodock", False) and g.laser is not None:
        ctx.rgb(*ck.GREEN)
        ctx.rectangle(6, -0.75, 8, 1.5).fill()
        ctx.rectangle(-14, -0.75, 8, 1.5).fill()
        ctx.rectangle(-0.75, 6, 1.5, 8).fill()
        ctx.rectangle(-0.75, -14, 1.5, 8).fill()
    if g.view and not getattr(g, "autodock", False):
        ck.text(ctx, ck.VIEW_NAMES[g.view] + " VIEW", 0, -hh + 10, 9, ck.GREY)
    sp = g.space
    if sp is None:                   # combat practice: wave (yellow) and score (white)
        wave, score = str(g.wave), str(g.score)
        width = (len(wave) + len(score)) * 10 - 6 + 9
        x = -width / 2.0
        ctx.rgb(*ck.YELLOW)
        x += ck.number(ctx, g.wave, x, -hh + 4, ck._BIG, -1) + 9
        ctx.rgb(*ck.WHITE)
        ck.number(ctx, g.score, x, -hh + 4, ck._BIG, -1)
    if ms is not None:
        ctx.rgb(*ck.GREY)
        ck.number(ctx, ms, hw - 4, -hh + 3, ck._SMALL, 1)
    if g.bomb_t > 0:
        ctx.rgba(1, 1, 1, min(1.0, g.bomb_t * 2.0)).rectangle(-hw, -hh, 2 * hw, 2 * hh).fill()
    if g.over and g.ejected:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -50, 200, 100).fill()
        ck.text(ctx, "ESCAPE POD", 0, -30, 24, ck.YELLOW)
        ck.text(ctx, "ship and cargo lost", 0, -2, 13, ck.WHITE)
        ck.text(ctx, "C: to the station" if g.again.endswith("station") else g.again, 0, 22, 12, ck.GREY)
        ck.text(ctx, "F: title screen", 0, 38, 12, ck.GREY)
    elif g.over and getattr(g, "net", None) is not None:     # a duel's own end screen
        ck.draw_duel_over(ctx, g, -60)
    elif g.over:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -50, 200, 100).fill()
        ck.text(ctx, "GAME OVER", 0, -30, 26, ck.RED)
        ck.text(ctx, "SCORE %d   KILLS %d" % (g.score, g.kills), 0, -2, 14, ck.WHITE)
        ck.text(ctx, g.again, 0, 22, 12, ck.GREY)
        ck.text(ctx, "F: title screen", 0, 38, 12, ck.GREY)
    elif g.msg_t > 0:
        ctx.rgba(0, 0, 0, 0.6).rectangle(-78, -hh + 24, 156, 18).fill()
        ck.text(ctx, g.msg, 0, -hh + 33, 14, ck.YELLOW)
    if g.flash > 0:                  # just been hit: a red frame (the badge flashes its LEDs)
        ctx.rgb(*ck.RED)
        t = 2.5
        ctx.rectangle(-hw, -hh, 2 * hw, t).fill()
        ctx.rectangle(-hw, hh - t, 2 * hw, t).fill()
        ctx.rectangle(-hw, -hh, t, 2 * hh).fill()
        ctx.rectangle(hw - t, -hh, t, 2 * hh).fill()
