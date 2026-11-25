"""Tufty's flight screen: a 3D view over an Elite-style dashboard, 320 x 240.

    +--------------------------------------+
    |                                      |
    |        3D view  320 x 180            |   crosshair, messages, game over, wave/score
    |                                      |
    +--------------------------------------+
    | SH ====   [2x2]  .--scanner--.  O  SP ====|   dashboard 320 x 60: bars either side
    | EN ====   missiles  '-------'  compass CT ====|   (SH EN FU LT | SP CT AL), missile column,
    | FU ====                              AL ====|   elliptical scanner, compass, S lamp
    | LT ====                                     |
    +--------------------------------------+

The scanner is the radar; hostile ships are red, as in the EMF build. Everything is drawn through
a ctx (ctx_tufty.py) from whole-number rectangles and a few lines. The game state comes from
game.Game exactly as cockpit.draw_hud reads it, so no rules change. Layout numbers are constants
at the top: change them freely. Moved from Corteil/tufty_ace_commarder in build 109: the game's
cockpit module is handed in (use), layout_tufty places and calls it (FlightFrame went), and the
SP, FU and missile gauges follow the ship you fly (its top speed, tank and pylons).
"""
import math

ck = None       # the game's cockpit module: set by use()


def use(cockpit):
    global ck
    ck = cockpit

VIEW_W, VIEW_H = 320, 180
DASH_H = 60
SCREEN_W, SCREEN_H = 320, 240

# scanner (relative to the dashboard centre)
SC_RX, SC_RY = 62, 18
SC_Y = 6                 # ellipse centre, down from the dashboard centre
STICK = 12               # tallest blip stalk, pixels

# gauges: three bars either side. label x, bar x, bar width, first row y, row step, bar height
LEFT = (-157, -141, 48)
RIGHT = (94, 110, 48)
ROW0, ROW_STEP, BAR_H = -20, 12, 7
COMPASS_X, COMPASS_Y, COMPASS_R = 78, -12, 9      # top of the column right of the scanner
MISSILE_X, MISSILE_Y, MISSILE_STEP = -80, -20, 8      # a column of up to five lamps (one per pylon)
S_X, S_Y = 70, 17                                       # the S lamp (safe zone), below the compass
E_X, E_Y = 86, 17                                       # the E lamp (ECM firing), beside it
ECM_RGB = (0.63, 0.0, 1.0)                              # violet, as the ECM's LED flash

PANEL = (0.04, 0.04, 0.07)
RULE = (0.38, 0.38, 0.48)
TAU = math.pi * 2
_RING_OUT = tuple((SC_RX * math.cos(i * TAU / 28) - 0.75, SC_Y + SC_RY * math.sin(i * TAU / 28) - 0.75)
                  for i in range(28))
