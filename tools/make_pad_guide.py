"""The Ace Commander game pad guide: an A4 page for each pad layout, the pad drawn as a
wireframe with every button's job pointed out, flying (top) and off the flight (bottom).

    python3 tools/make_pad_guide.py [out.pdf]       (default: pad_guide.pdf in the repo)

Page 1: the 8BitDo Micro (hosts/pi/pad_pi.py MICRO_*, chosen by its name or --pad micro).
Page 2: any other pad SDL knows (Xbox, PlayStation, 8BitDo SN30...), its buttons named by
position as an Xbox pad's (pad_pi.py FLIGHT_MAP, BADGE_MAP). Both on every pygame host:
the Raspberry Pi, Windows, Linux, macOS and the M5 CardputerZero.

Needs ReportLab and the DejaVu fonts, as tools/make_key_guide.py. When a pad map in
pad_pi.py changes, change it here too.
"""
import json
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(REPO, "metadata.json")) as f:
    BUILD = json.load(f).get("version", "?")

D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Sans", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", D + "DejaVuSans-Bold.ttf"))

INK = colors.HexColor("#1b1f24")
WIRE = colors.HexColor("#1b1f24")
ACCENT = colors.HexColor("#1f6f43")     # flying
MENU = colors.HexColor("#1f4f8f")       # off the flight
GREY = colors.HexColor("#6e7781")
FILL = colors.white
W, H = A4
U = mm * 0.72           # the pads are drawn at this scale (their sizes below are in mm)
COL = 44 * mm           # the label columns' distance from the pad's centre
TEXT = 8.4              # label size
ROOM = W / 2 - COL - 12 * mm    # how wide a label may be before it wraps

# ---- the pads, as wireframes: every button is (name, shape, x, y, size...) in mm from
# the drawing's centre; shapes: "dpad" (cross), "circle", "pill", "stick", "shoulder"

MICRO = {
    "title": "8BitDo Micro",
    "body": ("rect", -40, -21, 80, 42, 9),
    "buttons": [
        ("DPAD", "dpad", -24, -1, 15),
        ("X", "circle", 24, 9, 4.2), ("A", "circle", 33, 0, 4.2),
        ("B", "circle", 24, -9, 4.2), ("Y", "circle", 15, 0, 4.2),
        ("-", "circle", -6, 13, 2.8), ("+", "circle", 6, 13, 2.8),       # round (Brian)
        ("STAR", "circle", -4, -13, 2.6), ("HOME", "circle", 4, -13, 2.6),  # star on the left
        # four shoulder buttons in a row on the top edge (Brian): L and R outside,
        # L2 and R2 smaller, inside them
        ("L", "shoulder", -29, 22, 15, 4.2), ("L2", "shoulder", -13, 21.6, 9, 3.4),
        ("R2", "shoulder", 13, 21.6, 9, 3.4), ("R", "shoulder", 29, 22, 15, 4.2),
    ],
    "above": ("L", "L2", "-", "+", "R2", "R"),     # labelled in a row above the pad
    "below": ("STAR", "HOME"),                      # and below it
    "row_y": (30, -26),         # the rows' heights, mm from the pad's centre
    "side_mid": 0,
    "letters": {"X": "X", "A": "A", "B": "B", "Y": "Y", "-": "−", "+": "+", "HOME": "⌂",
                "STAR": "★", "L": "L", "R": "R", "L2": "L2", "R2": "R2"},
}

STANDARD = {
    "title": "Any other game pad (Xbox, PlayStation, 8BitDo SN30...)",
    "body": ("pad",),
    "buttons": [
        ("LSTICK", "stick", -27, 6, 7), ("RSTICK", "stick", 15, -9, 7),
        ("DPAD", "dpad", -15, -9, 13),
        ("Y", "circle", 28, 13, 3.6), ("B", "circle", 36, 5, 3.6),
        ("A", "circle", 28, -3, 3.6), ("X", "circle", 20, 5, 3.6),
        ("BACK", "pill", -7, 8, 6, 2.6), ("START", "pill", 7, 8, 6, 2.6),
        ("GUIDE", "circle", 0, 15, 3.2),
        # shoulders float above the body (Brian)
        ("LT", "shoulder", -28, 30, 16, 4.5), ("LB", "shoulder", -28, 25, 18, 3.6),
        ("RT", "shoulder", 28, 30, 16, 4.5), ("RB", "shoulder", 28, 25, 18, 3.6),
    ],
    "above": ("LT", "LB", "BACK", "GUIDE", "START", "RB", "RT"),
    "below": ("LSTICK", "DPAD", "RSTICK"),
    "row_y": (35, -26),
    "side_mid": 4,
    "letters": {"Y": "Y", "B": "B", "A": "A", "X": "X", "BACK": "◁", "START": "▷",
                "GUIDE": "⌂", "LB": "LB", "RB": "RB", "LT": "LT", "RT": "RT",
                "LSTICK": "L", "RSTICK": "R"},
}

