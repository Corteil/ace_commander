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
choose = bs.choose
TMP_SAVE = os.path.join(HERE, "shots", "test_commander.json")
os.makedirs(os.path.dirname(TMP_SAVE), exist_ok=True)


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
assert a.cmdr is None and a.choices() == ["NEW COMMANDER", "COMBAT PRACTICE", "SHIP VIEWER", "SPEED TEST"]
c = frame(a); fits(c)
assert [t[0] for t in c.texts] == ["< NEW COMMANDER >"], "one piece of text on the title screen"
assert c.calls.get("line_to", 0) > 5, "and a ship"
tick(a, fresh=["JOYRIGHT"]); assert a.menu == 1
assert [t[0] for t in frame(a).texts] == ["< COMBAT PRACTICE >"]
tick(a, fresh=["JOYLEFT"]); assert a.menu == 0
tick(a, fresh=["JOYLEFT"]); assert a.menu == 3, "wraps round"
tick(a, fresh=["JOYRIGHT"]); assert a.menu == 0
tick(a, fresh=["JOYDOWN"]); assert a.menu == 1    # up and down work as well
tick(a, fresh=["JOYUP"]); assert a.menu == 0
tick(a, fresh=["F"]); assert App.minimised == 1 and a.mode == "menu"
# the ship tumbles for a while, flies off, and the next one comes in
t = a.title
assert t.name == "COBRA MK III"
seen = [t.name]
for i in range(3000):
    tick(a)
    if i % 7 == 0:
        fits(frame(a))
    if t.name != seen[-1]:
        seen.append(t.name)
assert seen[1] == "MAMBA" and len(seen) > 8, seen
assert not set(seen) & set(mod.title.SKIP)
print("title screen: ok (ships shown: %d)" % len(set(seen)))

# ---- flight: joystick steers, lettered buttons do the rest ------------------
random.seed(11)
choose(a, "COMBAT PRACTICE")
assert a.mode == "flight" and not a.career
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
g.say("", 0)
tick(a, fresh=["D"]); assert g.msg == "NO TARGET", "D fires a missile"
tick(a, held=["D"]); assert g.msg == "NO TARGET"
g.say("", 0)
tick(a, held=["D"]); tick(a, held=["D"]); assert g.msg == "", "holding D fires only once"
tick(a)
tick(a, fresh=["B"]); assert g.msg == "NO ENERGY BOMB", "B is the energy bomb, not fitted yet"
g.say("", 0)

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
print("joystick steering, E/F speed, D missile, C and joystick-press fire: ok")

# ---- in-flight menu on A ----------------------------------------------------
def texts(a):
    c = frame(a); fits(c)
    return [t[0] for t in c.texts]

g.speed = 20.0
tick(a, held=["E", "JOYLEFT"])              # slowing down and turning...
tick(a, held=["E", "JOYLEFT", "A"])         # ...when A is pressed
assert a.paused
for _ in range(3):
    tick(a, held=["E", "JOYLEFT"])
assert a.paused and not a.use_tilt and a.fmenu == 0, "directions held through don't do anything"
t0 = g.time
tick(a)
assert g.time == t0, "nothing moves while the menu is open"
tick(a, held=[])
tx = texts(a)
assert "PAUSED" in tx and "RESUME" in tx and "PAUSE MENU" in tx and "STATUS" not in tx
tick(a, fresh=["C"])
assert not a.paused, "C on RESUME resumes"
tick(a, fresh=["A"]); assert a.paused
tick(a, fresh=["A"]); assert not a.paused, "A resumes too"
tick(a, fresh=["A"]); tick(a, fresh=["F"]); assert not a.paused, "and so does F"
tick(a, fresh=["A"])
tick(a, fresh=["D"]); tick(a, fresh=["B"]); assert a.fmenu == 0, "lettered buttons don't move the menu"
tick(a, fresh=["JOYDOWN"]); assert a.fmenu == 1
tick(a, fresh=["C"]); assert a.fsub == "pause" and a.fmenu == 0
tx = texts(a)
assert "PAUSE MENU" in tx and "STEER: JOYSTICK" in tx and "QUIT TO TITLE" in tx
tick(a, fresh=["JOYRIGHT"]); assert a.use_tilt, "joystick left/right switches to tilt"
assert "STEER: TILT" in texts(a)
tick(a, fresh=["B"]); tick(a, fresh=["E"]); assert a.use_tilt, "B and E don't switch it"
tick(a, fresh=["C"]); assert not a.use_tilt, "C switches it too"
tick(a, fresh=["C"]); assert a.use_tilt
tick(a, fresh=["F"]); assert a.paused and a.fsub is None and a.fmenu == 1, "F goes back a page"
tick(a, fresh=["A"]); assert not a.paused

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
# in tilt steering a tap on D re-zeroes and holding it fires a missile
g.say("", 0)
z = a.zero
for _ in range(11):
    tick(a, held=["D"])
