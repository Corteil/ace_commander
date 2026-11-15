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
from ace_commander import market as market_mod
from ace_commander import equipment as equipment_mod
mod = ace_commander.ace
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
assert a._fitems() == ["RESUME", "LOCAL CHART", "STATUS", "SETTINGS", "QUIT TO TITLE", "DEBUG"], a._fitems()
assert texts(a)
fpick(a, "STATUS"); assert a.fsub == "status"
tx = texts(a)
assert "AVERAGE" in tx and any("6 kills" in t and "EASY" in t for t in tx), tx
assert any("more for ABOVE AVERAGE" in t for t in tx)
assert any(t.startswith("LAVE") and "fuel 7.0 LY" in t for t in tx), tx
tick(a, fresh=["C"]); assert a.fsub is None and a.paused
fpick(a, "SETTINGS"); assert a.fsub == "settings"
assert a._fitems()[1] == "DOCKING: ASSISTED" and a.game.docking == "B", a._fitems()
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a._fitems()[1] == "DOCKING: AUTOMATIC" and a.game.docking == "C"
assert commander.load(SAVE).docking == "C", "the choice is saved straight away"
tick(a, fresh=["JOYRIGHT"]); assert a.cmdr.docking == "A" and a.game.docking == "A"
tick(a, fresh=["JOYLEFT"]); tick(a, fresh=["JOYLEFT"]); assert a.cmdr.docking == "B"
assert "QUIT TO TITLE" not in a._fitems(), "settings only"
tick(a, fresh=["F"]); fpick(a, "QUIT TO TITLE")
assert a.mode == "menu" and commander.load(SAVE).kills == 0, "quitting to the title mid-flight saves nothing"
assert a.cmdr.kills == 6, "but the flight carries on with CONTINUE"
assert a.choices()[0] == "CONTINUE" and a.menu == 0
assert texts(a) == ["< CONTINUE >"]

# practice doesn't touch the commander, and each kind of game starts fresh
choose(a, "COMBAT PRACTICE")
assert not a.career and a.game.level == 1 and a.game.kills == 0
practice_cash = a.cmdr.cash
kill(a.game, 3); tick(a)
assert a.cmdr.kills == 6 and a.cmdr.cash == practice_cash, "no kills or bounties for the commander"
assert a.game.bounty == 3 * a.game.types["SIDEWINDER"].bounty and not a.game.msg.endswith(" Cr")
tick(a, fresh=["A"]); assert "STATUS" not in texts(a)
fpick(a, "QUIT TO TITLE")
assert a.mode == "menu" and commander.load(SAVE).kills == 0
choose(a, "CONTINUE")
assert a.mode == "docked" and a.cmdr.kills == 6, "practice kills aren't banked by docking"
launch(a)
assert a.career and a.game.level == 0 and a.game.kills == 0

# the commander's missiles go into the flight, and the ones fired are gone
g = a.game
assert g.missiles == a.cmdr.missiles == 3, (g.missiles, a.cmdr.missiles)
g.missiles -= 1; tick(a)
assert a.cmdr.missiles == 2
g.missiles = 3; tick(a)
# a commander's flight has no waves: no message, no wave and score on the HUD,
# no NEXT WAVE cheat
g = a.game
assert not (g.msg.startswith("WAVE") and g.msg_t > 0)
c_ = CountCtx(); a.draw(c_)
assert not any(t[0].startswith("WAVE") for t in c_.texts)
from ace_commander import cockpit as cockpit_mod
digits = []
real_number = cockpit_mod.number
cockpit_mod.number = lambda ctx, v, *r, **k: (digits.append(v), real_number(ctx, v, *r, **k))[1]
show = a.show_ms; a.show_ms = False   # its own digits
a.draw(CountCtx())
cockpit_mod.number = real_number; a.show_ms = show
assert digits == [], "no wave or score on a commander's HUD"
tick(a, fresh=["A"]); a.fsub = "debug"; assert "NEXT WAVE" not in a._fitems(); a.fsub = None
tick(a, fresh=["A"])
# scooped canisters go into the commander's hold, with fuel scoops fitted
g = a.game; g.spawn_t = g.rock_t = 1e9; g.objs[:] = []
assert g.scoop is not None and sum(a.cmdr.cargo) == 0
def scoop_one(a, y=-20.0):
    g = a.game
    g.speed = 10.0
    g.objs.append(game.Obj(g.types["CANISTER"], "can", 0.0, y, 200.0))
    for _ in range(60):
        tick(a)
        if not any(o.kind == "can" for o in g.objs):
            return
