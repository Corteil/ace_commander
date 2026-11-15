"""The game's own galaxy, market, words and missions (original_data.py,
builds 56-57), played in a copy of the app without Elite's files."""
import os, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
import badge_stubs as bs
from badge_stubs import CountCtx

# a copy of the app without ship_data.py and game_data.py, as an app store
# player would have it
TMP = os.path.join(HERE, "noelite")
shutil.rmtree(TMP, ignore_errors=True)
shutil.copytree(REPO, os.path.join(TMP, "ace_commander"),
                ignore=shutil.ignore_patterns("ship_data.py", "game_data.py", "__pycache__",
                                              ".git", "tests", "*.json"))
sys.path.insert(0, TMP)
bs.install()
import ace_commander
from ace_commander import briefing, content, describe, docked, galaxy, missions, original_data as d
mod = ace_commander.ace
assert "noelite" in mod.__file__ and content.OWN and not content.HAVE_ELITE
assert mod.game_data is d and mod.SAVE_PATH.endswith("/commander.json")
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(TMP, "test.json")
mod.SAVE_PATH = SAVE
DT = 0.04


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


# ---- descriptions --------------------------------------------------------------
for n in range(8):
    g = galaxy.Galaxy(galaxy.seeds_for(d.SEEDS, n), d.PAIRS)
    seen = set()
    for i in range(256):
        s = describe.describe(d, g.system(i), g.system_seeds(i))
        assert s and s[0].isupper() and s.endswith("."), s
        assert "<" not in s and "%" not in s, s
        assert len(describe.wrap(s, docked.DESC_WIDTHS)) <= len(docked.DESC_Y), s
        assert s == describe.describe(d, g.system(i), g.system_seeds(i)), "always the same"
        seen.add(s)
    assert len(seen) > 240, len(seen)
print("descriptions: every system in all eight galaxies, fitting System data: ok")

# ---- the mission texts ---------------------------------------------------------------
for n in (missions.BRIEF_1, missions.DEBRIEF_1, missions.BRIEF_2, missions.BRIEF_3,
          missions.DEBRIEF_2):
    pages = describe.mission_pages(d, n, "Ripley", 0)
    assert pages and all("[" not in t for t, _ in pages), n
    assert pages[-1][0].endswith("MESSAGE ENDS")
assert describe.mission_pages(d, missions.BRIEF_1, "Ripley", 0)[0][1], "the Phantom shown"
assert "Rotuvaga" in describe.mission_pages(d, missions.BRIEF_1, "Ripley", 0)[0][0]
assert "this galaxy" in describe.mission_pages(d, missions.BRIEF_1, "Ripley", 1)[0][0]
assert "Ripley" in describe.mission_pages(d, missions.BRIEF_2, "Ripley", 2)[0][0]
assert "Constrictor" not in str(d.MISSION_TEXTS) and "Thargoid" not in str(d.MISSION_TEXTS)
print("mission texts: our own, the name and the trail filled in: ok")

# ---- the trail -------------------------------------------------------------------------
for gal, system, always, words in d.SPECIAL:
    n = missions.special_sentence(d, 0, gal, system)
    assert (n is not None) == always, (gal, system)
    n = missions.special_sentence(d, 1, gal, system)
    assert n and describe.special(d, n, "Somewhere") and "%" not in describe.special(d, n, "X")
g1 = galaxy.Galaxy(galaxy.seeds_for(d.SEEDS, 1), d.PAIRS)
assert g1.system(g1.find(*d.MISSION_PLACES["constrictor"][1:])).name == "ELNADA"
print("trail clues: only while the Phantom is hunted, the rest always: ok")

# ---- both missions, played -----------------------------------------------------------------
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
c = e.cmdr
assert e.galaxy.system(c.system).name == "DAENOR" and c.data == "own"


def launch(a):
    a.dock.go(0); tick(a, fresh=["C"])
    for _ in range(200):
        tick(a)
        if a.mode == "flight":
            break
    a.game.encounter_t = a.game.station_t = 1e9


def debug(a, line):
    if not a.paused:
        tick(a, fresh=["A"])
    a.fsub = "dgroup"
    a.dgroup = mod.cheat_group(line)
    a.fmenu = [i for i, t in enumerate(a._fitems()) if t.startswith(line)][0]
    tick(a, fresh=["C"])


def read_all(a):
    assert a.mode == "brief"
    for _ in range(int(2.2 / DT)):
        tick(a)
    words = []
    for _ in range(40):
        words += texts(a)
        if a.mode != "brief":
            break
        tick(a, fresh=["C"])
    assert a.mode == "docked"
    return " ".join(words)


c.kills = 200
e._dock()
w = read_all(e)
assert "Hollis" in w and "Phantom" in w and c.mission == 1
assert '"data": "own"' in open(SAVE).read()
# System data at Tuelve, while hunting: the trail
c.system = e.galaxy.find(*d.MISSION_PLACES["shipyard"][1:]); e._dock()
e.dock.open("SYSTEM DATA")
assert any("Rotuvaga" in t for t in texts(e))
launch(e)
debug(e, "TO MISSION SYSTEM")
assert c.galaxy == 1 and e.galaxy.system(c.system).name == "ELNADA"
debug(e, "ADD THE CONSTRICTOR"); tick(e, fresh=["A"])
o = [o for o in e.game.objs + e.game.new if o.role == "constrictor"][0]
assert o.bp.title == "PHANTOM"
e.game._kill(o); tick(e)
debug(e, "DOCK NOW")
w = read_all(e)
assert "5000 credits" in w and c.mission == 2
c.kills = 700
c.galaxy = 2; e._place(); c.system = e.galaxy.nearest(96, 96)
e._dock()
assert "Argatu" in read_all(e) and c.mission == 6
launch(e); debug(e, "TO MISSION SYSTEM")
assert e.galaxy.system(c.system).name == "ARGATU"
debug(e, "DOCK NOW")
assert "Mercer" in read_all(e) and c.mission == 10
launch(e)
assert e.game.plans
debug(e, "TO MISSION SYSTEM")
assert e.galaxy.system(c.system).name == "VEDAO"
debug(e, "DOCK NOW")
assert "Navy Energy Unit" in read_all(e) and c.mission == 14 and "navy" in c.extras
shutil.rmtree(TMP, ignore_errors=True)
print("both missions, with our own systems, ships and words: ok")
print("ALL ORIGINAL DATA TESTS PASSED")