# what each button does: (button, label) left of the pad, then right of it, in order top down
MICRO_FLIGHT = (
    [("L", "L: slower (hold)"), ("L2", "L2: E.C.M."), ("-", "−: next view"),
     ("DPAD", "D-pad: pitch and roll"), ("STAR", "★: not used")],
    [("R", "R: faster (hold)"), ("R2", "R2: energy bomb"), ("+", "+: pause menu"),
     ("X", "X (hold): jump drive"), ("A", "A: fire laser"), ("Y", "Y: docking computer"),
     ("B", "B: missile"), ("HOME", "Home (hold 1 s): escape pod")],
)
MICRO_MENUS = (
    [("L", "L: tab before"), ("L2", "L2: not used"), ("-", "−: Options (docked)"),
     ("DPAD", "D-pad: move, pick, change"), ("STAR", "★: not used")],
    [("R", "R: next tab"), ("R2", "R2: not used"), ("+", "+: launch / pause menu"),
     ("X", "X: find a system (chart)"), ("A", "A: choose, buy"), ("Y", "Y: sell, system data"),
     ("B", "B: back"), ("HOME", "Home: not used")],
)
STANDARD_FLIGHT = (
    [("LT", "LT: missile"), ("LB", "LB: E.C.M. (Hardcore)"), ("BACK", "View / Back: not used"),
     ("LSTICK", "Left stick: speed (up / down), yaw; click: arm missile"),
     ("DPAD", "D-pad: front / rear / left / right view")],
    [("RT", "RT: fire laser"), ("RB", "RB: energy bomb"), ("GUIDE", "Guide (hold 1 s): escape pod"),
     ("START", "Menu / Start: pause menu"), ("Y", "Y: in-flight screens in turn"),
     ("B", "B: docking computer"), ("X", "X: hyperspace (hold: galactic)"),
     ("A", "A (hold): jump drive"), ("RSTICK", "Right stick: pitch and roll; click: next view")],
)
STANDARD_MENUS = (
    [("LT", "LT: not used"), ("LB", "LB: tab before"), ("BACK", "View / Back: Options (docked)"),
     ("LSTICK", "Left stick: move, as the D-pad"), ("DPAD", "D-pad: move, pick, change")],
    [("RT", "RT: fire (in-flight screens)"), ("RB", "RB: next tab"), ("GUIDE", "Guide: not used"),
     ("START", "Menu / Start: launch / pause menu"), ("Y", "Y: find a system, next tab"),
     ("B", "B: back"), ("X", "X: sell, system data"), ("A", "A: choose, buy"),
     ("RSTICK", "Right stick: not used")],
)


def _button(c, cx, cy, b):
    """Draw one button (wireframe) at the drawing's centre (cx, cy); return its
    centre in points (where a pointer line ends)."""
    name, shape = b[0], b[1]
    x, y = cx + b[2] * U, cy + b[3] * U
    c.setStrokeColor(WIRE)
    c.setFillColor(FILL)
    c.setLineWidth(0.9)
    if shape == "circle":
        c.circle(x, y, b[4] * U, stroke=1, fill=1)
    elif shape == "stick":
        c.circle(x, y, b[4] * U, stroke=1, fill=1)
        c.circle(x, y, b[4] * 0.62 * U, stroke=1, fill=0)
    elif shape == "pill":
        w, h = b[4] * U, b[5] * U
        c.roundRect(x - w / 2, y - h / 2, w, h, h / 2, stroke=1, fill=1)
    elif shape == "shoulder":
        w, h = b[4] * U, b[5] * U
        c.roundRect(x - w / 2, y - h / 2, w, h, h / 2.2, stroke=1, fill=1)
    elif shape == "dpad":
        s = b[4] * U
        t = s / 3.0
        p = c.beginPath()
        pts = [(-t / 2, s / 2), (t / 2, s / 2), (t / 2, t / 2), (s / 2, t / 2), (s / 2, -t / 2),
               (t / 2, -t / 2), (t / 2, -s / 2), (-t / 2, -s / 2), (-t / 2, -t / 2), (-s / 2, -t / 2),
               (-s / 2, t / 2), (-t / 2, t / 2)]
        p.moveTo(x + pts[0][0], y + pts[0][1])
        for px, py in pts[1:]:
            p.lineTo(x + px, y + py)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
        c.setLineWidth(0.5)
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):      # arrows
            ax, ay = x + dx * s * 0.36, y + dy * s * 0.36
            c.line(ax - dy * 1.2, ay - dx * 1.2, ax + dx * 1.6, ay + dy * 1.6)
            c.line(ax + dy * 1.2, ay + dx * 1.2, ax + dx * 1.6, ay + dy * 1.6)
    return x, y