assert not g.fuel_scoops, "a new commander has no fuel scoops"
shield = g.shield
scoop_one(a)
assert sum(a.cmdr.cargo) == 0 and g.shield < shield, "without fuel scoops a canister is hit"
g.shield = 100.0
g.fuel_scoops = True; a.cmdr.extras.append("scoops")
scoop_one(a, 20.0)
assert sum(a.cmdr.cargo) == 0 and g.shield < 100.0, "and with them, it has to pass below you"
g.shield = 100.0
scoop_one(a)
assert sum(a.cmdr.cargo) == 1 and sum(a.cmdr.cargo[:game.SCOOP_GOODS]) == 1
i = a.cmdr.cargo.index(1)
assert g.msg == mod.GOODS[i][0], (g.msg, i)
fpick(a, "STATUS"); assert any("hold 1/20t" in t for t in texts(a)); tick(a, fresh=["C"]); tick(a, fresh=["A"])
a.cmdr.cargo[12] = 19                   # 19 t of minerals: room for one more
scoop_one(a); assert market_mod.hold_used(a.cmdr.cargo) == 20
scoop_one(a); assert market_mod.hold_used(a.cmdr.cargo) == 20 and g.msg == "HOLD FULL"
# dying goes back to the last save, as in the original: the kills, bounties,
# cargo and missiles since docking are lost
g.objs[:] = []
before = commander.load(SAVE).to_dict()
assert before["kills"] == 6 and sum(a.cmdr.cargo) > 0
kill(g, 2); tick(a)
assert a.cmdr.kills == 8 and a.cmdr.cash > before["credits"] * 10
g.missiles = 0
g._hurt(1000.0); tick(a)
assert g.over and a.cmdr.to_dict() == before, "back to the last save"
assert commander.load(SAVE).to_dict() == before, "and nothing new is written"
assert "C: back to last save" in texts(a)
for _ in range(5):
    tick(a)
assert a.cmdr.kills == 6 and a.cmdr.missiles == before["missiles"], "nothing banked after dying"
tick(a, fresh=["C"]); assert a.mode == "docked" and a.cmdr.kills == 6
assert a.cmdr.to_dict() == before and commander.load(SAVE).to_dict() == before
launch(a); assert not g.over and g.kills == 0
kill(g); tick(a); assert a.cmdr.kills == 7
# bounties are paid into the commander's cash as you go, and the cash is shown
cash = a.cmdr.cash
kills_before = a.cmdr.kills
side = g.types["SIDEWINDER"].bounty
rock = g.types["ASTEROID"].bounty
assert side > 0 and rock > 0
kill(g); tick(a)                        # a Sidewinder
assert a.cmdr.cash == cash + side and g.msg == a.cmdr.cash_text(), (a.cmdr.cash, g.msg)
g._kill(game.Obj(g.types["ASTEROID"], "rock", 0.0, 0.0, 3000.0)); tick(a)
assert a.cmdr.cash == cash + side + rock, "rocks have small bounties too"
tick(a); assert a.cmdr.cash == cash + side + rock, "paid once"
fpick(a, "STATUS"); assert any(t.endswith(a.cmdr.cash_text()) and t.startswith("hold") for t in texts(a))
tick(a, fresh=["C"]); tick(a, fresh=["A"])
need = a.cmdr.next_rank()[1]
kill(g, need); tick(a)
assert g.msg.startswith("RANK: ") and a.cmdr.cash == cash + rock + side * (1 + need), "a new rank shows instead"
assert commander.load(SAVE).cash < a.cmdr.cash
fpick(a, "QUIT TO TITLE")
assert a.mode == "menu" and commander.load(SAVE).cash < a.cmdr.cash, "quitting mid-flight saves nothing"
choose(a, "CONTINUE"); assert a.mode == "flight"
flight_kills = g.kills
total_kills = a.cmdr.kills
assert total_kills == kills_before + 1 + need

# a flight left part-way for the title screen carries on
fpick(a, "QUIT TO TITLE"); assert a.mode == "menu"
choose(a, "CONTINUE"); assert a.mode == "flight" and g.kills == flight_kills and not a.docked

