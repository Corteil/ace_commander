"""The system description sentence ("goat soup", build 52) and D for system
data on the charts."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import describe, docked, galaxy, chart, commander
mod = ace_commander.ace
gd = mod.game_data
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_describe.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE

assert gd.DESC_TOKENS and len(gd.DESC_MTIN) == 38 and gd.DESC_PAIRS[:2] == "\x0c\n"
gal = galaxy.Galaxy(gd.SEEDS, gd.PAIRS)
lave = [i for i in range(256) if gal.system(i).name == "LAVE"][0]
# the one every Elite player knows, word for word
assert describe.for_system(gd, gal, lave) == \
    "Lave is most famous for its vast rain forests and the Lavian tree grub.", \
    describe.for_system(gd, gal, lave)
# every system has one: a sentence, the same each time, no stray codes
seen = set()
for i in range(256):
    s = gal.system(i)
    t = describe.describe(gd, s, gal.system_seeds(i))
    assert t and t[0].isupper() and t.endswith(".") and len(t) < 140, (s.name, t)
    assert all(" " <= ch <= "~" for ch in t), (s.name, t)
    assert t == describe.describe(gd, s, gal.system_seeds(i)), "always the same"
    seen.add(t)
assert len(seen) > 200, "different for (nearly) every system"
# without the tables: none, and nothing breaks
class NoTables: pass
assert describe.describe(NoTables, gal.system(lave), gal.system_seeds(lave)) is None
# wrapping
assert describe.wrap("aa bb cc dd", (5, 5)) == ["aa bb", "cc dd"]
assert describe.wrap("abcdefgh", (4,)) == ["abcd"]
print("descriptions: Lave word for word, every system a sentence: ok")

# ---- the page -------------------------------------------------------------------
c = CountCtx(); docked.system_page(c, gal, gal.system(lave), None, 70, "help")
tx = [t for t in c.texts]
for s, (x, y), size in tx:
    assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
lines = [t[0] for t in tx]
assert "LAVE" in lines and "you are here" in lines and "help" in lines
assert " ".join(l for l in lines if l not in ("help",)).count("Lavian tree grub") == 1
# the longest description fits the lines there are
longest = max((describe.describe(gd, gal.system(i), gal.system_seeds(i)) for i in range(256)), key=len)
assert len(describe.wrap(longest, docked.DESC_WIDTHS)) <= len(docked.DESC_Y), longest
print("the System data page, with the description: ok")

# ---- D on the charts ------------------------------------------------------------
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
d = e.dock
d.open("LOCAL CHART")
assert "FUEL 7.0 LY   D: DATA" in [t[0] for t in (lambda c: (d.draw(c), c.texts)[1])(CountCtx())]
d.view.cx, d.view.cy = [(float(px), float(py)) for px, py, i, dd in d.view.dots if i != e.cmdr.system][0]
d.view._select()
pick = d.view.picked()
tick(e, fresh=["D"])
assert d.name() == "SYSTEM DATA" and d.data.index == pick and e.target is None, "data, not a target"
d.open("GALACTIC CHART"); tick(e, fresh=["D"])
assert d.name() == "SYSTEM DATA"
# in flight: D on the local chart shows the page, and back
d.go(0); tick(e, fresh=["C"])
for _ in range(200):
    tick(e)
    if e.mode == "flight":
        break
g = e.game; g.encounter_t = g.station_t = 1e9
tick(e, fresh=["A"]); e.fmenu = e._fitems().index("LOCAL CHART"); tick(e, fresh=["C"])
assert e.fsub == "chart"
tick(e, fresh=["D"])
assert e.fsub == "data" and e.data_of == e.chart.picked()
c = CountCtx(); e.draw(c)
assert "SYSTEM DATA" in [t[0] for t in c.texts]
tick(e, fresh=["D"]); assert e.fsub == "chart", "D again goes back"
tick(e, fresh=["D"]); tick(e, fresh=["F"]); assert e.fsub == "chart", "so does F"
os.path.exists(SAVE) and os.remove(SAVE)
print("D on the docked and in-flight charts: system data: ok")
print("ALL DESCRIBE TESTS PASSED")
