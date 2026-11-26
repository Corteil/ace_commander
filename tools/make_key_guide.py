"""The Ace Commander key guides, an A4 page each (the Pi's two): the badge (its buttons and the
Keyboard Hexpansion), the Raspberry Pi (keyboard and game pad) and the Tufty 2350
(its five buttons and the Qw/ST Pad).

Usage: python tools/make_key_guide.py [--platform badge|pi|tufty|all] [out.pdf]
With no file given: key_guide.pdf (the badge), key_guide_pi.pdf, key_guide_tufty.pdf
in the repo folder (gitignored). tools/make_release.py puts the Pi's and the
Tufty's guide in their zips as KEY_GUIDE.pdf.

Needs ReportLab and the DejaVu fonts (Debian: python3-reportlab, fonts-dejavu-core).
DejaVu is used because ReportLab's built-in Helvetica has no arrow or minus
glyphs. The build number comes from metadata.json. When a key changes in
ace.py, hosts/pi/keys_pi.py / pad_pi.py or hosts/tufty/controls_tufty.py,
change it here too.
"""
import argparse
import json
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Table,
                                TableStyle, KeepTogether, FrameBreak)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(REPO, "metadata.json")) as f:
    BUILD = json.load(f).get("version", "?")

D = "/usr/share/fonts/truetype/dejavu/"
pdfmetrics.registerFont(TTFont("Sans", D + "DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", D + "DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Mono", D + "DejaVuSansMono-Bold.ttf"))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold")

INK = colors.HexColor("#1b1f24")
ACCENT = colors.HexColor("#1f6f43")
RULE = colors.HexColor("#c9d1d9")
SHADE = colors.HexColor("#f2f5f7")
KEYBG = "#e6eaee"

title = ParagraphStyle("t", fontName="Sans-Bold", fontSize=20, leading=24, textColor=INK)
sub = ParagraphStyle("s", fontName="Sans", fontSize=9, leading=11, textColor=colors.HexColor("#57606a"))
head = ParagraphStyle("h", fontName="Sans-Bold", fontSize=11, leading=14, textColor=ACCENT,
                      spaceBefore=7, spaceAfter=3)
cell = ParagraphStyle("c", fontName="Sans", fontSize=8.7, leading=11, textColor=INK)
note = ParagraphStyle("n", fontName="Sans", fontSize=8.2, leading=10.4, textColor=colors.HexColor("#424a53"),
                      spaceBefore=2)


def k(*names):
    """Keys drawn as caps."""
    return " ".join('<font name="Mono" size="8.2" backColor="%s">&nbsp;%s&nbsp;</font>' % (KEYBG, n)
                    for n in names)


def table(rows, widths, header=None):
    data = []
    if header:
        data.append([Paragraph("<b>%s</b>" % h, cell) for h in header])
    for r in rows:
        data.append([Paragraph(c, cell) for c in r])
    t = Table(data, colWidths=widths)
    style = [("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
             ("TOPPADDING", (0, 0), (-1, -1), 1.9), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.9),
             ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), SHADE))
    t.setStyle(TableStyle(style))
    return t


def section(name, *flow):
    return KeepTogether([Paragraph(name, head)] + list(flow))


W = (A4[0] - 24 * mm - 8 * mm) / 2      # column width
A, B, C = W * 0.36, W * 0.30, W * 0.34   # action / first device column / second


# ---- the badge --------------------------------------------------------------------------

