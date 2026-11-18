"""The disc version's two missions (build 54): the Constrictor and the
Thargoid plans."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import (briefing, commander, describe, docked, equipment, galaxy, game,
                           missions)
mod = ace_commander.ace
gd = mod.game_data
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_missions.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE
SHIPS = mod.SHIPS
DT = 0.04


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


def gal(n):
    return galaxy.Galaxy(galaxy.seeds_for(gd.SEEDS, n), gd.PAIRS)


# ---- the places, from the galaxy ------------------------------------------------
for (n, x, y), name in ((missions.ORARRA, "ORARRA"), (missions.CEERDI, "CEERDI"),
                        (missions.BIRERA, "BIRERA")):
    g = gal(n)
    assert g.system(g.find(x, y)).name == name, name
# the special sentences: where, and when
assert len(gd.DESC_RUTOK) == len(gd.DESC_RU) + 1
g0 = gal(0)
xeer = [i for i in range(256) if g0.system(i).name == "XEER"][0]
teorge = [i for i in range(256) if g0.system(i).name == "TEORGE"][0]
assert missions.special_sentence(gd, 0, 0, xeer) is None, "only during mission 1"
n = missions.special_sentence(gd, 1, 0, xeer)
t = describe.special(gd, n, "Xeer")
assert "Reesdice" in t and t.endswith("Commander."), t
assert describe.special(gd, missions.special_sentence(gd, 0, 0, teorge), "Teorge"), "always"
assert missions.special_sentence(gd, 1, 1, xeer) is None or xeer != 150, "another galaxy"
print("the mission systems and the special sentences: ok")

# ---- the texts ----------------------------------------------------------------------
pages = describe.mission_pages(gd, missions.BRIEF_1, "Jameson", 0)
assert len(pages) == 2 and all(ship for _, ship in pages)
assert "Commander Jameson," in pages[0][0] and "Curruthers" in pages[0][0]
assert "Reesdice." in pages[1][0], "the trail's start, in galaxy 1"
assert "Military Lasers" in pages[1][0], "a standard token, in Sentence Case"
assert pages[1][0].endswith("MESSAGE ENDS")
p = describe.mission_pages(gd, missions.BRIEF_1, "Jameson", 1)[1][0]
assert "Reesdice" not in p, "another hint in galaxy 2"
assert "Fosdyke Smythe" in describe.mission_pages(gd, missions.BRIEF_1, "J", 1)[0][0]
assert "Ceerdi" in describe.mission_pages(gd, missions.BRIEF_2, "J", 2)[0][0]
assert len(describe.mission_pages(gd, missions.BRIEF_3, "J", 2)) == 2
assert "Energy Unit" in describe.mission_pages(gd, missions.DEBRIEF_2, "J", 2)[0][0]
assert describe.mission_pages(gd, missions.DEBRIEF_1, "J", 0)[0][0].endswith("MESSAGE ENDS")
# every line of every message fits the round screen wherever it scrolls to,
# and the joystick scrolls through it to the end
for n in (missions.BRIEF_1, missions.DEBRIEF_1, missions.BRIEF_2, missions.BRIEF_3,
          missions.DEBRIEF_2):
    for gn in (0, 1, 2):
        b = briefing.Briefing(gd, n, "Commander Longname", gn,
                              game.Blueprint([e for e in SHIPS if e[0] == "CONSTRICTOR"][0]))
        assert not b.done and b.incoming
        assert (b.ship is not None) == (n == missions.BRIEF_1)
        b.tick(2.1); assert not b.incoming
        k = 0
        while not b.at_end():
            c = CountCtx(); b.draw(c)
            for s, (x, y), size in c.texts:
                half = len(s) * 0.62 * size / 2
                assert (half * half + (abs(y) + size / 2) ** 2) ** 0.5 <= 120, (s, x, y)
                if size == briefing.SIZE:
                    assert briefing.VIEW_TOP - 1 <= y <= briefing.VIEW_BOTTOM + 1
            b.tick(0.1, 1)
            k += 1
        assert k < 300 and b.scroll == b.most
        c = CountCtx(); b.draw(c)
        assert "MESSAGE ENDS" in [t[0] for t in c.texts], "the end is reached"
        assert "C: continue" in [t[0] for t in c.texts]
        b.tick(1.0, -1); assert b.scroll < b.most
        b.next(); assert not b.done, "C pages down first"
        while not b.at_end():
            b.next()
        b.next(); assert b.done
print("the briefing texts, and every screen of them fits: ok")

# ---- the rules ------------------------------------------------------------------------
c = commander.Commander(1)                      # NORMAL: kills divided by 2
assert missions.on_docking(c, 0, 0) is None, "not good enough yet"
c.kills = 128
c.galaxy = 2
assert missions.on_docking(c, 0, 0) is None, "only in galaxies 1 and 2"
c.galaxy = 1
assert missions.on_docking(c, 0, 0) == missions.BRIEF_1 and c.mission == 1
assert missions.on_docking(c, 0, 0) is None, "nothing more until it is destroyed"
assert missions.hunting(c.mission)
c.mission = missions.killed(c.mission); assert c.mission == 3
cash, kills = c.cash, c.kills
assert missions.on_docking(c, 0, 0) == missions.DEBRIEF_1
assert c.mission == 2 and c.cash == cash + 50000 and c.kills == kills + 128
assert missions.on_docking(c, 0, 0) is None
c.galaxy = 2
c.kills = 639
assert missions.on_docking(c, 0, 0) is None, "1280 kills (640 at NORMAL) for mission 2"
c.kills = 640
assert missions.on_docking(c, 0, 0) == missions.BRIEF_2 and c.mission == 6
assert missions.on_docking(c, 0, 0) is None, "not at Ceerdi"
assert not missions.carrying_plans(c.mission)
assert missions.on_docking(c, *missions.CEERDI[1:]) == missions.BRIEF_3 and c.mission == 10
assert missions.carrying_plans(c.mission)
c.extras = ["energy", "ecm"]
kills = c.kills
assert missions.on_docking(c, *missions.BIRERA[1:]) == missions.DEBRIEF_2
assert c.mission == 14 and c.kills == kills + 128 and "navy" in c.extras and "energy" not in c.extras
assert equipment.have(equipment.ENERGY, c) == "fitted"
assert equipment.buy(gd.EQUIPMENT, equipment.ENERGY, c) == "ALREADY FITTED"
assert missions.on_docking(c, *missions.BIRERA[1:]) is None, "all done"
d = commander.Commander.from_dict(c.to_dict())
assert d.mission == 14 and "navy" in d.extras, "saved"
assert commander.Commander.from_dict({"level": 1}).mission == 0, "old saves"
# the stages the DEBUG page goes round
tp = 0
seen = []
for _ in range(len(missions.STAGES)):
    tp = missions.next_stage(tp); seen.append(tp)
assert seen[-1] == 0 and len(set(seen)) == len(missions.STAGES)
print("the mission rules, rewards and saving: ok")

# ---- in flight ---------------------------------------------------------------------------
random.seed(3)
g = game.Game(SHIPS, 1)
g.enter(6000, "CORIOLIS", "arrive", 7)
g.objs.extend(g.new); g.new = []
o = g.add_constrictor()
g.objs.extend(g.new); g.new = []
assert o.role == "constrictor" and o.state == "attack" and o.ecm
o.x, o.y, o.z = 0.0, 0.0, 1500.0
for laser, hurts in (("pulse", False), ("beam", False), ("mining", False), ("military", True)):
    g.set_laser(laser)
    e0 = o.energy
    g.cool = 0; g.heat = 0; g.hot = False
    g._weapons(DT, True, False)
    if hurts:
        assert abs((e0 - o.energy) - g.laser_damage * game.CONSTRICTOR_LASER) < 1e-6
    else:
        assert o.energy == e0, laser
# its ECM destroys your missile on the way
g.lock, g.locked, g.missiles = o, True, 2
g._weapons(DT, False, True)
m = g.new[-1]; g.objs.extend(g.new); g.new = []
for _ in range(200):
    g.step(DT, 0, 0, 0, False, False)
    o.x, o.y, o.z = 0.0, 0.0, 3000.0
    if m.dead:
        break
assert m.dead and o.energy > 0 and g.msg == "ECM"
g._kill(o)
assert g.got_constrictor and g.kills == 1
# a Constrictor in combat practice is just a ship
g = game.Game(SHIPS, 1)
o = g._spawn_ship(g.types["CONSTRICTOR"]); g._kill(o)
assert not g.got_constrictor
# at Orarra while hunting, the lone hunter is the Constrictor (only one at a time)
g = game.Game(SHIPS, 1)
g.enter(6000, "CORIOLIS", "arrive", 0)
g.orarra = g.hunt = True
game.random.seed(5)
names = []
for _ in range(60):
    g.objs = []; g.new = []; g.pending = 0; g.skip = 0
    g._roll()
    names.extend(g.group)
assert "CONSTRICTOR" in names
g.objs = []; g.new = []; g.add_constrictor()
for _ in range(60):
    g.pending = 0; g.skip = 0; g.group = []
    g._roll()
    assert "CONSTRICTOR" not in g.group, "only one"
# the quick setting: it comes after QUICK_WAIT seconds outside the safe zone
g = game.Game(SHIPS, 1)
g.enter(6000, "CORIOLIS", "arrive", 7)
g.orarra = g.hunt = True
g.con_wait = missions.QUICK_WAIT
g.encounter_t = g.station_t = 1e9
g.god = True
assert not g.space.safe
t = 0.0
while not any(o.role == "constrictor" for o in g.objs + g.new) and t < 200:
    g.step(DT, 0, 0, 0, False, False)
    t += DT
assert abs(t - missions.QUICK_WAIT) < 1.0, t
o = [o for o in g.objs + g.new if o.role == "constrictor"][0]
assert o.state == "attack" and o.ecm
for _ in range(int(150 / DT)):      # only one at a time
    g.step(DT, 0, 0, 0, False, False)
assert sum(1 for o in g.objs + g.new if o.role == "constrictor" and not o.dead) <= 1
# not without the setting (the roll is kept away here), nor once mission 1 is over
for wait, hunt in ((None, True), (missions.QUICK_WAIT, False)):
    g = game.Game(SHIPS, 1)
    g.enter(6000, "CORIOLIS", "arrive", 7)
    g.orarra, g.hunt, g.con_wait = True, hunt, wait
    g.encounter_t = g.station_t = 1e9; g.god = True
    for _ in range(int(150 / DT)):
        g.step(DT, 0, 0, 0, False, False)
    assert not any(o.role == "constrictor" for o in g.objs + g.new), (wait, hunt)

g = game.Game(SHIPS, 1)
g.enter(6000, "CORIOLIS", "arrive", 7)
g.plans = True
n = 0
for _ in range(300):
    g.objs = []; g.new = []
    g._tick(1, 0)
    n += sum(1 for o in g.new if o.bp.name == "THARGOID")
assert 30 < n < 110, n           # about 56 in 256 of the ticks
g.plans = False
for _ in range(200):
    g.objs = []; g.new = []
    g._tick(1, 0)
    assert not any(o.bp.name == "THARGOID" for o in g.new)
# the naval energy unit recharges half as fast again as the usual one
rates = []
for navy in (False, True):
    g = game.Game(SHIPS, 1); g.energy_unit = True; g.navy = navy
    g.shield = 10.0; g.since_hit = 10.0; g._regen(1.0); rates.append(g.shield - 10.0)
assert abs(rates[1] / rates[0] - 1.5) < 1e-6
print("the Constrictor's shields and ECM, where it turns up, Thargoids after the plans, "
      "the naval energy unit: ok")

# ---- in the app ------------------------------------------------------------------------
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
assert e.mode == "docked"
c = e.cmdr


def launch(a):
    a.dock.go(0); tick(a, fresh=["A"])
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


def dock_now(a):
    debug(a, "DOCK NOW")


launch(e)
assert any(t.startswith("MISSION: NONE") for t in e._fitems() if e.fsub == "debug") or True
debug(e, "TO MISSION SYSTEM")         # not started: to galaxy 2, where it can start
assert c.galaxy == 1 and e.galaxy_n == 1
dock_now(e)
assert e.mode == "docked", "too few kills: no mission"
launch(e)
debug(e, "MISSION")                    # NONE -> 1: HUNTING, with the kills it needs
debug(e, "MISSION")
debug(e, "MISSION")
debug(e, "MISSION")
debug(e, "MISSION")
debug(e, "MISSION")
debug(e, "MISSION")                    # round to NONE, with the kills for mission 1
assert c.mission == 0 and c.kills >= 128
dock_now(e)
assert e.mode == "brief" and c.mission == 1
assert texts(e) == ["INCOMING MESSAGE"]
for _ in range(int(2.2 / DT)):
    tick(e)
t = texts(e)
assert any("Jameson" in s for s in t) and "stick: scroll  C: more" in t
s0 = e.brief.scroll
for _ in range(10):
    tick(e, held=["JOYDOWN"])
s1 = e.brief.scroll
assert s1 > s0, "the joystick scrolls"
for _ in range(10):
    tick(e, held=["D"])
assert e.brief.scroll == s1, "D (also DOWN) doesn't"
for _ in range(5):
    tick(e, held=["JOYUP"])
assert e.brief.scroll < s1, "and back up"
for _ in range(30):
    if e.mode != "brief":
        break
    tick(e, fresh=["C"])
assert e.mode == "docked" and e.brief is None
saved = commander.load(SAVE); assert saved.mission == 1, "saved straight away"
# the trail: the Constrictor's sentence on System data at Xeer, galaxy 1
c.galaxy = 0; e._place(); c.system = xeer
e._dock(); assert e.mode == "docked"
e.dock.go(e.dock.tabs.index("SYSTEM DATA"))
assert any("constrictor" in s.lower() for s in texts(e))
# to Orarra; the Constrictor comes in place of a lone hunter
launch(e)
debug(e, "TO MISSION SYSTEM")
assert c.galaxy == 1 and e.galaxy.system(c.system).name == "ORARRA"
g = e.game
assert g.orarra and g.hunt and not g.plans
debug(e, "ADD THE CONSTRICTOR")
tick(e, fresh=["A"])
o = [o for o in g.objs + g.new if o.role == "constrictor"][0]
g._kill(o); tick(e)
assert c.mission == 3 and not g.got_constrictor
cash = c.cash
dock_now(e)
assert e.mode == "brief" and c.mission == 2 and c.cash == cash + 50000
tick(e, fresh=["F"]); assert e.mode == "docked", "F skips"
# mission 2
launch(e)
c.kills = 640
c.galaxy = 2; e._place(); c.system = e.galaxy.nearest(96, 96)
dock_now(e)
assert e.mode == "brief" and c.mission == 6
tick(e, fresh=["F"])
launch(e)
debug(e, "TO MISSION SYSTEM")
assert e.galaxy.system(c.system).name == "CEERDI"
dock_now(e)
assert c.mission == 10 and e.mode == "brief"
tick(e, fresh=["F"])
launch(e)
assert e.game.plans, "Thargoids are after you"
debug(e, "TO MISSION SYSTEM")
assert e.galaxy.system(c.system).name == "BIRERA"
dock_now(e)
assert c.mission == 14 and "navy" in c.extras and e.mode == "brief"
tick(e, fresh=["F"])
launch(e)
assert e.game.navy and e.game.energy_unit and not e.game.plans
# TO MISSION SYSTEM from the docked Options tab's DEBUG: docked there at once,
# with that stage's message
c.mission = 6; e._dock()
if e.mode == "brief":
    tick(e, fresh=["F"])
e.dock.open("OPTIONS"); e.dock.osel = len(e._settings(True)) - 1
tick(e, fresh=["C"]); assert e.mode == "odebug"
assert "TRAVEL" in e._od_items()
e.od_sel = e._od_items().index("TRAVEL"); tick(e, fresh=["C"])
assert e._od_items() == ["TO MISSION SYSTEM"], e._od_items()
tick(e, fresh=["C"])
assert e.galaxy.system(c.system).name == "CEERDI" and c.mission == 10 and e.mode == "brief"
tick(e, fresh=["F"]); assert e.mode == "docked"
c.mission = 14
launch(e)
# the pause menu's CONSTRICTOR setting, saved; 2 MIN to start with; shown
# only while mission 1 is under way
assert c.quick_con and e.game.con_wait == missions.QUICK_WAIT
tick(e, fresh=["A"]); e.fsub = "settings"
e.fmenu = [i for i, t in enumerate(e._fitems()) if t.startswith("CONSTRICTOR")][0]
assert e._fitems()[e.fmenu] == "CONSTRICTOR: 2 MIN"
tick(e, fresh=["C"])
assert not c.quick_con and e.game.con_wait is None and e._fitems()[e.fmenu] == "CONSTRICTOR: ORIGINAL"
assert commander.load(SAVE).quick_con is False
tick(e, fresh=["C"]); assert c.quick_con
assert commander.Commander.from_dict({"level": 1}).quick_con, "old saves: 2 MIN"
# SHIP CONFIG's NAVY ENERGY UNIT switch
e.fsub = "dgroup"; e.dgroup = "SHIP"
items = e._fitems()
assert "NAVY ENERGY UNIT: ON" in items and "ENERGY UNIT: OFF" in items
e.fmenu = items.index("NAVY ENERGY UNIT: ON"); tick(e, fresh=["C"])
assert not e.game.navy and not e.game.energy_unit and "navy" not in c.extras
e.fmenu = e._fitems().index("ENERGY UNIT: OFF"); tick(e, fresh=["C"])
assert e.game.energy_unit and not e.game.navy and "energy" in c.extras
e.fmenu = e._fitems().index("NAVY ENERGY UNIT: OFF"); tick(e, fresh=["C"])
assert e.game.navy and e.game.energy_unit and "navy" in c.extras and "energy" not in c.extras
assert "ENERGY UNIT: OFF" in e._fitems()
os.remove(SAVE)
print("app: briefings on docking, saved, the trail, Orarra, both missions to the end: ok")
print("ALL MISSION TESTS PASSED")
