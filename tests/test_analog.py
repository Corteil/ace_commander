"""A host's analogue controls (the Raspberry Pi's game pad, Brian 2026-11-19):
AceCommander.analog (roll, pitch, yaw, speed) and Game's yaw, which Elite and
the badge don't have. The badge never sets analog, so nothing changes there."""
import math, os, sys, types
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
SAVE = os.path.join(HERE, "shots", "test_analog.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def an(roll=0.0, pitch=0.0, yaw=0.0, speed=None):
    return types.SimpleNamespace(roll=roll, pitch=pitch, yaw=yaw, speed=speed)


def flying():
    bs.press(())
    a = ace_commander.AceCommander()
    assert a.analog is None, "nothing analogue on the badge"
    choose(a, "NEW COMMANDER")
    tick(a, fresh=["C"])
    tick(a, fresh=["KEY_1"])
    for _ in range(200):
        tick(a)
        if a.mode != "launch":
            break
    assert a.mode == "flight"
    g = a.game
    g.spawn_t = g.rock_t = g.encounter_t = 1e9
    g.objs[:] = []
    return a, g


def ahead(g, z=1000.0):
    o = game.Obj(g.types[[n for n in g.types if n != "CORIOLIS"][0]], "rock", 0.0, 0.0, z)
    g.objs.append(o)
    return o


# ---- Game: yaw turns the nose right, so what was ahead swings left -------------
g = game.Game(mod.SHIPS, 1)
o = ahead(g)
x0 = o.x
dust = [list(p) for p in g.dust]
g.speed = 0.0
g.step(0.1, 0.0, 0.0, -1.0, False, False, 1.0)
assert o.x < x0 - 1, ("yaw right: the rock ahead goes left", o.x)
assert abs(o.y) < 1e-6, "yaw doesn't pitch"
assert abs(math.hypot(o.x, o.z) - 1000.0) < 1.0, "a turn, not a move"
assert all(isinstance(v, int) for p in g.dust for v in p), "dust stays whole numbers"
r = o.m
for i in (0, 3, 6):
    assert abs(r[i] ** 2 + r[i + 1] ** 2 + r[i + 2] ** 2 - 1.0) < 1e-6, "still unit vectors"
print("Game yaw: the world turns about the up axis: ok")

# ---- AceCommander.analog: roll, pitch, yaw add to the steering ------------------
a, g = flying()
o = ahead(g, 2000.0)
a.analog = an(yaw=1.0)
for _ in range(5):
    tick(a)
assert o.x < -10, ("analogue yaw right", o.x)
o.x, o.y, o.z = 0.0, 0.0, 2000.0
a.analog = an(roll=0.0, pitch=-1.0)        # the stick up, as the joystick's up
for _ in range(5):
    tick(a)
pitch_up = o.y
o.x, o.y, o.z = 0.0, 0.0, 2000.0
a.analog = an()
bs.press(["JOYUP"])
for _ in range(5):
    a.update(40)
bs.press(())
assert abs(o.y - pitch_up) < 1.0 and abs(o.y) > 1, ("analogue up = the joystick's up", o.y, pitch_up)
print("analogue roll / pitch / yaw: ok")

# ---- speed: where the power stick sits ---------------------------------------
a.analog = an(speed=0.0)
for _ in range(100):
    tick(a)
assert g.speed < 0.5, ("bottom: stopped", g.speed)
a.analog = an(speed=0.5)
for _ in range(100):
    tick(a)
assert abs(g.speed - g.max_speed / 2) < 1.0, ("centre: half speed", g.speed, g.max_speed)
a.analog = an(speed=1.0)
for _ in range(100):
    tick(a)
assert g.speed >= g.max_speed - 0.01, ("top: full speed", g.speed)
a.analog = an(speed=None)
s = g.speed
tick(a, held=["KEY_-"])
assert g.speed < s, "speed None: the keys still work"
print("analogue speed: bottom stopped, centre half, top full: ok")

# ---- CONTROLS flip turns yaw with roll ----------------------------------------
o.x, o.y, o.z = 0.0, 0.0, 2000.0
a.tilt_flip = 2
a.analog = an(yaw=1.0)
for _ in range(5):
    tick(a)
assert o.x > 10, ("left / right flipped: yaw too", o.x)
a.tilt_flip = 0
a.analog = None
print("CONTROLS flip: ok")

# ---- the docking computer: the stick taken over switches it off ---------------
a.cmdr.extras.append("docking"); g.computer = True
g.to_station(4000.0, slot=False)
assert g.start_autodock() is None and g.autodock
a.analog = an(speed=0.5)                    # resting sticks don't
tick(a); tick(a)
assert g.autodock, "a resting pad leaves the computer flying"
a.analog = an(roll=0.9)
tick(a)
assert not g.autodock, "a pushed stick takes over"
print("docking computer: ok")
print("ALL ANALOG TESTS PASSED")
