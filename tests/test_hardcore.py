"""Hardcore Mode rules (manual ECM, armed missiles), using the game's own ship data so it runs
without Elite's files. Standard mode must behave as before."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import game, rules
mod = ace_commander.ace
SHIPS = mod.SHIPS
DT = 0.04


def flight(hardcore, seed=1):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.rules = rules.GameRules(hardcore)
    g.rock_t = g.encounter_t = g.spawn_t = 1e9
    g.objs[:] = []
    return g


def put(g, name, kind, x, y, z):
    o = game.Obj(g.types[name], kind, float(x), float(y), float(z))
    g.objs.append(o)
    return o


def target(g, z=4000):
    """A ship held still in the sights (as tests/test_game.py does)."""
    name = next(n for n in g.types if g.types[n].energy and n not in ("MISSILE",))
    o = put(g, name, "ship", 300, 100, z)
    d = math.sqrt(300 * 300 + 100 * 100 + z * z)
    game._look(o.m, -300 / d, -100 / d, -z / d)
    o.state = "break"; o.t = 99; o.aim = [1.0, 0.0, 0.0]
    o.pin = (300.0, 100.0, float(z))
    return o


def run(g, secs, fire=False, missile=False):
    for _ in range(int(secs / DT)):
        for o in g.objs:
            if hasattr(o, "pin"):           # held in the sights
                o.x, o.y, o.z = o.pin
        g.step(DT, 0, 0, 0, fire, missile)


# ---- the rules object
assert rules.GameRules().active() == []
assert set(rules.GameRules(True).active()) == set(rules.FLAGS)
print("rules flags: ok")

# ---- standard mode: ECM fires by itself, missiles lock without arming (as before)
g = flight(False)
g.ecm = True
m = put(g, "MISSILE", "missile", 0, 0, 2000)
m.t = 8.0
run(g, 0.2)
assert m.dead and g.ecm_t > 0, "standard ECM should fire by itself"
g = flight(False)
t = target(g)
run(g, game.LOCK_TIME + 0.5)
assert g.locked, "standard missiles lock without arming"
g.step(DT, 0, 0, 0, False, True)
assert any(o.kind == "pmissile" for o in g.new + g.objs), "standard D fires"
print("standard mode unchanged: ok")

# ---- hardcore ECM: nothing happens until the key
g = flight(True)
g.ecm = True
m = put(g, "MISSILE", "missile", 0, 0, 2000)
m.t = 8.0
shield = g.shield
run(g, 0.2)
assert not m.dead and g.ecm_t <= 0, "hardcore ECM must not fire by itself"
assert g.fire_ecm() and m.dead and g.ecm_t > 0 and g.shield == shield - game.ECM_COST
assert not g.fire_ecm(), "no second pulse while pulsing"
g2 = flight(True)
assert not g2.fire_ecm() and g2.msg == "NO ECM", g2.msg
print("hardcore manual ECM: ok")

# ---- hardcore missiles: arm, lock, fire; unarm; not armed = no launch
g = flight(True)
t = target(g)
run(g, game.LOCK_TIME + 1.0)
assert not g.locked and g.lock is None, "no lock while not armed"
g.step(DT, 0, 0, 0, False, True)
assert g.msg == "MISSILE NOT ARMED" and not any(o.kind == "pmissile" for o in g.new + g.objs)
n = g.missiles
assert g.arm_missile() and g.armed
run(g, game.LOCK_TIME * 0.5)
g.step(DT, 0, 0, 0, False, True)
assert g.msg == "NO LOCK" and g.missiles == n, g.msg      # armed but not locked yet
run(g, game.LOCK_TIME)
assert g.locked
g.unarm_missile()
assert not g.armed and not g.locked and g.lock is None
g.step(DT, 0, 0, 0, False, True)
assert g.missiles == n, "unarmed must not fire"
g.arm_missile()
run(g, game.LOCK_TIME + 0.5)
g.step(DT, 0, 0, 0, False, True)
assert g.missiles == n - 1 and not g.armed, "fired once; each missile is armed afresh"
assert any(o.kind == "pmissile" for o in g.new + g.objs)
g3 = flight(True)
g3.missiles = 0
assert not g3.arm_missile() and g3.msg == "NO MISSILES"
print("hardcore arm / lock / fire / unarm: ok")

# ---- mass lock (standard and hardcore): the jump drive drops out near the planet or the sun
def jump_flight(hardcore):
    g = flight(hardcore)
    g.enter(6000, "CORIOLIS", "launch", 3)
    sp = g.space
    sp.station.x = sp.station.y = 0.0
    sp.station.z = -1e7                       # far from the station: not the safe zone
    sp.sx, sp.sy, sp.sz = 1e8, 0.0, 0.0       # the sun far away: no heat
    g.cabin = game.COOL_CABIN
    g.encounter_t = 1e9
    g.speed = game.PLAYER_MAX
    return g, sp


def jumping_at(g, sp, dist):
    sp.px = sp.py = 0.0
    sp.pz = dist
    for _ in range(2):          # the first step measures where things are
        g.speed = game.PLAYER_MAX
        g.msg_t = 0.0
        g.step(DT, 0, 0, 1.0, False, False)
    return g.jumping


for hc in (False, True):
    g, sp = jump_flight(hc)
    assert jumping_at(g, sp, sp.pr * 6), "far from everything: the jump drive runs"
    assert not jumping_at(g, sp, sp.pr * 1.5), "mass locked near the planet, in either mode"
    assert g.msg == "MASS LOCKED", g.msg
    assert not jumping_at(g, sp, sp.pr * 1.9), "inside 2 radii"
    assert jumping_at(g, sp, sp.pr * 2.2), "outside 2 radii"
    if hc:
        g.space.px = 1e8
        sp.sx, sp.sy, sp.sz = 0.0, 0.0, sp.sr * 1.5     # the sun counts too
        g.speed = game.PLAYER_MAX
        g.cabin = game.COOL_CABIN
        g.step(DT, 0, 0, 1.0, False, False)
        assert not g.jumping, "no jump drive near the sun"
print("mass lock (planet and sun, both modes): ok")

# ---- a new flight starts disarmed
g = flight(True)
g.arm_missile()
g.reset()
assert not g.armed

# ---- through the app: the setting, the keyboard, and the badge's own buttons
from badge_stubs import tick, choose
SAVE = os.path.join(HERE, "shots", "test_hardcore.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def bs_texts(a):
    c = bs.CountCtx(); a.draw(c)
    for t, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (t, y)
    return c.texts


def app_flight(hardcore):
    bs.press(())
    a = ace_commander.AceCommander()
    a.p_hardcore = hardcore
    tick(a)
    choose(a, "COMBAT PRACTICE")
    g = a.game
    g.spawn_t = g.rock_t = g.encounter_t = 1e9
    g.objs[:] = []
    g.speed = 10.0
    tick(a)
    return a, g


a, g = app_flight(False)
assert not g.rules.hardcore and not any(s.startswith("HARDCORE") for s in a._settings(False)), \
    "HARDCORE isn't a setting: practice's page or a new commander picks it"
s0 = g.speed
for _ in range(10):
    tick(a, held=["KEY_E"])
assert g.speed > s0, "standard: the E key is still speed up"
print("standard keys unchanged: ok")

a, g = app_flight(True)
assert g.rules.hardcore
g.ecm = True
m = put(g, "MISSILE", "missile", 0, 0, 2000)
m.t = 8.0
s0 = g.speed
tick(a, fresh=["KEY_E"])
assert m.dead and g.ecm_t > 0, "hardcore: the E key pulses the ECM"
for _ in range(8):
    tick(a, held=["KEY_E"])
assert g.speed <= s0 + 0.01, "hardcore: the E key no longer changes speed"
t = target(g)
tick(a, fresh=["KEY_T"])
assert g.armed, "hardcore: T arms"
tick(a, fresh=["KEY_U"])
assert not g.armed, "hardcore: U disarms"
print("hardcore keys (E, T, U): ok")

a, g = app_flight(True)       # the badge alone: both speed buttons pulse the ECM, D arms then fires
g.ecm = True
m = put(g, "MISSILE", "missile", 0, 0, 2000)
m.t = 8.0
tick(a, held=["F"], fresh=["E"])
assert m.dead and g.ecm_t > 0, "hardcore: E with F held pulses the ECM"
t = target(g)
tick(a, fresh=["D"])
assert g.armed and g.missiles == 4, "hardcore: the first D arms"
for _ in range(int(game.LOCK_TIME / DT) + 2):
    for o in g.objs:
        if hasattr(o, "pin"):
            o.x, o.y, o.z = o.pin
    tick(a)
assert g.locked
tick(a, fresh=["D"])
assert g.missiles == 3 and not g.armed, "hardcore: the next D fires"
print("hardcore badge buttons (E+F, D): ok")

# ---- docking is by hand only in Hardcore; the DOCKING setting is left as it was
for style in "ABC":
    g = flight(False)
    g.set_docking(style)
    assert g.docking == style, "standard: the setting decides"
    g = flight(True)
    g.set_docking(style)
    assert g.docking == "A", "hardcore: always by hand"
a, g = app_flight(True)
a.cmdr = ace_commander.commander.Commander(1)
a.cmdr.hardcore = True
a.cmdr.docking = "C"
assert "DOCKING: MANUAL" in a._settings(True)
a._change("DOCKING: MANUAL", False)
assert a.cmdr.docking == "C", "the saved style isn't changed in Hardcore"
assert "DOCKING: MANUAL" in a._settings(True), "a Hardcore flight stays so until it ends"
a.mode = "menu"
a.cmdr.hardcore = False
assert "DOCKING: AUTOMATIC" in a._settings(True)
g.computer = False
assert g.start_autodock() == "NO DOCKING COMPUTER", "only a bought docking computer flies you in"
print("hardcore docking: ok")

# ---- the commander's HARDCORE: picked with the commander, fixed but for DEBUG
cm = ace_commander.commander
c = cm.Commander(1)
assert c.hardcore is False and cm.Commander.from_dict(c.to_dict()).hardcore is False
c.hardcore = True
assert cm.Commander.from_dict(c.to_dict()).hardcore is True, "kept in the save"
d = c.to_dict(); del d["hardcore"]
assert cm.Commander.from_dict(d).hardcore is None, "an old save: not known yet"
# an old save takes options.json's old HARDCORE
import json as _json
with open(mod.options_path(), "w") as f:
    f.write(_json.dumps({"hardcore": True}))
with open(SAVE, "w") as f:
    f.write(_json.dumps(d))
b = ace_commander.AceCommander()
assert b.cmdr.hardcore is True and _json.loads(b.saved)["hardcore"] is True, "old option carried over"
os.remove(SAVE); os.remove(mod.options_path())

n = ace_commander.AceCommander()
tick(n)
choose(n, "NEW COMMANDER")
assert n.mode == "level" and n.n_sel == 1 and not n.n_hardcore, "on LEVEL (NAME above it: build 89)"
tx = [t[0] for t in bs_texts(n)]
assert "< NORMAL >" in tx and "< OFF >" in tx and "top rank at 3200 kills" in tx, tx
tick(n, fresh=["JOYDOWN"]); tick(n, fresh=["JOYRIGHT"])
assert n.n_hardcore and n.level == 1
tick(n, fresh=["JOYUP"]); tick(n, fresh=["JOYRIGHT"]); assert n.level == 2
tick(n, fresh=["C"])
assert n.mode == "docked" and n.cmdr.hardcore and n.cmdr.level == 2
assert _json.load(open(SAVE))["hardcore"] is True
assert not any(s.startswith("HARDCORE") for s in n._settings(True)), "not an option any more"
assert "DOCKING: MANUAL" in n._settings(True)
# DEBUG > COMMANDER > HARDCORE: the only way to change it
n.od_from = "docked"
assert "HARDCORE: ON" in n._cheats("COMMANDER", False)
assert n._odebug("HARDCORE: ON") == "HARDCORE OFF" and not n.cmdr.hardcore
assert _json.load(open(SAVE))["hardcore"] is False
n._odebug("HARDCORE: OFF"); assert n.cmdr.hardcore
print("commander HARDCORE: picked when made, DEBUG changes it: ok")

# ---- combat practice's page: LEVEL and HARDCORE before the flight ------------
p = ace_commander.AceCommander()
tick(p)
p.menu = p.choices().index("COMBAT PRACTICE")
tick(p, fresh=["CONFIRM"])
assert p.mode == "practice" and p.p_sel == 0 and p.p_level == 1
c = bs.CountCtx(); p.draw(c)
shown = [t[0] for t in c.texts]
assert "COMBAT PRACTICE" in shown and "< NORMAL >" in shown and "< OFF >" in shown, shown
for t, (x, y), size in c.texts:
    assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (t, y)
tick(p, fresh=["JOYRIGHT"]); assert p.p_level == 2, "right: the next level"
tick(p, fresh=["JOYDOWN"]); assert p.p_sel == 1
before = p._hardcore()
tick(p, fresh=["JOYRIGHT"]); assert p.p_hardcore and p._hardcore() == before, "practice's own HARDCORE"
tick(p, fresh=["CONFIRM"])
g = p.game
assert p.mode == "flight" and not p.career and g.level == 2 and g.rules.hardcore
assert not g.armed and g.rules.missile_lock_required and g.rules.manual_ecm
assert g.ecm, "practice flies with an ECM"
m = put(g, "MISSILE", "missile", 0, 0, 2000)
m.t = 8.0
tick(p)
assert not m.dead, "Hardcore: the ECM waits for its key"
tick(p, fresh=["KEY_E"])
assert m.dead and g.ecm_t > 0, "and fires on it"
q = ace_commander.AceCommander()
assert q.p_level == 2 and q.p_hardcore, "both kept in options.json"
# back to the title part-way: the same settings carry the fight on, new ones start afresh
p.mode = "menu"
g.score = 7
choose(p, "COMBAT PRACTICE"); assert p.game is g and g.score == 7, "the fight carries on"
p.mode = "menu"
p.menu = p.choices().index("COMBAT PRACTICE")
tick(p, fresh=["CONFIRM"]); tick(p, fresh=["JOYDOWN"]); tick(p, fresh=["JOYLEFT"])
assert not p.p_hardcore
tick(p, fresh=["CONFIRM"])
g = p.game
assert p.mode == "flight" and not g.rules.hardcore and g.score == 0, "HARDCORE off: a new flight"
assert g.ecm
g.spawn_t = g.rock_t = g.encounter_t = 1e9
g.objs[:] = []
m = put(g, "MISSILE", "missile", 0, 0, 300)
m.t = 8.0
for _ in range(5):
    tick(p)
assert m.dead and g.ecm_t > 0, "standard: practice's ECM fires by itself at a missile close by"
p.mode = "menu"
p.menu = p.choices().index("COMBAT PRACTICE")
tick(p, fresh=["CONFIRM"]); tick(p, fresh=["CANCEL"]); assert p.mode == "menu", "F: back"
print("combat practice page: ok")
# ---- Hardcore saves only when asked (build 133): Options > SAVE COMMANDER, docked
import json
from ace_commander import commander


def on_file():
    return json.load(open(SAVE))["credits"]


for hard in (False, True):
    bs.press(())
    a = ace_commander.AceCommander()
    a.cmdr = commander.Commander(1)
    a.cmdr.hardcore = hard
    a._write()                      # a new commander is saved as it's made, in both modes
    a._dock()
    start = on_file()
    a.cmdr.cash += 5000             # 500 Cr: bought, sold, flown...
    a._dock()                       # docking again
    a.dock.open("OPTIONS")
    items = a._settings(True)
    if not hard:
        assert on_file() == start + 500, "standard: docking saves"
        assert not any(i.startswith("SAVE") for i in items), "standard: no SAVE line"
        continue
    assert on_file() == start, "Hardcore: docking doesn't save"
    a._launch()
    assert on_file() == start, "Hardcore: launching doesn't save"
    a._dock()
    a.dock.open("OPTIONS")
    items = a._settings(True)
    assert items[0] == "SAVE COMMANDER", items
    a.dock.osel = 0
    a.dock.change_option()
    assert on_file() == start + 500, "SAVE COMMANDER saves"
    assert a._settings(True)[0] == "COMMANDER SAVED"
    bs_texts(a)                     # it fits on the round screen
    a.cmdr.cash += 1000
    if a.game is None:
        a.game = game.Game(SHIPS)
    a._restore()                    # destroyed: back to the last save
    assert a.cmdr.credits == start + 500, a.cmdr.credits
    a._dock()
    tick(a, fresh=["CANCEL"])       # Options back to Status
    tick(a, fresh=["CANCEL"])       # Status to the title: not saved either
    assert a.mode == "menu" and on_file() == start + 500
print("Hardcore saves only by SAVE COMMANDER: ok")
print("ALL HARDCORE TESTS PASSED")
