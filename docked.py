"""The docked screens, as tabs: Status, Market, Equip ship, Local chart,
Galactic chart and System data. A row of small squares at the top shows
which is open.

On the market the joystick picks a good, C buys one and D sells one (hold
either to keep going). On Equip ship the joystick picks an item and C buys
it. On the two charts C makes the selected system the hyperspace target;
once launched, the in-flight menu offers a jump to it.
"""
from . import chart, cockpit, commander, describe, equipment, market, missions
try:        # the description sentence's tables, made by tools/import_galaxy.py
    from . import game_data
except Exception:
    game_data = None

TABS = ("STATUS", "MARKET", "EQUIP SHIP", "REPAIR SHOP", "LOCAL CHART", "GALACTIC CHART",
        "SYSTEM DATA", "OPTIONS")
PAINT_PRICE = 100   # tenths of a credit: a new colour at the Repair Shop costs 10.0 Cr
SPIN = 0.8          # radians a second the Repair Shop's ship turns
ROWS = 6            # goods shown at once on the market
SAY_TIME = 1.5      # seconds a market message stays
PRICE_X = 24        # where the market's columns end
STOCK_X = 52
HOLD_X = 88
EPRICE_X = 52       # Equip ship's price column


def _legal(n):
    """Legal status as a name (game.legal_name, without importing the game)."""
    return "CLEAN" if n <= 0 else ("OFFENDER" if n < 50 else "FUGITIVE")


