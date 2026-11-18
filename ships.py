"""The ships you can own and fly (Brian, build 78), and the Shipyard's and
Hangar's rules. Not in BBC Elite, so the rules are ours. No badge imports,
so it runs and tests on a PC.

Each type is known by Elite's name (the game's own content shows its own
name for it: Blueprint.title). What the table gives: the price, the hold,
how many of the four views take a laser, the missile pylons, and the tech
level a shipyard needs to sell it. What comes from the ship data, compared
with the Cobra Mk III in the same data so that the Cobra flies as it always
has: top speed (its speed), toughness (its energy: how much damage the
shields and hull soak up), turning (its energy again, as its mass: light
ships turn faster, heavy ones slower) and
its standard weapons (its laser power and missiles).

A shipyard sells the types its tech level allows, a few at a time chosen by
the system (so each station has its own); pirate worlds (anarchies and
feudal systems) also sell a stolen ship or two, any type that fits the
station's slot, cheap, and buying one makes you an offender.

You can own several ships. The one you fly is the commander's own fields
(lasers, missiles, extras, hold, cargo, colour); the others are kept in the
hangar as dicts (pack / unpack). In Hardcore Mode a ship stays at the
station where you left it; otherwise the hangar goes with you.
"""
COBRA = "COBRA MK III"
PLAYER_MAX = 40.0       # the Cobra's top speed (game.PLAYER_MAX)

# name: (price in tenths of a credit, hold in tonnes, laser mounts, missile
# pylons, the lowest tech level that sells it, sold only stolen)
# mounts: 1 front only, 2 front and rear, 4 all four views
TYPES = {
    "WORM": (25000, 2, 1, 0, 1, False),
    "SHUTTLE": (30000, 10, 1, 0, 1, False),
    "SIDEWINDER": (40000, 4, 2, 1, 1, False),
    "TRANSPORTER": (50000, 30, 1, 0, 2, False),
    "GECKO": (65000, 6, 2, 1, 2, False),
    "ADDER": (85000, 22, 2, 1, 3, False),
    "COBRA MK I": (90000, 12, 2, 2, 3, False),
    "KRAIT": (125000, 10, 2, 1, 4, False),
    "MAMBA": (140000, 8, 2, 2, 5, False),
    COBRA: (400000, 20, 4, 4, 5, False),
    "MORAY": (240000, 30, 4, 2, 6, False),
    "ASP MK II": (650000, 10, 4, 2, 9, False),
    "FER DE LANCE": (750000, 6, 4, 2, 10, False),
    "PYTHON": (950000, 60, 4, 4, 10, False),
    "BOA": (1200000, 75, 4, 5, 12, False),
    "VIPER": (300000, 4, 2, 2, 8, True),        # the police's: only stolen
    "CONSTRICTOR": (3000000, 8, 4, 5, 14, True),  # the navy's prototype: only stolen
}
PRICE, HOLD, MOUNTS, PYLONS, TECH, STOLEN_ONLY = range(6)

SHOWN = 6               # most legal ships a shipyard has at once
STOLEN_PRICE = 0.65     # a stolen ship costs this much of the price
STOLEN_LEGAL = 32       # buying one ORs this into your legal status: an offender
PIRATE_GOV = 2          # governments below this (anarchy, feudal) sell stolen ships
RESALE = 0.6            # what a ship fetches, of its price (stolen: half that)
EQUIP_RESALE = 0.5      # and its equipment, of what it cost


def known(name):
    return name in TYPES


def spec(name):
    """The table's row for this type (the Cobra's for one not in it)."""
    return TYPES.get(name, TYPES[COBRA])


def base_hold(name):
    return spec(name)[HOLD]