def badge():
    H = ["Action", "Badge", "Keyboard"]
    left = [
        section("FLYING", table([
            ["Pitch (nose up / down)", "Joystick " + k("↑", "↓"), k("W", "S") + " or " + k("↑", "↓")],
            ["Roll left / right", "Joystick " + k("←", "→"), k("A", "D") + " or " + k("←", "→")],
            ["Fire lasers (hold)", k("C") + " or press joystick", k("Space") + " " + k("F") + " " + k("Enter")],
            ["Speed up / slow down", k("F") + " / " + k("E"), k("+") + " / " + k("−") + " or " + k("E") + " / " + k("Q")],
            ["Fire missile", k("D"), k("M")],
            ["Energy bomb", k("B"), k("Backspace") + " (or " + k("Tab") + "*)"],
            ["Escape pod (if fitted)", "—", k("Esc")],
            ["Jump drive (in-system)", "Hold " + k("F") + " at full speed", "Hold " + k("J")],
            ["Views: front / rear / left / right", "Menu line VIEW", k("1", "2", "3", "4") + " · next " + k("V")],
            ["Docking computer on / off", "Menu line", k("C") + " / " + k("P")],
            ["Pause menu", k("A"), k("P") + " (when the docking computer is off)"],
        ], [A, B, C], H)),
        Paragraph("Speed keys also work as " + k("=") + " / " + k("_") + " (no Shift). The jump drive needs full speed, no ships on the radar and no planet or sun "
                  "close by (“MASS LOCKED”). With tilt steering: tilt to steer, tap "
                  + k("D") + " to re-zero, hold " + k("D") + " to fire a missile.", note),

        section("HYPERSPACE", table([
            ["Hyperspace to the target", "Menu HYPERSPACE", k("H")],
            ["Galactic hyperdrive (if fitted)", "Menu GALACTIC JUMP", k("Shift") + " + " + k("H") + " (or " + k("Ctrl") + " + " + k("H") + "*)"],
            ["Pick a target", "Chart: " + k("C"), "Chart: " + k("Enter")],
        ], [A, B, C], H)),
        Paragraph(k("H") + " with no target opens the local chart. On a chart, "
                  + k("C") + " only selects the system (the line under its name says TARGET); "
                  "then " + k("H") + " jumps.", note),

        section("HARDCORE MODE", table([
            ["Fire the E.C.M.", k("E") + " + " + k("F") + " together", k("E")],
            ["Arm / disarm a missile", k("D") + " arms, " + k("D") + " again fires", k("T") + " / " + k("U")],
        ], [A, B, C], H)),
        Paragraph("Select HARDCORE: ON when you make a new commander (it stays for that commander), "
                  "or on the Combat practice page. "
                  "In Hardcore " + k("E") + " is the E.C.M., so use " + k("+") + " to speed up; "
                  "missiles lock only while armed; docking is by hand only, unless you have "
                  "bought a docking computer.", note),
        Paragraph("<b>MULTIPLAYER</b> (2-4 badges): the E.C.M. is by hand: " + k("B") + " on the badge, "
                  + k("E") + " on a keyboard. Duel destroyed: " + k("C") + " next round; other modes "
                  "come back by themselves. " + k("F") + " leaves the game.", note),
    ]

    right = [
        section("SCREENS IN FLIGHT  (Elite's f4–f9)", table([
            [k("5"), "Galactic chart"], [k("6"), "Local chart"],
            [k("7"), "System data (target, or here)"], [k("8"), "Market prices (view only)"],
            [k("9"), "Commander status"], [k("0"), "Inventory (hold)"],
        ], [W * 0.18, W * 0.82])),
        Paragraph("The game keeps running, as in Elite. Press the same key, " + k("C") + ", "
                  + k("F") + " or " + k("Esc") + " to go back to space; " + k("1") + "–" + k("4")
                  + " go back in that view. On a screen only steering, speed and lasers work, and "
                  "the lasers can't hit anything. Missiles, E.C.M., " + k("J") + " and the bomb wait "
                  "until you are looking at space.", note),

        section("ON A SCREEN OR CHART", table([
            ["Move the cursor / scroll", "Joystick", k("↑", "↓", "←", "→")],
            ["Select target (chart)", k("C"), k("Enter")],
            ["System data (chart)", k("D"), k("D")],
            ["Back to space", k("F"), k("Esc")],
        ], [A, B, C], H)),

        section("PAUSE MENU", table([
            ["Pick a line", "Joystick " + k("↑", "↓"), k("↑", "↓")],
            ["Choose", k("C"), k("Enter")],
            ["Change a setting / the VIEW", "Joystick " + k("←", "→"), k("←", "→")],
            ["Back / resume", k("F") + " / " + k("A"), k("Esc") + " / " + k("P")],
        ], [A, B, C], H)),

        section("DOCKED", table([
            [k("1"), "Launch (badge: " + k("A") + ")"],
            [k("2") + " " + k("8"), "Market: " + k("C") + " buys, " + k("D") + " sells"],
            [k("3"), "Market, on the first good in your hold (to sell)"],
            [k("4"), "Equip ship: " + k("C") + " buys"],
            [k("5") + " " + k("6") + " " + k("7"), "Galactic chart (" + k("B") + ": find) · local chart · system data"],
            [k("9") + " / " + k("0"), "Status (" + k("C") + ": Options) / Inventory (" + k("C") + ": sell all)"],
            [k("−") + " / " + k("="), "Shipyard (Repair Shop inside) / Options"],
            ["Joystick " + k("←", "→"), "Next / previous screen (or " + k("E") + " / " + k("B") + ")"],
            [k("F") + " or " + k("Esc"), "Back to Status, then the title"],
        ], [W * 0.33, W * 0.67])),

        section("SHIP VIEWER", table([
            [k("C") + " or " + k("N"), "Next ship"], [k("P"), "Previous ship"],
            ["Joystick", "Turn it"], [k("F") + " or " + k("Esc"), "Back to the title"],
        ], [W * 0.33, W * 0.67])),
    ]
    return dict(
        heading="ACE COMMANDER · KEY GUIDE",
        sub="Badge buttons and keyboard keys, in flight and docked. Keys follow BBC "
            "Elite’s layout where the game has the same feature.",
        pages=[(left, right)],
        footer=["* Tab and Ctrl need the updated Keyboard Hexpansion driver "
                "(sodoku/tildagon-keebdexpansion PR #5); every other key works with either driver.",
                "Badge: buttons A–F round the screen, joystick in the "
                "middle.  Keyboard: the Tildagon Keyboard Hexpansion or a USB keyboard.",
                "Off the flight (docked, the title) the keyboard's A–F are "
                "the badge's buttons A–F, except while typing a name or a search."],
        device="the EMF Tildagon badge")


