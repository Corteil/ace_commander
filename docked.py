"""The docked screens, as tabs: Status, Inventory, Market, Equip ship,
Repair Shop, Galactic chart, Local chart and System data. A row of small
squares at the top shows which is open. Options opens from Status (C).

On the market the joystick picks a good, C buys one and D sells one (hold
either to keep going). On Equip ship the joystick picks an item and C buys
it. On the two charts C makes the selected system the hyperspace target;
once launched, the in-flight menu offers a jump to it.
"""
from . import chart, cockpit, commander, describe, equipment, market, missions, ships
from . import content
game_data = content.DATA     # Elite's text tables, or the game's own (content.py)

# the order the joystick goes round them, starting from Status (you arrive
# there, as Elite's BAY shows f8, and F goes back): Status, Inventory, Market,
# Equip ship, then the Repair Shop after it (Brian, build 77), the Shipyard and
# the Hangar (build 79), Galactic chart,
# Local chart, System data. Options is not a tab: C on Status opens it, and F
# goes back to Status (Brian: A launches, so C is free).
TABS = ("STATUS", "INVENTORY", "MARKET", "EQUIP SHIP", "SHIPYARD", "HANGAR",
        "GALACTIC CHART", "LOCAL CHART", "SYSTEM DATA")
PAINT_PRICE = 100   # tenths of a credit: a new colour at the Repair Shop costs 10.0 Cr
TRANSPONDER_K = 0.25     # a new transponder for a stolen ship costs this much of its price (pirate worlds)
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
                 options=None, bps=None):
        """ship is your ship's blueprint, for the Repair Shop, which is shown
        inside the Shipyard. options: (a function giving
        the settings' lines, a function changing one: given the line and
        whether to go back), the app's, for Options (C on Status); None: no Options.
        bps: a function giving a ship type's blueprint (or None), for the
        Shipyard and Hangar (build 79), which are shown only with it."""
        self.bps = bps
        self.options = options
        self.osel = 0           # the line picked on Options
        self.cmdr = cmdr
        self.ship = ship
        self.spin = 0.0         # the Repair Shop's ship, turning
        self.paint = cmdr.colour if 0 <= cmdr.colour < len(cockpit.SHIP_COLOURS) else 0
        self.gal = gal          # None without game_data.py: then only Status
        self.equip = equip
        if gal is None:
            self.tabs = TABS[:1]
        else:                   # an older game_data.py may not have goods or equipment
            self.tabs = tuple(t for t in TABS
                              if not (t == "MARKET" and not (goods and cmdr.market is not None))
                              and not (t == "INVENTORY" and not goods)
                              and not (t == "EQUIP SHIP" and not equip)
                              and not (t in ("SHIPYARD", "HANGAR") and not (bps and equip)))
        self.goods = goods
        self.itop = 0           # the first good shown on Inventory
        self.market = None
        if "MARKET" in self.tabs:
            self.market = market.Market(goods, gal.system(cmdr.system).economy, cmdr)
        self.sel = 0            # the good picked on the market
        self.top = 0            # the first good shown
        self.mount = 0          # the view a laser bought on Equip ship goes to
        self.esel = 0           # the item picked on Equip ship
        self.etop = 0
        self.for_sale = 0       # how many items this station sells
        if "EQUIP SHIP" in self.tabs:
            self.for_sale = equipment.on_sale(gal.system(cmdr.system).tech)
        self.yard = []          # the Shipyard's stock: (name, price, stolen) each
        if "SHIPYARD" in self.tabs:
            h = gal.system(cmdr.system)
            self.yard = ships.for_sale(cmdr.galaxy, cmdr.system, h.tech, h.government)
        self.ysel = 0           # the ship picked at the Shipyard
        self.hsel = 0           # and in the Hangar (0: the one you fly)
        self.msg = None         # why the last trade didn't happen
        self.msg_t = 0.0
        self.sold = False       # the message says what Inventory's sell all made
        self.tab = 0
        self.in_options = False     # Options open, over Status (C on Status)
        self.repair = ship is not None and "SHIPYARD" in self.tabs   # the Repair Shop, in the Shipyard
        self.in_repair = False      # the Repair Shop open, over the Shipyard (C on your ship there)
        self.in_stats = False       # a ship's stats open, over the Shipyard (build 81)
        self.target = target if gal is not None else None   # a system index, or None
        self.here = gal.system(cmdr.system) if gal is not None else None
        self.view = None        # the chart, on the chart tabs
        self.cursor = False     # on a chart: the joystick moves the cursor (after C), not the tab
        self.chart_tab = None   # the last chart tab opened: where D on System data goes back to
        self.data = None        # the galaxy.System on the System data tab

    def name(self):
        if self.in_options:
            return "OPTIONS"
        if self.in_repair:
            return "REPAIR SHOP"
        if self.in_stats:
            return "SHIP STATS"
        return self.tabs[self.tab]

    def open(self, name):
        """Open the tab with this name, or a sub-screen: OPTIONS (Status's)
        or REPAIR SHOP (the Shipyard's, build 80)."""
        if name == "OPTIONS":
            if self.options:
                self.go(0)
                self.in_options = True
            return
        if name == "REPAIR SHOP":
            if self.repair:
                self.go(self.tabs.index("SHIPYARD"))
                self.ysel = 0
                self.in_repair = True
            return
        self.go(self.tabs.index(name))

    def back(self):
        """F: from a sub-screen to its tab, else to Status. False if already
        on Status (then F leaves for the title)."""
        if self.in_repair or self.in_stats:
            ysel = self.ysel
            self.go(self.tab)
            self.ysel = ysel        # back on the page it came from
            return True
        if self.tab or self.in_options:
            self.go(0)
            return True
        return False

    def go(self, tab, sel=None):
        """Open tab number tab (it wraps round). On a chart the cursor starts
        on system sel, or on the target if sel is None."""
        self.tab = tab % len(self.tabs)
        self.in_options = False
        self.in_repair = False
        self.in_stats = False
        self.msg = None         # a message is about the tab it was said on
        self.sold = False
        n = self.name()
        c = self.cmdr
        self.view = None
        self.data = None
        self.cursor = False
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
        if self.view is not None:
            self.view.active = False
            self.view.docked = True

    def use_cursor(self, on):
        """On a chart: C gives the joystick to the cursor, F gives it back to the tabs."""
        self.cursor = on
        if self.view is not None:
            self.view.active = on

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

    def scroll_inventory(self, step):
        """Inventory's list up (-1) or down (1), if there is more that way."""
        from . import screens
        n = len(screens.cargo_rows(self.cmdr))
        self.itop = max(0, min(n - (screens.ROWS - 1), self.itop + step))

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

    def next_mount(self):
        """The next view round (front, rear, left, right) for lasers: only the
        views your ship has a laser mount on (ships.mounts)."""
        self.mount = (self.mount + 1) % ships.mounts(self.cmdr.ship)

    def buy_item(self):
        """Buy the highlighted item. Returns True if it happened."""
        why = equipment.buy(self.equip, self.esel, self.cmdr, self.mount)
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

    def sell_all(self):
        """Sell everything in the hold at this station's prices (Inventory's C,
        Brian's). Returns True if anything was sold."""
        m = self.market
        c = self.cmdr
        why = None
        if m is None:
            why = "NO MARKET HERE"
        elif not any(c.cargo):
            why = "NOTHING TO SELL"
        if why:
            self.msg = why
            self.msg_t = SAY_TIME
            self.sold = False
            return False
        before = c.cash
        for i in range(len(c.cargo)):
            while c.cargo[i] > 0 and m.sell(i) is None:
                pass
        got = c.cash - before
        self.msg = "SOLD: +%d.%d Cr" % (got // 10, got % 10)
        self.msg_t = SAY_TIME
        self.sold = True        # shown in green: not a refusal
        return True

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
        self.sold = False
        return why is None

    def transponder_price(self):
        """A new transponder for a stolen ship (Brian, build 84): sold only at the
        Repair Shop on pirate worlds, for TRANSPONDER_K of the ship's price; None
        if not on offer here (a clean ship, or a law-abiding world)."""
        c = self.cmdr
        if not c.stolen or self.here is None or self.here.government >= ships.PIRATE_GOV:
            return None
        return int(ships.spec(c.ship)[ships.PRICE] * TRANSPONDER_K)

    def buy_transponder(self):
        """A new transponder, so the ship reads as a new one: it isn't stolen any more,
        so it no longer keeps you an offender or gets spotted by the police.
        Returns True if it happened."""
        c = self.cmdr
        p = self.transponder_price()
        if p is None:
            return False
        if c.cash < p:
            self._say("NOT ENOUGH CASH")
            return False
        c.cash -= p
        c.stolen = False
        self._say("NEW TRANSPONDER FITTED", True)
        return True

    # ---- the shipyard and the hangar (build 79) ----------------------------------

    def _kept_at(self):
        """Where a ship you leave here is kept: this station in Hardcore Mode,
        else None (the hangar goes with you)."""
        c = self.cmdr
        return (c.galaxy, c.system) if c.hardcore else None

    def _say(self, msg, good=False):
        self.msg = msg
        self.msg_t = SAY_TIME
        self.sold = good        # green, not a refusal

    def _sell_off(self, cargo):
        """Sell cargo at this station's prices, crediting your balance: what
        is left in a ship being sold, or what doesn't fit the hold of the ship
        you change to (Brian, build 81). Returns what it made. With no market
        here nothing is sold and the cargo stays where it is."""
        m = self.market
        got = 0
        if m is None:
            return 0
        for i, n in enumerate(cargo):
            if n:
                got += n * m.prices[i]
                m.stock[i] += n
            cargo[i] = 0
        self.cmdr.cash += got
        return got

    def _changed(self, title, spill):
        """Say the change of ship, or what the cargo that didn't fit made."""
        if spill:
            self._say("CARGO OVER: +%d.%d Cr" % (spill // 10, spill % 10), True)
        else:
            self._say(title, True)

    def _now_flying(self):
        """The ship changed: the Repair Shop and the lasers' mounts follow."""
        c = self.cmdr
        self.ship = self.bps(c.ship)
        self.paint = c.colour if 0 <= c.colour < len(cockpit.SHIP_COLOURS) else 0
        self.mount = 0

    def pick_ship(self, step):
        """The Shipyard's next (1) or previous (-1) page: 0 is your own ship
        (and the Repair Shop), then the ships for sale."""
        self.ysel = (self.ysel + step) % (len(self.yard) + 1)
        self.msg = None

    def open_stats(self):
        """The picked page's ship's stats, over the Shipyard (C on any page,
        build 82): a ship for sale (then C buys, D trades in) or your own."""
        if "SHIPYARD" in self.tabs:
            self.in_stats = True
            self.msg = None

    def trade_in_value(self):
        """What the ship you fly fetches in trade, cargo not counted."""
        return ships.value(ships.pack(self.cmdr), self.equip)

    def buy_ship(self, trade):
        """Buy the picked ship. trade: trade in the one you fly (its value
        comes off the price); else it goes into the hangar. Its cargo moves
        across; what doesn't fit the new hold is sold here. The new ship
        comes with its standard weapons. A stolen one makes you an offender.
        Returns True if it happened."""
        if not self.ysel or not self.yard:
            return False
        c = self.cmdr
        name, price, stolen = self.yard[self.ysel - 1]
        old = ships.pack(c, self._kept_at())
        if not ships.tank(name) and ships.stranded(c.hangar + ([] if trade else [old]),
                                                    c.galaxy, c.system, bool(c.hardcore)):
            self._say("NEED A SHIP THAT JUMPS")     # it has no hyperdrive (build 83)
            return False
        credit = ships.value(old, self.equip) if trade else 0
        if c.cash + credit < price:
            self._say("NOT ENOUGH CASH")
            return False
        c.cash += credit - price
        bp = self.bps(name)
        ships.new_ship(c, name, bp, stolen)
        ships.move_cargo(old["cargo"], c.cargo, c.hold)
        spill = self._sell_off(old["cargo"])    # what doesn't fit is sold (Brian, build 81)
        if not trade:
            c.hangar.append(old)
        if stolen:
            c.legal = (c.legal | ships.STOLEN_LEGAL) & 255
        self._now_flying()
        self.in_stats = False       # back to the Shipyard, on your new ship
        self.ysel = 0
        self._changed("NEW SHIP: " + (bp.title if bp is not None else name), spill)
        return True

    def owned(self):
        """Your ships for the Hangar: the one you fly, then the ones kept."""
        return [ships.pack(self.cmdr)] + self.cmdr.hangar

    def pick_owned(self, step):
        self.hsel = (self.hsel + step) % len(self.owned())
        self.msg = None

    def _where(self, entry):
        """Why a kept ship can't be used from here, or None if it can."""
        c = self.cmdr
        if ships.here(entry, c.galaxy, c.system, bool(c.hardcore)):
            return None
        g, s = entry["at"]
        if g != c.galaxy:
            return "KEPT IN GALAXY %d" % (g + 1)
        return "KEPT AT " + self.gal.system(s).name

    def fly_owned(self):
        """Fly the picked kept ship; the one you flew goes into the hangar,
        and its cargo moves across, what doesn't fit sold here. True if it
        happened."""
        c = self.cmdr
        if self.hsel == 0:
            self._say("YOU ARE FLYING IT")
            return False
        entry = c.hangar[self.hsel - 1]
        why = self._where(entry)
        if why:
            self._say(why)
            return False
        old = ships.pack(c, self._kept_at())
        c.hangar.pop(self.hsel - 1)
        ships.unpack(c, entry)
        ships.move_cargo(old["cargo"], c.cargo, c.hold)
        spill = self._sell_off(old["cargo"])    # what doesn't fit is sold (Brian, build 81)
        c.hangar.insert(0, old)
        self.hsel = 0
        self._now_flying()
        bp = self.ship
        self._changed("NOW FLYING " + (bp.title if bp is not None else c.ship), spill)
        return True

    def sell_owned(self):
        """Sell the picked kept ship and its cargo here. True if it happened."""
        c = self.cmdr
        if self.hsel == 0:
            self._say("YOU ARE FLYING IT")
            return False
        entry = c.hangar[self.hsel - 1]
        why = self._where(entry)
        if why:
            self._say(why)
            return False
        rest = c.hangar[:self.hsel - 1] + c.hangar[self.hsel:]
        if not c.max_fuel() and ships.stranded(rest, c.galaxy, c.system, bool(c.hardcore)):
            self._say("NEED A SHIP THAT JUMPS")     # you fly one with no hyperdrive (build 83)
            return False
        got = ships.value(entry, self.equip)
        c.cash += got
        self._sell_off(entry["cargo"])
        c.hangar.pop(self.hsel - 1)
        self.hsel = min(self.hsel, len(c.hangar))
        self._say("SOLD: +%d.%d Cr" % (got // 10, got % 10), True)
        return True

    def tick(self, dt):
        self.spin += SPIN * dt
        if self.msg_t > 0:
            self.msg_t -= dt
            if self.msg_t <= 0:
                self.msg = None
                self.sold = False

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
        elif self.name() == "SHIPYARD":
            self._draw_shipyard(ctx)
        elif self.name() == "SHIP STATS":
            self._draw_stats(ctx)
        elif self.name() == "HANGAR":
            self._draw_hangar(ctx)
        elif self.name() == "OPTIONS":
            self._draw_options(ctx)
        elif self.name() == "INVENTORY":     # the same screen as in flight
            from . import screens
            sell = self.market is not None and any(self.cmdr.cargo)
            screens.draw_inventory(ctx, self.cmdr, self.goods, self.itop,
                                   "C: sell all   < > screens" if sell
                                   else "< > screens   F: status")
            if self.msg:
                cockpit.text(ctx, self.msg, 0, 76, 12,
                             cockpit.GREEN if self.sold else cockpit.RED)
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
        text(ctx, "A: LAUNCH", 0, 68, 14, cockpit.GREEN)
        hint = ["C: options"] if self.options else []
        if len(self.tabs) > 1:
            hint.append("< > screens")
        text(ctx, "   ".join(hint), 0, 84, 11, cockpit.GREY)
        text(ctx, "F: title screen", 0, 98, 11, cockpit.GREY)

    def back_to_chart(self):
        """D on System data: back to the chart you came from (the local chart
        if none yet), with the cursor on the system you were looking at."""
        name = self.chart_tab if self.chart_tab in self.tabs else "LOCAL CHART"
        if name in self.tabs:
            self.go(self.tabs.index(name), self.data.index if self.data is not None else None)
            self.use_cursor(True)       # carry on looking round

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
        text(ctx, "MARKET", 0, -100, 11, cockpit.GREY)     # no system name: Status has it (build 85)
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
        # eight lines fit inside the round edge above the hints; more scroll (build 131)
        cockpit.menu_lines(ctx, items, sel, -62, 15, 8)
        text(ctx, "up / down: pick   C: change", 0, 66, 11, cockpit.GREY)
        text(ctx, "F: back to status", 0, 82, 11, cockpit.GREY)

    def _draw_repair(self, ctx):
        """Your ship turning in the chosen colour, the colours as a row of
        swatches, and what a new coat costs."""
        import math
        text = cockpit.text
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "REPAIR SHOP", 0, -100, 11, cockpit.GREY)     # no system name: Status has it (build 85)
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
        tp = self.transponder_price()
        if self.msg:
            text(ctx, self.msg, 0, 70, 12, cockpit.GREEN if self.sold else cockpit.RED)
        elif tp is not None:    # a stolen ship on a pirate world (build 84)
            text(ctx, "D: new transponder %d Cr" % (tp // 10), 0, 70, 11, cockpit.GREY)
        else:
            text(ctx, "up/down: colour   C: paint", 0, 70, 11, cockpit.GREY)
        text(ctx, "F: back to shipyard", 0, 88, 11, cockpit.GREY)

    def _spin_ship(self, ctx, bp, py, rgb, px=60.0):
        """bp turning, its middle py pixels above the screen's middle, scaled
        to about px pixels across."""
        import math
        o = _Show(bp)
        z = max(200.0, bp.size * cockpit.FOCAL / px)
        o.z = z
        o.y = py * z / cockpit.FOCAL
        a = self.spin
        ca, sa = math.cos(a), math.sin(a)
        t = 0.35
        ct, st = math.cos(t), math.sin(t)
        o.m = [ca, -sa * st, sa * ct, 0.0, ct, st, -sa, -ca * st, ca * ct]
        cockpit.draw_ship(ctx, o, rgb, 3, True)

    def _ship_lines(self, name, bp):
        """Two lines on what a ship type flies like: top speed and hold,
        then laser mounts and missile pylons."""
        speed = ships.flight(bp, self.bps(ships.COBRA))[0]
        mounts = {1: "front", 2: "front+rear", 4: "4 views"}[ships.mounts(name)]
        t = ships.tank(name)
        return ("speed %d   hold %dt   %s" % (int(speed + 0.5), ships.base_hold(name),
                                           "%d.%d LY" % (t // 10, t % 10) if t else "no jumps"),
                "lasers %s   missiles %d" % (mounts, ships.pylons(name)))

    def _foot(self, ctx, hint):
        """The message (green if it worked) or the hint, then the tabs' line."""
        text = cockpit.text
        if self.msg:
            text(ctx, self.msg, 0, 72, 12, cockpit.GREEN if self.sold else cockpit.RED)
        else:
            text(ctx, hint, 0, 72, 11, cockpit.GREY)
        text(ctx, "< > screens   F: status", 0, 88, 11, cockpit.GREY)

    def _draw_shipyard(self, ctx):
        """One page at a time: first your own ship (D: the Repair Shop), then
        each ship for sale, turning, with its price and what it flies like;
        up / down for the others (builds 79-80)."""
        text = cockpit.text
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "SHIPYARD", 0, -100, 11, cockpit.GREY)     # no system name: Status has it (build 85)
        text(ctx, "%d of %d" % (self.ysel + 1, len(self.yard) + 1), 0, -86, 10, cockpit.GREY)
        if self.ysel == 0:          # your own ship
            bp = self.ship
            if bp is not None:
                self._spin_ship(ctx, bp, 48, cockpit.ship_rgb(c.colour))
            text(ctx, bp.title if bp is not None else c.ship, 0, -12, 14, cockpit.WHITE)
            a, b = self._ship_lines(c.ship, bp)
            text(ctx, a, 0, 4, 11, cockpit.GREY)
            text(ctx, b, 0, 18, 11, cockpit.GREY)
            text(ctx, "trade-in %d Cr" % (self.trade_in_value() // 10), 0, 36, 12, cockpit.YELLOW)
            text(ctx, c.cash_text(), 0, 53, 12, cockpit.CYAN)
            self._foot(ctx, "C: stats" + ("   D: repair shop" if self.repair else ""))
            return
        name, price, stolen = self.yard[self.ysel - 1]
        bp = self.bps(name)
        if bp is not None:
            self._spin_ship(ctx, bp, 48, cockpit.RED if stolen else cockpit.CYAN)
        title = bp.title if bp is not None else name
        text(ctx, title + ("  (STOLEN)" if stolen else ""), 0, -12, 14,
             cockpit.RED if stolen else cockpit.WHITE)
        a, b = self._ship_lines(name, bp)
        text(ctx, a, 0, 4, 11, cockpit.GREY)
        text(ctx, b, 0, 18, 11, cockpit.GREY)
        text(ctx, "%d Cr   trade-in %d Cr" % (price // 10, self.trade_in_value() // 10),
             0, 36, 12, cockpit.YELLOW)
        text(ctx, c.cash_text(), 0, 53, 12, cockpit.CYAN)
        self._foot(ctx, "C: stats and buying")

    def _draw_stats(self, ctx):
        """A ship's stats, over the Shipyard (build 81): what it costs (or
        fetches in trade), how it flies against the Cobra Mk III, its hold,
        mounts and pylons, what it comes with and where it is sold. For one
        for sale, C buys it and D trades yours in."""
        text = cockpit.text
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        own = self.ysel == 0 or not self.yard
        if own:
            name, price, stolen = c.ship, None, c.stolen
        else:
            name, price, stolen = self.yard[self.ysel - 1]
        bp = self.bps(name)
        title = bp.title if bp is not None else name
        text(ctx, title + ("  (STOLEN)" if stolen else ""), 0, -98, 14,
             cockpit.RED if stolen else cockpit.WHITE)
        if own:
            text(ctx, "trade-in %d Cr" % (self.trade_in_value() // 10), 0, -82, 12, cockpit.YELLOW)
        else:
            text(ctx, "%d Cr   trade-in %d Cr" % (price // 10, self.trade_in_value() // 10),
                 0, -82, 12, cockpit.YELLOW)
        speed, turn, tough = ships.flight(bp, self.bps(ships.COBRA))
        hold = ships.base_hold(name)
        mounts = {1: "front", 2: "front, rear", 4: "all 4 views"}[ships.mounts(name)]
        n = ships.pylons(name)
        sp = ships.spec(name)
        std = ships.standard_missiles(name, bp)
        rows = (("jump range", ships.jump_text(name)),
                ("top speed", "%d" % int(speed + 0.5)),
                ("turning", "%d%%" % int(turn * 100 + 0.5)),
                ("shields", "%d%%" % int(tough * 100 + 0.5)),
                ("hold", "%dt (%dt with bay)" % (hold, ships.big_hold(name))),
                ("lasers", mounts),
                ("missiles", "%d pylon%s" % (n, "" if n == 1 else "s")),
                ("fitted", ("%s, %d missile%s" % (ships.standard_laser(bp), std, "" if std == 1 else "s"))
                 if std else ships.standard_laser(bp) + " laser"),
                ("sold", "stolen only" if sp[ships.STOLEN_ONLY] else "from tech %d" % sp[ships.TECH]))
        y = -66
        for label, value in rows:
            text(ctx, label, -86, y, 11, cockpit.GREY, -1)
            text(ctx, value, 86, y, 11, cockpit.CYAN, 1)
            y += 12
        cobra = self.bps(ships.COBRA)
        text(ctx, "turning, shields: %s = 100%%" % (cobra.title if cobra is not None else ships.COBRA),
             0, 44, 9, cockpit.GREY)
        if self.msg:
            text(ctx, self.msg, 0, 58, 12, cockpit.GREEN if self.sold else cockpit.RED)
        elif not own:
            text(ctx, "C: buy   D: trade in", 0, 58, 11, cockpit.GREY)
        text(ctx, "F: back to shipyard", 0, 74, 11, cockpit.GREY)

    def _fitout(self, e):
        """A ship's fit-out as lines for the Hangar: its fuel, its lasers by
        view, missiles and hold, then its other equipment."""
        short = {"pulse": "pulse", "beam": "beam", "military": "mil", "mining": "mine"}
        lasers = ["%s %s" % (v, short.get(k, k)) for v, k in zip("FBLR", e["lasers"]) if k]
        from . import market
        used = market.hold_used(e["cargo"])
        t = ships.tank(e["type"])
        f = e.get("fuel", t)
        lines = ["fuel %d.%d of %d.%d LY" % (f // 10, f % 10, t // 10, t % 10) if t else "no hyperdrive",
                 "lasers " + "  ".join(lasers) if lasers else "no lasers",
                 "missiles %d/%d   hold %dt, %dt used" % (e["missiles"], ships.pylons(e["type"]),
                                                       e["hold"], used)]
        names = {"ecm": "ECM", "scoops": "scoops", "pod": "pod", "bomb": "bomb",
                 "energy": "energy unit", "navy": "navy unit", "docking": "dock comp",
                 "hyperdrive": "gal. drive"}
        kit = [names[k] for k in ("ecm", "scoops", "pod", "bomb", "energy", "navy", "docking",
                                  "hyperdrive") if k in e["extras"]]
        if not kit:
            lines.append("no other equipment")
        else:
            lines.append("  ".join(kit[:4]))
            if kit[4:]:
                lines.append("  ".join(kit[4:]))
        return lines

    def _draw_hangar(self, ctx):
        """Your ships one at a time, the one you fly first: turning in its own
        paint, where it is, its fit-out, and what it is worth (build 80)."""
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "HANGAR", 0, -100, 11, cockpit.GREY)     # no system name: Status has it (build 85)
        own = self.owned()
        self.hsel %= len(own)
        e = own[self.hsel]
        text(ctx, "%d of %d" % (self.hsel + 1, len(own)), 0, -86, 10, cockpit.GREY)
        bp = self.bps(e["type"])
        if bp is not None:
            self._spin_ship(ctx, bp, 50, cockpit.ship_rgb(e["colour"]), 54.0)
        text(ctx, bp.title if bp is not None else e["type"], 0, -16, 14, cockpit.WHITE)
        if self.hsel == 0:
            where, col = "flying", cockpit.GREEN
        else:
            why = self._where(e)
            v = ships.value(e, self.equip)
            where = ("here, worth %d Cr" % (v // 10)) if why is None else why.lower()
            col = cockpit.YELLOW if why is None else cockpit.GREY
        text(ctx, where, 0, -4, 11, col)
        y = 8
        for line in self._fitout(e):      # up to six lines
            text(ctx, line, 0, y, 11, cockpit.CYAN)
            y += 11
        if len(own) == 1:
            self._foot(ctx, "your only ship")
        else:
            self._foot(ctx, "C: fly   D: sell" if self.hsel else "down: your other ships")

    def _draw_equip(self, ctx):
        """What this station sells, ROWS at a time: name, price, what you have."""
        text = cockpit.text
        e = self.equip
        c = self.cmdr
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "EQUIP SHIP", 0, -100, 11, cockpit.GREY)     # no system name: Status has it (build 85)
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
            h = equipment.have(i, c, self.mount)
            if h:
                text(ctx, h, HOLD_X, y, 11, cockpit.GREEN, 1)
        if self.etop + ROWS < self.for_sale:
            ctx.rgb(*cockpit.DIM).rectangle(-3, 44, 6, 2).fill()
        text(ctx, c.cash_text(), 0, 58, 12, cockpit.CYAN)
        if self.msg:
            text(ctx, self.msg, 0, 75, 12, cockpit.RED)
        else:
            text(ctx, "C: buy   D: laser " + equipment.MOUNT_NAMES[self.mount], 0, 75, 11, cockpit.GREY)
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
