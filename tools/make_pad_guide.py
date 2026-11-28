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
        ("LT", "shoulder", -28, 25.5, 16, 4.5), ("LB", "shoulder", -28, 20.5, 18, 3.6),
        ("RT", "shoulder", 28, 25.5, 16, 4.5), ("RB", "shoulder", 28, 20.5, 18, 3.6),
    ],
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
    """The pad at (cx, cy) with each button's job pointed out: labels (left, right)."""
    c.setFillColor(colour)
    c.setFont("Sans-Bold", 12)
    c.drawCentredString(cx, cy + 46 * mm, heading)
    # shoulders first, behind the body
    centres = {}
    for b in pad["buttons"]:
        if b[1] == "shoulder":
            centres[b[0]] = _button(c, cx, cy, b)
    _body(c, cx, cy, pad)
    for b in pad["buttons"]:
        if b[1] != "shoulder":
            centres[b[0]] = _button(c, cx, cy, b)
    _letters(c, cx, cy, pad)
    left, right = labels
    for side, items in ((-1, left), (1, right)):
        n = len(items)
        top = cy + 36 * mm
        step = 72 * mm / max(1, n - 1) if n > 1 else 0
        lx = cx + side * (COL - 4 * mm)      # where the pointer lines bend
        tx = cx + side * COL
        for i, (name, text) in enumerate(items):
            ty = top - i * step
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
                y = ty - 3 - j * (TEXT + 1.5) + (len(lines) - 1) * (TEXT + 1.5) / 2
                if side < 0:
                    c.drawRightString(tx, y, line)
                else:
                    c.drawString(tx, y, line)


def _wrap(text):
    """text in lines no wider than ROOM (at TEXT), broken after its colon if it can be,
    else between words."""
    if pdfmetrics.stringWidth(text, "Sans", TEXT) <= ROOM:
        return [text]
    words = text.split(" ")
    lines = [""]
    for w in words:
        t = (lines[-1] + " " + w).strip()
        if pdfmetrics.stringWidth(t, "Sans", TEXT) <= ROOM or not lines[-1]:
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
