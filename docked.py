"""The docked screens, as tabs: Status, Market, Local chart, Galactic chart
and System data. A row of small squares at the top shows which is open.

On the market the joystick picks a good, C buys one and D sells one (hold
either to keep going). On the two charts C makes the selected system the
hyperspace target; once launched, the in-flight menu offers a jump to it.
The equipment screen joins these tabs in phase 4.
"""
from . import chart, cockpit, commander, market

TABS = ("STATUS", "MARKET", "LOCAL CHART", "GALACTIC CHART", "SYSTEM DATA")
ROWS = 6            # goods shown at once on the market
SAY_TIME = 1.5      # seconds a market message stays
PRICE_X = 24        # where the market's columns end
STOCK_X = 52
HOLD_X = 88


def _ly(d):
    return "%d.%d LY" % (d // 10, d % 10)


class Docked:
    def __init__(self, cmdr, gal, target=None, goods=None):
        self.cmdr = cmdr
        self.gal = gal          # None without game_data.py: then only Status
        if gal is None:
            self.tabs = TABS[:1]
        elif goods and cmdr.market is not None:
            self.tabs = TABS
        else:                   # an older game_data.py, without the goods
            self.tabs = tuple(t for t in TABS if t != "MARKET")
        self.market = None
        if "MARKET" in self.tabs:
            self.market = market.Market(goods, gal.system(cmdr.system).economy, cmdr)
        self.sel = 0            # the good picked on the market
        self.top = 0            # the first good shown
        self.msg = None         # why the last trade didn't happen
        self.msg_t = 0.0
        self.tab = 0
        self.target = target if gal is not None else None   # a system index, or None
        self.here = gal.system(cmdr.system) if gal is not None else None
        self.view = None        # the chart, on the chart tabs
        self.data = None        # the galaxy.System on the System data tab

    def name(self):
        return self.tabs[self.tab]

    def open(self, name):
        """Open the tab with this name."""
        self.go(self.tabs.index(name))

    def go(self, tab):
        """Open tab number tab (it wraps round)."""
        self.tab = tab % len(self.tabs)
        n = self.name()
        c = self.cmdr
        self.view = None
        self.data = None
        if n == "LOCAL CHART":
            self.view = chart.Chart(self.gal, c.system, c.fuel, self.target, "TARGET")
        elif n == "GALACTIC CHART":
            self.view = chart.GalChart(self.gal, c.system, c.fuel, self.target, "TARGET")
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

    # ---- the market ---------------------------------------------------------

    def pick_good(self, step):
        """Move the market's highlight up (-1) or down (1), scrolling the list."""
        n = len(self.market.goods)
        self.sel = (self.sel + step) % n
        if self.sel < self.top:
            self.top = self.sel
        elif self.sel >= self.top + ROWS:
            self.top = self.sel - ROWS + 1

    def trade(self, buy):
        """Buy (or sell) one of the highlighted good. Returns True if it happened."""
        m = self.market
        why = m.buy(self.sel) if buy else m.sell(self.sel)
        self.msg = why
        self.msg_t = SAY_TIME if why else 0.0
        return why is None

    def tick(self, dt):
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
        text(ctx, "%d kills   level: %s" % (c.kills, commander.LEVELS[c.level]),
             0, -2, 12, cockpit.YELLOW)
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

    def _draw_data(self, ctx):
        """Everything about one star system."""
        text = cockpit.text
        s = self.data
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "SYSTEM DATA", 0, -100, 11, cockpit.GREY)
        text(ctx, s.name, 0, -80, 22, cockpit.WHITE)
        if s.index == c.system:
            text(ctx, "you are here", 0, -60, 11, cockpit.GREEN)
        else:
            d = self.gal.distance(c.system, s.index)
            text(ctx, "%s away%s" % (_ly(d), "" if 0 < d <= c.fuel else ", too far"),
                 0, -60, 11, cockpit.GREEN if 0 < d <= c.fuel else cockpit.RED)
        ctx.rgb(*cockpit.DIM).rectangle(-90, -50, 180, 1).fill()
        text(ctx, s.government_name(), 0, -36, 12, cockpit.station_colour(s.government))
        y = -20
        for line in (s.economy_name(), "Tech level %d" % s.tech,
                     "Population %d.%d billion" % (s.population // 10, s.population % 10),
                     "Productivity %d M Cr" % s.productivity,
                     "Radius %d km" % s.radius):
            text(ctx, line, 0, y, 12, cockpit.YELLOW)
            y += 16
        text(ctx, "< > screens   F: status", 0, 68, 11, cockpit.GREY)

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
