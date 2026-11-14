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
assert g.lock is o and not g.locked, "in the sights, but not locked yet"
g.step(DT, 0, 0, 0, False, True)
assert g.missiles == 4 and g.msg == "NO LOCK", "a missile won't fire before it has locked"
n = 2
while not g.locked:
    g.step(DT, 0, 0, 0, False, False)
    n += 1
assert abs(n * DT - game.LOCK_TIME) <= 2 * DT, "locks after %.2f s" % (n * DT)
# another ship coming nearer the crosshair starts the lock again
other = put(g, "SIDEWINDER", "ship", 0, 0, 5000, True)
other.state = "break"; other.t = 99; other.aim = [1.0, 0.0, 0.0]
g.step(DT, 0, 0, 0, False, False)
assert g.lock is other and not g.locked and g.lock_t == 0.0
other.dead = True
g.step(DT, 0, 0, 0, False, False)
assert g.lock is o and not g.locked
o.x = 0.0        # it has been breaking sideways all this time; bring it back into the sights
for _ in range(int(game.LOCK_TIME / DT) + 2):
    g.step(DT, 0, 0, 0, False, False)
assert g.locked and g.lock is o
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
# hyperspace ------------------------------------------------------------------
g = fresh()
put(g, "PYTHON", "ship", 300, 100, 4000, True)
g.step(DT, 0, 0, 0, False, False)
assert g.lock is not None
g.start_jump()
n = 0
while not g.jumped:
    g.step(DT, 0, 0, 0, False, False)
    n += 1
    assert n < 1000
assert abs(n * DT - game.JUMP_COUNT) <= 2 * DT, n * DT
assert not g.objs and not g.new and g.lock is None and not g.locked and g.jump_t == 0
assert g.warp > 0 and g.spawn_t >= 5.0, "a quiet moment on arriving"
g.jumped = False
for _ in range(int(game.WARP_TIME / DT) + 2):
    g.step(DT, 0, 0, 0, False, False)
assert g.warp <= 0 and not g.jumped
# after a jump the old system is left behind; whoever started it sets the new one
assert g.space is None and g.pending == 0 and not g.docked
g.start_jump(); g._hurt(1e6); g.step(DT, 0, 0, 0, False, False)
assert g.over and g.jump_t == 0 and not g.jumped, "no jump once destroyed"
g.start_jump(); assert g.jump_t == 0
g.reset(); assert g.jump_t == 0 and g.warp == 0 and not g.jumped
print("hyperspace countdown, jump, arrival: ok")


# ---- the star system: planet, sun, station ----------------------------------
def dist(x, y, z):
    return math.sqrt(x * x + y * y + z * z)


def geometry(sp):
    st = sp.station
    return (dist(sp.px, sp.py, sp.pz), dist(sp.sx, sp.sy, sp.sz), dist(st.x, st.y, st.z),
            dist(sp.px - st.x, sp.py - st.y, sp.pz - st.z))


g = fresh()
g.enter(5000, "CORIOLIS", "launch", 3)
sp = g.space; st = sp.station
R = 5000 * game.PLANET_SCALE
assert sp.pr == R and sp.sr == R * game.SUN_SIZE and st.bp.name == "CORIOLIS" and sp.gov == 3
assert (st.x, st.y, st.z) == (0.0, 0.0, -game.LAUNCH_DIST), "just out of the slot, behind you"
assert abs(sp.pz - (game.STATION_ORBIT * R - game.LAUNCH_DIST)) < 1 and sp.px == sp.py == 0, "planet ahead"
assert st.m[8] > 0.999, "the slot faces the planet"
assert sp.safe and g.pending == 0 and not g.docked
assert abs(dist(sp.sx - sp.px, sp.sy - sp.py, sp.sz - sp.pz) - game.SUN_DIST * R) < 5
assert sp.sz < 0, "the sun is behind you on launching"
g.enter(500, "NO SUCH STATION", "launch")
assert g.space.station.bp.name == "CORIOLIS" and g.space.pr == 4000.0, "fallbacks"
g.enter(5000, "DODO", "launch")
assert g.space.station.bp.name == "DODO"

# turning moves the planet, sun and station together, and keeps their shape
g = fresh(3)
g.enter(6000, "CORIOLIS", "arrive", 1)
sp = g.space; st = sp.station
before = geometry(sp)
assert abs(before[2] - game.ARRIVE_DIST) < 1 and not sp.safe
assert abs(before[3] - game.STATION_ORBIT * 6000 * game.PLANET_SCALE) < 2
g.pending = 0; g.encounter_t = 1e9
g.speed = 0.0
for i in range(300):
    g.step(DT, 0.7 if i < 150 else -0.4, 0.9, -1.0, False, False)
after = geometry(sp)
for b, a in zip(before, after):
    assert abs(a - b) < b * 0.002, (before, after)
assert ortho_error(st.m) < 0.01
px, py, pz = sp.px - st.x, sp.py - st.y, sp.pz - st.z
d = dist(px, py, pz)
assert (st.m[6] * px + st.m[7] * py + st.m[8] * pz) / d > 0.999, "the slot still faces the planet"
roof = st.m[3:6]
for _ in range(25):
    g.step(DT, 0, 0, 0, False, False)
assert sum(a * b for a, b in zip(roof, st.m[3:6])) < 0.99, "the station turns about its nose"

