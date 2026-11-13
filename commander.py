"""The commander: the player's saved career. No badge imports, so it runs and
tests on a PC.

Phase 1 holds the level, the kill count and the rank that follows from it.
Credits, cargo, fuel and equipment arrive with the later phases; the fields
that already have a decided starting value (credits, docking style) are saved
now so old saves stay readable.
"""
import json

# The level is picked when the commander is made and never changes. It sets
# how many kills each rank needs here, and how tough the enemies are in
# game.py. The names and the divisors are placeholders until they are agreed.
LEVELS = ("EASY", "NORMAL", "HARD")
RANK_DIVISOR = (10, 4, 1)    # the original's kill counts are divided by this

# rank, and the kills it takes in the original game
RANKS = (
    ("HARMLESS", 0),
    ("MOSTLY HARMLESS", 8),
    ("POOR", 16),
    ("AVERAGE", 32),
    ("ABOVE AVERAGE", 64),
    ("COMPETENT", 128),
    ("DANGEROUS", 512),
    ("DEADLY", 2560),
    ("ELITE", 6400),
)

DOCKING = ("A", "B", "C")    # authentic, assisted, automatic
VERSION = 1


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
        self.credits = 100.0
        self.docking = "B"
        self._needs = thresholds(self.level)

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

    # ---- saving -----------------------------------------------------------

    def to_dict(self):
        return {"version": VERSION, "level": self.level, "kills": self.kills,
                "credits": self.credits, "docking": self.docking}

    @classmethod
    def from_dict(cls, d):
        c = cls(d.get("level", 1))
        c.kills = max(0, int(d.get("kills", 0)))
        c.credits = float(d.get("credits", 100.0))
        if d.get("docking") in DOCKING:
            c.docking = d["docking"]
        return c

    def save(self, path):
        """Write the commander to path. Returns True if it worked."""
        try:
            with open(path, "w") as f:
                f.write(json.dumps(self.to_dict()))
            return True
        except (OSError, ValueError):
            return False


def load(path):
    """The commander saved at path, or None if there isn't a readable one."""
    try:
        with open(path) as f:
            d = json.loads(f.read())
        if not isinstance(d, dict):
            return None
        return Commander.from_dict(d)
    except (OSError, ValueError, TypeError, KeyError):
        return None
