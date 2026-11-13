import math, os, random, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import Imu, App, CountCtx

G = 9.81


def load(**kw):
    bs.install(**kw)
    import ace_commander
    return ace_commander, ace_commander.app


tick = bs.tick


def frame(a):
    c = CountCtx()
    a.draw(c)
    assert c.depth == 0
    return c


def fits(c):
    for s, (x, y), size in c.texts:
        assert math.sqrt(x * x + y * y) + size / 2 <= 120.5, (s, x, y, size)


def rocks(mod, g):
    g.objs[:] = []
    ahead = mod.game.Obj(g.types["ASTEROID"], "rock", 0.0, 0.0, 3000.0)
    side = mod.game.Obj(g.types["ASTEROID"], "rock", 1000.0, 0.0, 3000.0)
    g.objs += [ahead, side]
    g.speed = 0.0
    return ahead, side


# ---- menu -----------------------------------------------------------------
pkg, mod = load()
a = pkg.AceCommander()
assert a.overlays == [] and len(mod.SHIPS) == 31
assert not a.use_tilt, "joystick steering is the default"
c = frame(a); fits(c)
assert [t[0] for t in c.texts][:5] == ["ACE", "COMMANDER", "FLIGHT", "SHIP VIEWER", "SPEED TEST"]
tick(a, fresh=["JOYDOWN"]); assert a.menu == 1
tick(a, fresh=["JOYUP"]); assert a.menu == 0
tick(a, fresh=["D"]); assert a.menu == 1          # buttons A and D also move the menu
tick(a, fresh=["A"]); assert a.menu == 0
tick(a, fresh=["F"]); assert App.minimised == 1 and a.mode == "menu"
print("menu: ok")

# ---- flight: joystick steers, lettered buttons do the rest ------------------
random.seed(11)
tick(a, fresh=["JOYFIRE"])
assert a.mode == "flight"
g = a.game
g.spawn_t = g.rock_t = 1e9
ahead, side = rocks(mod, g)
tick(a, held=["JOYUP"]); assert ahead.y < 0, "joystick up raises the nose: things ahead drop"
y = ahead.y
tick(a, held=["JOYDOWN"]); tick(a, held=["JOYDOWN"]); assert ahead.y > y
y = side.y
tick(a, held=["JOYRIGHT"]); assert side.y > y, "joystick right rolls right"
y = side.y
tick(a, held=["JOYLEFT"]); tick(a, held=["JOYLEFT"]); assert side.y < y

# the lettered buttons must NOT steer, although A/B/D/E are also up/right/down/left
ahead, side = rocks(mod, g)
for name in ("B", "E", "D"):
    tick(a, held=[name])
assert abs(ahead.x) < 1e-9 and abs(ahead.y) < 1e-9, (ahead.x, ahead.y)
assert abs(side.y) < 1e-9

g.speed = 10.0
tick(a, held=["F"]); assert g.speed > 10.0, "F speeds up"
s = g.speed
tick(a, held=["E"]); tick(a, held=["E"]); assert g.speed < s, "E slows down"
tick(a, fresh=["B"]); assert g.msg == "NO TARGET", "B fires a missile"
tick(a, held=["B"]); assert g.msg == "NO TARGET"
g.say("", 0)
tick(a, held=["B"]); tick(a, held=["B"]); assert g.msg == "", "holding B fires only once"
tick(a)

g.objs[:] = []
target = mod.game.Obj(g.types["ASTEROID"], "rock", 0.0, 0.0, 2000.0)
g.objs.append(target); g.speed = 0.0
tick(a, held=["C"]); assert target.energy < 60 and g.beam > 0, "C fires"
for name in ("JOYFIRE", "KEY_F", "KEY_SPACE"):
    e = target.energy
    for _ in range(6):
        tick(a, held=[name])
    assert target.energy < e, name
c = frame(a); fits(c)
print("joystick steering, E/F speed, B missile, C and joystick-press fire: ok")

# ---- pause on A -------------------------------------------------------------
g.speed = 20.0
tick(a, held=["E", "JOYLEFT"])              # slowing down and turning...
tick(a, held=["E", "JOYLEFT", "A"])         # ...when A is pressed
assert a.paused
for _ in range(3):
    tick(a, held=["E", "JOYLEFT"])