# flying forward closes on the station; the jump drive does it JUMP_K times faster
g = fresh(4)
g.enter(6000, "CORIOLIS", "arrive")
g.pending = 0; g.encounter_t = 1e9
sp = g.space; st = sp.station
st.x, st.y, st.z = 0.0, 0.0, st.z
g.speed = game.PLAYER_MAX
z0 = st.z; g.step(DT, 0, 0, 0, False, False)
slow = z0 - st.z
assert not g.jumping and abs(slow - game.PLAYER_MAX * game.SPEED_K * DT) < 0.5
z0 = st.z; g.step(DT, 0, 0, 1.0, False, False)
assert g.jumping and abs((z0 - st.z) - slow * game.JUMP_K) < 1, z0 - st.z
o = put(g, "SIDEWINDER", "ship", 2000, 0, 8000)
g.step(DT, 0, 0, 1.0, False, False)
assert not g.jumping, "not with a ship on the radar"
o.z = 50000.0; g.step(DT, 0, 0, 1.0, False, False)
assert g.jumping, "ships beyond radar range don't stop it"
g.objs[:] = []
r = put(g, "ASTEROID", "rock", 0, 0, 5000)
g.step(DT, 0, 0, 1.0, False, False)
assert g.jumping, "rocks don't stop it"
g.objs[:] = []
g.speed = game.PLAYER_MAX - 5; g.step(DT, 0, 0, 1.0, False, False)
assert not g.jumping, "only at full speed"
g.speed = game.PLAYER_MAX; g.start_jump(); g.step(DT, 0, 0, 1.0, False, False)
assert not g.jumping, "not during a hyperspace countdown"
g.jump_t = 0.0
n = 0
while not sp.safe:
    g.step(DT, 0, 0, 1.0, False, False)
    n += 1
    assert n < 2000
g.step(DT, 0, 0, 1.0, False, False)
assert not g.jumping and sp.d_station > game.SAFE_DIST - slow * game.JUMP_K * 3, "stops at the safe zone"
print("jump drive: about %.0f s of jumping to the safe zone, at full speed %.0f s" % (
    n * DT, (game.ARRIVE_DIST - game.SAFE_DIST) / (game.PLAYER_MAX * game.SPEED_K)))
# then on to the station, which docks you
while not g.docked:
    g.step(DT, 0, 0, 1.0, False, False)
    n += 1
    assert n < 4000
assert sp.d_station < game.DOCK_DIST and not g.jumping
print("flying straight from arriving to docked: %.0f s" % (n * DT))

# encounters: the ships that meet you on arriving, then a group now and then,
# and none in the safe zone
g = fresh(5)
g.set_level(2)
g.god = True
g.enter(6000, "CORIOLIS", "arrive")
assert g.pending == g.max_hostile == 5 and g.spawn_t >= 5.0
g.speed = 0.0
seen = 0
for _ in range(1000):
    g.step(DT, 0, 0, 0, False, False)
    seen = max(seen, sum(1 for o in g.objs if o.kind == "ship"))
    if g.pending == 0:
        break
assert g.pending == 0 and seen == 5, seen
for o in list(g.objs):
    if o.kind == "ship":
        g._kill(o)
g.step(DT, 0, 0, 0, False, False)
assert g.encounter_t > 0
gaps = []
t = 0.0
quiet = True
for _ in range(int(200 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    t += DT
    ships = [o for o in g.objs if o.kind == "ship"]
    if ships and quiet:
        gaps.append(t)
        t = 0.0
        g.step(DT, 0, 0, 0, False, False)
        for _ in range(200):
            g.step(DT, 0, 0, 0, False, False)
        for o in list(g.objs):
            if o.kind == "ship":
                g._kill(o)
        g.objs[:] = [o for o in g.objs if o.kind != "missile"]
assert len(gaps) >= 3, gaps
assert all(5 < x < game.ENCOUNTER[1] + 15 for x in gaps), gaps
print("encounters %d s apart: ok" % (sum(gaps) / len(gaps)))
g.to_station(game.SAFE_DIST - 2000)
assert g.space.safe
g.objs[:] = []
g.pending = 3; g.encounter_t = 0.0; g.rock_t = 0.0
for _ in range(int(60 / DT)):
    g.step(DT, 0, 0, 0, False, False)
assert not g.objs and g.pending == 0, "nothing turns up in the safe zone"

# docking: close enough to the station; not once destroyed
g = fresh(6)
g.enter(6000, "CORIOLIS", "launch")
g.step(DT, 0, 0, 0, False, False)
assert not g.docked, "launching doesn't dock you again"
g.to_station(game.DOCK_DIST - 50)
assert g.space.station.z == game.DOCK_DIST - 50
g.step(DT, 0, 0, 0, False, False)
assert g.docked
g.docked = False; g._hurt(1e6); g.to_station(100)
g.step(DT, 0, 0, 0, False, False)
assert not g.docked

# flying into the planet or the sun is the end, except for the invincible
for which in ("planet", "sun"):
    g = fresh(7)
    g.enter(6000, "CORIOLIS", "launch")
    sp = g.space
    if which == "planet":
        sp.px, sp.py, sp.pz = 0.0, 0.0, sp.pr - 10
    else:
        sp.sx, sp.sy, sp.sz = 0.0, 0.0, sp.sr - 10
    g.god = True; g.step(DT, 0, 0, 0, False, False)
    assert not g.over
    g.god = False; g.step(DT, 0, 0, 0, False, False)
    assert g.over and g.hull == 0, which

# combat practice has no star system: waves as before
g = fresh(8)
assert g.space is None
g.spawn_t = 0.0
for _ in range(50):
    g.step(DT, 0, 0, 1.0, False, False)
assert any(o.kind == "ship" for o in g.objs) and not g.jumping
g.reset(); assert g.space is None and g.pending == 0
print("star system: planet, sun, station, safe zone, docking, crashing: ok")
print("ALL GAME TESTS PASSED")
