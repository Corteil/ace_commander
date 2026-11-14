import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import commander, game
mod = ace_commander.app
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_commander.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


def fpick(a, label):
    """Open the in-flight menu if it isn't, and press C on this line of it."""
    if not a.paused:
        tick(a, fresh=["A"])
    a.fmenu = a._fitems().index(label)
    tick(a, fresh=["C"])


def launch(a):
    assert a.mode == "docked", a.mode
    a.dock.go(0)
    tick(a, fresh=["C"])
    assert a.mode == "launch"
    for _ in range(200):
        tick(a)
        if a.mode != "launch":
            break
    assert a.mode == "flight" and a.career and not a.docked


# ---- ranks and levels -------------------------------------------------------
assert commander.thresholds(2) == (0, 8, 16, 32, 64, 128, 512, 2560, 6400), "hardest is the original"
assert commander.thresholds(0)[-1] == 1280 and commander.thresholds(1)[-1] == 3200
assert commander.thresholds(0)[5] == 26, "Competent on the easiest level"
for level in range(3):
    t = commander.thresholds(level)
    assert t[0] == 0 and all(b > a for a, b in zip(t, t[1:])), t
c = commander.Commander(0)
assert c.rank() == "HARMLESS" and c.next_rank() == ("MOSTLY HARMLESS", 2)
assert c.add_kills(1) is None and c.add_kills(1) == "MOSTLY HARMLESS"
assert c.add_kills(0) is None
c.add_kills(1300)
assert c.rank() == "ELITE" and c.next_rank() is None
c = commander.Commander(2)
assert c.add_kills(7) is None and c.add_kills(1) == "MOSTLY HARMLESS"
assert commander.Commander(9).level == 2 and commander.Commander(-3).level == 0
print("ranks and levels: ok", [commander.thresholds(i)[-1] for i in range(3)])

# ---- save and load ----------------------------------------------------------
c = commander.Commander(2); c.add_kills(40); c.docking = "C"
assert c.save(SAVE)
d = commander.load(SAVE)
assert (d.level, d.kills, d.docking, d.credits, d.rank()) == (2, 40, "C", 100.0, "AVERAGE")
assert not c.save(os.path.join(HERE, "no", "such", "folder", "x.json")), "a failed save doesn't raise"
assert commander.load(os.path.join(HERE, "nothing.json")) is None
for junk in ("", "{", "[1, 2]", '{"level": "x"}', '{"kills": null}'):
    with open(SAVE, "w") as f:
        f.write(junk)
    assert commander.load(SAVE) is None, junk
with open(SAVE, "w") as f:
    f.write('{"level": 1, "kills": 3, "docking": "Z", "future": 1}')
d = commander.load(SAVE)
assert d.kills == 3 and d.docking == "B", "unknown values fall back, unknown keys are ignored"
os.remove(SAVE)
print("save and load: ok")

# ---- the level changes the enemies ------------------------------------------
def fight(level, seed, seconds=240):
    """Sit still and let them shoot: returns (damage taken, most hostile ships at once)."""
    random.seed(seed)
    g = game.Game(mod.SHIPS, level)
    taken = 0.0
    most = 0
    for _ in range(int(seconds / 0.05)):
        before = g.shield + g.hull
        g.step(0.05, 0.0, 0.0, 0.0, False, False)
        taken += max(0.0, before - (g.shield + g.hull))
        most = max(most, sum(1 for o in g.objs if o.kind == "ship" and o.state != "flee"))
        if g.over:
            g.reset()
        g.wave = 9      # late-game numbers, where the cap on ships matters
    return taken, most

res = [[fight(level, seed) for seed in (1, 2, 3)] for level in range(3)]
dmg = [sum(r[0] for r in rs) for rs in res]
most = [max(r[1] for r in rs) for rs in res]
assert dmg[0] < dmg[1] < dmg[2], dmg
assert most[0] <= 3 and most[1] <= 4 and most[2] <= 5 and most[2] > most[0], most
g = game.Game(mod.SHIPS)
assert g.level == 1, "the default is the middle level"
print("level changes enemy damage %s and numbers %s: ok" % ([int(d) for d in dmg], most))