# a new app instance (the badge restarted) finds the commander as last saved,
# docked: the flight since is lost, as in the original
fpick(a, "QUIT TO TITLE"); assert a.mode == "menu"
b = ace_commander.AceCommander()
assert b.cmdr.kills == commander.load(SAVE).kills == 6 < total_kills
assert b.cmdr.level == 0 and b.choices()[0] == "CONTINUE"
choose(b, "NEW COMMANDER")
assert any("replaces your saved commander" in t for t in texts(b))
tick(b, fresh=["JOYRIGHT"]); tick(b, fresh=["C"])
launch(b)
assert b.cmdr.kills == 0 and b.cmdr.level == 2 and b.game.level == 2
assert commander.load(SAVE).level == 2

# a new commander gets nothing from a flight the last one left part-way
n = ace_commander.AceCommander()
choose(n, "CONTINUE"); launch(n)
kill(n.game, 2); tick(n); assert n.cmdr.kills == 2
n.game.missiles = 1; n.game.bounty += 5000; tick(n)
fpick(n, "QUIT TO TITLE"); assert n.mode == "menu"
choose(n, "NEW COMMANDER"); tick(n, fresh=["C"])
assert n.mode == "docked" and n.cmdr.kills == 0 and n.cmdr.cash == 1000
assert n.cmdr.missiles == commander.START_MISSILES, (n.cmdr.kills, n.cmdr.cash, n.cmdr.missiles)

# a save that can't be written doesn't stop the game
mod.SAVE_PATH = os.path.join(HERE, "no", "such", "folder", "x.json")
c = ace_commander.AceCommander()
assert c.cmdr is None
choose(c, "NEW COMMANDER"); tick(c, fresh=["C"]); launch(c)
assert c.mode == "flight" and c.career
kill(c.game); tick(c); assert c.cmdr.kills == 1
c.game._hurt(1000.0); tick(c)
assert c.cmdr.kills == 0, "back to the last save, kept in memory though it couldn't be written"
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
debug(d, "INVINCIBLE"); debug(d, "INVINCIBLE")
import json as _json
_ver = _json.load(open(os.path.join(os.path.dirname(mod.__file__), "metadata.json")))["version"]
assert "DEBUG - BUILD %s" % _ver in texts(d), "the DEBUG page shows the build"
debug(d, "INVINCIBLE")
tx = texts(d)
items = d._fitems()
assert "INVINCIBLE: ON" in tx and g.god
# seven lines at a time, the chosen one in the middle, going round the end of the list
assert d.fmenu == 0 and len(items) > mod.DEBUG_ROWS
shown = [t for t in tx if t in items]
assert shown == [items[i % len(items)] for i in range(-3, 4)], shown
assert "DOCK NOW" in shown and items[3] in shown and items[4] not in shown
tick(d, fresh=["JOYUP"]); assert d.fmenu == len(items) - 1, "up from the top goes round"
tick(d, fresh=["JOYDOWN"]); assert d.fmenu == 0
# the frame time counter can be switched off and on
assert d.show_ms
debug(d, "FRAME TIME"); assert not d.show_ms and "FRAME TIME: OFF" in texts(d)
debug(d, "FRAME TIME"); assert d.show_ms
d.fmenu = 0
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
g.missiles = 0
debug(d, "REFILL MISSILES")
assert g.missiles == 4 and "NEXT WAVE" not in d._fitems(), "no waves in a commander's flight"
# FUEL TO 1/4 empties the tank to a quarter (1.7 LY), for trying sun skimming
debug(d, "FUEL TO 1/4"); assert d.cmdr.fuel == 17 and g.msg == "FUEL 1.7 LY"
# +1000 CR adds to the commander's cash
cash = d.cmdr.cash
debug(d, "+1000 CR"); assert d.cmdr.cash == cash + 10000 and d.paused
# SHIP CONFIG: change the ship's equipment, in this flight and for the commander
debug(d, "SHIP CONFIG"); assert d.fsub == "ship" and d.fmenu == 0
tx = texts(d)
assert "SHIP CONFIG" in tx and "LASER: PULSE" in tx and "MISSILES: 4" in tx, tx
def ship(label):
    d.fmenu = [i for i, t in enumerate(d._fitems()) if t.startswith(label)][0]
    tick(d, fresh=["C"])