assert a.paused and not a.use_tilt, "directions held through the pause don't change steering"
t0 = g.time
tick(a)
assert g.time == t0, "nothing moves while paused"
c = frame(a); fits(c)
texts = [t[0] for t in c.texts]
assert "PAUSED" in texts and any("JOYSTICK" in t for t in texts)
tick(a, fresh=["C"])
assert not a.paused, "C resumes"
tick(a, fresh=["A"]); assert a.paused
tick(a, fresh=["A"]); assert not a.paused, "A resumes too"
tick(a, fresh=["A"])
tick(a, fresh=["JOYRIGHT"]); assert a.use_tilt, "joystick left/right switches to tilt"
assert any("TILT" in t[0] for t in frame(a).texts)
tick(a, fresh=["B"]); tick(a, fresh=["E"]); assert a.use_tilt, "B and E don't switch it"
tick(a, fresh=["C"]); assert not a.paused

# tilt steering, with the joystick still working and D to re-zero
ahead, side = rocks(mod, g)
tick(a)
assert a.zero == (0.0, 0.0)
Imu.reading = [0.3 * G, 0.0, G]
y = side.y
tick(a); assert side.y != y, "tilt rolls"
Imu.reading = [0.0, 0.3 * G, G]
y = ahead.y
tick(a); assert ahead.y != y, "tilt pitches"
Imu.reading = [0.4 * G, 0.4 * G, G]
tick(a, fresh=["D"])
assert abs(a.zero[0] - 0.4) < 1e-9, "D re-zeroes"
x, y = side.x, side.y
tick(a); assert abs(side.x - x) < 1e-6 and abs(side.y - y) < 1e-6
y = ahead.y
tick(a, held=["JOYUP"]); assert ahead.y < y, "joystick still steers in tilt mode"
Imu.reading = [0.0, 0.0, G]
tick(a, fresh=["A"]); tick(a, fresh=["JOYLEFT"]); assert not a.use_tilt
tick(a, fresh=["F"]); assert a.mode == "menu" and not a.paused, "F from pause goes to the menu"
assert any(t[0] == "CONTINUE" for t in frame(a).texts)
tick(a, fresh=["C"]); assert a.mode == "flight" and a.game is g
print("pause on A, steering switch, tilt with D re-zero, menu and continue: ok")

# ---- keyboard ---------------------------------------------------------------
ahead, side = rocks(mod, g)
tick(a, held=["KEY_W"]); assert ahead.y < 0
y = ahead.y
tick(a, held=["KEY_S"]); tick(a, held=["KEY_S"]); assert ahead.y > y
y = ahead.y
tick(a, held=["UP"]); assert ahead.y < y, "arrow keys steer"
y = side.y
tick(a, held=["KEY_D"]); assert side.y > y
tick(a, held=["KEY_E"]); assert g.speed > 0
tick(a, fresh=["KEY_M"]); assert g.msg == "NO TARGET"
mod.INVERT_PITCH = True
y = ahead.y
tick(a, held=["JOYUP"]); assert ahead.y > y
mod.INVERT_PITCH = False
tick(a, fresh=["KEY_P"]); assert a.paused
tick(a, fresh=["C"])
print("keyboard and INVERT_PITCH: ok")

# ---- game over --------------------------------------------------------------
tick(a, held=["C", "F"])                    # firing and accelerating when killed
g._hurt(1000.0)
for _ in range(5):
    tick(a, held=["C", "F"])
assert g.over and a.mode == "flight", "buttons still held from the fight don't skip the screen"
c = frame(a); fits(c)
assert any(t[0] == "GAME OVER" for t in c.texts)
tick(a)
tick(a, fresh=["F"]); assert a.mode == "menu"
tick(a, fresh=["C"]); assert a.mode == "flight" and not a.game.over and a.game.score == 0
a.game._hurt(1000.0)
tick(a, fresh=["C"]); assert not a.game.over
print("game over: ok")

# ---- a long played game, drawing every frame --------------------------------
random.seed(21)
g = a.game
rng = random.Random(4)
worst = {"line_to": 0, "rectangle": 0, "text": 0, "total": 0}
held = []
for i in range(6000):
    if i % 20 == 0:
        held = [n for n in ("JOYUP", "JOYDOWN", "JOYLEFT", "JOYRIGHT", "C", "E", "F")
                if rng.random() < 0.35]
    if rng.random() < 0.02:
        held = held + ["B"]
    tick(a, held=held)
    if a.game.over and rng.random() < 0.05:
        tick(a); tick(a, fresh=["C"])
    if a.mode != "flight":      # random presses after dying can wander off via the menu
        a.mode, a.menu, a.bench = "menu", 0, None
        tick(a); tick(a, fresh=["C"])
        assert a.mode == "flight"
    c = frame(a)
    total = sum(c.calls.values())
    worst["total"] = max(worst["total"], total)
    for k in ("line_to", "rectangle", "text"):
        worst[k] = max(worst[k], c.calls.get(k, 0))
    if i % 500 == 0:
        fits(c)
