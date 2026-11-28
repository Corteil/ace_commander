"""The in-flight screens on the number row, as Elite's f7, f8 and f9: Market
Prices, Commander Status and Inventory. The game keeps running while one is
up (Brian: as Elite), so these only draw; ace.py does the rest. Imported the
first time one is opened, so it costs no memory until then. Docked, the same
three are the Market, Status and Inventory tabs (Brian: one screen each, docked
and in flight), with the docked parts (the cursor, A: LAUNCH, the hints) added.

No badge imports apart from cockpit's drawing helpers, so it runs on a PC.
"""
try:
    from . import cockpit, commander, market
except ImportError:         # imported on its own, as the PC tests do
    import cockpit
    import commander
    import market

ROWS = 8            # goods shown at a time on Inventory (less one)
MARKET_ROWS = 7     # goods shown at a time on the market, docked and in flight
MARKET_Y = -52      # the market's first row
MARKET_STEP = 16
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


def draw_status(ctx, c, here, target, dist, cond, legal, name=None, docked=None):
    """Elite's Commander Status, in flight and docked: the systems, condition,
    fuel, cash, legal status, rating and kills. here and target are system
    names (or None), dist the target's distance in tenths of a light year
    (red if it is beyond the fuel), cond Game.condition() ("DOCKED" docked).
    name: the commander's, for the title as Elite's "COMMANDER JAMESON" (build
    89). In flight the equipment fitted follows; docked is (the station's
    colour, the hint lines): the condition in that colour, the level, then
    A: LAUNCH and the hints (Equip ship lists the equipment)."""
    text = cockpit.text
    _blank(ctx)
    text(ctx, "COMMANDER " + name if name else "COMMANDER STATUS", 0, -99, 10, cockpit.WHITE)
    far = target and not (0 < dist <= c.fuel)
    rows = [("present", here or "-", cockpit.CYAN),
            ("hyperspace", ("%s %s" % (target, _ly(dist))) if target else "-",
             cockpit.RED if far else cockpit.CYAN),
            ("condition", cond, docked[0] if docked else _rgb(cond)),
            ("fuel", _ly(c.fuel), cockpit.CYAN),
            ("cash", c.cash_text(), cockpit.CYAN),
            ("legal status", legal, cockpit.YELLOW if legal == "CLEAN" else cockpit.RED),
            ("rating", c.rank(), cockpit.GREEN),
            ("kills", _kills(c), cockpit.YELLOW)]
    if docked:
        rows.append(("level", commander.LEVELS[c.level], cockpit.YELLOW))
    y = -80
    for label, value, rgb in rows:
        text(ctx, label, -8, y, 11, cockpit.GREY, 1)
        text(ctx, value, 0, y, 11, rgb, -1)
        y += 13
    if docked:                      # right under the rows (no gap: a small screen fits it bigger)
        ctx.rgb(*cockpit.DIM).rectangle(-70, y - 3, 140, 1).fill()
        text(ctx, "A: LAUNCH", 0, y + 10, 14, cockpit.GREEN)
        for i, hint in enumerate(docked[1]):
            text(ctx, hint, 0, y + 26 + 14 * i, 11, cockpit.GREY)
        return
    ctx.rgb(*cockpit.DIM).rectangle(-80, y - 5, 160, 1).fill()
    y += 5
    for s in equipment_lines(c):    # at most 6 lines: every item fits
        text(ctx, s, 0, y, 9, cockpit.WHITE)
        y += 10
    text(ctx, "C or F: back", 0, 100, 9, cockpit.GREY)


def cargo_rows(c):
    """The goods in the hold, for Inventory."""
    return [i for i, n in enumerate(c.cargo) if n]


def draw_market(ctx, m, c, title, top, sel=None, msg=None, hints=("C or F: back",)):
    """The market, docked and in flight (Elite's Market Prices): each good's
    price, stock and what is in the hold, MARKET_ROWS at a time from row top.
    Docked, sel is the good picked (a bar behind it) and msg why the last trade
    didn't happen (instead of the first hint); in flight nothing can be bought
    or sold (Brian)."""
    text = cockpit.text
    _blank(ctx)
    text(ctx, title, 0, -92, 11, cockpit.WHITE)
    for label, x in (("price", PRICE_X), ("qty", STOCK_X), ("hold", HOLD_X)):
        text(ctx, label, x, -68, 10, cockpit.GREY, 1)       # inside the round screen
    n = len(m.goods)
    if top > 0:                     # more above
        ctx.rgb(*cockpit.DIM).rectangle(-43, -63, 6, 2).fill()   # clear of the price column
    for row in range(MARKET_ROWS):
        i = top + row
        if i >= n:
            break
        y = MARKET_Y + row * MARKET_STEP
        if i == sel:
            ctx.rgb(*cockpit.DIM).rectangle(-102, y - 8, 204, 16).fill()
        unit = m.unit(i)
        p = m.prices[i]
        text(ctx, m.name(i), NAME_X, y, 11, cockpit.GREEN if i == sel else cockpit.WHITE, -1)
        text(ctx, "%d.%d" % (p // 10, p % 10), PRICE_X, y, 11, cockpit.YELLOW, 1)
        text(ctx, "%d%s" % (m.stock[i], unit) if m.stock[i] else "-", STOCK_X, y, 11,
             cockpit.CYAN, 1)
        if c.cargo[i]:
            text(ctx, "%d%s" % (c.cargo[i], unit), HOLD_X, y, 11, cockpit.GREEN, 1)
    if top + MARKET_ROWS < n:       # more below
        ctx.rgb(*cockpit.DIM).rectangle(-43, MARKET_Y + MARKET_ROWS * MARKET_STEP - 10, 6, 2).fill()
    text(ctx, "%s   hold %d/%dt" % (c.cash_text(), market.hold_used(c.cargo), c.hold),
         0, 62, 12, cockpit.CYAN)
    y = 78
    for i, hint in enumerate(hints):
        if i == 0 and msg:
            text(ctx, msg, 0, y, 12, cockpit.RED)
        else:
            text(ctx, hint, 0, y, 11, cockpit.GREY)
        y += 16


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