ship("LASER"); assert g.laser == d.cmdr.laser == "beam" and g.laser_period < 0.1
ship("LASER"); ship("LASER"); ship("LASER"); assert g.laser == d.cmdr.laser == "pulse", "round again"
ship("MISSILES"); assert g.missiles == d.cmdr.missiles == 0, "4 goes round to 0"
ship("MISSILES"); assert g.missiles == d.cmdr.missiles == 1
ship("ENERGY UNIT"); assert g.energy_unit and "energy" in d.cmdr.extras
ship("ENERGY UNIT"); assert not g.energy_unit and "energy" not in d.cmdr.extras
ship("CARGO BAY"); assert d.cmdr.hold == 35 and "CARGO BAY: 35T" in d._fitems()
ship("CARGO BAY"); assert d.cmdr.hold == 20
ship("FUEL SCOOPS"); assert g.fuel_scoops and "scoops" in d.cmdr.extras
ship("FUEL SCOOPS"); assert not g.fuel_scoops and "scoops" not in d.cmdr.extras
tick(d, fresh=["F"]); assert d.fsub == "debug" and d._fitems()[d.fmenu] == "SHIP CONFIG", "F goes back"
# TO THE SUN: at the edge of the heat, heading in; flying on, the cabin heats
# up to the scooping band and out again, and with fuel scoops the tank fills;
# the cabin temperature, altitude and fuel gauges show
d.cmdr.fuel = 20; g.fuel_scoops = True; d.cmdr.extras.append("scoops")
g.speed = 40.0
debug(d, "TO THE SUN"); tick(d, fresh=["A"])
temps = []
for _ in range(int(40 / 0.04)):
    tick(d, held=["F"])
    temps.append(g.cabin)
    if g.cabin >= game.SCOOP_TEMP and d.cmdr.fuel > 25:
        break
assert temps[0] > game.COOL_CABIN and temps[0] < game.SCOOP_TEMP, temps[0]
assert g.cabin >= game.SCOOP_TEMP and d.cmdr.fuel > 25, (g.cabin, d.cmdr.fuel)
assert all(b >= a for a, b in zip(temps, temps[1:])), "heating up all the way in"
print("TO THE SUN: %.0f s to the scooping band" % (len(temps) * 0.04))
tx = texts(d)
assert "CT" in tx and "AL" in tx and "FU" in tx and g.fuel == d.cmdr.fuel
fuel = d.cmdr.fuel
d.cmdr.fuel = 69
for _ in range(int(2.5 / 0.04)):
    tick(d, held=["F"])
assert d.cmdr.fuel == 70, "up to a full tank"
g.fuel_scoops = False; d.cmdr.extras.remove("scoops")
debug(d, "TO THE STATION"); tick(d, fresh=["A"]); tick(d)
tx = texts(d)
assert g.cabin == game.COOL_CABIN and "CT" not in tx and "FU" not in tx, "the gauges go away from the sun"
tick(d, fresh=["A"])
debug(d, "REFILL MISSILES")
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
assert "LAVE" in tx and "YOU ARE HERE" in tx and "FUEL 7.0 LY   D: DATA" in tx, tx
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
assert g.msg == "ZAONCE" and g.max_hostile == 4 and g.pending == 0, "a corporate state: no ambush"
assert g.space is not None and abs(g.space.d_station - game.ARRIVE_DIST) < 1
assert g.space.gov == e.galaxy.system(129).government
assert g.warp > 0 and not g.objs and not g.jumped and g.kills == 2
saved = commander.load(SAVE)
assert saved.system == 7 and saved.fuel != e.cmdr.fuel, "arriving doesn't save: only docking does"
assert e.cmdr.market is None, "a new system: its market comes on docking"
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
# RELEASE CANISTER puts one just ahead, drifting in to be scooped
n_cans = sum(1 for o in e.game.objs + e.game.new if o.kind == "can")
debug(e, "RELEASE CANISTER")
cans = [o for o in e.game.objs + e.game.new if o.kind == "can"]
assert len(cans) == n_cans + 1 and 0 < cans[-1].z <= 700 and cans[-1].m[8] < -0.99, "ahead, coming in"
tx = texts(e)
assert "RELEASE CANISTER" in tx and "DOCK NOW" in tx and "C: do it   F: back" in tx, tx
tick(e, fresh=["A"])
# dying stops a countdown; quitting to the title and coming back keeps the system
fpick(e, "LOCAL CHART")
e.chart.cx, e.chart.cy = [(float(px), float(py)) for px, py, i, d in e.chart.dots if i == 7][0]
e.chart._select(); tick(e, fresh=["C"]); assert g.jump_t > 0
# destroyed at Zaonce, never having docked there: back to the last save, at
# Lave, as it was then (the jump's fuel too)
assert e.cmdr.docked_at == 7
saved = commander.load(SAVE)
g._hurt(5000.0); tick(e); tick(e)
assert g.over and g.jump_t == 0 and e.cmdr.system == 7
assert e.cmdr.to_dict() == saved.to_dict(), "back to the last save"
assert g.again == "C: back to last save"
tick(e, fresh=["C"]); assert e.mode == "docked" and "LAVE" in texts(e)
# docked at Zaonce, destroyed there: you start again at Zaonce
e.cmdr.system = 129; e._dock()
assert e.cmdr.docked_at == 129 and "ZAONCE" in texts(e)
launch(e); e.game._hurt(5000.0); tick(e); tick(e)
assert e.game.over and e.cmdr.system == 129
tick(e, fresh=["C"]); assert e.mode == "docked" and "ZAONCE" in texts(e)
e.cmdr.fuel = 70

