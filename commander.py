"""The commander: the player's saved career. No badge imports, so it runs and
tests on a PC.

Phase 1 holds the level, the kill count and the rank that follows from it.
Phase 2 adds the star system the commander is in and the fuel in the tank.
Phase 3 adds cash (in tenths of a credit, as the original keeps it), the
cargo hold, and the market at the station they are at (see market.py), and
the docking style. Phase 4 adds the equipment (see equipment.py): missiles,
the laser, and a list of the other items fitted. Then the missions' progress
(see missions.py).
"""
import json

try:
    from . import ships
except ImportError:         # imported on its own, as the PC tests do
    import ships

# The level is picked when the commander is made and never changes. It sets
# how many kills each rank needs here, and how tough the enemies are in
# game.py.
LEVELS = ("EASY", "NORMAL", "HARD")
RANK_DIVISOR = (5, 2, 1)    # the original's kill counts are divided by this

# rank, and the kills it takes in the original game; ACE is ours (Brian's
# choice), between Deadly and Elite
RANKS = (
    ("HARMLESS", 0),
    ("MOSTLY HARMLESS", 8),
    ("POOR", 16),
    ("AVERAGE", 32),
    ("ABOVE AVERAGE", 64),
    ("COMPETENT", 128),
    ("DANGEROUS", 512),
    ("DEADLY", 2560),
    ("ACE", 4000),
    ("ELITE", 6400),
)

DOCKING = ("A", "B", "C")    # authentic, assisted, automatic
VERSION = 5          # 5: ships (build 78)
START_MISSILES = 3  # a new commander's missiles, as in the original
LASERS = ("pulse", "beam", "military", "mining")
GOODS = 17          # kinds of cargo (market.py)
HOLD = 20           # tonnes in a standard cargo hold
MAX_FUEL = 70       # tenths of a light year: the Cobra's full tank is 7.0 light years (others: ships.tank)


