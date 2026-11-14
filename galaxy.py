"""The galaxy: 256 star systems worked out from three seed numbers. No badge
imports, so it runs and tests on a PC.

Nothing about a system is stored except its chart position. Each system has
three 16-bit seeds; the next system's seeds come from "twisting" the last
one's four times, and everything about a system (where it is, its name,
economy, government and so on) is read out of the bits of its seeds. All of
it is whole-number arithmetic.

The starting seeds and the letter pairs for names come from game_data.py,
which tools/import_galaxy.py makes from your own copy of the Elite source.
"""

GOVERNMENTS = ("Anarchy", "Feudal", "Multi-government", "Dictatorship",
               "Communist", "Confederacy", "Democracy", "Corporate State")
ECONOMIES = ("Rich Industrial", "Average Industrial", "Poor Industrial",
             "Mainly Industrial", "Mainly Agricultural", "Rich Agricultural",
             "Average Agricultural", "Poor Agricultural")
from array import array

SIZE = 256
MAX_FUEL = 70       # tenths of a light year: a full tank is 7.0 light years


def _twist(s0, s1, s2):
    """The next seeds in the sequence."""
    return s1, s2, (s0 + s1 + s2) & 0xFFFF


def _isqrt(n):
    """Whole-number square root, rounded down."""
    if n < 2:
        return n
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


class System:
    """Everything about one star system."""

    def __init__(self, index, seeds, pairs):
        s0, s1, s2 = seeds
        self.index = index
        self.x = s1 >> 8
        self.y = s0 >> 8
        gov = (s1 >> 3) & 7
        eco = (s0 >> 8) & 7
        if gov <= 1:        # anarchies and feudal systems are never rich
            eco |= 2
        tech = ((s1 >> 8) & 3) + (eco ^ 7) + (gov >> 1)
        if gov & 1:
            tech += 1
        self.government = gov
        self.economy = eco
        self.tech = tech + 1                    # 1 to 15, as shown to the player
        self.population = 4 * tech + eco + gov + 1      # tenths of a billion
        self.productivity = ((eco ^ 7) + 3) * (gov + 4) * self.population * 8   # M Cr
        self.radius = 256 * (((s2 >> 8) & 15) + 11) + self.x    # km

        # the name: three or four letter pairs, twisting the seeds between each
        n = 4 if s0 & 64 else 3
        name = ""
        for _ in range(4):
            if n:
                i = 2 * ((s2 >> 8) & 31)
                if i:           # pair 0 means "no letters here"
                    name += pairs[i:i + 2]
                n -= 1
            s0, s1, s2 = _twist(s0, s1, s2)
        self.name = name.replace("?", "")

    def government_name(self):
        return GOVERNMENTS[self.government]

    def economy_name(self):
        return ECONOMIES[self.economy]


class Galaxy:
    def __init__(self, seeds, pairs):
        self.seeds = tuple(seeds)
        self.pairs = pairs
        # chart positions of all 256 systems (512 bytes), and each system's
        # seeds (1.5 KB) so that working one out doesn't start from the beginning
        self.xs = bytearray(SIZE)
        self.ys = bytearray(SIZE)
        self.all = array("H", bytes(6 * SIZE))
        s0, s1, s2 = self.seeds
        for i in range(SIZE):
            self.xs[i] = s1 >> 8
            self.ys[i] = s0 >> 8
            self.all[3 * i] = s0
            self.all[3 * i + 1] = s1
            self.all[3 * i + 2] = s2
            for _ in range(4):
                s0, s1, s2 = _twist(s0, s1, s2)

    def system(self, index):
        """Work out system number index (0 to 255)."""
        i = 3 * (index % SIZE)
        a = self.all
        return System(index % SIZE, (a[i], a[i + 1], a[i + 2]), self.pairs)

    def distance(self, a, b):
        """Between systems a and b, in tenths of a light year. The chart is
        twice as wide as it is tall, so up and down counts half."""
        dx = self.xs[a] - self.xs[b]
        dy = (self.ys[a] - self.ys[b]) // 2 if self.ys[a] >= self.ys[b] else \
            (self.ys[b] - self.ys[a]) // 2
        return 4 * _isqrt(dx * dx + dy * dy)

    def in_range(self, a, fuel):
        """Systems that can be reached from a with this much fuel (tenths of
        a light year), nearest first, as (distance, index). A system at no
        distance (some share a position) can't be jumped to."""
        out = []
        for b in range(SIZE):
            if b != a:
                d = self.distance(a, b)
                if 0 < d <= fuel:
                    out.append((d, b))
        out.sort()
        return out

    def find(self, x, y):
        """The index of the first system at chart position (x, y), or None."""
        for i in range(SIZE):
            if self.xs[i] == x and self.ys[i] == y:
                return i
        return None

    def nearest(self, x, y):
        """The index of the system closest to chart position (x, y)."""
        best = 0
        best_d = 1 << 30
        for i in range(SIZE):
            dx = self.xs[i] - x
            dy = (self.ys[i] - y) // 2 if self.ys[i] >= y else (y - self.ys[i]) // 2
            d = dx * dx + dy * dy
            if d < best_d:
                best_d = d
                best = i
        return best