assert g.msg == "", "not yet: the hold is %.2f s" % mod.HOLD_MISSILE
tick(a, held=["D"]); assert g.msg == "NO TARGET", "held long enough: missile"
g.say("", 0)
for _ in range(20):
    tick(a, held=["D"])
assert g.msg == "", "one missile per hold"
tick(a)
assert a.zero == z, "and letting go after a hold doesn't re-zero"
Imu.reading = [0.0, 0.0, G]
tick(a, fresh=["D"]); assert a.zero == (0.0, 0.0)
tick(a, fresh=["A"]); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
tick(a, fresh=["JOYLEFT"]); assert not a.use_tilt
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a.mode == "menu" and not a.paused, "QUIT TO TITLE"
choose(a, "COMBAT PRACTICE"); assert a.mode == "flight" and a.game is g, "the fight carries on"
print("in-flight menu on A, steering switch, tilt with D tap and hold, quit and carry on: ok")

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
tick(a, fresh=["C"]); assert not a.paused
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
choose(a, "COMBAT PRACTICE"); assert a.mode == "flight" and not a.game.over and a.game.score == 0
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
        held = held + ["D"]
    tick(a, held=held)
    if a.game.over and rng.random() < 0.05:
        tick(a); tick(a, fresh=["C"])
    if a.mode != "flight":      # random presses after dying can wander off via the menu
        a.mode, a.bench = "menu", None
        tick(a); choose(a, "COMBAT PRACTICE")
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
a.mode, a.paused = "menu", False
tick(a)
choose(a, "SHIP VIEWER")
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
choose(a, "COMBAT PRACTICE"); assert a.mode == "flight"
if a.game.over:
    tick(a, fresh=["C"])
a.use_tilt = True
Imu.fail = True
tick(a)
assert not a.tilt_ok and not a.use_tilt
tick(a, fresh=["A"]); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
tick(a, fresh=["JOYLEFT"]); tick(a, fresh=["C"]); assert not a.use_tilt
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
tick(a, fresh=["RIGHT"]); assert a.menu == 1
tick(a, fresh=["CONFIRM"]); assert a.mode == "flight" and not a.career
g = a.game; g.spawn_t = g.rock_t = 1e9
tick(a)
s = g.speed
tick(a, held=["UP"]); assert g.speed > s
tick(a, fresh=["LEFT"]); assert g.msg == "NO TARGET"
tick(a, fresh=["CANCEL"]); assert a.paused
tick(a, fresh=["DOWN"]); tick(a, fresh=["CONFIRM"]); assert a.fsub == "pause"
assert any("TILT" in t[0] for t in frame(a).texts)
tick(a, fresh=["RIGHT"]); assert not a.use_tilt
assert any("STICK" in t[0] for t in frame(a).texts)
tick(a, fresh=["CANCEL"]); tick(a, fresh=["CANCEL"]); assert not a.paused, "CANCEL backs out"
ahead, side = rocks(mod, g)
tick(a, held=["UP"]); assert ahead.y < 0 and g.speed == 0.0
tick(a, fresh=["CANCEL"]); tick(a, fresh=["DOWN"]); tick(a, fresh=["CONFIRM"])
tick(a, fresh=["DOWN"]); tick(a, fresh=["CONFIRM"]); assert a.mode == "menu"
print("older firmware fallback: ok")

# ---- no accelerometer and no keyboard modules -------------------------------
pkg, mod = load(imu=False, keyboard=False)
a = pkg.AceCommander()
assert not a.use_tilt
choose(a, "COMBAT PRACTICE")
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