# ---- new commander, kills, rank, save, continue -----------------------------
a = ace_commander.AceCommander()
assert a.cmdr is None and "CONTINUE" not in a.choices()
choose(a, "NEW COMMANDER")
assert a.mode == "level" and a.level == 1
tx = texts(a)
assert "< NORMAL >" in tx and "top rank at 3200 kills" in tx
assert not any("replaces" in t for t in tx)
tick(a, fresh=["JOYLEFT"]); assert a.level == 0 and "< EASY >" in texts(a)
tick(a, fresh=["JOYLEFT"]); assert a.level == 2 and "top rank at 6400 kills" in texts(a)
tick(a, fresh=["JOYRIGHT"]); assert a.level == 0
tick(a, fresh=["F"]); assert a.mode == "menu" and a.cmdr is None, "F backs out without making one"
choose(a, "NEW COMMANDER")
tick(a, fresh=["JOYLEFT"]); tick(a, fresh=["C"])
assert a.mode == "docked" and a.docked, "a new commander starts docked"
tx = texts(a)
assert "DOCKED" in tx and "LAVE" in tx and "HARMLESS" in tx and "C: LAUNCH" in tx, tx
assert "Dictatorship" in tx and "Rich Agricultural, tech 5" in tx and "fuel 7.0 LY   100.0 Cr" in tx, tx
tick(a, fresh=["F"]); assert a.mode == "menu"
choose(a, "CONTINUE"); assert a.mode == "docked", "F and back again is still docked"
tick(a, fresh=["A"]); assert a.mode == "launch", "A launches too"
texts(a)
tick(a, fresh=["C"]); assert a.mode == "flight", "C skips the tunnel"
assert a.mode == "flight" and a.career and a.cmdr.level == 0 and a.game.level == 0
assert commander.load(SAVE).level == 0, "saved as soon as it is made"
g = a.game
g.spawn_t = g.rock_t = 1e9
g.objs[:] = []

def kill(g, n=1):
    for _ in range(n):
        o = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0)
        g.objs.append(o)
        g._kill(o)

kill(g); tick(a)
assert a.cmdr.kills == 1 and not g.msg.startswith("RANK"), (a.cmdr.kills, g.msg)
kill(g); tick(a)
assert a.cmdr.kills == 2 and g.msg == "RANK: MOSTLY HARMLESS", (a.cmdr.kills, g.msg)
kill(g, 4); tick(a)
assert a.cmdr.kills == 6 and a.cmdr.rank() == "AVERAGE"
assert commander.load(SAVE).kills == 0, "not written every kill"
tick(a, fresh=["A"])
tx = texts(a)
assert "STATUS" in tx
assert a._fitems() == ["RESUME", "LOCAL CHART", "STATUS", "PAUSE MENU", "DEBUG"], a._fitems()
assert texts(a)
fpick(a, "STATUS"); assert a.fsub == "status"
tx = texts(a)
assert "AVERAGE" in tx and any("6 kills" in t and "EASY" in t for t in tx), tx
assert any("more for ABOVE AVERAGE" in t for t in tx)
assert any(t.startswith("LAVE") and "fuel 7.0 LY" in t for t in tx), tx
tick(a, fresh=["C"]); assert a.fsub is None and a.paused
fpick(a, "PAUSE MENU"); assert a.fsub == "pause"
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a.mode == "menu" and commander.load(SAVE).kills == 6, "quitting to the title saves"
assert a.choices()[0] == "CONTINUE" and a.menu == 0
assert texts(a) == ["< CONTINUE >"]

# practice doesn't touch the commander, and each kind of game starts fresh
choose(a, "COMBAT PRACTICE")
assert not a.career and a.game.level == 1 and a.game.kills == 0
kill(a.game, 3); tick(a)
assert a.cmdr.kills == 6
tick(a, fresh=["A"]); assert "STATUS" not in texts(a)
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a.mode == "menu" and commander.load(SAVE).kills == 6
choose(a, "CONTINUE")
assert a.mode == "docked" and a.cmdr.kills == 6, "practice kills aren't banked by docking"
launch(a)
assert a.career and a.game.level == 0 and a.game.kills == 0