_RING_IN = tuple((SC_RX // 2 * math.cos(i * TAU / 16) - 0.5, SC_Y + SC_RY // 2 * math.sin(i * TAU / 16) - 0.5)
                 for i in range(16))
_COMPASS = tuple((COMPASS_X + COMPASS_R * math.cos(i * TAU / 16) - 0.75,
                  COMPASS_Y + COMPASS_R * math.sin(i * TAU / 16) - 0.75) for i in range(16))


def _bar(ctx, col, row, label, frac, rgb):
    lx, bx, w = col
    y = ROW0 + row * ROW_STEP
    ck.text(ctx, label, lx, y + BAR_H // 2, 9, ck.GREY, -1)
    ctx.rgb(*ck.DIM).rectangle(bx, y, w, BAR_H).fill()
    if frac > 0:
        ctx.rgb(*rgb).rectangle(bx, y, w * min(1.0, frac), BAR_H).fill()


def _blip_colour(o):
    if o.kind == "ship":
        if o.role == "pirate" or o.state == "attack" or o.state == "break":
            return ck.RED
        if o.role == "police":
            return ck.POLICE_BLUE
        return ck.WHITE
    return o.rgb or ck.COLOUR[o.kind]


def _stalk(ctx, bx, by, h, size):
    if h >= 0:
        ctx.rectangle(bx, by - h, 1, h).fill()
    else:
        ctx.rectangle(bx, by, 1, -h).fill()
    ctx.rectangle(bx - size // 2, by - h - size // 2, size, size).fill()


def _scanner(ctx, g):
    ctx.rgb(*ck.RADAR_GRID)     # as the badge's and the Pi's (build 139)
    for px, py in _RING_OUT:
        ctx.rectangle(px, py, 1.5, 1.5).fill()
    for px, py in _RING_IN:
        ctx.rectangle(px, py, 1, 1).fill()
    ctx.rectangle(-SC_RX, SC_Y - 0.5, 2 * SC_RX, 1).fill()
    ctx.rectangle(-0.5, SC_Y - SC_RY, 1, 2 * SC_RY).fill()
    R, R2 = ck._RADAR_R, ck._RADAR_R2
    for o in g.objs:                 # whole numbers, like cockpit.draw_hud
        x = int(o.x)
        z = int(o.z)
        if x * x + z * z > R2:
            continue
        bx = x * SC_RX // R
        by = SC_Y - z * SC_RY // R
        h = int(o.y) * STICK // R
        h = STICK if h > STICK else (-4 if h < -4 else h)
        ctx.rgb(*_blip_colour(o))
        _stalk(ctx, bx, by, h, 3)
    sp = g.space
    if sp is not None:
        st = sp.station
        if st is not None and -R < st.x < R and -R < st.z < R:
            x, z = int(st.x), int(st.z)
            if x * x + z * z <= R2:
                h = int(max(-6000.0, min(22000.0, st.y))) * STICK // R
                h = STICK if h > STICK else (-4 if h < -4 else h)
                ctx.rgb(*ck.station_colour(sp.gov))
                _stalk(ctx, x * SC_RX // R, SC_Y - z * SC_RY // R, h, 5)
        if not sp.witch:
            _compass(ctx, sp)


def _compass(ctx, sp):
    ctx.rgb(*ck.RADAR_GRID)     # as the scanner (build 139)
    for px, py in _COMPASS:
        ctx.rectangle(px, py, 1.5, 1.5).fill()
    st = sp.station
    if sp.safe and st is not None:
        x, y, z, rgb = st.x, st.y, st.z, ck.station_colour(sp.gov)
    else:
        x, y, z, rgb = sp.px, sp.py, sp.pz, ck.PLANET
    d = math.sqrt(x * x + y * y + z * z)
    if d < 1:
        return
    k = (COMPASS_R - 2) / d
    dx, dy = COMPASS_X + int(x * k), COMPASS_Y - int(y * k)
    if z >= 0:
        ctx.rgb(*rgb).rectangle(dx - 1.5, dy - 1.5, 3, 3).fill()
    else:
        ctx.rgb(rgb[0] * 0.4, rgb[1] * 0.4, rgb[2] * 0.4).rectangle(dx - 1, dy - 1, 2, 2).fill()


ALT_FULL = 2.0           # AL is full this many planet radii above the surface (the safe zone's size)


def altitude(g):
    """(fraction 0..1, colour) for the AL gauge. One gauge, two dangers: height above the planet
    (cyan; full at ALT_FULL radii, empty on the surface) and, while the cabin is warming near a
    sun, height above the sun (orange; full where the cabin starts to warm, as cockpit used to
    show it). Combat practice and witchspace have nothing to measure: an empty dim bar."""
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


def _lamp(ctx, x, y, letter, on, rgb):
    """A square indicator lamp centred on (x, y): dim outline when off, filled with the letter
    cut out in black when on. Elite's S lamp lights inside the station's safe zone."""
    ctx.rgb(*(rgb if on else ck.DIM)).rectangle(x - 6, y - 6, 12, 12).fill()
    ctx.rgb(*PANEL).rectangle(x - 5, y - 5, 10, 10).fill() if not on else None
    ck.text(ctx, letter, x, y, 9, PANEL if on else ck.DIM)


def draw_dashboard(ctx, g):
    """ctx origin at the dashboard's centre; the dashboard fills 320 x 60 about it."""
    ctx.rgb(*PANEL).rectangle(-SCREEN_W // 2, -DASH_H // 2, SCREEN_W, DASH_H).fill()
    ctx.rgb(*RULE).rectangle(-SCREEN_W // 2, -DASH_H // 2, SCREEN_W, 1).fill()
    _bar(ctx, LEFT, 0, "SH", g.shield / 100.0, ck.CYAN)
    _bar(ctx, LEFT, 1, "EN", g.hull / 100.0, ck.GREEN if g.hull > 30 else ck.RED)
    tank = getattr(g, "fuel_max", ck.MAX_FUEL)       # the ship's own tank; 0: no hyperdrive
    fuel = g.fuel / tank if g.fuel is not None and tank else 0
    _bar(ctx, LEFT, 2, "FU", fuel, ck.RED if fuel < 0.25 else ck.GREEN)
    _bar(ctx, LEFT, 3, "LT", g.heat, ck.RED if g.hot else ck.YELLOW)
    _bar(ctx, RIGHT, 0, "SP", g.speed / getattr(g, "max_speed", 40.0), ck.CYAN if g.jumping else ck.GREEN)
    _bar(ctx, RIGHT, 1, "CT", (g.cabin - ck.COOL_CABIN) / (255.0 - ck.COOL_CABIN), ck.ct_colour(g.cabin))
    frac, rgb = altitude(g)
    _bar(ctx, RIGHT, 2, "AL", frac, rgb)
    for i in range(getattr(g, "max_missiles", 4)):  # missiles, one lamp per pylon, the top first
        ctx.rgb(*(ck.GREEN if i < g.missiles else ck.DIM))
        ctx.rectangle(MISSILE_X, MISSILE_Y + i * MISSILE_STEP, 6, 6).fill()
    sp = g.space
    _lamp(ctx, S_X, S_Y, "S", sp is not None and sp.safe, ck.GREEN)
    _lamp(ctx, E_X, E_Y, "E", g.ecm_t > 0, ECM_RGB)
    _scanner(ctx, g)


def draw_view_overlay(ctx, g, ms=None):
    """ctx origin at the view's centre (the view is 320 x 180): crosshair, combat
    wave/score, messages, game over, energy bomb flash."""
    hh = ck.VIEW_HH
    if not getattr(g, "autodock", False):
        ctx.rgb(*ck.GREEN)
        ctx.rectangle(6, -0.75, 8, 1.5).fill()
        ctx.rectangle(-14, -0.75, 8, 1.5).fill()
        ctx.rectangle(-0.75, 6, 1.5, 8).fill()
        ctx.rectangle(-0.75, -14, 1.5, 8).fill()
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
        ck.number(ctx, ms, ck.VIEW_HW - 4, -hh + 3, ck._SMALL, 1)
    if g.bomb_t > 0:
        ctx.rgba(1, 1, 1, min(1.0, g.bomb_t * 2.0)).rectangle(
            -ck.VIEW_HW, -hh, 2 * ck.VIEW_HW, 2 * hh).fill()
    if g.over and g.ejected:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -50, 200, 100).fill()
        ck.text(ctx, "ESCAPE POD", 0, -30, 24, ck.YELLOW)
        ck.text(ctx, "ship and cargo lost", 0, -2, 13, ck.WHITE)
        ck.text(ctx, "C: to the station" if g.again.endswith("station") else g.again, 0, 22, 12, ck.GREY)
        ck.text(ctx, "F: title screen", 0, 38, 12, ck.GREY)
    elif g.over:
        ctx.rgba(0, 0, 0, 0.8).rectangle(-100, -50, 200, 100).fill()
        ck.text(ctx, "GAME OVER", 0, -30, 26, ck.RED)
        ck.text(ctx, "SCORE %d   KILLS %d" % (g.score, g.kills), 0, -2, 14, ck.WHITE)
        ck.text(ctx, g.again, 0, 22, 12, ck.GREY)
        ck.text(ctx, "F: title screen", 0, 38, 12, ck.GREY)
    elif g.msg_t > 0:
        ctx.rgba(0, 0, 0, 0.6).rectangle(-78, -hh + 24, 156, 18).fill()
        ck.text(ctx, g.msg, 0, -hh + 33, 14, ck.YELLOW)


# ---- the badge's LED ring, shown as a border round the 3D view -----------------------------
# Upstream drives 12 ring LEDs (numbered 1-12). Tufty has no ring, so the same 12 values are
# painted as 12 sectors of a thin frame inside the view's edge. LED_ANGLE1 / LED_CLOCKWISE are
# ace.py's: LED 1 is 70 degrees anticlockwise from 3 o'clock and the numbers go clockwise, so a
# jump flash lights the side of the border where its streaks leave the screen.
BORDER = 3
LED_ANGLE1 = 70.0
LED_CLOCKWISE = True
BORDER_STEP = 4


def _led_at(x, y):
    a = math.atan2(-y, x) * 57.29578
    step = (LED_ANGLE1 - a) if LED_CLOCKWISE else (a - LED_ANGLE1)
    return int(math.floor(step / 30.0 + 0.5)) % 12 + 1


def border_runs(hw=VIEW_W // 2, hh=VIEW_H // 2, t=BORDER, step=BORDER_STEP):
    """[(led 1-12, x, y, w, h)] rectangles about the view's centre; neighbours of one LED merged."""
    runs = []

    def side(horizontal, fixed, length, lo, hi):
        pos, last = lo, None
        while pos < hi:
            n = min(step, hi - pos)
            c = pos + n / 2.0
            led = _led_at(c, fixed) if horizontal else _led_at(fixed, c)
            if last is not None and last[0] == led:
                runs[-1] = (led,) + ((last[1], last[2], last[3] + n, last[4]) if horizontal
                                     else (last[1], last[2], last[3], last[4] + n))
                last = runs[-1]
            else:
                x, y, w, h = (pos, fixed - length / 2.0, n, length) if horizontal else (fixed - length / 2.0, pos, length, n)
                runs.append((led, x, y, w, h))
                last = runs[-1]
            pos += n

    side(True, -hh + t / 2.0, t, -hw, hw)           # top
    side(True, hh - t / 2.0, t, -hw, hw)            # bottom
    side(False, -hw + t / 2.0, t, -hh + t, hh - t)  # left
    side(False, hw - t / 2.0, t, -hh + t, hh - t)   # right
    return runs


_BORDER = border_runs()


def draw_led_border(ctx, ring):
    """ctx origin at the view's centre; ring: 12 (r, g, b) tuples, 0-255, LED 1 first."""
    for led, x, y, w, h in _BORDER:
        r, g, b = ring[led - 1]
        if r or g or b:
            ctx.rgb(r / 255.0, g / 255.0, b / 255.0).rectangle(x, y, w, h).fill()
