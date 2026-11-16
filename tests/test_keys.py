"""Elite's keys on a keyboard (Brian chose Elite's scheme, 2026-11-16): + / -
speed, J the jump drive, H hyperspace, Ctrl+H the galactic hyperdrive, and the
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
from ace_commander import game
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
    a.hardcore = hardcore
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
                 ("KEY_0", "MARKET"), ("KEY_3", "MARKET"), ("KEY_8", "MARKET")):
    tick(a, fresh=[key])
    assert a.mode == "docked" and d.name() == tab, (key, d.name())
print("docked number keys: ok")

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

# ---- in flight: H, G and the screens ----------------------------------------
a, g = flying()
tick(a, fresh=["KEY_6"])
assert a.paused and a.fsub == "chart", "6: the local chart"
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"])
assert not a.paused

tick(a, fresh=["KEY_5"])
assert a.paused and a.fsub == "chart" and type(a.chart).__name__ == "GalChart", "5: galactic"
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"])

tick(a, fresh=["KEY_7"])
assert a.paused and a.fsub == "data" and a.data_of == a.cmdr.system, "7: here, no target"
tick(a, fresh=["CANCEL"])
assert a.fsub == "chart", "back to the chart"
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"])

for key in ("KEY_9", "KEY_0"):
    tick(a, fresh=[key])
    assert a.paused and a.fsub == "status", key
    tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"])
    assert not a.paused

tick(a, fresh=["KEY_8"])
assert not a.paused and g.msg == "MARKET: DOCKED ONLY", g.msg

# H with no target opens the local chart, as the menu's HYPERSPACE does
a.target = None
tick(a, fresh=["KEY_H"])
assert a.paused and a.fsub == "chart", "H, no target: pick one"
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"])
# with a target in range H starts the countdown
reach = [i for dist, i in a.galaxy.in_range(a.cmdr.system, a.cmdr.fuel)]
a.target = reach[0]
tick(a, fresh=["KEY_H"])
assert not a.paused and g.jump_t > 0 and a.jump_to[0] == reach[0], "H: hyperspace"
tick(a, fresh=["KEY_H"])
assert g.jump_t > 0 and not a.paused, "H again during the countdown does nothing"

# Ctrl+H (Elite's key, Brian) only with the galactic hyperdrive fitted, and it
# is never plain hyperspace; G does nothing
a, g = flying()
a.target = reach[0]
tick(a, held=["KEY_CTRL"]); tick(a, held=["KEY_CTRL"], fresh=["KEY_H"])
assert not a.paused and g.jump_t <= 0, "no hyperdrive: Ctrl+H does nothing"
tick(a)
a.cmdr.extras.append("hyperdrive")
tick(a, fresh=["KEY_G"])
assert g.jump_t <= 0, "G is not the galactic hyperdrive"
tick(a, held=["KEY_CTRL"]); tick(a, held=["KEY_CTRL"], fresh=["KEY_H"])
assert g.jump_t > 0 and a.jump_to == ("galaxy", 0), "Ctrl+H: galactic hyperspace"
print("H, Ctrl+H and the flight screens: ok")

# combat practice has no charts or hyperspace: the keys do nothing
bs.press(())
p = ace_commander.AceCommander()
choose(p, "COMBAT PRACTICE")
for key in ("KEY_5", "KEY_6", "KEY_7", "KEY_H"):
    tick(p, fresh=[key])
    assert not p.paused, key
print("combat practice: ok")
print("ALL KEY TESTS PASSED")