# ---- the Raspberry Pi -------------------------------------------------------------------

def pi():
    H = ["Action", "Keyboard", "Game pad"]
    A2, B2, C2 = W * 0.36, W * 0.34, W * 0.30
    left = [
        section("FLYING", table([
            ["Pitch (nose up / down)", k("W", "S") + " or " + k("↑", "↓"), "Right stick " + k("↑", "↓")],
            ["Roll left / right", k("A", "D") + " or " + k("←", "→"), "Right stick " + k("←", "→")],
            ["Yaw left / right", "—", "Left stick " + k("←", "→")],
            ["Fire lasers (hold)", k("Space") + " " + k("F") + " " + k("Enter"), k("RT")],
            ["Speed up / slow down", k("+") + " / " + k("−") + " or " + k("E") + " / " + k("Q"),
             "Left stick " + k("↑", "↓") + " (where it sits is the speed)"],
            ["Fire missile", k("M"), k("LT")],
            ["Energy bomb", k("Backspace") + " or " + k("Tab"), k("RB")],
            ["Escape pod (if fitted)", k("Esc"), "Hold " + k("Guide") + " 1 s"],
            ["Jump drive (in-system)", "Hold " + k("J"), "Hold " + k("A")],
            ["Views: front / rear / left / right", k("1", "2", "3", "4") + " · next " + k("V"),
             "D-pad " + k("↑", "↓", "←", "→") + " · next " + k("R3")],
            ["Docking computer on / off", k("C") + " / " + k("P"), k("B")],
            ["Pause menu", k("P") + " (docking computer off) or " + k("F1"), k("Start")],
        ], [A2, B2, C2], H)),
        Paragraph("Speed keys also work as " + k("=") + " / " + k("_") + " (no Shift). The jump "
                  "drive needs full speed, no ships on the radar and no planet or sun close by "
                  "(“MASS LOCKED”). The pad's left stick sets the speed: top full, middle half, "
                  "bottom stopped.", note),

        section("HYPERSPACE", table([
            ["Hyperspace to the target", k("H"), k("X")],
            ["Galactic hyperdrive (if fitted)", k("Shift") + " + " + k("H") + " or " + k("Ctrl") + " + " + k("H"),
             "Hold " + k("X") + " 1 s"],
            ["Pick a target", "Chart: " + k("Enter"), "Chart: " + k("A")],
        ], [A2, B2, C2], H)),
        Paragraph(k("H") + " with no target opens the local chart. On a chart, "
                  + k("Enter") + " only selects the system (the line under its name says TARGET); "
                  "then " + k("H") + " jumps.", note),

    ]

    right = [
        section("HARDCORE MODE", table([
            ["Fire the E.C.M.", k("E"), k("LB")],
            ["Arm / disarm a missile", k("T") + " / " + k("U"), k("L3") + " arms · " + k("LT") + " arms, then fires"],
        ], [A2, B2, C2], H)),
        Paragraph("Select HARDCORE: ON when you make a new commander (it stays for that commander), "
                  "or on the Combat practice page. In Hardcore " + k("E") + " is the E.C.M., so use "
                  + k("+") + " to speed up; missiles lock only while armed; docking is by hand "
                  "only, unless you have bought a docking computer.", note),
        Paragraph("<b>MULTIPLAYER</b> (start with " + k("--duel") + "): the E.C.M. is by hand: " + k("E")
                  + ", " + k("F2") + " or the pad's " + k("LB") + ". Duel destroyed: " + k("Enter")
                  + " next round; other modes come back by themselves. " + k("Esc") + " leaves the game.", note),

        section("SCREENS IN FLIGHT  (Elite's f4–f9)", table([
            [k("5"), "Galactic chart"], [k("6"), "Local chart"],
            [k("7"), "System data (target, or here)"], [k("8"), "Market prices (view only)"],
            [k("9"), "Commander status"], [k("0"), "Inventory (hold)"],
        ], [W * 0.18, W * 0.82])),
        Paragraph("Pad: " + k("Y") + " steps through local chart, galactic chart, status, "
                  "inventory and market, then back to space. The game keeps running, as in "
                  "Elite: steering, speed and lasers work, but the lasers can't hit anything. "
                  "Press the same key, " + k("Esc") + " or " + k("1") + "–" + k("4") + " to go back.", note),

        section("THE WINDOW", table([
            [k("F10"), "Badge layout (round) / Elite layout (3D view over a dashboard)"],
            [k("F11"), "Full screen / window"],
            [k("F12"), "Screenshot (in ~/Pictures/Ace Commander)"],
            ["Quit", "QUIT on the title screen, or close the window"],
        ], [W * 0.2, W * 0.8])),
    ]

    left2 = [
        section("ON A SCREEN OR CHART", table([
            ["Move the cursor / scroll", k("↑", "↓", "←", "→"), "D-pad"],
            ["Select target (chart)", k("Enter"), k("A")],
            ["System data (chart)", k("D"), k("X")],
            ["Find a system (galactic chart)", k("F2"), k("Back")],
            ["Back to space", k("Esc"), k("B")],
        ], [A2, B2, C2], H)),

        section("PAUSE MENU", table([
            ["Pick a line", k("↑", "↓"), "D-pad " + k("↑", "↓")],
            ["Choose", k("Enter"), k("A")],
            ["Change a setting / the VIEW", k("←", "→"), "D-pad " + k("←", "→")],
            ["Back / resume", k("Esc") + " / " + k("P"), k("B") + " / " + k("Start")],
        ], [A2, B2, C2], H)),

        section("SHIP VIEWER", table([
            ["Next ship", k("C") + " or " + k("N"), k("A")],
            ["Previous ship", k("P"), "—"],
            ["Turn it", k("↑", "↓", "←", "→"), "D-pad or left stick"],
            ["Back to the title", k("Esc"), k("B")],
        ], [A2, B2, C2], H)),
    ]

    right2 = [
        section("DOCKED", table([
            ["Launch", k("1"), k("Start")],
            ["Buy / choose", k("C") + " or " + k("Enter"), k("A")],
            ["Sell", k("D"), k("X")],
            ["Next / previous screen", k("→") + " / " + k("←"), k("RB") + " / " + k("LB")],
            ["Options", k("="), k("Back")],
            ["Find a system (galactic chart)", k("B"), k("Y")],
            ["Back to Status, then the title", k("Esc"), k("B")],
        ], [A2, B2, C2], H)),
        Paragraph("Screens by number: " + k("2") + " / " + k("8") + " market, " + k("3")
                  + " market on the first good in your hold, " + k("4") + " equip, " + k("5")
                  + " " + k("6") + " " + k("7") + " charts and system data, " + k("9")
                  + " status, " + k("0") + " inventory (" + k("C") + ": sell all), " + k("−")
                  + " shipyard (Repair Shop inside), " + k("=") + " options.", note),

    ]
    return dict(
        heading="ACE COMMANDER · KEY GUIDE · RASPBERRY PI",
        sub="Keyboard and game pad, in flight and docked. Keys follow BBC Elite’s layout "
            "where the game has the same feature; hints on screen name whatever you used last.",
        pages=[(left, right), (left2, right2)],
        heading2="RASPBERRY PI · SCREENS AND DOCKED",
        footer=["Game pad: any pad SDL knows (Xbox, PlayStation, 8BitDo...), its buttons named "
                "by position as on an Xbox pad: A bottom, B right, X left, Y top.",
                "The badge's buttons on the keyboard: " "F1–F6 are A–F, F7 the joystick pressed "
                "in. Docked and on the title the letters A–F are too (not while typing).",
                "Start options: --layout elite, --full, --sound, --debug. Saves go in "
                "~/.local/share/ace_commander/."],
        device="the Raspberry Pi")