# dying saves; flying again keeps the commander
g = a.game; g.spawn_t = g.rock_t = 1e9; g.objs[:] = []
kill(g, 2); tick(a)
g._hurt(1000.0); tick(a)
assert g.over and commander.load(SAVE).kills == 8, "saved at game over"
assert "C: back to the station" in texts(a)
tick(a, fresh=["C"]); assert a.mode == "docked" and a.cmdr.kills == 8
launch(a); assert not g.over and g.kills == 0
kill(g); tick(a); assert a.cmdr.kills == 9

# a flight left part-way for the title screen carries on
fpick(a, "PAUSE MENU"); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); assert a.mode == "menu"
choose(a, "CONTINUE"); assert a.mode == "flight" and g.kills == 1 and not a.docked

# a new app instance (the badge restarted) finds the commander
fpick(a, "PAUSE MENU")
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); assert a.mode == "menu"
b = ace_commander.AceCommander()
assert b.cmdr.kills == 9 and b.cmdr.level == 0 and b.choices()[0] == "CONTINUE"
choose(b, "NEW COMMANDER")
assert any("replaces your saved commander" in t for t in texts(b))
tick(b, fresh=["JOYRIGHT"]); tick(b, fresh=["C"])
launch(b)
assert b.cmdr.kills == 0 and b.cmdr.level == 2 and b.game.level == 2
assert commander.load(SAVE).level == 2

# a save that can't be written doesn't stop the game
mod.SAVE_PATH = os.path.join(HERE, "no", "such", "folder", "x.json")
c = ace_commander.AceCommander()
assert c.cmdr is None
choose(c, "NEW COMMANDER"); tick(c, fresh=["C"]); launch(c)
assert c.mode == "flight" and c.career
kill(c.game); tick(c); c.game._hurt(1000.0); tick(c)
assert c.cmdr.kills == 1
os.remove(SAVE)
print("new commander, rank, status, save, continue, practice kept apart: ok")

# ---- the DEBUG page of cheats -----------------------------------------------
mod.SAVE_PATH = SAVE
d = ace_commander.AceCommander()
choose(d, "NEW COMMANDER"); tick(d, fresh=["JOYLEFT"]); tick(d, fresh=["C"])    # EASY
launch(d)
g = d.game; g.spawn_t = g.rock_t = 1e9; g.objs[:] = []

def debug(a, line):
    """Open the in-flight menu, go to DEBUG and press C on this line of it."""
    if not a.paused:
        tick(a, fresh=["A"])
    if a.fsub != "debug":
        a.fsub = None
        a.fmenu = a._fitems_top().index("DEBUG")
        tick(a, fresh=["C"])
    assert a.fsub == "debug"
    a.fmenu = [i for i, s in enumerate(a._fitems()) if s.startswith(line)][0]
    tick(a, fresh=["C"])

tick(d, fresh=["A"])
assert texts(d)[-1] != "" and "DEBUG" in texts(d)
debug(d, "INVINCIBLE")
tx = texts(d)
assert "INVINCIBLE: ON" in tx and "+10 KILLS" in tx and g.god
tick(d, fresh=["A"]); assert not d.paused
g._hurt(5000.0); tick(d)
assert not g.over and g.hull == 100.0 and g.flash > 0, "hits flash but do no damage"
debug(d, "+10 KILLS")
assert d.cmdr.kills == 10 and d.cmdr.rank() == "AVERAGE", "cheated kills raise the rank"
debug(d, "ADD AN ENEMY"); debug(d, "ADD AN ENEMY")
tick(d, fresh=["A"]); tick(d)
assert sum(1 for o in g.objs if o.kind == "ship") == 2
debug(d, "KILL ALL ENEMIES")
tick(d, fresh=["A"]); tick(d)
assert not any(o.kind == "ship" for o in g.objs) and d.cmdr.kills == 12
g.missiles = 0; w = g.wave
debug(d, "REFILL MISSILES"); debug(d, "NEXT WAVE")
assert g.missiles == 4 and g.wave == w + 1
debug(d, "INVINCIBLE"); assert not g.god
tick(d, fresh=["F"]); assert d.fsub is None and d._fitems()[d.fmenu] == "DEBUG", "F goes back"
tick(d, fresh=["A"])
g._hurt(5000.0); tick(d); assert g.over, "and with it off you can die again"
mod.DEBUG_MENU = False
assert "DEBUG" not in d._fitems_top()
mod.DEBUG_MENU = True
os.remove(SAVE)
print("debug cheats: ok")