print("played 6000 frames with random input: ok (busiest frame %(total)d drawing calls)" % worst)

# ---- ship viewer ------------------------------------------------------------
tick(a)
a.mode, a.menu, a.paused = "menu", 0, False
tick(a)
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a.mode == "viewer"
v = a.viewer
seen = set()
for i in range(31):
    seen.add(v.name)
    c = frame(a); fits(c)
    tick(a, fresh=["C"])
assert len(seen) == 31 and v.idx == 0
tick(a, fresh=["KEY_P"]); assert v.idx == 30
tick(a, fresh=["KEY_N"]); assert v.idx == 0
r0, p0 = v.roll, v.pitch
tick(a, held=["JOYRIGHT"]); assert v.roll > r0
tick(a, held=["JOYUP"]); assert v.pitch < p0
tick(a, fresh=["F"]); assert a.mode == "menu"
print("ship viewer: ok")

# ---- tilt sensor fails mid-flight -------------------------------------------
a.menu = 0
tick(a, fresh=["C"]); assert a.mode == "flight"
if a.game.over:
    tick(a, fresh=["C"])
a.use_tilt = True
Imu.fail = True
tick(a)
assert not a.tilt_ok and not a.use_tilt
tick(a, fresh=["A"]); tick(a, fresh=["JOYLEFT"]); assert not a.use_tilt
assert any("no tilt sensor" in t[0] for t in frame(a).texts)
print("tilt sensor failure: ok")

# ---- TILT_DEFAULT -----------------------------------------------------------
pkg, mod = load()
mod.TILT_DEFAULT = True
assert pkg.AceCommander().use_tilt
print("TILT_DEFAULT: ok")

# ---- older firmware: no joystick / lettered-button names --------------------
pkg, mod = load(joystick=False)
assert mod.JOY is None and mod.FB is None
a = pkg.AceCommander()
assert a.use_tilt, "tilt is the default there"
tick(a, fresh=["CONFIRM"]); assert a.mode == "flight"
g = a.game; g.spawn_t = g.rock_t = 1e9
tick(a)
s = g.speed
tick(a, held=["UP"]); assert g.speed > s
tick(a, fresh=["LEFT"]); assert g.msg == "NO TARGET"
tick(a, fresh=["CANCEL"]); assert a.paused
assert any("TILT" in t[0] for t in frame(a).texts)
tick(a, fresh=["RIGHT"]); assert not a.use_tilt
assert any("STICK" in t[0] for t in frame(a).texts)
tick(a, fresh=["CONFIRM"]); assert not a.paused
ahead, side = rocks(mod, g)
tick(a, held=["UP"]); assert ahead.y < 0 and g.speed == 0.0
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"]); assert a.mode == "menu"
print("older firmware fallback: ok")

# ---- no accelerometer and no keyboard modules -------------------------------
pkg, mod = load(imu=False, keyboard=False)
a = pkg.AceCommander()
assert not a.use_tilt
tick(a, fresh=["C"])
for _ in range(50):
    tick(a, held=["JOYUP", "C", "F"]); frame(a)
print("no imu / no keyboard modules: ok")

# ---- ship_data.py missing ---------------------------------------------------
tmp = os.path.join(HERE, "noship")
shutil.rmtree(tmp, ignore_errors=True)
shutil.copytree(REPO, os.path.join(tmp, "ace_commander"),
                ignore=shutil.ignore_patterns("ship_data.py", "__pycache__", ".git", "tests"))
sys.path.insert(0, tmp)
sys.path.remove(PARENT)
pkg, mod = load()
assert "noship" in pkg.__file__ and mod.SHIPS == ()
a = pkg.AceCommander()
c = frame(a); fits(c)
assert any(t[0] == "ship_data.py" for t in c.texts)
tick(a, fresh=["C"]); assert a.mode == "menu"
tick(a, fresh=["F"]); assert App.minimised == 1
print("ship_data.py missing: ok")
print("ALL APP TESTS PASSED")
