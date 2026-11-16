"""The Equip Ship screen's rules: what a station sells, what it costs, and
fitting it to the commander's ship. No badge imports, so it runs and tests on
a PC.

The names and prices come from game_data.EQUIPMENT, which
tools/import_galaxy.py reads from your own copy of the Elite source. The
rules are written here afresh to behave as the original does:

  - a station sells the first (tech level + 2) items, as tech levels are
    shown (the original's internal level + 3), and all of them from tech
    level 10 up
  - fuel is 2 Cr a light year and always fills the tank
  - at most 4 missiles; one of each other item, and buying one you have
    says so and costs nothing
  - a laser is fitted to one of the four views (front, rear, left, right), as
    in the original; a new one replaces the old one on that view, whose price
    is refunded
"""
try:
    from . import commander as _commander
except ImportError:         # imported on its own, as the PC tests do
    import commander as _commander

(FUEL, MISSILE, CARGO_BAY, ECM, PULSE, BEAM, SCOOPS, POD, BOMB, ENERGY,
 DOCKING, HYPERDRIVE, MILITARY, MINING) = range(14)

MAX_MISSILES = 4
BIG_HOLD = 35           # tonnes with the large cargo bay
FUEL_PRICE = 2          # tenths of a credit per tenth of a light year (2 Cr a light year)
LASERS = {PULSE: "pulse", BEAM: "beam", MILITARY: "military", MINING: "mining"}
# the other items, by the name the commander keeps them under
EXTRAS = {ECM: "ecm", SCOOPS: "scoops", POD: "pod", BOMB: "bomb", ENERGY: "energy",
          DOCKING: "docking", HYPERDRIVE: "hyperdrive"}
# what the game can't do yet: shown, but not for sale (everything works now)
SOON = ()


def on_sale(tech):
    """How many items (from the top of the list) a station sells, for a
    system with this tech level as shown to the player (1 to 15)."""
    n = tech + 2
    return 14 if n >= 12 else n


def name(equip, i):
    """An item's name for the screen: one front laser, so not "EXTRA ... LASERS"."""
    n = equip[i][0]
    if n.startswith("EXTRA "):
        n = n[6:]
    if n.endswith(" LASERS"):
        n = n[:-1]
    if n.startswith("GALACTIC "):     # the longest name: shortened to fit the screen
        n = "GAL. " + n[9:]
    return n


def price(equip, i, cmdr):
    """What item i costs this commander, in tenths of a credit (fuel: to fill up)."""
    if i == FUEL:
        return (_commander.MAX_FUEL - cmdr.fuel) * FUEL_PRICE
    return equip[i][1]


MOUNT_NAMES = ("FRONT", "REAR", "LEFT", "RIGHT")


def have(i, cmdr, mount=0):
    """What the commander has of item i, for the screen, or "" for nothing.
    mount: the view a laser would be fitted to."""
    c = cmdr
    if i == FUEL:
        return "%d.%dLY" % (c.fuel // 10, c.fuel % 10)
    if i == MISSILE:
        return "%d/%d" % (c.missiles, MAX_MISSILES)
    if i == CARGO_BAY:
        return "fitted" if c.hold >= BIG_HOLD else ""
    if i in LASERS:
        return "fitted" if c.lasers[mount] == LASERS[i] else ""
    if i == ENERGY and "navy" in c.extras:     # mission 2's naval energy unit is better
        return "fitted"
    return "fitted" if EXTRAS[i] in c.extras else ""


def buy(equip, i, cmdr, mount=0):
    """Buy item i for the commander (a laser for the view mount). Returns
    None, or why not."""
    c = cmdr
    if i in SOON:
        return "COMING SOON"
    if i == FUEL and c.fuel >= _commander.MAX_FUEL:
        return "TANK FULL"
    if i == MISSILE and c.missiles >= MAX_MISSILES:
        return "MISSILES FULL"
    if have(i, c, mount) == "fitted":
        return "ALREADY FITTED"
    cost = price(equip, i, c)
    old = c.lasers[mount] if i in LASERS else ""
    refund = equip[_laser_item(old)][1] if old else 0
    if c.cash + refund < cost:
        return "NOT ENOUGH CASH"
    c.cash += refund - cost
    if i == FUEL:
        c.fuel = _commander.MAX_FUEL
    elif i == MISSILE:
        c.missiles += 1
    elif i == CARGO_BAY:
        c.hold = BIG_HOLD
    elif i in LASERS:
        c.lasers[mount] = LASERS[i]
    else:
        c.extras.append(EXTRAS[i])
    return None


def _laser_item(kind):
    for i, k in LASERS.items():
        if k == kind:
            return i
    return PULSE