# ---- the local chart, hyperspace and fuel -----------------------------------
c1 = commander.Commander(1)
assert c1.system is None and c1.fuel == 70
old = commander.Commander.from_dict({"version": 1, "level": 2, "kills": 5})
assert old.system is None and old.fuel == 70, "a phase 1 save still loads"
bad = commander.Commander.from_dict({"system": 999, "fuel": 500})
assert bad.system is None and bad.fuel == 70

e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"]); launch(e)
g = e.game; g.spawn_t = g.rock_t = 1e9; g.objs[:] = []
gal = e.galaxy
assert e.cmdr.system == 7 and gal.system(7).name == "LAVE" and e.cmdr.fuel == 70
fpick(e, "LOCAL CHART")
assert e.fsub == "chart" and e.chart.here == 7
tx = texts(e)
assert "LAVE" in tx and "YOU ARE HERE" in tx and "FUEL 7.0 LY" in tx, tx
tick(e, fresh=["C"]); assert e.fsub == "chart" and g.jump_t == 0, "can't jump to where you are"
reach = dict((i, dist) for dist, i in gal.in_range(7, 70))
assert all((0 < d <= 70) == (i in reach) for _, _, i, d in e.chart.dots if i != 7)
# every system in range is on the chart and inside the ring
for px, py, i, d in e.chart.dots:
    if i in reach:
        assert (px * px + py * py) ** 0.5 <= 70 * 1.25 + 3, (i, px, py)
assert set(reach) <= set(dot[2] for dot in e.chart.dots)
# steer the cursor to Zaonce (129) with the joystick and jump there
zx, zy = [(px, py) for px, py, i, d in e.chart.dots if i == 129][0]
for _ in range(400):
    ch = e.chart
    if ch.sel[2] == 129:
        break
    held = []
    if abs(ch.cx - zx) > 2:
        held.append("JOYRIGHT" if zx > ch.cx else "JOYLEFT")
    if abs(ch.cy - zy) > 2:
        held.append("JOYDOWN" if zy > ch.cy else "JOYUP")
    tick(e, held=held)
