"""The system description sentence (the "goat soup", PDESC in the original):
"Lave is most famous for its vast rain forests and the Lavian tree grub."
No badge imports, so it runs and tests on a PC.

The text comes from the original's extended tokens, which
tools/import_galaxy.py reads from your own copy of the Elite source into
game_data.py (DESC_TOKENS, DESC_MTIN, DESC_PAIRS). How they are put together
is written afresh here to behave as the original's DETOK / DETOK2 do:

  - a token is a string of bytes: 1-31 are jump codes (case changes, the
    system's name, the name with "ian", a made-up name), 32-90 letters and
    punctuation, 91-128 a random pick of five tokens (from DESC_MTIN),
    129-214 another token, and 215 on a two-letter token
  - the random numbers come from the original's DORND, seeded with the
    system's second and third seeds (s1, s2) so each system always says the
    same thing. As in Ian Bell's reading of it, the carry going in is taken
    to be clear.

The original also shows special sentences for a few systems during its
missions (RUTOK); those are left out, as the missions are.
"""

VOWELS = "AEIOUaeiou"


class _Writer:
    def __init__(self, tokens, mtin, pairs, name, s1, s2):
        self.tokens = tokens
        self.mtin = mtin
        self.pairs = pairs
        self.name = name[:1].upper() + name[1:].lower()
        self.rand = [s1 & 255, s1 >> 8, s2 & 255, s2 >> 8]
        self.out = []
        self.lower = False      # {lower case} (DTW6)
        self.sentence = False   # Sentence Case: a word's later letters in lower case (DTW1)
        self.cap = False        # {single cap}: the next letter in capitals (DTW8)
        self.in_word = False    # inside a word (DTW2 clear)

    def dornd(self):
        """The original's random numbers (DORND), the carry clear going in."""
        r = self.rand
        f1 = r[0]
        f2 = (f1 << 1) & 255
        f3 = r[2] + f2 + (1 if f1 > 127 else 0)
        r[0] = f3 & 255
        r[2] = f2
        m1 = r[1]
        m2 = (m1 + r[3] + (f3 >> 8)) & 255
        r[1] = m2
        r[3] = m1
        return m2

    def char(self, c):
        """Print one character the way DASC does: track words, and drop a
        pending capital."""
        self.out.append(c)
        self.cap = False
        self.in_word = c not in ". :\n"

    def letter(self, c):
        """A letter or symbol from a token, in the right case (DTS)."""
        if "A" <= c <= "Z":
            if self.lower or (self.sentence and self.in_word):
                c = c.lower()
            if self.cap:
                c = c.upper()
        self.char(c)

    def token(self, n, depth=0):
        t = self.tokens.get(n)
        if t is None or depth > 12:
            return
        for b in t:
            self.byte(b, depth)

    def byte(self, b, depth):
        if b < 32:
            self.jump(b, depth)
        elif b < 91:
            self.letter(chr(b))
        elif b < 129:
            # one of five tokens, picked at random (DT6)
            x = self.dornd()
            k = (x >= 51) + (x >= 102) + (x >= 153) + (x >= 204)
            self.token(self.mtin[b - 91] + k, depth + 1)
        elif b < 215:
            self.token(b, depth + 1)
        else:
            i = (b - 215) * 2
            for c in self.pairs[i:i + 2]:
                if c >= " ":
                    self.letter(c)

    def jump(self, j, depth):
        if j == 1:              # ALL CAPS
            self.lower = False
            self.sentence = False
        elif j == 2:            # Sentence Case
            self.lower = False
            self.sentence = True
        elif j == 3:            # the system's name
            for c in self.name:
                self.char(c)
        elif j == 13:           # lower case
            self.lower = True
            self.sentence = True
        elif j == 17:           # the name as an adjective: Lave -> Lavian
            stem = self.name
            if stem and stem[-1] in VOWELS:
                stem = stem[:-1]
            for c in stem:
                self.char(c)
            self.token(153, depth + 1)      # "IAN"
        elif j == 18:           # a made-up name: 1 to 4 random letter pairs
            self.cap = True
            n = self.dornd() & 3
            for _ in range(n + 1):
                i = 2 + (self.dornd() & 62)
                for c in self.pairs[i:i + 2]:
                    if "A" <= c <= "Z":
                        self.letter(c)
        elif j == 19:           # a capital for the next letter only
            self.cap = True
        # the rest (justify, left align, new line, ...) don't change the words

    def text(self):
        s = "".join(self.out).strip()
        while "  " in s:
            s = s.replace("  ", " ")
        return s


def describe(game_data, system, seeds):
    """The description sentence for a galaxy.System, given its three seeds
    (s0, s1, s2), or None without the tables in game_data."""
    tokens = getattr(game_data, "DESC_TOKENS", None)
    if not tokens:
        return None
    w = _Writer(tokens, game_data.DESC_MTIN, game_data.DESC_PAIRS, system.name,
                seeds[1], seeds[2])
    w.token(5)
    return w.text()


_cache = [None, None]   # the last (galaxy, index) described, and its sentence


def for_system(game_data, gal, index):
    """describe() for system index of galaxy gal, remembering the last one
    (the docked screens draw it every frame)."""
    key = (id(gal), index)
    if _cache[0] != key:
        _cache[0] = key
        _cache[1] = describe(game_data, gal.system(index), gal.system_seeds(index))
    return _cache[1]


def wrap(text, widths):
    """Split text into lines, the first at most widths[0] characters, the next
    widths[1] and so on (the last width for any after). Words longer than a
    line are cut."""
    lines = []
    words = text.split()
    line = ""
    for w in words:
        limit = widths[min(len(lines), len(widths) - 1)]
        if not line:
            line = w[:limit]
        elif len(line) + 1 + len(w) <= limit:
            line += " " + w
        else:
            lines.append(line)
            limit = widths[min(len(lines), len(widths) - 1)]
            line = w[:limit]
    if line:
        lines.append(line)
    return lines
