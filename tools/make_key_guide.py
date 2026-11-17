"""The Ace Commander key guide: badge buttons and keyboard keys on one A4 page.

Usage: python tools/make_key_guide.py [out.pdf]
With no file given it writes key_guide.pdf in the repo folder (gitignored).

Needs ReportLab and the DejaVu fonts (Debian: python3-reportlab, fonts-dejavu-core).
DejaVu is used because ReportLab's built-in Helvetica has no arrow or minus
glyphs. The build number comes from metadata.json. When a key changes in
ace.py, change it here too.
"""
import json
import os
import sys
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Table,
                                TableStyle, Spacer, KeepTogether, FrameBreak)

with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "metadata.json")) as f:
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
A, B, C = W * 0.36, W * 0.30, W * 0.34   # action / badge / keyboard

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
    ], [A, B, C], ["Action", "Badge", "Keyboard"])),
    Paragraph("Speed keys also work as " + k("=") + " / " + k("_") + " (no Shift). The jump drive needs full speed, no ships on the radar and no planet or sun "
              "close by (“MASS LOCKED”). With tilt steering: tilt to steer, tap "
              + k("D") + " to re-zero, hold " + k("D") + " to fire a missile.", note),

    section("HYPERSPACE", table([
        ["Hyperspace to the target", "Menu HYPERSPACE", k("H")],
        ["Galactic hyperdrive (if fitted)", "Menu GALACTIC JUMP", k("Shift") + " + " + k("H") + " (or " + k("Ctrl") + " + " + k("H") + "*)"],
        ["Pick a target", "Chart: " + k("C"), "Chart: " + k("Enter")],
    ], [A, B, C], ["Action", "Badge", "Keyboard"])),
    Paragraph(k("H") + " with no target opens the local chart. On a chart, "
              + k("C") + " only selects the system (the line under its name says TARGET); "
              "then " + k("H") + " jumps.", note),

    section("HARDCORE MODE", table([
        ["Fire the E.C.M.", k("E") + " + " + k("F") + " together", k("E")],
        ["Arm / disarm a missile", k("D") + " arms, " + k("D") + " again fires", k("T") + " / " + k("U")],
    ], [A, B, C], ["Action", "Badge", "Keyboard"])),
    Paragraph("Pick HARDCORE: ON when you make a new commander (it stays for that commander), "
              "or on the Combat practice page. "
              "In Hardcore " + k("E") + " is the E.C.M., so use " + k("+") + " to speed up; "
              "missiles lock only while armed; docking is by hand only, unless you have "
              "bought a docking computer.", note),
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
    ], [A, B, C], ["Action", "Badge", "Keyboard"])),

    section("PAUSE MENU", table([
        ["Pick a line", "Joystick " + k("↑", "↓"), k("↑", "↓")],
        ["Choose", k("C"), k("Enter")],
        ["Change a setting / the VIEW", "Joystick " + k("←", "→"), k("←", "→")],
        ["Back / resume", k("F") + " / " + k("A"), k("Esc") + " / " + k("P")],
    ], [A, B, C], ["Action", "Badge", "Keyboard"])),

    section("DOCKED", table([
        [k("1"), "Launch (badge: " + k("A") + ", or " + k("C") + " on Status)"],
        [k("2") + " " + k("8"), "Market: " + k("C") + " buys, " + k("D") + " sells, joystick picks"],
        [k("3"), "Market, on the first good in your hold (to sell)"],
        [k("4"), "Equip ship: " + k("C") + " buys"],
        [k("5") + " " + k("6") + " " + k("7"), "Galactic chart · local chart · system data"],
        [k("9") + " / " + k("0"), "Status / Inventory"],
        [k("−") + " / " + k("="), "Repair Shop / Options"],
        ["Joystick " + k("←", "→"), "Next / previous screen, in the keys' order (or " + k("E") + " / " + k("B") + ")"],
        [k("F") + " or " + k("Esc"), "Back to Status, then the title"],
    ], [W * 0.33, W * 0.67])),

    section("SHIP VIEWER", table([
        [k("C") + " or " + k("N"), "Next ship"], [k("P"), "Previous ship"],
        ["Joystick", "Turn it"], [k("F") + " or " + k("Esc"), "Back to the title"],
    ], [W * 0.33, W * 0.67])),
]


def page(c, doc):
    c.saveState()
    c.setFillColor(ACCENT)
    c.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
    c.setFont("Sans", 7)
    c.setFillColor(colors.HexColor("#6e7781"))
    c.drawString(12 * mm, 12.5 * mm, "* Tab and Ctrl need the updated Keyboard Hexpansion driver "
                 "(sodoku/tildagon-keebdexpansion PR #5); every other key works with either driver.")
    c.drawString(12 * mm, 9 * mm, "Badge: buttons A–F round the screen, joystick in the "
                 "middle.  Keyboard: the Tildagon Keyboard Hexpansion or a USB keyboard.")
    c.drawString(12 * mm, 5.5 * mm, "Ace Commander for the EMF Tildagon badge · build %s" % BUILD)
    c.restoreState()


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "key_guide.pdf")
doc = BaseDocTemplate(out, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm,
                      topMargin=10 * mm, bottomMargin=16 * mm,
                      title="Ace Commander key guide", author="Ace Commander")
top_h = 21 * mm
body_top = A4[1] - 10 * mm - top_h
fh = body_top - 16 * mm
frames = [Frame(12 * mm, body_top, A4[0] - 24 * mm, top_h, id="top", leftPadding=0,
                rightPadding=0, topPadding=6, bottomPadding=0),
          Frame(12 * mm, 16 * mm, W, fh, id="l", leftPadding=0, rightPadding=0, topPadding=0),
          Frame(12 * mm + W + 8 * mm, 16 * mm, W, fh, id="r", leftPadding=0, rightPadding=0,
                topPadding=0)]
doc.addPageTemplates([PageTemplate(id="p", frames=frames, onPage=page)])
story = [Paragraph("ACE COMMANDER · KEY GUIDE", title),
         Paragraph("Badge buttons and keyboard keys, in flight and docked. Keys follow BBC "
                   "Elite’s layout where the game has the same feature.", sub),
         FrameBreak()] + left + [FrameBreak()] + right
doc.build(story)
print("written", out)