assert e.chart.sel[2] == 129, e.chart.sel
tx = texts(e)
d129 = reach[129]
assert "ZAONCE" in tx and ("%d.%d LY   C: JUMP" % (d129 // 10, d129 % 10)) in tx, tx
tick(e, fresh=["C"])
assert not e.paused and e.fsub is None and g.jump_t > 0 and g.msg == "HYPERSPACE 5"
kill(g, 2)
o = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0); g.objs.append(o)
seen = set()
for _ in range(200):
    tick(e)
    seen.add(g.msg)
    if e.cmdr.system == 129:
        break
assert e.cmdr.system == 129 and e.cmdr.fuel == 70 - d129, (e.cmdr.system, e.cmdr.fuel)
assert set("HYPERSPACE %d" % n for n in (5, 4, 3, 2, 1)) <= seen, seen
assert g.msg == "ZAONCE: 4 SHIPS TO CLEAR" and g.arriving == 4, g.msg
assert g.warp > 0 and not g.objs and not g.jumped and g.kills == 2
saved = commander.load(SAVE)
assert (saved.system, saved.fuel, saved.kills) == (129, 70 - d129, 2), "arriving saves"
texts(e)        # the streaks draw
for _ in range(60):
    tick(e)
assert g.warp <= 0
# the chart is now centred on Zaonce, and less fuel reaches fewer systems
fpick(e, "LOCAL CHART")
assert e.chart.here == 129 and "ZAONCE" in texts(e)
far = [dot for dot in e.chart.dots if dot[3] > e.cmdr.fuel]
assert far, "something is out of range now"
e.chart.cx, e.chart.cy = float(far[0][0]), float(far[0][1]); e.chart._select()
if e.chart.sel[3] > e.cmdr.fuel:
    assert any("TOO FAR" in t for t in texts(e))
    tick(e, fresh=["C"]); assert e.fsub == "chart" and g.jump_t == 0, "no jump without the fuel"
tick(e, fresh=["F"])
assert e.fsub is None and e._fitems()[e.fmenu] == "LOCAL CHART" and e.chart is None
tick(e, fresh=["A"])
e.cmdr.fuel = 3
debug(e, "REFILL FUEL"); assert e.cmdr.fuel == 70
tick(e, fresh=["A"])
# dying stops a countdown; quitting to the title and coming back keeps the system
fpick(e, "LOCAL CHART")
e.chart.cx, e.chart.cy = [(float(px), float(py)) for px, py, i, d in e.chart.dots if i == 7][0]
e.chart._select(); tick(e, fresh=["C"]); assert g.jump_t > 0
g._hurt(5000.0); tick(e); tick(e)
assert g.over and g.jump_t == 0 and e.cmdr.system == 129
assert g.again == "C: back to the station"
tick(e, fresh=["C"]); assert e.mode == "docked" and e.cmdr.fuel == 70, "docking fills the tank"
assert "ZAONCE" in texts(e)

# arriving: clear the ships that meet you and you are docked
launch(e)
g.spawn_t = g.rock_t = 1e9
assert g.arriving is None and g.kills == 0
fpick(e, "LOCAL CHART")
e.chart.cx, e.chart.cy = [(float(px), float(py)) for px, py, i, d in e.chart.dots if i == 7][0]
e.chart._select(); tick(e, fresh=["C"])
for _ in range(200):
    tick(e)
    if e.cmdr.system == 7:
        break
assert e.cmdr.system == 7 and g.arriving == 4 and e.cmdr.fuel == 70 - d129
g.spawn_t = 1e9
kill(g, 3); tick(e)
assert g.arriving == 1 and g.dock_t == 0 and e.mode == "flight"
o = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0); g.objs.append(o)
o2 = game.Obj(g.types["SIDEWINDER"], "ship", 500.0, 0.0, 3000.0); g.objs.append(o2)
g._kill(o); tick(e); tick(e)
assert g.arriving == 0 and g.dock_t == 0, "not while a ship is still about"
g._kill(o2); tick(e); tick(e)
assert g.msg == "ALL CLEAR: DOCKING" and g.dock_t > 0 and e.mode == "flight"
g.spawn_t = 0.0
for _ in range(200):
    tick(e)
    if e.mode == "docked":
        break
assert e.mode == "docked" and e.docked and not any(x.kind == "ship" for x in g.objs), "no more come"
assert e.cmdr.fuel == 70 and e.cmdr.kills == 2 + 5
saved = commander.load(SAVE)
assert (saved.system, saved.fuel, saved.kills) == (7, 70, 7), "docking saves"
tx = texts(e)
assert "LAVE" in tx and "DOCKED" in tx
launch(e)
assert e.game.arriving is None and e.game.kills == 0 and not e.game.docked
debug(e, "DOCK NOW"); assert e.mode == "docked" and not e.paused
print("arriving, clearing the ships, docking, refuelling: ok")

# ---- the docked tabs, targets, and the jump line in the in-flight menu ----
d = e.dock
assert d.tabs == ("STATUS", "LOCAL CHART", "GALACTIC CHART", "SYSTEM DATA") and d.tab == 0
assert any("< > screens" in t for t in texts(e))
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "LOCAL CHART" and d.view.verb == "TARGET"
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "LOCAL CHART", "the joystick moves the cursor here"
tick(e, fresh=["B"]); assert d.name() == "GALACTIC CHART" and len(d.view.dots) == 256
tx = texts(e)
assert "GALAXY 1" in tx and "LAVE" in tx and "YOU ARE HERE" in tx, tx
tick(e, fresh=["B"]); assert d.name() == "SYSTEM DATA" and d.data.name == "LAVE"
tx = texts(e)
assert "you are here" in tx and "Dictatorship" in tx and "Population 2.5 billion" in tx, tx
assert "Productivity 7000 M Cr" in tx and "Radius 4116 km" in tx and "Tech level 5" in tx
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "STATUS", "tabs wrap round"
tick(e, fresh=["E"]); assert d.name() == "SYSTEM DATA"
tick(e, fresh=["F"]); assert d.name() == "STATUS" and e.mode == "docked", "F goes back to Status"
# pick Diso (147) on the galactic chart by steering to it
d.go(2)
tx_, ty_ = [(dot[0], dot[1]) for dot in d.view.dots if dot[2] == 147][0]
for _ in range(400):
    v = d.view
    if v.sel[2] == 147:
        break
    held = []
    if abs(v.cx - tx_) > 1:
        held.append("JOYRIGHT" if tx_ > v.cx else "JOYLEFT")
    if abs(v.cy - ty_) > 1:
        held.append("JOYDOWN" if ty_ > v.cy else "JOYUP")
    tick(e, held=held)
