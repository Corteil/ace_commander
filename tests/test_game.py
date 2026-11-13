import math
import random
import sys

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)        # game.py and ship_data.py are imported directly
import game
import ship_data

SHIPS = ship_data.SHIPS
DT = 0.04


def fresh(seed=1):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.spawn_t = 1e9   # no surprise arrivals unless a test wants them
    g.rock_t = 1e9
    return g


def put(g, name, kind, x, y, z, face_player=False):
    o = game.Obj(g.types[name], kind, float(x), float(y), float(z))
    if face_player:
        d = math.sqrt(x * x + y * y + z * z)
        game._look(o.m, -x / d, -y / d, -z / d)
    g.objs.append(o)
    return o


def ortho_error(m):
    worst = 0.0
    rows = (m[0:3], m[3:6], m[6:9])
    for i in range(3):
        for j in range(3):
            dot = sum(a * b for a, b in zip(rows[i], rows[j]))
            worst = max(worst, abs(dot - (1.0 if i == j else 0.0)))
    return worst


# 1. steering directions ----------------------------------------------------
g = fresh()
o = put(g, "ASTEROID", "rock", 0, 0, 3000)
g.speed = 0.0
g.step(DT, 1.0, 0.0, 0.0, False, False)        # nose up
assert o.y < -1 and abs(o.x) < 1e-6, (o.x, o.y)   # thing ahead drops down the screen
g = fresh()
o = put(g, "ASTEROID", "rock", 1000, 0, 3000)
g.speed = 0.0
g.step(DT, 0.0, 1.0, 0.0, False, False)        # roll right
assert o.y > 1 and o.x < 1000, (o.x, o.y)         # thing on the right rises
g = fresh()
o = put(g, "ASTEROID", "rock", 0, 0, 3000)
g.speed = 20.0
g.step(DT, 0.0, 0.0, 0.0, False, False)
assert abs(o.z - (3000 - 20 * game.SPEED_K * DT)) < 1e-6, o.z
g.step(1.0, 0.0, 0.0, 1.0, False, False)       # dt is capped at 0.1
assert abs(g.speed - (20.0 + game.THROTTLE_RATE * 0.1)) < 1e-6, g.speed
for _ in range(100):
    g.step(DT, 0, 0, 1.0, False, False)
assert g.speed == game.PLAYER_MAX
for _ in range(200):
    g.step(DT, 0, 0, -1.0, False, False)
assert g.speed == 0.0
print("steering, throttle: ok")

# 2. look/turn keep a proper rotation ---------------------------------------
random.seed(2)
m = [1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0]
for _ in range(500):
    d = game._unit(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))
    game._turn(m, d[0], d[1], d[2], 0.3)
    game._roll(m, 0.1)
    assert ortho_error(m) < 1e-6
    # right-handed like the identity: side = roof x nose
    cx = m[4] * m[8] - m[5] * m[7]
    assert abs(cx - m[0]) < 1e-6
for d in ((0, 1, 0), (0, -1, 0), (1, 0, 0), (0, 0, -1)):
    game._look(m, float(d[0]), float(d[1]), float(d[2]))
    assert ortho_error(m) < 1e-9 and abs(m[6] - d[0]) + abs(m[7] - d[1]) + abs(m[8] - d[2]) < 1e-9
m = [1.0, 0, 0, 0, 1.0, 0, 0, 0, 1.0]
game._turn(m, 0.0, 0.0, -1.0, 0.2)   # exactly behind: must not blow up
assert ortho_error(m) < 1e-6
print("orientation maths: ok")

# 3. laser ------------------------------------------------------------------
g = fresh()
o = put(g, "SIDEWINDER", "ship", 0, 0, 2500, True)
o.state = "break"; o.t = 99; o.aim = [0.0, 0.0, 1.0]   # keep it from shooting back
g.speed = 0.0
shots = 0
for _ in range(400):
    g.step(DT, 0, 0, 0, True, False)
    if o.dead:
        break
assert o.dead and g.kills == 1 and g.score >= 10, (o.energy, g.kills, g.score)
assert g.booms, "an explosion appears"
print("laser kill: ok (score %d)" % g.score)

