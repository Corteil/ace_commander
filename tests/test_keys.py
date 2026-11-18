"""Elite's keys on a keyboard (Brian chose Elite's scheme, 2026-11-16): + / -
speed, J the jump drive, H hyperspace, Shift+H the galactic hyperdrive, and the
number row as f0-f9 in flight and docked. Needs the galaxy data (Elite's
game_data.py, or the game's own)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import game, screens
mod = ace_commander.ace
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_keys.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def docked():
    bs.press(())
    a = ace_commander.AceCommander()
    choose(a, "NEW COMMANDER")
    tick(a, fresh=["C"])
    assert a.mode == "docked", a.mode
    return a


def flying(hardcore=False):
    a = docked()
    a.cmdr.hardcore = hardcore
    a.dock.go(0)
    tick(a, fresh=["KEY_1"])            # f0: launch
    assert a.mode == "launch", a.mode
    for _ in range(200):
        tick(a)
        if a.mode != "launch":
            break
    assert a.mode == "flight" and a.career
    g = a.game
    g.spawn_t = g.rock_t = g.encounter_t = 1e9
    g.objs[:] = []
    return a, g


# ---- docked: the number row picks the tab -----------------------------------
a = docked()
d = a.dock
for key, tab in (("KEY_2", "MARKET"), ("KEY_4", "EQUIP SHIP"), ("KEY_5", "GALACTIC CHART"),
                 ("KEY_6", "LOCAL CHART"), ("KEY_7", "SYSTEM DATA"), ("KEY_9", "STATUS"),
                 ("KEY_3", "MARKET"), ("KEY_8", "MARKET"), ("KEY_=", "OPTIONS"),
                 ("KEY_+", "OPTIONS")):
    tick(a, fresh=[key])
    assert a.mode == "docked" and d.name() == tab, (key, d.name())
# 0: Inventory, the same screen as in flight, as a tab
tick(a, fresh=["KEY_0"]); assert d.name() == "INVENTORY"
assert "INVENTORY" in [x[0] for x in (lambda c: (a.draw(c), c)[1])(bs.CountCtx()).texts]
tick(a, fresh=["F"]); assert d.name() == "STATUS", "F: back to Status"
# the joystick goes round the tabs from Status, the Repair Shop after Equip
# ship; Options is Status's sub-screen (build 77, Brian)
order = []
for _ in range(len(d.tabs)):
    order.append(d.name()); tick(a, fresh=["JOYRIGHT"])
assert order == ["STATUS", "INVENTORY", "MARKET", "EQUIP SHIP",
                 "SHIPYARD", "HANGAR", "GALACTIC CHART", "LOCAL CHART", "SYSTEM DATA"], order
assert d.name() == "STATUS", "round again"
# 3: Elite's Sell Cargo: the market, on the first good in the hold
a.cmdr.cargo[5] = 2; a.cmdr.cargo[9] = 1
tick(a, fresh=["KEY_3"]); assert d.name() == "MARKET" and d.sel == 5, d.sel
# -: the Shipyard (build 80: it holds the Repair Shop)
tick(a, fresh=["KEY_-"]); assert d.name() == "SHIPYARD", d.name()
tick(a, fresh=["KEY_3"]); tick(a, fresh=["KEY__"]); assert d.name() == "SHIPYARD"
a.repair_shop = False; a._make_dock(); d = a.dock
tick(a, fresh=["KEY_-"]); assert d.name() == "SHIPYARD" and not d.repair, "the Repair Shop off"
tick(a, fresh=["C"]); assert d.name() == "SHIPYARD", "no Repair Shop to open"
print("docked number keys, Inventory, Sell, Repair Shop, Options: ok")

# ---- + / - and J ------------------------------------------------------------
for hardcore in (False, True):
    a, g = flying(hardcore)
    g.speed = 10.0
    tick(a, held=["KEY_+"])
    assert g.speed > 10.0, "+ speeds up"
    s = g.speed
    tick(a, held=["KEY_="])
    assert g.speed > s, "= (+ without shift) speeds up"
    s = g.speed
    tick(a, held=["KEY_-"])
    assert g.speed < s, "- slows down"
    s = g.speed
    tick(a, held=["KEY__"])
    assert g.speed < s, "_ slows down"
    s = g.speed
    tick(a, held=["KEY_J"])
    assert g.speed > s, "J holds speed up"
print("+ / - and J, both modes: ok")

# J at full speed away from the planet, sun and station is the jump drive
a, g = flying()
sp = g.space
sp.safe = False
g.speed = game.PLAYER_MAX
g._massed = lambda space: False         # as if far from the planet and sun
g.cabin = 0
tick(a, held=["KEY_J"])
assert g.jumping, "J at full speed: the jump drive"
tick(a)
assert not g.jumping, "let go, and it stops"
print("J jump drive: ok")

# ---- in flight: the screens, which don't pause (Brian: as Elite) -----------
a, g = flying()
a.target = None
for key, screen in (("KEY_6", "chart"), ("KEY_5", "chart"), ("KEY_7", "data"),
                    ("KEY_8", "market"), ("KEY_9", "status"), ("KEY_0", "inventory")):
    tick(a, fresh=[key])
    assert a.fsub == screen and not a.paused, (key, a.fsub, a.paused)
    texts = bs.CountCtx(); a.draw(texts); assert texts.texts, key
    tick(a, fresh=["CANCEL"])
    if screen == "data":
        tick(a, fresh=["CANCEL"])       # data goes back to its chart first
    assert a.fsub is None and not a.paused, key
tick(a, fresh=["KEY_5"]); assert type(a.chart).__name__ == "GalChart", "5: galactic"
tick(a, fresh=["CANCEL"])
tick(a, fresh=["KEY_7"]); assert a.data_of == a.cmdr.system, "7: here, with no target"
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"])

# the game runs on with a screen up; Elite's primary keys still fly
t0 = g.t if hasattr(g, "t") else None
tick(a, fresh=["KEY_9"])
g.speed = 10.0
z = [o.z for o in g.objs]
tick(a, held=["KEY_+"]); assert g.speed > 10.0, "+ on a screen"
s = g.speed
tick(a, held=["KEY_-"]); assert g.speed < s, "- on a screen"
pitch0 = g.frame
tick(a)
assert g.frame > pitch0, "the game steps with a screen up"
# the joystick and buttons are the screen's: up / down don't steer, F closes
tick(a, held=["JOYUP"]); tick(a, fresh=["F"]); assert a.fsub is None
print("flight screens, game running: ok")

# Elite's secondary keys do nothing on a screen; lasers fire but can't hit
a, g = flying()
g.missiles = 4
tick(a, fresh=["KEY_9"])
tick(a, fresh=["KEY_M"]); assert g.missiles == 4, "M: no missile on a screen"
g.speed = game.PLAYER_MAX
g.space.safe = False
g._massed = lambda space: False
g.cabin = 0
tick(a, held=["KEY_J"]); assert not g.jumping, "J: no jump drive on a screen"
g.speed = 0.0           # stopped, so it doesn't fly into the target
ship = game.Obj(g.types["COBRA MK III"], "ship", 0.0, 0.0, 600.0)
ship.role = "pirate"
g.objs.append(ship)
tick(a)                 # the level scales a new ship's energy on its first step
e = ship.energy
heat = g.heat
def ahead():
    ship.x = ship.y = 0.0       # kept in the sights: this is about the laser, not the AI
    ship.z = 600.0


for _ in range(10):
    ahead(); tick(a, held=["KEY_SPACE"])
assert ship.energy == e and g.heat > heat, "the laser fires (heat) but can't hit"
assert g.condition() == "RED", "a pirate in range"
tick(a, fresh=["KEY_9"]); assert a.fsub is None and g.looking
for _ in range(10):
    ahead(); tick(a, held=["KEY_SPACE"])
assert ship.energy < e or ship.dead, "looking at space it hits"
print("secondary keys and lasers on a screen: ok")

# H with no target opens the local chart; with a target in range it jumps
a, g = flying()
a.target = None
tick(a, fresh=["KEY_H"])
assert a.fsub == "chart" and not a.paused, "H, no target: pick one"
tick(a, fresh=["CANCEL"])
reach = [i for dist, i in a.galaxy.in_range(a.cmdr.system, a.cmdr.fuel)]
a.target = reach[0]
tick(a, fresh=["KEY_H"])
assert not a.paused and g.jump_t > 0 and a.jump_to[0] == reach[0], "H: hyperspace"
tick(a, fresh=["KEY_H"])
assert g.jump_t > 0 and a.fsub is None, "H again during the countdown does nothing"

# on a chart C only selects (Brian): the target is set, no countdown; C on
# where you are clears it; H then jumps
a, g = flying()
a.target = None
tick(a, fresh=["KEY_6"]); ch = a.chart
dot = [d for d in ch.dots if d[2] == reach[0]][0]
ch.cx, ch.cy = float(dot[0]), float(dot[1]); ch._select()
tick(a, fresh=["C"])
assert a.target == reach[0] and a.fsub == "chart" and g.jump_t <= 0, "C selects only"
assert any(t.startswith("TARGET") for t in [x[0] for x in (lambda c: (a.draw(c), c)[1])(bs.CountCtx()).texts])
ch.cx, ch.cy = 0.0, 0.0; ch._select()
tick(a, fresh=["C"]); assert a.target is None, "C on where you are clears it"
ch.cx, ch.cy = float(dot[0]), float(dot[1]); ch._select(); tick(a, fresh=["C"])
tick(a, fresh=["KEY_H"]); assert g.jump_t > 0 and a.fsub is None, "H jumps from the chart"
print("chart C selects, H jumps: ok")

# Shift+H (Brian: the Keyboard Hexpansion never sends Ctrl) or Ctrl+H, only
# with the galactic hyperdrive fitted, and never plain hyperspace; G does nothing
for mod_key in ("KEY_SHIFT", "KEY_CTRL"):
    a, g = flying()
    a.target = reach[0]
    tick(a, held=[mod_key]); tick(a, held=[mod_key], fresh=["KEY_H"])
    assert g.jump_t <= 0 and a.fsub is None, (mod_key, "no hyperdrive: does nothing")
    tick(a)
    a.cmdr.extras.append("hyperdrive")
    tick(a, fresh=["KEY_G"])
    assert g.jump_t <= 0, "G is not the galactic hyperdrive"
    tick(a, held=[mod_key]); tick(a, held=[mod_key], fresh=["KEY_H"])
    assert g.jump_t > 0 and a.jump_to == ("galaxy", 0), (mod_key, "galactic hyperspace")

# as the Keyboard Hexpansion sends it: Shift down, H down, Shift up, H up, all
# before the next frame (Brian's badge log): still the galactic hyperdrive
a, g = flying()
a.cmdr.extras.append("hyperdrive")
for ev, name in ((bs.ButtonDownEvent, "KEY_SHIFT"), (bs.ButtonDownEvent, "KEY_H"),
                 (bs.ButtonUpEvent, "KEY_SHIFT"), (bs.ButtonUpEvent, "KEY_H")):
    bs.bus.send(ev(bs.PHYSICAL[name]))
tick(a)
assert g.jump_t > 0 and a.jump_to == ("galaxy", 0), "Shift+H within one frame"
# and a plain H after it is plain hyperspace again (no target: the chart)
a, g = flying()
a.target = None
tick(a, fresh=["KEY_SHIFT"]); tick(a); tick(a, fresh=["KEY_H"])
assert a.fsub == "chart", "Shift let go before H: plain H"
print("H, Shift+H, Ctrl+H: ok")

# the number row on a screen or in the menu: the screen's own key closes it,
# 1-4 fly on looking that way, another screen's key goes straight there
a, g = flying()
a.target = None
tick(a, fresh=["KEY_6"]); tick(a, fresh=["KEY_6"]); assert a.fsub is None, "6 again"
tick(a, fresh=["KEY_8"]); tick(a, fresh=["KEY_8"]); assert a.fsub is None, "8 again"
tick(a, fresh=["KEY_9"]); tick(a, fresh=["KEY_0"]); assert a.fsub == "inventory", "9 then 0"
tick(a, fresh=["KEY_0"]); assert a.fsub is None, "0 again"
tick(a, fresh=["KEY_6"]); tick(a, fresh=["KEY_5"])
assert type(a.chart).__name__ == "GalChart", "6 then 5"
tick(a, fresh=["KEY_8"]); assert a.fsub == "market", "5 then 8"
tick(a, fresh=["KEY_2"]); assert a.fsub is None and g.view == 1, "2: fly on, looking back"
tick(a, fresh=["KEY_9"]); tick(a, fresh=["KEY_1"]); assert a.fsub is None and g.view == 0
tick(a, fresh=["A"]); assert a.paused                          # the menu still pauses
tick(a, fresh=["KEY_9"]); assert a.fsub == "status" and not a.paused, "9 from the menu"
tick(a, fresh=["A"]); assert a.paused and a.fsub is None, "A on a screen: the menu"
tick(a, fresh=["KEY_3"]); assert not a.paused and g.view == 2, "3 from the menu"
print("number keys on a screen: ok")

# Market Prices: every good, scrolls, buys nothing; same prices docked
a, g = flying()
cash, cargo = a.cmdr.cash, list(a.cmdr.cargo)
tick(a, fresh=["KEY_8"])
prices = list(a.fmarket.prices)
for _ in range(20):
    tick(a, fresh=["JOYDOWN"])
assert a.top == len(a.fmarket.goods) - screens.ROWS, a.top
tick(a, fresh=["DOWN"]); assert a.top == len(a.fmarket.goods) - screens.ROWS
tick(a, fresh=["UP"]); assert a.top == len(a.fmarket.goods) - screens.ROWS - 1, "cursor keys scroll"
tick(a, fresh=["D"]); tick(a, fresh=["B"])
assert a.cmdr.cash == cash and a.cmdr.cargo == cargo, "nothing bought or sold"
print("market prices: ok")

# Esc is Elite's ESCAPE (Brian): the escape pod, looking at space only; on a
# screen or in the menu Esc is still back
a, g = flying()
tick(a, fresh=["KEY_ESCAPE"])
assert not g.over and g.msg == "NO ESCAPE POD", g.msg
a.cmdr.extras.append("pod"); g.pod = True
tick(a, fresh=["KEY_9"]); tick(a, fresh=["KEY_ESCAPE"])
assert a.fsub is None and not g.over, "Esc on a screen: back, no pod"
tick(a, fresh=["A"]); tick(a, fresh=["KEY_ESCAPE"])
assert not a.paused and not g.over, "Esc in the menu: resume, no pod"
cargo = list(a.cmdr.cargo)
tick(a, fresh=["KEY_ESCAPE"])
assert g.over and g.ejected and g.msg == "ESCAPE POD LAUNCHED", g.msg
seen = None
for _ in range(400):
    tick(a)
    if a.mode == "docking" and seen is None:
        seen = a.tunnel.me.bp.name if a.tunnel.me is not None else None
    if a.mode == "docked":
        break
assert seen == "ESCAPE POD", ("the docking scene shows the pod coming in (Brian)", seen)
assert a.mode == "docked" and "pod" not in a.cmdr.extras, "woken up docked, pod used"
# a normal launch shows the ship you fly
a.dock.go(0); tick(a, fresh=["KEY_1"])
assert a.mode == "launch" and a.tunnel.me.bp.name == a._ship_name() == "COBRA MK III"
print("Esc escape pod, the pod in the docking scene: ok")

# Tab is Elite's energy bomb (a driver's own TAB button: the firmware has none)
a, g = flying()
a.cmdr.extras.append("bomb"); g.bombs = 1
rock = game.Obj(g.types["ASTEROID"], "rock", 0.0, 0.0, 800.0); g.objs.append(rock)
tick(a, fresh=["KEY_9"]); tick(a, fresh=["KEY_TAB"])
assert g.bombs == 1, "Tab on a screen: nothing (a secondary key)"
tick(a, fresh=["KEY_9"])
tick(a, fresh=["KEY_TAB"])
assert g.bombs == 0 and "bomb" not in a.cmdr.extras, "Tab: the energy bomb, used up"
# the patched Keyboard Hexpansion driver sends LCTRL as its own key with CTRL
# as its parent, and TAB as a plain key: both reach the game
lctrl = bs.Button("LCTRL", "Keyboard", bs.KEYS["CTRL"])
a, g = flying()
a.cmdr.extras.append("hyperdrive")
bs.bus.send(bs.ButtonDownEvent(lctrl)); tick(a)
tick(a, fresh=["KEY_H"])
bs.bus.send(bs.ButtonUpEvent(lctrl))
assert g.jump_t > 0 and a.jump_to == ("galaxy", 0), "the driver's LCTRL + H"
# the patched driver also sends a held Shift as LSHIFT / RSHIFT
a, g = flying()
a.cmdr.extras.append("hyperdrive")
lshift = bs.Button("LSHIFT", "Keyboard")
bs.bus.send(bs.ButtonDownEvent(lshift)); tick(a)
tick(a, fresh=["KEY_H"])
bs.bus.send(bs.ButtonUpEvent(lshift))
assert g.jump_t > 0 and a.jump_to == ("galaxy", 0), "the driver's LSHIFT + H"
print("Tab energy bomb, the driver's LCTRL and LSHIFT: ok")

# Elite's docking computer keys (Brian): C on, P off; P is the menu otherwise
a, g = flying()
assert g.space.safe, "just launched: in the safe zone"
tick(a, fresh=["KEY_C"])
assert not g.autodock and g.msg == "NO DOCKING COMPUTER", g.msg
a.cmdr.extras.append("docking"); g.computer = True
tick(a, fresh=["KEY_C"]); assert g.autodock, "C: the docking computer on"
tick(a, fresh=["KEY_P"]); assert not g.autodock and not a.paused, "P: off, no menu"
tick(a, fresh=["KEY_P"]); assert a.paused, "P with it off: the menu"
tick(a, fresh=["KEY_C"]); assert not g.autodock, "C in the menu does nothing"
tick(a, fresh=["KEY_P"]); assert not a.paused
g.space.safe = False
tick(a, fresh=["KEY_C"]); assert not g.autodock and g.msg == "STATION TOO FAR", g.msg
print("C / P docking computer: ok")

# Backspace sets off the energy bomb too (an unpatched keyboard drops Tab)
a, g = flying()
a.cmdr.extras.append("bomb"); g.bombs = 1
tick(a, fresh=["KEY_BACKSPACE"])
assert g.bombs == 0 and "bomb" not in a.cmdr.extras, "Backspace: the energy bomb"
print("Backspace energy bomb: ok")

# combat practice has no charts or hyperspace: the keys do nothing
bs.press(())
p = ace_commander.AceCommander()
choose(p, "COMBAT PRACTICE")
for key in ("KEY_5", "KEY_6", "KEY_7", "KEY_H"):
    tick(p, fresh=[key])
    assert not p.paused, key
tick(p, fresh=["A"]); p.fmenu = p._fitems_top().index("SETTINGS"); tick(p, fresh=["C"])
tick(p, fresh=["KEY_6"]); assert p.paused and p.fsub == "settings", "no chart there: Settings stays"
print("combat practice: ok")
print("ALL KEY TESTS PASSED")