def thresholds(level):
    """Kills needed for each rank at this level, always rising."""
    div = RANK_DIVISOR[level]
    out = []
    last = -1
    for _, kills in RANKS:
        k = (kills + div // 2) // div
        if k <= last:
            k = last + 1
        out.append(k)
        last = k
    return tuple(out)


class Commander:
    def __init__(self, level=1):
        self.level = max(0, min(len(LEVELS) - 1, int(level)))
        self.kills = 0
        self.cash = 1000        # tenths of a credit
        self.cargo = [0] * GOODS
        self.hold = HOLD        # tonnes the hold takes
        self.market = None      # the market where they are (market.new), or None
        self.missiles = START_MISSILES
        self.lasers = ["pulse", "", "", ""]     # the laser on each view (LASERS): front, rear, left, right; "" none
        self.extras = []        # other items fitted, by name (equipment.EXTRAS)
        self.docked_at = None   # the last system docked at: where they start again if destroyed
        self.docking = "B"
        self.system = None      # which star system the commander is in (None: the start)
        self.galaxy = 0         # which of the 8 galaxies (0 is the first)
        self.colour = 0         # the ship's paint (cockpit.SHIP_COLOURS), from the Repair Shop
        self.legal = 0          # legal status, 0 clean to 255 (game.FUGITIVE and up: a fugitive)
        self.mission = 0        # how far the two missions have got: the original's TP (missions.py)
        self.hardcore = False   # Hardcore Mode (rules.py): picked with the level, then fixed
        self.quick_con = True   # the Constrictor turns up after missions.QUICK_WAIT (else rarely, as the original)
        self.data = ""          # the data set the commander belongs to: "elite" or "own" ("" unknown)
        self.fuel = MAX_FUEL    # tenths of a light year
        self.ship = "COBRA MK III"  # the ship flown (ships.TYPES), from build 78
        self.stolen = False     # bought stolen at a pirate world's shipyard
        self.hangar = []        # the other ships owned (ships.pack's dicts)
        self._needs = thresholds(self.level)

    def max_fuel(self):
        """A full tank for the ship flown (ships.tank: 0 with no hyperdrive)."""
        return ships.tank(self.ship)

    @property
    def credits(self):
        return self.cash / 10.0

    def cash_text(self):
        """Cash as the original shows it: 1234.5 Cr."""
        return "%d.%d Cr" % (self.cash // 10, self.cash % 10)

    def rank_index(self):
        i = 0
        for n, need in enumerate(self._needs):
            if self.kills >= need:
                i = n
        return i

    def rank(self):
        return RANKS[self.rank_index()][0]

    def next_rank(self):
        """(name, kills still needed) for the next rank, or None at the top."""
        i = self.rank_index() + 1
        if i >= len(RANKS):
            return None
        return RANKS[i][0], self._needs[i] - self.kills

    def add_kills(self, n):
        """Count n more kills. Returns the new rank's name if it went up."""
        before = self.rank_index()
        self.kills += n
        if self.rank_index() > before:
            return self.rank()
        return None

    @property
    def laser(self):
        """The front laser, which a commander always has."""
        return self.lasers[0]

    @laser.setter
    def laser(self, kind):
        self.lasers[0] = kind

    # ---- saving -----------------------------------------------------------

    def to_dict(self):
        return {"version": VERSION, "level": self.level, "kills": self.kills,
                "credits": self.credits, "docking": self.docking,
                "system": self.system, "fuel": self.fuel, "cargo": self.cargo,
                "market": self.market, "hold": self.hold, "missiles": self.missiles,
                "laser": self.laser, "lasers": self.lasers, "extras": self.extras, "docked_at": self.docked_at,
                "galaxy": self.galaxy, "colour": self.colour,
                "legal": self.legal, "mission": self.mission,
                "quick_con": self.quick_con, "data": self.data, "hardcore": self.hardcore,
                "ship": self.ship, "stolen": self.stolen, "hangar": self.hangar}

    @classmethod
    def from_dict(cls, d):
        c = cls(d.get("level", 1))
        c.kills = max(0, int(d.get("kills", 0)))
        c.cash = max(0, int(round(float(d.get("credits", 100.0)) * 10)))
        if isinstance(d.get("ship"), str) and ships.known(d["ship"]):
            c.ship = d["ship"]
        # the ship's hold (with the large cargo bay at most) and its pylons
        c.hold = max(ships.base_hold(c.ship), min(ships.big_hold(c.ship), int(d.get("hold", HOLD))))
        c.missiles = max(0, min(ships.pylons(c.ship), int(d.get("missiles", START_MISSILES))))
        if d.get("laser") in LASERS:
            c.laser = d["laser"]
        mounted = d.get("lasers")
        if isinstance(mounted, list) and len(mounted) == 4:     # one a view, "" for none
            front = c.laser
            c.lasers = [k if k in LASERS else "" for k in mounted]
            if not c.lasers[0]:
                c.lasers[0] = front     # the front laser can't be taken away
        extras = d.get("extras")
        if isinstance(extras, list):
            c.extras = [x for x in extras if isinstance(x, str)]
        cargo = d.get("cargo")
        if isinstance(cargo, list) and len(cargo) == GOODS:
            c.cargo = [max(0, int(n)) for n in cargo]
        m = d.get("market")
        if (isinstance(m, dict) and isinstance(m.get("system"), int)
                and isinstance(m.get("r"), int) and isinstance(m.get("stock"), list)
                and len(m["stock"]) == GOODS):
            c.market = {"system": m["system"], "r": m["r"] & 0xFF,
                        "stock": [max(0, int(n)) for n in m["stock"]]}
        if d.get("docking") in DOCKING:
            c.docking = d["docking"]
        s = d.get("system")
        if isinstance(s, int) and 0 <= s < 256:
            c.system = s
        c.fuel = max(0, min(c.max_fuel(), int(d.get("fuel", c.max_fuel()))))
        k = d.get("legal")
        if isinstance(k, int):
            c.legal = max(0, min(255, k))
        if isinstance(d.get("data"), str):
            c.data = d["data"]
        if isinstance(d.get("quick_con"), bool):
            c.quick_con = d["quick_con"]
        # None: a save from before build 74 (ace.py then takes options.json's old HARDCORE)
        c.hardcore = d["hardcore"] if isinstance(d.get("hardcore"), bool) else None
        k = d.get("mission")
        if isinstance(k, int):
            c.mission = k & 0xFF
        k = d.get("colour")
        if isinstance(k, int) and 0 <= k < 32:
            c.colour = k
        g = d.get("galaxy")
        if isinstance(g, int) and 0 <= g < 8:
            c.galaxy = g
        s = d.get("docked_at")
        if isinstance(s, int) and 0 <= s < 256:
            c.docked_at = s
        c.stolen = d.get("stolen") is True
        h = d.get("hangar")
        if isinstance(h, list):
            c.hangar = [e for e in (_hangar_entry(x) for x in h) if e is not None]
        return c

    def save(self, path):
        """Write the commander to path. Returns True if it worked."""
        try:
            with open(path, "w") as f:
                f.write(json.dumps(self.to_dict()))
            return True
        except (OSError, ValueError):
            return False


def _hangar_entry(x):
    """A hangar entry from a save, checked (ships.pack makes them), or None."""
    try:
        lasers = [k if k in LASERS else "" for k in x["lasers"]][:4]
        while len(lasers) < 4:
            lasers.append("")
        cargo = [max(0, int(n)) for n in x["cargo"]]
        if len(cargo) != GOODS:
            return None
        at = x.get("at")
        if at is not None:
            at = [int(at[0]) & 7, int(at[1]) & 255]
        t = x["type"]
        if not ships.known(t):
            return None
        return {"type": t, "lasers": lasers,
                "missiles": max(0, min(ships.pylons(t), int(x["missiles"]))),
                "extras": [e for e in x["extras"] if isinstance(e, str)],
                "hold": max(ships.base_hold(t), min(ships.big_hold(t), int(x["hold"]))), "cargo": cargo,
                "colour": int(x.get("colour", 0)) & 31, "stolen": x.get("stolen") is True,
                "fuel": max(0, min(ships.tank(t), int(x.get("fuel", ships.tank(t))))),
                "at": at}
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def load(path, data=None):
    """The commander saved at path, or None if there isn't a readable one, or
    if it belongs to another data set than data ("elite" or "own"; a save
    from before data sets were recorded loads anywhere)."""
    try:
        with open(path) as f:
            d = json.loads(f.read())
        if not isinstance(d, dict):
            return None
        if data and d.get("data") and d.get("data") != data:
            return None
        return Commander.from_dict(d)
    except (OSError, ValueError, TypeError, KeyError):
        return None
