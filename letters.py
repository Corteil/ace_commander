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


def face_dots(e, s=1.0):
    """For each face of ship entry e: its normal . a vertex on it (the vertices scaled
    by s). With the camera on the ship's view axis d away from its middle, and nz the
    normal's turned z (into the screen), a face shows when face_dot + d * nz < 0: seen
    in perspective, as cockpit.draw_ship judges it (judging by nz alone, as if from far
    off, shows the far side's lines of a ship close up)."""
    verts, edges, normals = e[1], e[2], e[3]
    fv = [-1] * len(normals)
    for a, b, f1, f2 in edges:
        if fv[f1] < 0:
            fv[f1] = a
        if fv[f2] < 0:
            fv[f2] = a
    out = []
    for i in range(len(normals)):
        v = fv[i]
        if v < 0:
            out.append(0.0)
        else:
            nx, ny, nz = normals[i]
            x, y, z = verts[v]
            out.append((nx * x + ny * y + nz * z) * s)
    return out


def draw_edges(ctx, e, pts, vis, depth, rgb, side_on=False):
    """Ship entry e's lines between screen points pts (None: behind the camera), where
    face i shows if vis[i]. A ship made of convex parts (e[6]: the ring station, the
    convoy's freighter) is drawn as the game does: back to front by depth (each vertex's
    distance from the camera, the ship's middle 0), a part nearer than the middle
    blacking out what is behind it first (only when side_on, the nose more across the
    view than along it, for a part that says so: as cockpit.draw_ship)."""
    edges = e[2]
    parts = e[6] if len(e) > 6 else None
    if not parts:
        ctx.rgb(*rgb)
        ctx.begin_path()
        for a, b, f1, f2 in edges:
            if vis[f1] or vis[f2]:
                p = pts[a]
                q = pts[b]
                if p is not None and q is not None:
                    ctx.move_to(p[0], p[1])
                    ctx.line_to(q[0], q[1])
        ctx.stroke()
        return
    order = []
    for vs, es, hides in parts:
        d = 0.0
        for v in vs:
            d += depth[v]
        order.append((d / len(vs), vs, es, hides))
    order.sort(key=lambda t: -t[0])
    for d, vs, es, hides in order:
        if d < 0 and (hides == 1 or (hides == 2 and side_on)):
            fill_hull(ctx, [pts[v] for v in vs])
        ctx.rgb(*rgb)
        ctx.begin_path()
        for i in es:
            a, b, f1, f2 = edges[i]
            if vis[f1] or vis[f2]:
                p = pts[a]
                q = pts[b]
                if p is not None and q is not None:
                    ctx.move_to(p[0], p[1])
                    ctx.line_to(q[0], q[1])
        ctx.stroke()


def fill_hull(ctx, pts):
    """Fill black the outline round pts (the smallest convex shape holding them all),
    if none is None (behind the camera)."""
    for p in pts:
        if p is None:
            return
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
    depth = []
    for x, y, z in verts:
        x, z = x * ca + z * sa, -x * sa + z * ca
        y, z = y * cb - z * sb, y * sb + z * cb
        d = 1.0 + z * k / 400.0     # a little perspective: the camera 400 / k in front
        pts.append((x * k / d, SHIP_Y - y * k / d))
        depth.append(z)
    # hidden lines (build 151: the far side showed through): faces turned the same way
    dots = face_dots(e)
    vis = []
    cam = 400.0 / k
    for i, (nx, ny, nz) in enumerate(e[3]):
        if nx == 0 and ny == 0 and nz == 0:
            vis.append(True)        # no normal: always drawn
            continue
        nz = -nx * sa + nz * ca
        nz = ny * sb + nz * cb
        vis.append(dots[i] + cam * nz < 0)
    draw_edges(ctx, e, pts, vis, depth, SHIP_RGB, -0.5 < ca * cb < 0.5)
    return e[5] if len(e) > 5 else e[0]
