"""The docked screens, as tabs: Status, Local chart, Galactic chart and
System data. A row of small squares at the top shows which is open.

On the two charts C makes the selected system the hyperspace target; once
launched, the in-flight menu offers a jump to it. The market and the
equipment screen join these tabs in later phases.
"""
from . import chart, cockpit, commander

TABS = ("STATUS", "LOCAL CHART", "GALACTIC CHART", "SYSTEM DATA")


def _ly(d):
    return "%d.%d LY" % (d // 10, d % 10)


class Docked:
    def __init__(self, cmdr, gal, target=None):
        self.cmdr = cmdr
        self.gal = gal          # None without game_data.py: then only Status
        self.tabs = TABS if gal is not None else TABS[:1]
        self.tab = 0
        self.target = target if gal is not None else None   # a system index, or None
        self.here = gal.system(cmdr.system) if gal is not None else None
        self.view = None        # the chart, on the chart tabs
        self.data = None        # the galaxy.System on the System data tab

    def name(self):
        return self.tabs[self.tab]

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
        self.go(TABS.index("SYSTEM DATA"))

    # ---- drawing ------------------------------------------------------------

    def draw(self, ctx):
        if self.view is not None:
            self.view.draw(ctx)
        elif self.data is not None:
            self._draw_data(ctx)
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
        text(ctx, "fuel %s   %d.%d Cr" % (
            _ly(c.fuel), int(c.credits), int(c.credits * 10) % 10), 0, 30, 12, cockpit.CYAN)
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