# launching puts you outside the station, facing the planet; arriving is far
# off, and flying up to the station docks you
launch(e)
g.spawn_t = g.rock_t = 1e9
sp = g.space
assert sp is not None and sp.station.z == -game.LAUNCH_DIST and sp.pz > 0 and sp.safe
assert g.kills == 0 and g.pending == 0
c = CountCtx(); e.draw(c)
assert c.calls.get("arc", 0) == 2 and not c.texts[1:], "the planet ahead: a disc and its outline"
g.space.sx, g.space.sy, g.space.sz = 0.0, 0.0, 400000.0      # put the sun behind the planet
c = CountCtx(); e.draw(c)
assert c.calls.get("arc", 0) == 3, "the sun, then the planet's disc over it and its outline"
# a planet behind the sun is hidden by it: no black disc over the sun
class ArcLog(CountCtx):
    def __init__(self):
        CountCtx.__init__(self); object.__setattr__(self, "log", [])
    def rgb(self, *a):
        self.log.append(("rgb", a)); return CountCtx.__getattr__(self, "rgb")(*a)
    def arc(self, *a):
        self.log.append(("arc",)); return CountCtx.__getattr__(self, "arc")(*a)
sp_ = g.space
keep = (sp_.sx, sp_.sy, sp_.sz, sp_.px, sp_.py, sp_.pz)
sp_.px, sp_.py, sp_.pz = 0.0, 0.0, 900000.0             # the planet far behind...
sp_.sx, sp_.sy, sp_.sz = 0.0, 0.0, 300000.0             # ...the sun
lg = ArcLog(); e.draw(lg)
colours = [x[1] for x in lg.log if x[0] == "rgb"]
from ace_commander import cockpit as ck
fill, edge = ck.PLANET_COLOURS[g.space.planet % len(ck.PLANET_COLOURS)]
k = colours.index(fill)
assert lg.calls.get("arc", 0) == 3 and colours[k + 1] == edge, colours[:8]
assert colours[k + 2] == ck.SUN_COLOURS[g.space.sun % len(ck.SUN_COLOURS)], "the sun last, over it"
from ace_commander import cockpit as ck

sp_.sx, sp_.sy, sp_.sz, sp_.px, sp_.py, sp_.pz = keep
# each system's sun has its colour
keep_space, keep_sys = e.game.space, e.cmdr.system
cols = set()
for i in range(40):
    e.cmdr.system = i; e._enter_space("launch"); cols.add(e.game.space.sun)
assert cols == set(range(len(ck.SUN_COLOURS))), cols
pcols = set()
for i in range(60):
    e.cmdr.system = i; e._enter_space("launch"); pcols.add(e.game.space.planet)