def big_hold(name):
    """The hold with the large cargo bay fitted: three quarters as much again
    (the Cobra's 20 t to 35 t, as the original)."""
    h = base_hold(name)
    return h + max(1, h * 3 // 4)


def pylons(name):
    return spec(name)[PYLONS]


def mounts(name):
    """How many views take a laser: 1 front, 2 front and rear, 4 all."""
    return spec(name)[MOUNTS]


def flight(bp, cobra):
    """(top speed, turn rate factor, toughness) for a ship of blueprint bp,
    against the Cobra's blueprint (either may be None: then the Cobra's)."""
    if bp is None or cobra is None:
        return PLAYER_MAX, 1.0, 1.0
    speed = PLAYER_MAX * bp.speed / max(1, cobra.speed)
    turn = (cobra.energy / float(max(1, bp.energy))) ** 0.5     # energy as its mass
    turn = max(0.6, min(1.4, turn))
    tough = max(0.4, bp.energy / float(max(1, cobra.energy)))
    return speed, turn, tough


def standard_laser(bp):
    """The front laser a new ship of this type comes with, by its laser power."""
    p = bp.laser if bp is not None else 2
    if p >= 6:
        return "military"
    if p >= 3:
        return "beam"
    return "pulse"


def standard_missiles(name, bp):
    return min(pylons(name), bp.missiles if bp is not None else 0)


class _Rnd:
    """A small seeded generator (MicroPython's random has no Random class):
    the same numbers for the same seed, on the badge and on a PC."""

    def __init__(self, seed):
        self.x = seed & 0x7FFFFFFF

    def below(self, n):
        """A number from 0 to n - 1."""
        self.x = (self.x * 1103515245 + 12345) & 0x7FFFFFFF
        return (self.x >> 8) % n

    def shuffle(self, a):
        for i in range(len(a) - 1, 0, -1):
            j = self.below(i + 1)
            a[i], a[j] = a[j], a[i]


def for_sale(galaxy, system, tech, gov, fits=None):
    """What this system's shipyard sells: a list of (name, price, stolen),
    cheapest first. fits(name): True if the type fits the station's slot
    (None: all do)."""
    rnd = _Rnd(galaxy * 4099 + system * 31 + 7)
    ok = sorted(n for n, s in TYPES.items()
                if not s[STOLEN_ONLY] and s[TECH] <= tech and (fits is None or fits(n)))
    rnd.shuffle(ok)
    out = [(n, TYPES[n][PRICE], False) for n in ok[:SHOWN]]
    if gov < PIRATE_GOV:
        hot = sorted(n for n in TYPES if fits is None or fits(n))
        rnd.shuffle(hot)
        for n in hot[:1 + rnd.below(2)]:
            out.append((n, int(TYPES[n][PRICE] * STOLEN_PRICE), True))
    out.sort(key=lambda e: e[1])
    return out


# ---- owning ships -------------------------------------------------------------

def pack(c, at=None):
    """The commander's current ship as a hangar entry. at: where it is kept,
    (galaxy, system) in Hardcore Mode, or None (it goes with you)."""
    return {"type": c.ship, "lasers": list(c.lasers), "missiles": c.missiles,
            "extras": list(c.extras), "hold": c.hold, "cargo": list(c.cargo),
            "colour": c.colour, "stolen": c.stolen, "at": list(at) if at else None}


def unpack(c, d):
    """Make hangar entry d the commander's current ship."""
    c.ship = d["type"]
    c.lasers = list(d["lasers"])
    c.missiles = d["missiles"]
    c.extras = list(d["extras"])
    c.hold = d["hold"]
    c.cargo = list(d["cargo"])
    c.colour = d["colour"]
    c.stolen = d["stolen"]


def new_ship(c, name, bp, stolen=False):
    """Make a brand new ship of type name the commander's current one, with
    its standard weapons and nothing else. Cargo is the caller's business."""
    c.ship = name
    c.lasers = [standard_laser(bp), "", "", ""]
    c.missiles = standard_missiles(name, bp)
    c.extras = []
    c.hold = base_hold(name)
    c.cargo = [0] * len(c.cargo)
    c.stolen = stolen


def move_cargo(src, dst, hold):
    """Move cargo from list src into list dst while it fits in hold tonnes
    (goods in kg and g, past the first TONNE_GOODS, always fit, as the market
    has it). Changes both lists."""
    try:
        from . import market
    except ImportError:
        import market
    for i in range(len(src)):
        while src[i] > 0:
            if i < market.TONNE_GOODS and market.hold_used(dst) >= hold:
                break
            src[i] -= 1
            dst[i] += 1


def value(entry, equip):
    """What a ship (a hangar entry) fetches: RESALE of its price (half that
    if stolen), and EQUIP_RESALE of what its equipment cost. equip:
    game_data.EQUIPMENT, or None. In tenths of a credit."""
    try:
        from . import equipment
    except ImportError:
        import equipment
    name = entry["type"]
    v = spec(name)[PRICE] * RESALE
    if entry.get("stolen"):
        v *= 0.5
    extra = 0
    if equip:
        for kind in entry["lasers"]:
            if kind:
                extra += equip[equipment.laser_item(kind)][1]
        for i, key in equipment.EXTRAS.items():
            if key in entry["extras"]:
                extra += equip[i][1]
        if entry["hold"] > base_hold(name):
            extra += equip[equipment.CARGO_BAY][1]
        extra += entry["missiles"] * equip[equipment.MISSILE][1]
    return int(v + extra * EQUIP_RESALE)


def here(entry, galaxy, system, hardcore):
    """True if a hangar entry can be flown from this station."""
    if not hardcore or entry.get("at") is None:
        return True
    return entry["at"][0] == galaxy and entry["at"][1] == system