def _body(c, cx, cy, pad):
    c.setStrokeColor(WIRE)
    c.setFillColor(FILL)
    c.setLineWidth(1.3)
    body = pad["body"]
    if body[0] == "rect":
        _, x, y, w, h, r = body
        c.roundRect(cx + x * U, cy + y * U, w * U, h * U, r * U, stroke=1, fill=1)
    else:                       # a pad with two grips, a smooth outline (Brian)
        pts = [(0, 20), (24, 20), (38, 17), (45, 8), (48, -8), (47, -21), (40, -28), (31, -25),
               (22, -16), (0, -14), (-22, -16), (-31, -25), (-40, -28), (-47, -21), (-48, -8),
               (-45, 8), (-38, 17), (-24, 20)]
        _smooth(c, [(cx + x * U, cy + y * U) for x, y in pts])


def _smooth(c, pts):
    """A closed smooth outline through pts (Catmull-Rom as cubic Beziers)."""
    n = len(pts)
    p = c.beginPath()
    p.moveTo(*pts[0])
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6.0, p1[1] + (p2[1] - p0[1]) / 6.0)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6.0, p2[1] - (p3[1] - p1[1]) / 6.0)
        p.curveTo(c1[0], c1[1], c2[0], c2[1], p2[0], p2[1])
    p.close()
    c.drawPath(p, stroke=1, fill=1)


def _letters(c, cx, cy, pad):
    c.setFillColor(INK)
    for b in pad["buttons"]:
        s = pad["letters"].get(b[0])
        if not s:
            continue
        x, y = cx + b[2] * U, cy + b[3] * U
        size = 6.5 if len(s) == 1 else 5.5
        c.setFont("Sans-Bold", size)
        c.drawCentredString(x, y - size * 0.35, s)