assert pcols == set(range(len(ck.PLANET_COLOURS))), pcols
e.cmdr.system = 7; e._enter_space("launch")
a1 = e.game.space.sun; e._enter_space("arrive"); assert e.game.space.sun == a1, "the same each visit"
e.game.space, e.cmdr.system = keep_space, keep_sys
g = e.game; g.spawn_t = g.rock_t = 1e9; g.pending = 0; g.group = []
# messages have a dark band behind them, to read against the sun
g.say("FUEL SCOOPS ON"); c = CountCtx(); e.draw(c)
assert "FUEL SCOOPS ON" in [t[0] for t in c.texts] and c.calls.get("rgba", 0) >= 1
g.space.sz = -400000.0
g.jumping = True; g.fwd = 400
c = CountCtx(); e.draw(c)
assert c.calls.get("line_to", 0) >= len(g.dust) - 2, "stardust streaks with the jump drive on"
g.jumping = False; g.fwd = 0
lave = e.galaxy.system(e.cmdr.system)
assert sp.pr == max(4000.0, lave.radius * game.PLANET_SCALE)
assert sp.station.bp.name == ("DODO" if lave.tech >= game.DODO_TECH else "CORIOLIS")
fpick(e, "LOCAL CHART")
e.chart.cx, e.chart.cy = [(float(px), float(py)) for px, py, i, d in e.chart.dots if i == 7][0]
e.chart._select(); tick(e, fresh=["C"])
for _ in range(200):
    tick(e)
    if e.cmdr.system == 7:
        break
assert e.cmdr.system == 7 and e.cmdr.fuel == 70 - d129
assert g.space is not sp and not g.space.safe and g.pending == 0, "Lave, a dictatorship: no ambush"
k0 = e.cmdr.kills
kill(g, 3); tick(e)
g.pending = 0; g.encounter_t = 1e9
g.trader_t = g.police_t = 1e9      # no traders or police in the way
g.objs[:] = [o for o in g.objs if o.kind != "ship"]
debug(e, "TO THE STATION")
assert g.space.station.z == 4000.0 and g.space.safe
fuel_before = e.cmdr.fuel
e.cmdr.docking = "C"; g.set_docking("C")    # at full speed only automatic docking works
tick(e, fresh=["A"])
seen = set()
for _ in range(400):
    tick(e, held=["F"])        # F: speed up
    seen.add(e.mode)
    if e.mode == "docked":
        break
assert "docking" in seen, "flying in shows the docking tunnel first"
assert 1.0 <= e.dock_hold <= 2.0, "the view of the bay stays 1 to 2 s"
assert e.mode == "docked" and e.docked, "flying into the station docks you"
assert e.cmdr.fuel == fuel_before < 70 and e.cmdr.kills == k0 + 3, "docking doesn't refuel"
saved = commander.load(SAVE)
assert (saved.system, saved.fuel, saved.kills) == (7, fuel_before, k0 + 3), "docking saves"
tx = texts(e)
assert "LAVE" in tx and "DOCKED" in tx
launch(e)
assert e.game.kills == 0 and not e.game.docked and e.game.space.safe
debug(e, "DOCK NOW"); assert e.mode == "docked" and not e.paused
# practice has no star system, and leaving it for the commander makes one again
tick(e, fresh=["F"]); assert e.mode == "menu"
choose(e, "COMBAT PRACTICE"); assert e.game.space is None and not e.career
e._to_title(); choose(e, "CONTINUE"); assert e.mode == "docked"
launch(e); assert e.game.space is not None and e.game.space.safe
debug(e, "DOCK NOW"); assert e.mode == "docked"
print("launching, arriving, flying to the station, docking, refuelling: ok")

# ---- the docked tabs, targets, and the jump line in the in-flight menu ----
d = e.dock
assert d.tabs == ("STATUS", "MARKET", "EQUIP SHIP", "LOCAL CHART", "GALACTIC CHART",
                  "SYSTEM DATA", "OPTIONS")
assert d.tab == 0 and any("< > screens" in t for t in texts(e))
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "MARKET"
# ---- the market (Lave: rich agricultural, so food is cheap and computers dear)
m = d.market; c = e.cmdr
assert c.market["system"] == c.system == 7 and len(m.prices) == 17
tx = texts(e)
assert "MARKET  LAVE" in tx and "FOOD" in tx and "price" in tx and "C: buy   D: sell" in tx, tx
assert 36 <= m.prices[0] <= 40 and 896 <= m.prices[7] <= 908, (m.prices[0], m.prices[7])
assert m.stock[16] == 0, "never any alien items"
cash0, food0 = c.cash, m.stock[0]
tick(e, fresh=["C"])
assert c.cargo[0] == 1 and c.cash == cash0 - m.prices[0] and m.stock[0] == food0 - 1, "C buys one"
assert any(t.startswith("1t") for t in texts(e)) and any("hold 1/20t" in t for t in texts(e))
tick(e, fresh=["D"])
assert c.cargo[0] == 0 and c.cash == cash0 and m.stock[0] == food0, "D sells one at the same price"
tick(e, fresh=["D"]); assert d.msg == "NONE TO SELL" and "NONE TO SELL" in texts(e)
for _ in range(int(1.6 / 0.04)):
    tick(e)
