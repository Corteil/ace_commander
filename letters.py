"""The game's name in block letters, built from rectangles (text is slow to
draw on the badge). Shared by the title screen (title.py) and the loading
screen (app.py), so it imports nothing and is quick to load. Also the loading
screens' ship (build 110): one of the game's own designs, tumbling."""
import math

_GLYPHS = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#...#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
}


def block_rects(word, px, y):
    """Rectangles (x, y, w, h) that spell word in 5 by 7 block letters with
    px-sized dots, centred on x = 0 with its top at y. Each row of a letter
    is one rectangle per run of dots, to keep the count down."""
    step = 6 * px
    x0 = -(len(word) * step - px) / 2.0
    out = []
    for i, ch in enumerate(word):
        rows = _GLYPHS.get(ch)
        if rows is None:
            continue
        gx = x0 + i * step
        for r, row in enumerate(rows):
            c = 0
            while c < 5:
                if row[c] == "#":
                    start = c
                    while c < 5 and row[c] == "#":
                        c += 1
                    out.append((gx + start * px, y + r * px, (c - start) * px, px))
                else:
                    c += 1
    return tuple(out)


ACE = block_rects("ACE", 4, -110)
COMMANDER = block_rects("COMMANDER", 2, -76)
ACE_RGB = (1, 0.85, 0.2)
COMMANDER_RGB = (1, 1, 1)


def draw_name(ctx):
    """ACE in yellow and COMMANDER in white, at the top of the screen."""
    ctx.rgb(*ACE_RGB)
    for x, y, w, h in ACE:
        ctx.rectangle(x, y, w, h).fill()
    ctx.rgb(*COMMANDER_RGB)
    for x, y, w, h in COMMANDER:
        ctx.rectangle(x, y, w, h).fill()


# ---- the loading screens' ship (build 110, Brian: "should have a ship on it from
# one of our ships"): the Kestrel, the game's own design for the ship you start
# in (Elite's Cobra Mk III role), from original_ships; the badge's app.py and the
# Tufty's host_tufty both draw it, between the name and the bar
LOAD_SHIP = "COBRA MK III"
SHIP_RGB = (0.3, 0.85, 1.0)
SHIP_Y = -18            # its middle, on the 240 canvas
SHIP_SIZE = 32.0        # half its span on the screen, about
BAR_Y = 42              # the loading bar under it, and the module being loaded below that


def load_ship(ships):
    """The loading screen's ship from original_ships.SHIPS, or None."""
    for e in ships:
        if e[0] == LOAD_SHIP:
            return e
    return None


def draw_ship(ctx, e, t):
    """The ship entry e as a wireframe turning with time t (seconds), in
    SHIP_RGB, centred on SHIP_Y. Returns the name to show under it."""
    verts = e[1]
    span = 1.0
    for v in verts:
        for c in v:
            if c > span:
                span = c
            elif -c > span:
                span = -c
    k = SHIP_SIZE / span
    ca = math.cos(t * 0.9)
    sa = math.sin(t * 0.9)
    cb = math.cos(0.45)     # tipped towards you
    sb = math.sin(0.45)
    pts = []
    for x, y, z in verts:
        x, z = x * ca + z * sa, -x * sa + z * ca
        y, z = y * cb - z * sb, y * sb + z * cb
        d = 1.0 + z * k / 400.0     # a little perspective
        pts.append((x * k / d, SHIP_Y - y * k / d))
    ctx.rgb(*SHIP_RGB)
    ctx.begin_path()
    for edge in e[2]:
        a = pts[edge[0]]
        b = pts[edge[1]]
        ctx.move_to(a[0], a[1])
        ctx.line_to(b[0], b[1])
    ctx.stroke()
    return e[5] if len(e) > 5 else e[0]