def drawing(c, cx, cy, pad, labels, colour, heading):
    """The pad at (cx, cy) with each button's job pointed out. labels: (left, right);
    the pad's "above" and "below" buttons (shoulders, the little ones in the middle)
    have theirs in a row above or below it instead (Brian: the labels can float round
    the pad), ordered left to right so their wires don't cross."""
    c.setFillColor(colour)
    c.setFont("Sans-Bold", 12)
    c.drawCentredString(cx, cy + 50 * mm, heading)
    centres = {}
    for b in pad["buttons"]:            # shoulders first, behind the body
        if b[1] == "shoulder":
            centres[b[0]] = _button(c, cx, cy, b)
    _body(c, cx, cy, pad)
    for b in pad["buttons"]:
        if b[1] != "shoulder":
            centres[b[0]] = _button(c, cx, cy, b)
    _letters(c, cx, cy, pad)
    above, below = set(pad.get("above", ())), set(pad.get("below", ()))
    # a button that does nothing here isn't labelled (Brian)
    labels = tuple([it for it in side if "not used" not in it[1]] for side in labels)
    every = list(labels[0]) + list(labels[1])
    rows = (([it for it in every if it[0] in above], cy + pad["row_y"][0] * mm, 1),
            ([it for it in every if it[0] in below], cy + pad["row_y"][1] * mm, -1))
    fixed = []                          # the rows' wires: the side columns mustn't cross them
    for items, y, up in rows:
        if not items:
            continue
        # left to right; of buttons one above another (LT over LB) the one nearer the row
        # gets the inner label, so their wires don't cross
        near = lambda it: up * centres[it[0]][1]         # noqa: E731  (nearer the row: larger)
        items.sort(key=lambda it: (round(centres[it[0]][0], 1),
                                   near(it) if centres[it[0]][0] < cx else -near(it)))
        n = len(items)
        span = min(W - 28 * mm, n * 34 * mm)
        room = span / n - 2 * mm
        for i, (name, text) in enumerate(items):
            x = cx - span / 2 + span * (i + 0.5) / n
            lines = _wrap(text, room)
            bx, by = centres[name]
            c.setStrokeColor(colour)
            c.setLineWidth(0.5)
            end = y - up * 1.5 * mm             # the wire ends just short of the text,
            half = max(pdfmetrics.stringWidth(t, "Sans", TEXT) for t in lines) / 2
            ex = min(max(bx, x - half + 1 * mm), x + half - 1 * mm)     # under the part of
            c.line(bx, by, ex, end)             # it nearest its button (Brian), not its middle
            fixed.append(((bx, by), (ex, end)))
            c.setFillColor(colour)
            c.circle(bx, by, 0.7, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont("Sans", TEXT)
            for j, line in enumerate(lines):
                k = (len(lines) - 1 - j) if up > 0 else j      # grow away from the pad
                c.drawCentredString(x, y + up * k * (TEXT + 1.5) - (0 if up > 0 else TEXT), line)
    for side, items in ((-1, labels[0]), (1, labels[1])):
        items = [it for it in items if it[0] not in above and it[0] not in below]
        n = len(items)
        if not n:
            continue
        step = min(14 * mm, 52 * mm / max(1, n - 1))
        lx = cx + side * (COL - 4 * mm)      # where the pointer lines bend
        tx = cx + side * COL
        found = None
        for drop in range(0, 9):            # lower the column until its wires cross none
            mid = cy + (pad.get("side_mid", 0) - drop * 4) * mm
            slots = [mid + (n - 1) * step / 2 - i * step for i in range(n)]
            found = _uncrossed(items, centres, lx, slots, fixed, cx + side * (COL + ROOM))
            if found is not None:
                break
        if found is None:
            mid = cy + pad.get("side_mid", 0) * mm
            slots = [mid + (n - 1) * step / 2 - i * step for i in range(n)]
            found = _uncrossed(items, centres, lx, slots) or items
        items = found
        for i, (name, text) in enumerate(items):
            ty = slots[i]
            bx, by = centres[name]
            c.setStrokeColor(colour)
            c.setLineWidth(0.5)
            c.line(bx, by, lx, ty)
            c.line(lx, ty, tx - side * 1 * mm, ty)
            c.setFillColor(colour)
            c.circle(bx, by, 0.7, stroke=0, fill=1)
            c.setFillColor(INK)
            c.setFont("Sans", TEXT)
            lines = _wrap(text)
            for j, line in enumerate(lines):
                yy = ty - 3 - j * (TEXT + 1.5) + (len(lines) - 1) * (TEXT + 1.5) / 2
                if side < 0:
                    c.drawRightString(tx, yy, line)
                else:
                    c.drawString(tx, yy, line)


def _crosses(a, b, c, d):
    """Whether segments a-b and c-d cross (touching ends don't count)."""
    def turn(p, q, r):
        v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
        return (v > 1e-9) - (v < -1e-9)
    return (turn(a, b, c) * turn(a, b, d) < 0) and (turn(c, d, a) * turn(c, d, b) < 0)


def _near(a, b, p, r):
    """Whether point p is within r of segment a-b (away from its ends)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    if L == 0:
        return False
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L
    if t <= 0.02 or t >= 1:
        return False
    qx, qy = a[0] + t * dx, a[1] + t * dy
    return (qx - p[0]) ** 2 + (qy - p[1]) ** 2 < r * r


def _uncrossed(items, centres, lx, slots, fixed=(), text_end=None):
    """items in an order whose pointer lines (from centres[name] to (lx, slot)) don't
    cross each other (Brian: "the label wires should not cross"), with as few as can be
    passing over another button: a branch-and-bound search over the orders. As given,
    top down, if no order keeps the lines apart."""
    order = sorted(items, key=lambda it: -centres[it[0]][1])
    n = len(order)
    others = list(centres.items())
    r = 3.6 * U
    over = {}                           # (item, slot) -> buttons its line passes over

    def cost(i, k):
        key = (i, k)
        if key not in over:
            a = centres[order[i][0]]
            b = (lx, slots[k])
            over[key] = sum(1 for name, p in others if name != order[i][0] and _near(a, b, p, r))
        return over[key]

    best = [None, 10 ** 9]
    chosen = []
    used = [False] * n

    def place(k, total):
        if total >= best[1]:
            return
        if k == n:
            best[0], best[1] = list(chosen), total
            return
        for i in range(n):
            if used[i]:
                continue
            a = centres[order[i][0]]
            b = (lx, slots[k])
            if any(_crosses(a, b, centres[order[j][0]], (lx, slots[m])) for m, j in enumerate(chosen)):
                continue
            if any(_crosses(a, b, f0, f1) for f0, f1 in fixed):
                continue
            if text_end is not None:        # nor through this label (its line and text)
                y = slots[k]
                band = [((lx, y + d), (text_end, y + d)) for d in (-4, 0, 5)]
                if any(_crosses(f0, f1, g0, g1) for f0, f1 in fixed for g0, g1 in band):
                    continue
            used[i] = True
            chosen.append(i)
            place(k + 1, total + cost(i, k))
            chosen.pop()
            used[i] = False

    place(0, 0)
    return [order[i] for i in best[0]] if best[0] is not None else None


def _wrap(text, room=None):
    """text in lines no wider than room (default ROOM, at TEXT), broken between words."""
    room = ROOM if room is None else room
    if pdfmetrics.stringWidth(text, "Sans", TEXT) <= room:
        return [text]
    words = text.split(" ")
    lines = [""]
    for w in words:
        t = (lines[-1] + " " + w).strip()
        if pdfmetrics.stringWidth(t, "Sans", TEXT) <= room or not lines[-1]:
            lines[-1] = t
        else:
            lines.append(w)
    return lines

def page(c, pad, flight, menus, note):
    c.setFillColor(ACCENT)
    c.rect(0, H - 6 * mm, W, 6 * mm, stroke=0, fill=1)
    c.setFillColor(INK)
    c.setFont("Sans-Bold", 20)
    c.drawString(14 * mm, H - 19 * mm, "ACE COMMANDER: GAME PAD")
    c.setFont("Sans", 10)
    c.setFillColor(GREY)
    c.drawString(14 * mm, H - 25 * mm, pad["title"])
    drawing(c, W / 2, H - 88 * mm, pad, flight, ACCENT, "FLYING")
    drawing(c, W / 2, H - 205 * mm, pad, menus, MENU, "MENUS, DOCKED, TITLE")
    c.setFont("Sans", 7.5)
    c.setFillColor(GREY)
    y = 20 * mm
    for line in note:
        c.drawString(14 * mm, y, line)
        y -= 3.6 * mm
    c.drawString(14 * mm, 8 * mm, "Ace Commander build %s · the Raspberry Pi, Windows, Linux, macOS and the "
                 "M5 CardputerZero (pygame)" % BUILD)
    c.showPage()


def make(out=None):
    out = out or os.path.join(REPO, "pad_guide.pdf")
    c = canvas.Canvas(out, pagesize=A4)
    c.setTitle("Ace Commander game pad guide")
    c.setAuthor("Ace Commander")
    page(c, MICRO, MICRO_FLIGHT, MICRO_MENUS, [
        "Used when the pad's name says 8BitDo Micro, or with --pad micro (its other modes may give "
        "another name).",
        "Buttons by what is printed on it. On an in-flight screen (charts, status...): D-pad the "
        "cursor, A target, Y system data,",
        "X find, L / R the screen before / after, B back to space. On-screen hints name its buttons."])
    page(c, STANDARD, STANDARD_FLIGHT, STANDARD_MENUS, [
        "Any pad SDL knows as a game controller; buttons by position, named as an Xbox pad's (A bottom, "
        "B right, X left, Y top).",
        "On an in-flight screen: D-pad the cursor, A target, X system data, B back to space, Y the next "
        "screen, Back find, RT fires.",
        "With --pad standard an 8BitDo Micro uses this page's layout too. On-screen hints name the pad's "
        "buttons."])
    c.save()
    return out


if __name__ == "__main__":
    print("written", make(sys.argv[1] if len(sys.argv) > 1 else None))
