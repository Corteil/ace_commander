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

The same tokens make the missions' texts (mission_pages) and the special
sentences a few systems have (RUTOK, game_data.DESC_RUTOK; see missions.py
for when they are said).
"""

VOWELS = "AEIOUaeiou"


class _Writer:
    def __init__(self, tokens, mtin, pairs, name, s1, s2, cmdr="", galaxy=0):
        self.tokens = tokens
        self.cmdr = cmdr        # the commander's name (jump 4)
        self.galaxy = galaxy    # picks the captain's name (27) and the Constrictor's trail (28)
        self.std = False        # printing a standard token (jump 6 to 5): in Sentence Case
        self.pages = []         # mission texts: (text, shows the ship) for each screen
        self.ship = False
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
            if self.std:
                if self.in_word:
                    c = c.lower()
            elif self.lower or (self.sentence and self.in_word):
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
        elif j == 4:            # the commander's name
            for c in self.cmdr:
                self.char(c)
        elif j == 5 or j == 6:  # back to extended tokens / a standard token
            self.std = j == 6
        elif j == 8:            # tab: a new word
            self.in_word = False
        elif j == 12:           # carriage return: a new paragraph
            self.char("\n")
        elif j == 23 or j == 29:    # white, lower case (MT13)
            self.lower = True
            self.sentence = True
        elif j == 9 or j == 24 or j == 25:  # clear screen, wait for a key, incoming message
            self.page()
        elif j == 22:           # the ship, and wait for a key
            self.ship = True
            self.page()
        elif j == 27:           # the captain's name, one for each of the first three galaxies
            self.token(217 + min(self.galaxy, 2), depth + 1)
        elif j == 28:           # where the Constrictor was last seen
            self.token(220 + min(self.galaxy, 1), depth + 1)
        # the rest (justify, left align, new line, ...) don't change the words

    def text(self):
        s = "".join(self.out).strip()
        while "  " in s:
            s = s.replace("  ", " ")
        return s

    def page(self):
        """End the screen so far, if anything is on it."""
        paras = [p.strip() for p in self.text().split("\n")]
        while paras and not paras[-1]:
            paras.pop()
        if paras:
            self.pages.append(("\n".join(paras), self.ship))
        self.out = []
        self.ship = False


class _Grammar:
    """The game's own descriptions (original_data.DESCRIBE): each <word> is
    one of its choices, picked by a small random-number generator seeded
    from the system (whole numbers only, cheap on the badge)."""

    def __init__(self, rules, name, s1, s2, pairs):
        self.rules = rules
        self.name = name[:1].upper() + name[1:].lower()
        self.pairs = pairs
        self.x = ((s1 ^ (s2 << 3)) & 0xFFFF) or 0xACE1

    def rnd(self):
        """The next number, 0 to 65535 (a 16-bit xorshift)."""
        x = self.x
        x ^= (x << 7) & 0xFFFF
        x ^= x >> 9
        x ^= (x << 8) & 0xFFFF
        self.x = x
        return x

    def adjective(self):
        stem = self.name
        if stem and stem[-1] in VOWELS:
            stem = stem[:-1]
        return stem + "ian"

    def made_up(self):
        n = 1 + self.rnd() % 3
        s = ""
        for _ in range(n):
            i = 2 + 2 * (self.rnd() % 31)
            s += self.pairs[i:i + 2].replace("?", "")
        return s[:1] + s[1:].lower()

    def expand(self, word, depth=0):
        choices = self.rules.get(word)
        if not choices or depth > 8:
            return ""
        t = choices[self.rnd() % len(choices)]
        out = []
        i = 0
        while i < len(t):
            c = t[i]
            if c == "<":
                j = t.index(">", i)
                out.append(self.expand(t[i + 1:j], depth + 1))
                i = j + 1
            elif c == "%" and i + 1 < len(t):
                k = t[i + 1]
                out.append(self.name if k == "N" else self.adjective() if k == "I"
                           else self.made_up() if k == "R" else "")
                i += 2
            else:
                out.append(c)
                i += 1
        return "".join(out)


def describe(game_data, system, seeds):
    """The description sentence for a galaxy.System, given its three seeds
    (s0, s1, s2), or None without the tables in game_data."""
    rules = getattr(game_data, "DESCRIBE", None)
    if rules:
        g = _Grammar(rules, system.name, seeds[1], seeds[2], game_data.PAIRS)
        words = g.expand("start").split(" ")
        for i in range(len(words) - 1):     # "a ancient" -> "an ancient"
            if words[i] in ("a", "A") and words[i + 1][:1].lower() in "aeiou":
                words[i] += "n"
        s = " ".join(words)
        return s[:1].upper() + s[1:]
    tokens = getattr(game_data, "DESC_TOKENS", None)
    if not tokens:
        return None
    w = _Writer(tokens, game_data.DESC_MTIN, game_data.DESC_PAIRS, system.name,
                seeds[1], seeds[2])
    w.token(5)
    return w.text()


def special(game_data, n, name):
    """Special system sentence n (RUTOK, or the game's own SPECIAL) for a
    system called name."""
    own = getattr(game_data, "SPECIAL", None)
    if own:
        if not 0 < n <= len(own):
            return None
        return own[n - 1][3].replace("%N", name[:1] + name[1:].lower())
    rutok = getattr(game_data, "DESC_RUTOK", None)
    if not rutok or n >= len(rutok):
        return None
    w = _Writer(game_data.DESC_TOKENS, game_data.DESC_MTIN, game_data.DESC_PAIRS, name, 0, 0)
    w.lower = w.sentence = True     # PDESC prints it as token 176 does: lower case,
    w.cap = True                    # a capital to start
    for b in rutok[n]:
        w.byte(b, 0)
    t = w.text()
    return t + "." if t and t[-1] not in ".!?" else t


def mission_pages(game_data, n, cmdr, galaxy):
    """Mission text n (an extended token, see missions.py) as a list of
    screens: (text with paragraphs split by newlines, shows the ship).
    cmdr: the commander's name; galaxy: 0 for the first."""
    own = getattr(game_data, "MISSION_TEXTS", None)
    if own:
        trail = getattr(game_data, "TRAIL", {})
        return [(t.replace("[NAME]", cmdr).replace("[TRAIL]", trail.get(galaxy, trail.get(1, ""))),
                 ship) for t, ship in own.get(n, ())]
    tokens = getattr(game_data, "DESC_TOKENS", None)
    if not tokens or n not in tokens:
        return []
    w = _Writer(tokens, game_data.DESC_MTIN, game_data.DESC_PAIRS, "", 0, 0, cmdr, galaxy)
    w.token(n)
    w.page()
    return w.pages


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