assert d.view.sel[2] == 147, d.view.sel
assert "DISO" in texts(e)
tick(e, fresh=["C"])
assert e.target == 147 and d.name() == "SYSTEM DATA" and d.data.name == "DISO"
dd = gal.distance(7, 147)
tx = texts(e)
assert "Democracy" in tx and ("%d.%d LY away" % (dd // 10, dd % 10)) in tx, tx
d.go(0); assert any(t.startswith("target: DISO") for t in texts(e))
d.go(1); assert d.view.sel[2] == 147, "the chart opens on the target"
# a far system can be looked up, but not jumped to
d.go(2)
far = max(d.view.dots, key=lambda dot: dot[3])
d.view.cx, d.view.cy = float(far[0]), float(far[1]); d.view._select()
assert any("TOO FAR  C: DATA" in t for t in texts(e))
tick(e, fresh=["C"]); assert e.target == far[2] and d.name() == "SYSTEM DATA"
assert any("too far" in t for t in texts(e))
launch(e)
assert not any(s.startswith("JUMP") for s in e._fitems_top()), "no jump line out of range"
fpick(e, "PAUSE MENU"); tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["C"])
choose(e, "CONTINUE"); assert e.mode == "flight"   # back in the same flight
e.target = 147
assert e._fitems_top()[1] == "JUMP: DISO", e._fitems_top()
assert texts(e) is not None
g = e.game; g.spawn_t = g.rock_t = 1e9; g.objs[:] = []
fpick(e, "JUMP: DISO")
assert not e.paused and g.jump_t > 0 and e.jump_to == (147, dd)
assert not any(s.startswith("JUMP") for s in e._fitems_top()), "not twice"
for _ in range(200):
    tick(e)
    if e.cmdr.system == 147:
        break
assert e.cmdr.system == 147 and e.target is None and e.cmdr.fuel == 70 - dd
debug(e, "DOCK NOW")
assert e.mode == "docked" and e.dock.here.name == "DISO" and e.dock.target is None
assert e.dock.view is None and e.cmdr.fuel == 70
print("docked tabs, charts, system data, targets, jump line, launch tunnel: ok")

f = ace_commander.AceCommander()
choose(f, "CONTINUE")
assert f.mode == "docked"
assert f.cmdr.system == 147 and f.galaxy is not None
# practice has no chart, and neither does a commander without game_data.py
choose_p = ace_commander.AceCommander()
choose(choose_p, "COMBAT PRACTICE")
assert "LOCAL CHART" not in choose_p._fitems_top()
gd = mod.game_data; mod.game_data = None
n = ace_commander.AceCommander()
choose(n, "CONTINUE")
assert n.mode == "docked" and n.galaxy is None and n.dock.tabs == ("STATUS",)
assert "COMMANDER" in texts(n) and "LAVE" not in texts(n) and "F: title screen" in texts(n)
tick(n, fresh=["JOYRIGHT"]); tick(n, fresh=["B"]); assert n.dock.tab == 0
launch(n)
assert "LOCAL CHART" not in n._fitems_top()
fpick(n, "STATUS"); texts(n)
mod.game_data = gd
os.remove(SAVE)
print("local chart, hyperspace countdown, fuel, arriving saves: ok")
print("ALL COMMANDER TESTS PASSED")
