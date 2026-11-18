"""The in-flight screens on the number row, as Elite's f7, f8 and f9: Market
Prices, Commander Status and Inventory. The game keeps running while one is
up (Brian: as Elite), so these only draw; ace.py does the rest. Imported the
first time one is opened, so it costs no memory until then.

No badge imports apart from cockpit's drawing helpers, so it runs on a PC.
"""
try:
    from . import cockpit, market
except ImportError:         # imported on its own, as the PC tests do
    import cockpit
    import market

ROWS = 8            # goods shown at a time on Market Prices and Inventory
ROW_Y = -58         # the first row
ROW_STEP = 16
NAME_X = -96
PRICE_X = 30
STOCK_X = 66
HOLD_X = 92


def _rgb(name):
    return {"GREEN": cockpit.GREEN, "YELLOW": cockpit.YELLOW, "RED": cockpit.RED}[name]


def _ly(d):
    return "%d.%d LY" % (d // 10, d % 10)


def _blank(ctx):
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()


def equipment_lines(c):
    """What is fitted, as lines short enough for the round screen: the lasers
    on one line (front / rear / left / right, "-" for none), then the rest two
    to a line, longest names first so they sit where the circle is widest."""
    lines = ["LASERS " + "/".join((n or "-").upper() for n in c.lasers)]
    items = []
    for key, label in (("docking", "DOCKING COMPUTER"), ("navy", "NAVY ENERGY UNIT"),
                       ("hyperdrive", "GAL. HYPERDRIVE"), ("energy", "ENERGY UNIT"),
                       ("bomb", "ENERGY BOMB"), ("scoops", "FUEL SCOOPS"),
                       ("pod", "ESCAPE POD"), ("ecm", "E.C.M.")):
        if key in c.extras:
            items.append(label)
    if c.hold > 20:
        items.append("LARGE CARGO BAY")
    if c.missiles:
        items.append("%d MISSILE%s" % (c.missiles, "" if c.missiles == 1 else "S"))
    for i in range(0, len(items), 2):
        lines.append("  ".join(items[i:i + 2]))
    return lines


def _kills(c):
    """Kills, and how many more for the next rank (kept from the old status page)."""
    nxt = c.next_rank()
    return "%d, %d more" % (c.kills, nxt[1]) if nxt else "%d" % c.kills


def draw_status(ctx, c, here, target, dist, cond, legal, name=None):
    """Elite's Commander Status: the systems, condition, fuel, cash, legal
    status, rating and the equipment fitted. here and target are system
    names (or None), dist the target's distance in tenths of a light year,
    cond Game.condition(). name: the commander's, for the title as Elite's
    "COMMANDER JAMESON" (build 89)."""
    text = cockpit.text
    _blank(ctx)
    text(ctx, "COMMANDER " + name if name else "COMMANDER STATUS", 0, -99, 10, cockpit.WHITE)
    rows = (("present", here or "-", cockpit.CYAN),
            ("hyperspace", ("%s %s" % (target, _ly(dist))) if target else "-", cockpit.CYAN),
            ("condition", cond, _rgb(cond)),
            ("fuel", _ly(c.fuel), cockpit.CYAN),
            ("cash", c.cash_text(), cockpit.CYAN),
            ("legal status", legal, cockpit.YELLOW if legal == "CLEAN" else cockpit.RED),
            ("rating", c.rank(), cockpit.GREEN),
            ("kills", _kills(c), cockpit.YELLOW))
    y = -80
    for label, value, rgb in rows:
        text(ctx, label, -8, y, 11, cockpit.GREY, 1)
        text(ctx, value, 0, y, 11, rgb, -1)
        y += 13
    ctx.rgb(*cockpit.DIM).rectangle(-80, y - 5, 160, 1).fill()
    y += 5
    for s in equipment_lines(c):    # at most 6 lines: every item fits
        text(ctx, s, 0, y, 9, cockpit.WHITE)
        y += 10
    text(ctx, "C or F: back", 0, 100, 9, cockpit.GREY)


def cargo_rows(c):
    """The goods in the hold, for Inventory."""
    return [i for i, n in enumerate(c.cargo) if n]


def draw_market(ctx, m, c, here, top):
    """Elite's Market Prices in flight: the prices and stock here and what is
    in the hold, ROWS at a time from row top. Nothing can be bought or sold
    (Brian): that is docked only. Everything sits DY lower than the docked
    market so the title fits where the circle is narrow (Brian)."""
    DY = 10
    text = cockpit.text
    _blank(ctx)
    text(ctx, "MARKET PRICES  " + here, 0, -100 + DY, 11, cockpit.WHITE)
    for label, x in (("price", PRICE_X), ("qty", STOCK_X), ("hold", HOLD_X)):
        text(ctx, label, x, -76 + DY, 10, cockpit.GREY, 1)
    rows = range(len(m.goods))
    if top > 0:
        ctx.rgb(*cockpit.DIM).rectangle(-43, -69 + DY, 6, 2).fill()   # clear of the price column
    for row in range(ROWS):
        k = top + row
        if k >= len(rows):
            break
        i = rows[k]
        y = ROW_Y + DY + row * ROW_STEP
        unit = m.unit(i)
        p = m.prices[i]
        text(ctx, m.name(i), NAME_X, y, 11, cockpit.WHITE, -1)
        text(ctx, "%d.%d" % (p // 10, p % 10), PRICE_X, y, 11, cockpit.YELLOW, 1)
        text(ctx, "%d%s" % (m.stock[i], unit) if m.stock[i] else "-", STOCK_X, y, 11,
             cockpit.CYAN, 1)
        if c.cargo[i]:
            text(ctx, "%d%s" % (c.cargo[i], unit), HOLD_X, y, 11, cockpit.GREEN, 1)
    if top + ROWS < len(rows):
        ctx.rgb(*cockpit.DIM).rectangle(-43, ROW_Y + DY + ROWS * ROW_STEP - 10, 6, 2).fill()
    text(ctx, "%s   hold %d/%dt" % (c.cash_text(), market.hold_used(c.cargo), c.hold),
         0, 76 + DY, 11, cockpit.CYAN)
    text(ctx, "C or F: back", 0, 92 + DY, 10, cockpit.GREY)


def draw_inventory(ctx, c, goods, top, foot="C or F: back"):
    """Elite's Inventory: fuel, cash and what is in the hold. foot: the hint
    at the bottom (docked it is one of the tabs)."""
    text = cockpit.text
    _blank(ctx)
    text(ctx, "INVENTORY", 0, -100, 12, cockpit.WHITE)
    text(ctx, "fuel %s   %s" % (_ly(c.fuel), c.cash_text()), 0, -82, 11, cockpit.CYAN)
    text(ctx, "hold %d/%dt" % (market.hold_used(c.cargo), c.hold), 0, -68, 11, cockpit.CYAN)
    rows = cargo_rows(c)
    if not rows:
        text(ctx, "the hold is empty", 0, -20, 11, cockpit.GREY)
    if top > 0:
        ctx.rgb(*cockpit.DIM).rectangle(-3, -54, 6, 2).fill()
    for row in range(ROWS - 1):
        k = top + row
        if k >= len(rows):
            break
        i = rows[k]
        y = ROW_Y + 16 + row * ROW_STEP
        g = goods[i]
        text(ctx, g[0], NAME_X + 16, y, 11, cockpit.WHITE, -1)
        text(ctx, "%d%s" % (c.cargo[i], market.UNITS[g[3]]), HOLD_X - 8, y, 11,
             cockpit.GREEN, 1)
    if top + ROWS - 1 < len(rows):
        ctx.rgb(*cockpit.DIM).rectangle(-3, ROW_Y + 16 + (ROWS - 1) * ROW_STEP - 10, 6, 2).fill()
    text(ctx, foot, 0, 92, 10, cockpit.GREY)
