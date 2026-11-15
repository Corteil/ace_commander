"""The game's name in block letters, built from rectangles (text is slow to
draw on the badge). Shared by the title screen (title.py) and the loading
screen (app.py), so it imports nothing and is quick to load."""

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