# ---- the Tufty 2350 ---------------------------------------------------------------------

def tufty():
    H = ["Action", "Tufty buttons", "Qw/ST Pad"]
    A3, B3, C3 = W * 0.34, W * 0.36, W * 0.30
    left = [
        section("FLYING", table([
            ["Pitch (nose up / down)", k("UP") + " / " + k("DOWN"), "D-pad " + k("↑", "↓")],
            ["Roll left / right", k("A") + " / " + k("C"), "D-pad " + k("←", "→")],
            ["Fire lasers (hold)", k("B"), k("A")],
            ["Speed up / slow down", k("A") + " + " + k("C") + ", then " + k("UP") + " / " + k("DOWN"),
             k("X") + " / " + k("Y")],
            ["Fire missile", "By itself", k("B")],
            ["Energy bomb", "—", k("−")],
            ["Jump drive (in-system)", "Hold " + k("UP") + " at full speed (speed mode)",
             "Hold " + k("X") + " at full speed"],
            ["Views, docking computer", "Pause menu", "Pause menu"],
            ["Pause menu", k("UP") + " + " + k("DOWN") + " together", k("+")],
        ], [A3, B3, C3], H)),
        Paragraph(k("A") + " + " + k("C") + " together switches " + k("UP") + " / " + k("DOWN")
                  + " between pitch and speed (the game says which); it stays so until you "
                  "switch again. The jump drive needs full speed, no ships on the radar and no "
                  "planet or sun close by (“MASS LOCKED”).", note),

        section("HYPERSPACE", table([
            ["Hyperspace / galactic jump", "Pause menu", "Pause menu"],
            ["Pick a target", "Chart: " + k("B"), "Chart: " + k("A")],
        ], [A3, B3, C3], H)),
        Paragraph("On a chart, select only picks the system (the line under its name says "
                  "TARGET); then choose HYPERSPACE on the pause menu.", note),

        section("HARDCORE MODE  (with the Pad)", table([
            ["Fire the E.C.M.", "—", k("X") + " + " + k("Y") + " together"],
            ["Arm / fire a missile", "—", k("B") + " arms, " + k("B") + " again fires"],
        ], [A3, B3, C3], H)),
        Paragraph("Select HARDCORE: ON when you make a new commander, or on the Combat practice "
                  "page. Missiles lock only while armed; docking is by hand only, unless you "
                  "have bought a docking computer.", note),
    ]

    right = [
        section("MENUS, SCREENS AND DOCKED", table([
            ["Move the cursor / scroll", k("UP") + " " + k("DOWN") + ", " + k("A") + " / " + k("C")
             + " as " + k("←", "→"), "D-pad"],
            ["Next / previous screen (docked)", k("C") + " / " + k("A"), "D-pad " + k("→") + " / " + k("←")],
            ["Select / buy / choose", k("B"), k("A")],
            ["Sell / system data", "—", k("B")],
            ["Back", k("A") + " + " + k("C") + " together", k("X")],
            ["Launch / pause menu", "—", k("+")],
            ["Find a system (galactic chart)", "—", k("Y")],
            ["The badge's B (bomb, next tab)", "—", k("−")],
        ], [A3, B3, C3], H)),

        section("TYPING A NAME OR A SEARCH", table([
            ["Change the letter", k("UP") + " / " + k("DOWN"), "D-pad " + k("↑", "↓")],
            ["Keep it, next letter", k("B"), k("A") + " or " + k("→")],
            ["Back a letter", k("C"), k("B") + " or " + k("←")],
            ["Done", k("A"), k("+")],
        ], [A3, B3, C3], H)),

        section("WITHOUT THE PAD",
            Paragraph("The Tufty's five buttons alone play Combat practice only: missiles fire by "
                      "themselves and every canister holds one. Plug a Pimoroni Qw/ST Pad into "
                      "the Qw/ST socket for the whole game: trading, docking, hyperspace and the "
                      "rest. The Tufty's buttons still work with the Pad in. Hints on screen "
                      "name whichever you pressed last.", note)),
    ]
    return dict(
        heading="ACE COMMANDER · KEY GUIDE · TUFTY 2350",
        sub="The Tufty’s buttons (A, B, C, UP, DOWN) and the Qw/ST Pad, in flight and docked.",
        pages=[(left, right)],
        footer=["Sound: a Qwiic buzzer (SparkFun, or Arduino Modulino) on the Qw/ST socket, "
                "if you have one.",
                "Install: unzip into the TUFTY drive's apps/ folder (the Mass Storage app, or "
                "double-tap RESET)."],
        device="the Pimoroni Tufty 2350")