g = fresh()
near = put(g, "ASTEROID", "rock", 100, 0, 3000)      # within aim assist (150 at this range)
far = put(g, "ASTEROID", "rock", 700, 0, 3000)       # well off the crosshair
behind = put(g, "ASTEROID", "rock", 0, 0, -500)
g.speed = 0.0
e0 = (near.energy, far.energy, behind.energy)
g.step(DT, 0, 0, 0, True, False)
assert near.energy < e0[0] and far.energy == e0[1] and behind.energy == e0[2]
g = fresh()
a = put(g, "ASTEROID", "rock", 0, 0, 4000)
b = put(g, "ASTEROID", "rock", 0, 0, 2000)
g.speed = 0.0
g.step(DT, 0, 0, 0, True, False)
assert b.energy < 60 and a.energy == 60, "the nearer one takes the hit"
g = fresh()
c = put(g, "ASTEROID", "rock", 0, 0, game.LASER_RANGE + 500)
g.speed = 0.0
g.step(DT, 0, 0, 0, True, False)
assert c.energy == 60, "out of range"
print("laser aim, range, nearest-first: ok")

g = fresh()
g.speed = 0.0
t_hot = None
for i in range(2000):
    g.step(DT, 0, 0, 0, True, False)
    if g.hot and t_hot is None:
        t_hot = g.time
        break
assert t_hot is not None and 5 < t_hot < 30, t_hot
beam_while_hot = False
for i in range(40):
    g.step(DT, 0, 0, 0, True, False)
    assert g.hot or g.heat < 0.5
for i in range(200):
    g.step(DT, 0, 0, 0, False, False)
assert not g.hot and g.heat < 0.5
print("laser overheat after %.1fs of continuous fire, then recovers: ok" % t_hot)

# 4. missiles ---------------------------------------------------------------
g = fresh()
g.speed = 0.0
g.step(DT, 0, 0, 0, False, True)
assert g.missiles == 4 and g.msg == "NO TARGET"
o = put(g, "PYTHON", "ship", 300, 100, 4000, True)
o.state = "break"; o.t = 99; o.aim = [1.0, 0.0, 0.0]
g.step(DT, 0, 0, 0, False, False)
assert g.lock is o
g.step(DT, 0, 0, 0, False, True)
assert g.missiles == 3 and any(x.kind == "pmissile" for x in g.objs)
e0 = o.energy
for _ in range(400):
    g.step(DT, 0, 0, 0, False, False)
    if o.energy < e0:
        break
assert o.energy == e0 - game.MISSILE_DAMAGE, (o.energy, e0)
assert not any(x.kind == "pmissile" for x in g.objs)
print("player missile homes and hits: ok")

g = fresh()
g.speed = 0.0
ms = put(g, "MISSILE", "missile", 0, 0, 3000, True)
ms.t = 12.0
for _ in range(400):
    g.step(DT, 0, 0, 0, False, False)
    if ms.dead:
        break
assert ms.dead and g.shield == 70.0, g.shield
g = fresh()
g.speed = 0.0
ms = put(g, "MISSILE", "missile", 0, 0, 3000, True)
ms.t = 12.0
for _ in range(40):
    g.step(DT, 0, 0, 0, True, False)
assert ms.dead and g.shield == 100.0 and g.score == 5, (g.shield, g.score)
print("enemy missile hits, or can be shot down: ok")

# 5. collisions -------------------------------------------------------------
g = fresh()
g.speed = 10.0
put(g, "CANISTER", "can", 0, 0, 200)
for _ in range(60):
    g.step(DT, 0, 0, 0, False, False)
assert g.cargo == 1 and g.score == 25 and g.shield == 100.0
g = fresh()
g.speed = 30.0
rock = put(g, "ASTEROID", "rock", 0, 0, 400)
for _ in range(30):
    g.step(DT, 0, 0, 0, False, False)
assert g.shield < 100.0 and g.speed < 30.0, (g.shield, g.speed)
print("scooping cargo and ramming rocks: ok")

