import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
sys.path.insert(0, REPO)
import galaxy
try:
    import game_data as gd
except ImportError:
    sys.exit("game_data.py is missing: run tools/import_galaxy.py on your copy of the Elite source")

g = galaxy.Galaxy(gd.SEEDS, gd.PAIRS)

# ---- known facts about the original's first galaxy --------------------------
# These prove the converter read the right numbers and the generator is right.
lave = g.system(7)
assert (lave.name, lave.x, lave.y) == ("LAVE", 20, 173), (lave.name, lave.x, lave.y)
assert lave.government_name() == "Dictatorship" and lave.economy_name() == "Rich Agricultural"
assert (lave.tech, lave.population, lave.productivity, lave.radius) == (5, 25, 7000, 4116)
assert g.find(*gd.START_XY) == 7, "a new commander starts at Lave"
for index, name in ((0, "TIBEDIED"), (129, "ZAONCE"), (147, "DISO"), (55, "LEESTI"),
                    (46, "RIEDQUAT"), (39, "REORTE")):
    assert g.system(index).name == name, (index, g.system(index).name)
diso = g.system(147)
assert (diso.government_name(), diso.economy_name(), diso.tech) == \
    ("Democracy", "Average Agricultural", 8)
assert g.distance(7, 147) == 36 and g.distance(7, 55) == 36, "Diso and Leesti are 3.6 light years from Lave"
near = [(g.system(b).name, d) for d, b in g.in_range(7, galaxy.MAX_FUEL)]
assert [n for n, d in near] == ["LEESTI", "DISO", "REORTE", "ZAONCE", "RIEDQUAT", "ORERVE"], near
print("Lave and its neighbours match the original: ok", near)

# ---- every system is sane ---------------------------------------------------
names = set()
for i in range(galaxy.SIZE):
    s = g.system(i)
    assert s.index == i and (s.x, s.y) == (g.xs[i], g.ys[i])
    assert 0 <= s.government < 8 and 0 <= s.economy < 8 and 1 <= s.tech <= 15, (i, s.tech)
    assert s.government > 1 or s.economy & 2, "anarchies and feudal systems are never rich"
    assert 2 <= len(s.name) <= 8 and s.name.isalpha() and s.name.isupper(), s.name
    assert s.population > 0 and s.productivity > 0 and s.radius > 2000
    names.add(s.name)
assert len(names) == galaxy.SIZE, "every name is different"
assert g.system(256).name == "TIBEDIED", "indexes wrap"
print("all 256 systems: ok")

# ---- distances and range ----------------------------------------------------
for a in (0, 7, 100, 255):
    assert g.distance(a, a) == 0
    for b in range(galaxy.SIZE):
        assert g.distance(a, b) == g.distance(b, a) >= 0
assert g.in_range(7, 35) == [], "nothing within 3.5 light years of Lave"
assert [b for d, b in g.in_range(7, 36)] == [55, 147]
stranded = [i for i in range(galaxy.SIZE) if not g.in_range(i, galaxy.MAX_FUEL)]
print("distances: ok (systems with no neighbour within 7 light years: %d)" % len(stranded))
assert g.nearest(20, 173) == 7 and g.nearest(21, 172) == 7
assert g.find(255, 255) is None or g.xs[g.find(255, 255)] == 255
assert galaxy._isqrt(0) == 0 and galaxy._isqrt(15) == 3 and galaxy._isqrt(16) == 4
assert galaxy._isqrt(65535 * 2) == 362

# ---- other seeds give another galaxy without breaking -----------------------
g2 = galaxy.Galaxy((1, 2, 3), gd.PAIRS)
assert len({g2.system(i).name for i in range(256)}) > 100
print("ALL GALAXY TESTS PASSED")