PLATFORMS = {"badge": (badge, "key_guide.pdf"), "pi": (pi, "key_guide_pi.pdf"),
             "tufty": (tufty, "key_guide_tufty.pdf")}


def make(platform, out=None):
    """Write the platform's guide to out (default: its name in the repo folder)."""
    fn, name = PLATFORMS[platform]
    g = fn()
    out = out or os.path.join(REPO, name)
    lines = g["footer"] + ["Ace Commander for %s · build %s" % (g["device"], BUILD)]
    foot_h = (len(lines) * 3.5 + 2) * mm

    def page(c, doc):
        c.saveState()
        c.setFillColor(ACCENT)
        c.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
        c.setFont("Sans", 7)
        c.setFillColor(colors.HexColor("#6e7781"))
        y = 5.5 * mm + (len(lines) - 1) * 3.5 * mm
        for line in lines:
            c.drawString(12 * mm, y, line)
            y -= 3.5 * mm
        c.restoreState()

    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                          topMargin=10 * mm, bottomMargin=foot_h,
                          title=g["heading"].title(), author="Ace Commander")
    top_h = 21 * mm
    body_top = A4[1] - 10 * mm - top_h
    fh = body_top - foot_h
    frames = [Frame(12 * mm, body_top, A4[0] - 24 * mm, top_h, id="top", leftPadding=0,
                    rightPadding=0, topPadding=6, bottomPadding=0),
              Frame(12 * mm, foot_h, W, fh, id="l", leftPadding=0, rightPadding=0, topPadding=0),
              Frame(12 * mm + W + 8 * mm, foot_h, W, fh, id="r", leftPadding=0, rightPadding=0,
                    topPadding=0)]
    doc.addPageTemplates([PageTemplate(id="p", frames=frames, onPage=page)])
    story = [Paragraph(g["heading"], title), Paragraph(g["sub"], sub)]
    for n, (left, right) in enumerate(g["pages"]):
        if n:
            story += [FrameBreak(), Paragraph(g["heading2"], title)]
        story += [FrameBreak()] + left + [FrameBreak()] + right
    doc.build(story)
    if doc.page != len(g["pages"]):     # a column too long spills into the next frame
        raise SystemExit("%s: %d pages, not %d: a column is too long"
                         % (out, doc.page, len(g["pages"])))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--platform", choices=sorted(PLATFORMS) + ["all"], default="badge")
    ap.add_argument("out", nargs="?", help="the PDF to write (one platform only)")
    args = ap.parse_args()
    names = sorted(PLATFORMS) if args.platform == "all" else [args.platform]
    if args.out and len(names) > 1:
        ap.error("give no file with --platform all")
    for p in names:
        print("written", make(p, args.out))


if __name__ == "__main__":
    main()
