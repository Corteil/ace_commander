"""The station market: prices, stock, and buying and selling. Rules only, no
badge imports, so it runs and tests on a PC.

The goods themselves (name, base price, economic factor, unit, base quantity
and mask) come from game_data.GOODS, which tools/import_galaxy.py reads from
your own copy of the Elite source. The way prices and stock are worked out
from them is written here afresh, to behave as the original does:

  price (tenths of a credit) = 4 * ((base price + (r AND mask)
                                     + economy * factor) mod 256)
  stock = (base quantity + (r AND mask) - economy * factor) mod 256,
          none if that is 128 or more (a negative number in 8 bits), then
          mod 64; never any alien items

where r is a random byte picked on arriving in a system, and economy is the
system's economy, 0 (rich industrial) to 7 (poor agricultural). Prices stay
the same while you trade; buying and selling only changes the stock.
"""

TONNE_GOODS = 13    # the first 13 goods come in tonne canisters and share the hold
HOLD = 20           # tonnes in a standard cargo hold
UNIT_LIMIT = 200    # the most you can carry of each of the others (kg, g, alien items)
ALIEN = 16          # alien items: never in stock at a market
UNITS = {"t": "t", "k": "kg", "g": "g"}


def price(good, economy, r):
    """A good's price in tenths of a credit, in this economy, for random byte r."""
    _, base, factor, _, _, mask = good
    return 4 * ((base + (r & mask) + economy * factor) & 0xFF)


def stock(good, index, economy, r):
    """How much of a good a market has to start with."""
    if index == ALIEN:
        return 0
    _, _, factor, _, qty, mask = good
    a = (qty + (r & mask) - economy * factor) & 0xFF
    if a >= 128:
        return 0
    return a & 63


def new(goods, system, economy, r):
    """The market a commander finds on arriving at system: saved with the
    commander, so it stays the same until they jump somewhere else."""
    return {"system": system, "r": r & 0xFF,
            "stock": [stock(g, i, economy, r) for i, g in enumerate(goods)]}


def scoop(cmdr, goods, i):
    """Put one of good i, scooped in flight, into the commander's hold.
    Returns its name, or None if there is no room."""
    c = cmdr
    if i < TONNE_GOODS:
        if hold_used(c.cargo) >= c.hold:
            return None
    elif c.cargo[i] >= UNIT_LIMIT:
        return None
    c.cargo[i] += 1
    return goods[i][0] if goods else "CARGO"


def hold_used(cargo):
    """Tonnes of cargo in the hold."""
    return sum(cargo[:TONNE_GOODS])


class Market:
    """A station's market, for one commander: what it sells and for how much,
    and buying and selling one unit at a time."""

    def __init__(self, goods, economy, cmdr):
        self.goods = goods
        self.cmdr = cmdr
        m = cmdr.market
        self.stock = m["stock"]
        self.prices = [price(g, economy, m["r"]) for g in goods]

    def name(self, i):
        return self.goods[i][0]

    def unit(self, i):
        return UNITS[self.goods[i][3]]

    def why_not_buy(self, i):
        """Why one more of good i can't be bought, or None if it can."""
        c = self.cmdr
        if self.stock[i] <= 0:
            return "NONE LEFT"
        if c.cash < self.prices[i]:
            return "NOT ENOUGH CASH"
        if i < TONNE_GOODS:
            if hold_used(c.cargo) >= c.hold:
                return "HOLD FULL"
        elif c.cargo[i] >= UNIT_LIMIT:
            return "CAN'T CARRY MORE"
        return None

    def buy(self, i):
        """Buy one of good i. Returns None, or why it couldn't be bought."""
        why = self.why_not_buy(i)
        if why is None:
            c = self.cmdr
            self.stock[i] -= 1
            c.cargo[i] += 1
            c.cash -= self.prices[i]
        return why

    def sell(self, i):
        """Sell one of good i, at the same price. Returns None, or why not."""
        c = self.cmdr
        if c.cargo[i] <= 0:
            return "NONE TO SELL"
        c.cargo[i] -= 1
        self.stock[i] += 1
        c.cash += self.prices[i]
        return None