# 6. enemies attack, and the game ends --------------------------------------
random.seed(5)
g = game.Game(SHIPS)
steps = 0
while not g.over and steps < 60000:
    g.step(DT, 0, 0, 0, False, False)
    steps += 1
    assert len(g.objs) <= game.MAX_OBJECTS + 4
assert g.over and g.hull == 0.0, "sitting still gets you killed"
print("idle player is destroyed after %.0fs: ok" % g.time)
t0 = g.time
for _ in range(100):
    g.step(DT, 1, 1, 1, True, True)       # input is ignored once it's over
assert g.speed < 14 and g.kills == 0
g.reset()
assert not g.over and g.hull == 100.0 and g.objs == [] and g.score == 0
print("game over and reset: ok")

# 7. a simple autopilot can win fights --------------------------------------
def autopilot(g):
    t = None
    best = 1e18
    for o in g.objs:
        if o.kind in ("ship", "missile"):
            d = o.x * o.x + o.y * o.y + o.z * o.z
            if d < best:
                best, t = d, o
    if t is None:
        return 0.0, 0.0, 0.0, False, False
    d = math.sqrt(best)
    # roll until the target is straight up or down, then pitch on to it
    roll = max(-1.0, min(1.0, -t.x / d * 4))
    pitch = max(-1.0, min(1.0, t.y / d * 6)) if t.z > 0 else 1.0
    aimed = t.z > 0 and (t.x * t.x + t.y * t.y) < (t.z * 0.05) ** 2
    return pitch, roll, 0.3 if d > 2500 else -0.3, aimed, False

total_kills = 0
worst_ortho = 0.0
for seed in range(6):
    random.seed(100 + seed)
    g = game.Game(SHIPS)
    steps = 0
    while not g.over and g.time < 240:
        p, r, th, f, ms = autopilot(g)
        g.step(DT, p, r, th, f, ms)
        for o in g.objs:
            assert all(math.isfinite(v) for v in (o.x, o.y, o.z))
            worst_ortho = max(worst_ortho, ortho_error(o.m))
    total_kills += g.kills
    print("  seed %d: %3.0fs  kills %2d  wave %d  score %4d  %s" % (
        seed, g.time, g.kills, g.wave, g.score, "destroyed" if g.over else "alive"))
assert total_kills >= 6, total_kills
# steering turns everything in whole-number steps of 1/16384, so directions are a
# little out of true; this is how far, as a fraction (0.01 would be 1%)
print("  worst direction error %.5f" % worst_ortho)
assert worst_ortho < 0.01, worst_ortho
print("autopilot games: %d kills in total: ok" % total_kills)

# 8. soak: random thrashing for a long time ---------------------------------
random.seed(9)
g = game.Game(SHIPS)
rng = random.Random(77)
restarts = 0
p = r = th = 0.0
f = ms = False
for i in range(40000):   # about 27 minutes of play
    if i % 15 == 0:
        p, r, th = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1)
        f, ms = rng.random() < 0.6, rng.random() < 0.1
    g.step(rng.choice((0.02, 0.04, 0.07, 0.2)), p, r, th, f, ms)
    assert len(g.objs) <= game.MAX_OBJECTS + 4 and len(g.booms) <= 4
    if g.over and rng.random() < 0.01:
        g.reset()
        restarts += 1
print("soak run: 40000 steps, %d restarts, no errors: ok" % restarts)

# 9. ship data without stats, or with hardly any ships ----------------------
random.seed(3)
bare = tuple(s[:4] for s in SHIPS)
g = game.Game(bare)
for _ in range(3000):
    g.step(DT, 0.2, 0.1, 0.0, True, True)
one = tuple(s for s in SHIPS if s[0] == "ADDER")
g = game.Game(one)
assert g.missiles == 0
for _ in range(3000):
    g.step(DT, 0.2, 0.1, 0.0, True, True)
g = game.Game(())
for _ in range(500):
    g.step(DT, 0.2, 0.1, 0.0, True, True)
print("missing stats / one ship / no ships: ok")
print("ALL GAME TESTS PASSED")