assert d.msg is None, "the message goes"
# holding C keeps buying, until the hold is full or the stock runs out
c.cash = 100000
for _ in range(60):
    tick(e, held=["C"])
tick(e)
assert c.cargo[0] == min(20, food0) and (d.msg in ("HOLD FULL", "NONE LEFT") or c.cargo[0] < 20), (c.cargo[0], d.msg)
if c.cargo[0] == 20:
    tick(e, fresh=["C"]); assert d.msg == "HOLD FULL"
# gold is by the kilo and doesn't use the hold
for _ in range(5):
    tick(e, fresh=["JOYDOWN"])
assert d.sel == 5 and d.top == 0
for _ in range(8):
    tick(e, fresh=["JOYDOWN"])
assert d.sel == 13 and d.top == 8 and m.unit(13) == "kg", "the list scrolls"
if m.stock[13]:
    tick(e, fresh=["C"]); assert c.cargo[13] == 1
c.cash = 5
tick(e, fresh=["JOYUP"]); tick(e, fresh=["C"])
assert d.msg in ("NOT ENOUGH CASH", "NONE LEFT")
# trades are saved: on leaving for the title, and on launching
bought = list(c.cargo)
c.cash = 1234
tick(e, fresh=["F"]); assert d.name() == "STATUS" and any(t.endswith("   123.4 Cr") for t in texts(e))
tick(e, fresh=["F"]); assert e.mode == "menu"
saved = commander.load(SAVE)
assert saved.cargo == bought and saved.cash == 1234 and saved.market == c.market, "saved on leaving"
choose(e, "CONTINUE"); assert e.mode == "docked"
d = e.dock
assert d.market.stock == saved.market["stock"] and e.cmdr.cargo == bought, "the same market again"
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "MARKET"
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "EQUIP SHIP"
# ---- Equip ship (Lave, tech level 5: the first 7 items)
eq = mod.EQUIP
c = e.cmdr
assert d.for_sale == 7 and len(eq) == 14
tx = texts(e)
assert "EQUIP SHIP  LAVE" in tx and "FUEL" in tx and "MISSILE" in tx and "PULSE LASER" in tx, tx
assert "LARGE CARGO BAY" in tx and "E.C.M. SYSTEM" in tx and "price" in tx and "have" in tx
assert c.laser == "pulse" and "fitted" in tx and c.missiles == 3 and "3/4" in tx
# fuel: 2 Cr a light year, filling the tank
c.cash = 10000; c.fuel = 40
d.esel = 0; tx = texts(e); assert "6.0" in tx, "3.0 LY to fill: 6.0 Cr"
tick(e, fresh=["C"]); assert c.fuel == 70 and c.cash == 10000 - 60
tick(e, fresh=["C"]); assert d.msg == "TANK FULL" and c.cash == 9940
# missiles, up to 4
tick(e, fresh=["JOYDOWN"]); assert d.esel == 1
tick(e, fresh=["C"]); assert c.missiles == 4 and c.cash == 9940 - eq[1][1]
tick(e, fresh=["C"]); assert d.msg == "MISSILES FULL" and c.missiles == 4
# the large cargo bay: 35 t, once
tick(e, fresh=["JOYDOWN"]); cash = c.cash
tick(e, fresh=["C"]); assert c.hold == 35 and c.cash == cash - eq[2][1]
tick(e, fresh=["C"]); assert d.msg == "ALREADY FITTED" and c.cash == cash - eq[2][1]
# the ECM is for sale now
tick(e, fresh=["JOYDOWN"]); assert d.esel == 3 and "soon" not in texts(e)
cash = c.cash = 20000
tick(e, fresh=["C"]); assert "ecm" in c.extras and c.cash == cash - eq[3][1]
# a beam laser: the pulse laser's price comes back
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["JOYDOWN"]); assert d.esel == 5
c.cash = cash = 20000
tick(e, fresh=["C"]); assert c.laser == "beam" and c.cash == cash - eq[5][1] + eq[4][1]
# fuel scoops; then the list goes round, and scrolls
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["C"]); assert "scoops" in c.extras
tick(e, fresh=["JOYDOWN"]); assert d.esel == 0 and d.etop == 0, "round to the top"
c.cash = 5; d.esel = 1; c.missiles = 0
tick(e, fresh=["C"]); assert d.msg == "NOT ENOUGH CASH" and c.missiles == 0
# what is bought goes into the next flight
c.cash = 100000; c.missiles = 2
saved_c = commander.Commander.from_dict(c.to_dict())
assert (saved_c.hold, saved_c.laser, saved_c.missiles, "scoops" in saved_c.extras) == (35, "beam", 2, True)
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "LOCAL CHART" and d.view.verb == "TARGET"
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "LOCAL CHART", "the joystick moves the cursor here"
tick(e, fresh=["B"]); assert d.name() == "GALACTIC CHART" and len(d.view.dots) == 256
tx = texts(e)
assert "GALAXY 1" in tx and "LAVE" in tx and "YOU ARE HERE" in tx, tx
tick(e, fresh=["B"]); assert d.name() == "SYSTEM DATA" and d.data.name == "LAVE"
tx = texts(e)
assert "you are here" in tx and "Dictatorship" in tx and "Tech 5   Pop 2.5 billion" in tx, tx
assert "Productivity 7000 M Cr" in tx and "Radius 4116 km" in tx
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "OPTIONS"
tx = texts(e)
before = c.docking
assert "STEER: JOYSTICK" in tx and "DOCKING: " + mod.DOCK_NAMES[before] in tx, tx
assert "CONSTRICTOR: 2 MIN" in tx
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["C"])
after = commander.DOCKING[(commander.DOCKING.index(before) + 1) % 3]
assert c.docking == after and "DOCKING: " + mod.DOCK_NAMES[after] in texts(e), "C changes it"
assert commander.load(SAVE).docking == after, "saved"
tick(e, fresh=["C"]); tick(e, fresh=["C"]); assert c.docking == before
tick(e, fresh=["JOYRIGHT"]); assert d.name() == "STATUS", "tabs wrap round"
tick(e, fresh=["E"]); assert d.name() == "OPTIONS"
tick(e, fresh=["E"]); assert d.name() == "SYSTEM DATA"
tick(e, fresh=["F"]); assert d.name() == "STATUS" and e.mode == "docked", "F goes back to Status"
# pick Diso (147) on the galactic chart by steering to it
d.open("GALACTIC CHART")
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
d.open("LOCAL CHART"); assert d.view.sel[2] == 147, "the chart opens on the target"
# a far system can be looked up, but not jumped to
d.open("GALACTIC CHART")
far = max(d.view.dots, key=lambda dot: dot[3])
d.view.cx, d.view.cy = float(far[0]), float(far[1]); d.view._select()
assert any("TOO FAR  C: DATA" in t for t in texts(e))
tick(e, fresh=["C"]); assert e.target == far[2] and d.name() == "SYSTEM DATA"
assert any("too far" in t for t in texts(e))
launch(e)
assert not any(s.startswith("JUMP") for s in e._fitems_top()), "no jump line out of range"
fpick(e, "QUIT TO TITLE")
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
assert e.dock.view is None and e.cmdr.fuel == 70 - dd, "fuel is bought, not given"
assert e.dock.for_sale == equipment_mod.on_sale(gal.system(147).tech)
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
assert n.mode == "docked" and n.galaxy is None and n.dock.tabs == ("STATUS", "OPTIONS")
assert "COMMANDER" in texts(n) and "LAVE" not in texts(n) and "< > screens   F: title" in texts(n)
tick(n, fresh=["JOYRIGHT"]); tick(n, fresh=["B"]); assert n.dock.tab == 0
launch(n)
assert "LOCAL CHART" not in n._fitems_top()
fpick(n, "STATUS"); texts(n)
mod.game_data = gd
os.remove(SAVE)
print("local chart, hyperspace countdown, fuel, only docking saves: ok")
print("ALL COMMANDER TESTS PASSED")