def _ly(d):
    return "%d.%d LY" % (d // 10, d % 10)


class Docked:
    def __init__(self, cmdr, gal, target=None, goods=None, equip=None, ship=None,
                 repair=False, options=None):
        """ship is your ship's blueprint, for the Repair Shop, which is shown
        only with repair (a DEBUG switch for now). options: (a function giving
        the settings' lines, a function changing one: given the line and
        whether to go back), the app's, for the Options tab; None: no tab."""
        self.options = options
        self.osel = 0           # the line picked on Options
        self.cmdr = cmdr
        self.ship = ship
        self.spin = 0.0         # the Repair Shop's ship, turning
        self.paint = cmdr.colour if 0 <= cmdr.colour < len(cockpit.SHIP_COLOURS) else 0
        self.gal = gal          # None without game_data.py: then only Status
        self.equip = equip
        if gal is None:
            self.tabs = TABS[:1] + (("OPTIONS",) if options else ())
        else:                   # an older game_data.py may not have goods or equipment
            self.tabs = tuple(t for t in TABS
                              if not (t == "MARKET" and not (goods and cmdr.market is not None))
                              and not (t == "EQUIP SHIP" and not equip)
                              and not (t == "REPAIR SHOP" and not (repair and ship))
                              and not (t == "OPTIONS" and not options))
        self.market = None
        if "MARKET" in self.tabs:
            self.market = market.Market(goods, gal.system(cmdr.system).economy, cmdr)
        self.sel = 0            # the good picked on the market
        self.top = 0            # the first good shown
        self.esel = 0           # the item picked on Equip ship
        self.etop = 0
        self.for_sale = 0       # how many items this station sells
        if "EQUIP SHIP" in self.tabs:
            self.for_sale = equipment.on_sale(gal.system(cmdr.system).tech)
        self.msg = None         # why the last trade didn't happen
        self.msg_t = 0.0
        self.tab = 0
        self.target = target if gal is not None else None   # a system index, or None
        self.here = gal.system(cmdr.system) if gal is not None else None
        self.view = None        # the chart, on the chart tabs
        self.chart_tab = None   # the last chart tab opened: where D on System data goes back to
        self.data = None        # the galaxy.System on the System data tab

    def name(self):
        return self.tabs[self.tab]

    def open(self, name):
        """Open the tab with this name."""
        self.go(self.tabs.index(name))

    def go(self, tab, sel=None):
        """Open tab number tab (it wraps round). On a chart the cursor starts
        on system sel, or on the target if sel is None."""
        self.tab = tab % len(self.tabs)
        n = self.name()
        c = self.cmdr
        self.view = None
        self.data = None
        if sel is None:
            sel = self.target
        if n == "LOCAL CHART":
            self.view = chart.Chart(self.gal, c.system, c.fuel, sel, "TARGET")
            self.chart_tab = n
        elif n == "GALACTIC CHART":
            self.view = chart.GalChart(self.gal, c.system, c.fuel, sel, "TARGET",
                                       c.galaxy + 1)
            self.chart_tab = n
        elif n == "SYSTEM DATA":
            self.data = self.gal.system(self.target if self.target is not None else c.system)

    def pick(self):
        """C on a chart: the selected system becomes the target and its data
        is shown. Picking where you are clears the target."""
        i = self.view.picked()
        if i is None:
            return
        self.target = None if i == self.cmdr.system else i
        self.open("SYSTEM DATA")

    # ---- options --------------------------------------------------------------

    def pick_option(self, step):
        self.osel = (self.osel + step) % len(self.options[0]())

    def change_option(self, back=False):
        items = self.options[0]()
        self.options[1](items[self.osel % len(items)], back)

    # ---- the market ---------------------------------------------------------

    def pick_good(self, step):
        """Move the market's highlight up (-1) or down (1), scrolling the list."""
        n = len(self.market.goods)
        self.sel = (self.sel + step) % n
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + ROWS:
            self.top = self.sel - ROWS + 1

    def pick_item(self, step):
        """Move Equip ship's highlight up (-1) or down (1), scrolling the list."""
        n = self.for_sale
        self.esel = (self.esel + step) % n
        if self.esel < self.etop:
            self.etop = self.esel
        elif self.esel >= self.etop + ROWS:
            self.etop = self.esel - ROWS + 1

    def buy_item(self):
        """Buy the highlighted item. Returns True if it happened."""
        why = equipment.buy(self.equip, self.esel, self.cmdr)
        self.msg = why
        self.msg_t = SAY_TIME if why else 0.0
        return why is None

    def trade(self, buy):
        """Buy (or sell) one of the highlighted good. Returns True if it happened."""
        m = self.market
        why = m.buy(self.sel) if buy else m.sell(self.sel)
        self.msg = why
        self.msg_t = SAY_TIME if why else 0.0
        return why is None

    # ---- the repair shop --------------------------------------------------------

    def pick_paint(self, step):
        """Move the Repair Shop's choice of colour up (-1) or down (1)."""
        self.paint = (self.paint + step) % len(cockpit.SHIP_COLOURS)

    def buy_paint(self):
        """Paint the ship the chosen colour. Returns True if it happened."""
        c = self.cmdr
        why = None
        if self.paint == c.colour:
            why = "ALREADY THAT COLOUR"
        elif c.cash < PAINT_PRICE:
            why = "NOT ENOUGH CASH"
        else:
            c.cash -= PAINT_PRICE
            c.colour = self.paint
        self.msg = why
        self.msg_t = SAY_TIME if why else 0.0
        return why is None

    def tick(self, dt):
        self.spin += SPIN * dt
        if self.msg_t > 0:
            self.msg_t -= dt
            if self.msg_t <= 0:
                self.msg = None

    # ---- drawing ------------------------------------------------------------

    def draw(self, ctx):
        if self.view is not None:
            self.view.draw(ctx)
        elif self.data is not None:
            self._draw_data(ctx)
        elif self.name() == "MARKET":
            self._draw_market(ctx)
        elif self.name() == "EQUIP SHIP":
            self._draw_equip(ctx)
        elif self.name() == "REPAIR SHOP":
            self._draw_repair(ctx)
        elif self.name() == "OPTIONS":
            self._draw_options(ctx)
        else:
            self._draw_status(ctx)
        if len(self.tabs) > 1:      # which tab is open
            n = len(self.tabs)
            x = -(n * 11 - 5) // 2
            for i in range(n):
                ctx.rgb(*(cockpit.GREEN if i == self.tab else cockpit.DIM))
                ctx.rectangle(x + i * 11, -115, 6, 5).fill()

    def _draw_status(self, ctx):
        """Where you are, who you are, and what is in the tank."""
        text = cockpit.text
        c = self.cmdr
        s = self.here
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        col = cockpit.station_colour(s.government if s is not None else None)
        text(ctx, "DOCKED", 0, -100, 11, col)
        if s is not None:
            text(ctx, s.name, 0, -80, 22, cockpit.WHITE)
            text(ctx, s.government_name(), 0, -59, 11, col)
            text(ctx, "%s, tech %d" % (s.economy_name(), s.tech), 0, -45, 11, cockpit.GREY)
        else:
            text(ctx, "COMMANDER", 0, -70, 20, cockpit.WHITE)
        ctx.rgb(*cockpit.DIM).rectangle(-90, -34, 180, 1).fill()
        text(ctx, c.rank(), 0, -20, 16, cockpit.GREEN)
        text(ctx, "%d kills  %s  %s" % (c.kills, commander.LEVELS[c.level],
                                        _legal(c.legal)), 0, -2, 12, cockpit.YELLOW)
        nxt = c.next_rank()
        if nxt:
            text(ctx, "%d more for %s" % (nxt[1], nxt[0]), 0, 13, 12, cockpit.YELLOW)
        text(ctx, "fuel %s   %s" % (_ly(c.fuel), c.cash_text()), 0, 30, 12, cockpit.CYAN)
        if self.target is not None:
            t = self.gal.system(self.target)
            d = self.gal.distance(c.system, self.target)
            text(ctx, "target: %s %s" % (t.name, _ly(d)), 0, 45, 11,
                 cockpit.CYAN if 0 < d <= c.fuel else cockpit.RED)
        ctx.rgb(*cockpit.DIM).rectangle(-70, 56, 140, 1).fill()
        text(ctx, "C: LAUNCH", 0, 70, 14, cockpit.GREEN)
        if len(self.tabs) > 1:
            text(ctx, "< > screens   F: title", 0, 88, 11, cockpit.GREY)
        else:
            text(ctx, "F: title screen", 0, 88, 11, cockpit.GREY)

    def back_to_chart(self):
        """D on System data: back to the chart you came from (the local chart
        if none yet), with the cursor on the system you were looking at."""
        name = self.chart_tab if self.chart_tab in self.tabs else "LOCAL CHART"
        if name in self.tabs:
            self.go(self.tabs.index(name), self.data.index if self.data is not None else None)

    def show(self, index):
        """D on a chart: open System data for system index, leaving the
        target as it is."""
        if index is None:
            return
        self.open("SYSTEM DATA")
        self.data = self.gal.system(index)

    def _draw_data(self, ctx):
        """Everything about one star system."""
        c = self.cmdr
        s = self.data
        d = None if s.index == c.system else self.gal.distance(c.system, s.index)
        system_page(ctx, self.gal, s, d, c.fuel, "< >   D: chart   F: status", c)

    def _draw_market(self, ctx):
        """The goods, ROWS at a time: name, price, stock and what is in the hold."""
        text = cockpit.text
        m = self.market
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "MARKET  " + self.here.name, 0, -100, 11, cockpit.GREY)
        for label, x in (("price", PRICE_X), ("qty", STOCK_X), ("hold", HOLD_X)):
            text(ctx, label, x, -74, 10, cockpit.GREY, 1)
        if self.top > 0:                            # more above
            ctx.rgb(*cockpit.DIM).rectangle(-3, -69, 6, 2).fill()
        for row in range(ROWS):
            i = self.top + row
            y = -58 + row * 18
            if i == self.sel:
                ctx.rgb(*cockpit.DIM).rectangle(-102, y - 8, 204, 16).fill()
            col = cockpit.GREEN if i == self.sel else cockpit.WHITE
            unit = m.unit(i)
            p = m.prices[i]
            text(ctx, m.name(i), -96, y, 11, col, -1)
            text(ctx, "%d.%d" % (p // 10, p % 10), PRICE_X, y, 11, cockpit.YELLOW, 1)
            text(ctx, "%d%s" % (m.stock[i], unit) if m.stock[i] else "-", STOCK_X, y, 11,
                 cockpit.CYAN, 1)
            if c.cargo[i]:
                text(ctx, "%d%s" % (c.cargo[i], unit), HOLD_X, y, 11, cockpit.GREEN, 1)
        if self.top + ROWS < len(m.goods):          # more below
            ctx.rgb(*cockpit.DIM).rectangle(-3, 44, 6, 2).fill()
        text(ctx, "%s   hold %d/%dt" % (c.cash_text(), market.hold_used(c.cargo), c.hold),
             0, 58, 12, cockpit.CYAN)
        if self.msg:
            text(ctx, self.msg, 0, 75, 12, cockpit.RED)
        else:
            text(ctx, "C: buy   D: sell", 0, 75, 11, cockpit.GREY)
        text(ctx, "< > screens   F: status", 0, 91, 11, cockpit.GREY)

    def _draw_options(self, ctx):
        """The same settings as the title screen's Options and the in-flight
        Settings."""
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "OPTIONS", 0, -94, 14, cockpit.GREY)
        items = self.options[0]()
        sel = self.osel % len(items)
        y = -60
        for i, label in enumerate(items):
            if i == sel:
                ctx.rgb(*cockpit.DIM).rectangle(-104, y - 9, 208, 18).fill()
            text(ctx, label, 0, y, 14, cockpit.GREEN if i == sel else cockpit.GREY)
            y += 20
        text(ctx, "up / down: pick   C: change", 0, 66, 11, cockpit.GREY)
        text(ctx, "< > screens   F: status", 0, 82, 11, cockpit.GREY)

    def _draw_repair(self, ctx):
        """Your ship turning in the chosen colour, the colours as a row of
        swatches, and what a new coat costs."""
        import math
        text = cockpit.text
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "REPAIR SHOP  " + self.here.name, 0, -100, 11, cockpit.GREY)
        name, rgb = cockpit.SHIP_COLOURS[self.paint]
        o = _Show(self.ship)
        z = 560.0
        o.z = z
        o.y = 38.0 * z / cockpit.FOCAL      # 38 pixels above the middle
        a = self.spin
        ca, sa = math.cos(a), math.sin(a)
        t = 0.35                            # tipped towards you, to see the top
        ct, st = math.cos(t), math.sin(t)
        # turned about the vertical by a, then tipped by t
        o.m = [ca, -sa * st, sa * ct, 0.0, ct, st, -sa, -ca * st, ca * ct]
        cockpit.draw_ship(ctx, o, rgb, 3, True)
        text(ctx, name, 0, 8, 16, rgb)
        n = len(cockpit.SHIP_COLOURS)
        x0 = -(n * 18 - 6) // 2
        for i in range(n):
            x = x0 + i * 18
            if i == self.paint:
                ctx.rgb(*cockpit.WHITE).rectangle(x - 2, 22, 16, 16).fill()
            ctx.rgb(*cockpit.SHIP_COLOURS[i][1]).rectangle(x, 24, 12, 12).fill()
        if self.paint == c.colour:
            text(ctx, "your colour   " + c.cash_text(), 0, 52, 12, cockpit.CYAN)
        else:
            text(ctx, "paint %d.%d Cr   %s" % (PAINT_PRICE // 10, PAINT_PRICE % 10,
                                             c.cash_text()), 0, 52, 12, cockpit.YELLOW)
        if self.msg:
            text(ctx, self.msg, 0, 70, 12, cockpit.RED)
        else:
            text(ctx, "up/down: colour   C: paint", 0, 70, 11, cockpit.GREY)
        text(ctx, "< > screens   F: status", 0, 88, 11, cockpit.GREY)

    def _draw_equip(self, ctx):
        """What this station sells, ROWS at a time: name, price, what you have."""
        text = cockpit.text
        e = self.equip
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "EQUIP SHIP  " + self.here.name, 0, -100, 11, cockpit.GREY)
        for label, x in (("price", EPRICE_X), ("have", HOLD_X)):
            text(ctx, label, x, -74, 10, cockpit.GREY, 1)
        if self.etop > 0:
            ctx.rgb(*cockpit.DIM).rectangle(-3, -69, 6, 2).fill()
        for row in range(min(ROWS, self.for_sale)):
            i = self.etop + row
            y = -58 + row * 18
            if i == self.esel:
                ctx.rgb(*cockpit.DIM).rectangle(-102, y - 8, 204, 16).fill()
            soon = i in equipment.SOON
            col = cockpit.GREY if soon else (cockpit.GREEN if i == self.esel else cockpit.WHITE)
            text(ctx, equipment.name(e, i), -96, y, 11, col, -1)
            if soon:
                text(ctx, "soon", EPRICE_X, y, 11, cockpit.GREY, 1)
            else:
                p = equipment.price(e, i, c)
                text(ctx, "%d.%d" % (p // 10, p % 10), EPRICE_X, y, 11, cockpit.YELLOW, 1)
            h = equipment.have(i, c)
            if h:
                text(ctx, h, HOLD_X, y, 11, cockpit.GREEN, 1)
        if self.etop + ROWS < self.for_sale:
            ctx.rgb(*cockpit.DIM).rectangle(-3, 44, 6, 2).fill()
        text(ctx, c.cash_text(), 0, 58, 12, cockpit.CYAN)
        if self.msg:
            text(ctx, self.msg, 0, 75, 12, cockpit.RED)
        else:
            text(ctx, "C: buy", 0, 75, 11, cockpit.GREY)
        text(ctx, "< > screens   F: status", 0, 91, 11, cockpit.GREY)


class _Show:
    """A ship as draw_ship wants it, for the Repair Shop."""
    kind = "ship"
    hit = 0.0

    def __init__(self, bp):
        self.bp = bp
        self.x = self.y = self.z = 0.0
        self.m = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


# where the description's lines go, and how many characters fit on each (the
# screen is round, so lower lines are shorter)
DESC_Y = (24, 36, 48, 60, 72)
DESC_WIDTHS = (38, 37, 35, 32, 28)


_special = [None, None]     # the last (galaxy, system, mission) given a special sentence, and it


def system_page(ctx, gal, s, dist, fuel, help_line, cmdr=None):
    """Everything about star system s (a galaxy.System): dist is how far it
    is from you in tenths of a light year (None: you are there), fuel what
    you have. Used by the System data tab and by D on the in-flight chart.
    cmdr: the commander, when docked; the station you are at may then say
    something special instead of the usual sentence (the missions' RUTOK)."""
    text = cockpit.text
    ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
    text(ctx, "SYSTEM DATA", 0, -102, 10, cockpit.GREY)
    text(ctx, s.name, 0, -85, 20, cockpit.WHITE)
    if dist is None:
        text(ctx, "you are here", 0, -67, 11, cockpit.GREEN)
    else:
        ok = 0 < dist <= fuel
        text(ctx, "%s away%s" % (_ly(dist), "" if ok else ", too far"),
             0, -67, 11, cockpit.GREEN if ok else cockpit.RED)
    ctx.rgb(*cockpit.DIM).rectangle(-90, -58, 180, 1).fill()
    text(ctx, s.government_name(), 0, -47, 11, cockpit.station_colour(s.government))
    y = -34
    for line in (s.economy_name(),
                 "Tech %d   Pop %d.%d billion" % (s.tech, s.population // 10, s.population % 10),
                 "Productivity %d M Cr" % s.productivity,
                 "Radius %d km" % s.radius):
        text(ctx, line, 0, y, 11, cockpit.YELLOW)
        y += 13
    words = None
    if cmdr is not None and dist is None and game_data is not None:
        key = (cmdr.galaxy, s.index, cmdr.mission)
        if _special[0] != key:
            n = missions.special_sentence(game_data, cmdr.mission, cmdr.galaxy, s.index)
            _special[0] = key
            _special[1] = describe.special(game_data, n, s.name) if n else None
        words = _special[1]
    if not words and game_data is not None:
        words = describe.for_system(game_data, gal, s.index)
    if words:
        for line, y in zip(describe.wrap(words, DESC_WIDTHS), DESC_Y):
            text(ctx, line, 0, y, 10, cockpit.CYAN)
    text(ctx, help_line, 0, 90, 10, cockpit.GREY)
