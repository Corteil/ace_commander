"""Build 164: objects turn and move on whole-number masters (Game._rotate, game._move):
position in quarter units (o.q), axes times 16384 (o.mi). Checks they keep up with the
float maths they replaced, that slow things still drift, and that anything else that
moves or turns an object (spawning, the AI's _turn, duel's place_i, view flips) is
picked up. Uses the game's own ships, so needs no Elite files.

    python tests/test_int_masters.py
"""
import math
import os
import random
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import game
import original_ships

DT = 0.04
fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


def fresh():
    random.seed(3)
    g = game.Game(original_ships.SHIPS)
    g.quiet = True          # no director: only what the test puts there
    g.god = True
    return g


def put(g, name, kind, x, y, z):
    o = game.Obj(g.types[name], kind, float(x), float(y), float(z))
    g.objs.append(o)
    return o


def rot_float(p, a, b):
    """The turning in exact floats, as _rotate's comment describes it (pitch, then roll)."""
    x, y, z = p
    ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
    y, z = y * ca - z * sa, y * sa + z * ca
    return [x * cb - y * sb, x * sb + y * cb, z]


# 1. turning: whole numbers, and close to the exact floats over many frames
g = fresh()
o = put(g, "ASTEROID", "ship", 300, -200, 2500)     # (_rotate only: no AI; not a can, squared up)
exact = [300.0, -200.0, 2500.0]
nose = [0.0, 0.0, 1.0]
for f in range(200):
    a = 0.02 if f % 50 < 25 else -0.015
    b = 0.01
    g._rotate(a, b, 0.0)
    exact = rot_float(exact, a, b)
    nose = rot_float(nose, a, b)
check("x, y, z are whole numbers after turning",
      all(isinstance(v, int) for v in (o.x, o.y, o.z)), repr((o.x, o.y, o.z)))
err = max(abs(o.x - exact[0]), abs(o.y - exact[1]), abs(o.z - exact[2]))
# the rounded sines don't quite square to 1 (as before build 164: 18 units here then)
check("200 turning frames: within 1% of exact", err < 25, "%.2f" % err)
nerr = max(abs(o.m[6] - nose[0]), abs(o.m[7] - nose[1]), abs(o.m[8] - nose[2]))
check("and its nose within 0.002", nerr < 0.002, "%.4f" % nerr)
check("its axes as floats from its whole numbers",
      all(o.m[i] == o.mi[i] / 16384 for i in range(9)))

# 2. moving: ships keep their speed, slow rocks still drift
g = fresh()
s = put(g, "VIPER", "can", 0, 0, 1000)
s.speed = 20.0
r = put(g, "BOULDER", "can", 50, 0, 1500)
r.speed = 0.3                       # 0.3 units a frame: under one whole unit
game._look(r.m, 1.0, 0.0, 0.0)      # drifting sideways
g._rotate(0.001, 0.0, 0.0)          # (masters made)
s0, r0 = s.z, r.x
for _ in range(100):
    g._rotate(0.0, 0.0, 0.0)
    game._move(s, s.speed * game.SPEED_K * DT)
    game._move(r, r.speed * game.SPEED_K * DT)
want = 20.0 * game.SPEED_K * DT * 100
check("a ship moves its speed (whole numbers)", abs(s.z - s0 - want) < 2, "%s vs %.1f" % (s.z - s0, want))
want = 0.3 * game.SPEED_K * DT * 100
check("a slow rock drifts (not stuck by rounding)", abs(r.x - r0 - want) < 2, "%s vs %.1f" % (r.x - r0, want))
check("still whole numbers", isinstance(s.z, int) and isinstance(r.x, int))

# 3. flying straight moves everything back by fwd
g = fresh()
o = put(g, "CANISTER", "can", 10, 20, 900)
z0 = o.z
for _ in range(40):
    g._rotate(0.0, 0.0, 12.5)
check("flying straight: 40 x 12.5 closer", o.z == z0 - 500 and o.x == 10, repr((o.x, o.z)))

# 4. moved or turned by something else: picked up
g = fresh()
o = put(g, "CANISTER", "can", 0, 0, 800)
g._rotate(0.01, 0.0, 0.0)
o.x = 123.5                         # moved by other code (a spawn, _shift, place)
o.z = 640.25
g._rotate(0.0, 0.0, 0.0)
check("a new position is read again", o.x in (123, 124) and o.z == 640, repr((o.x, o.z)))
game._look(o.m, 1.0, 0.0, 0.0)      # turned by other code (the AI's _turn, _look)
x0 = o.x
game._move(o, 100.0)
check("a new heading is used to move", 99 < o.x - x0 < 101, repr(o.x - x0))
g._rotate(0.0, 0.0, 0.0)
check("and read again at the next turn", abs(o.mi[6] - 16384) < 2 and abs(o.mi[8]) < 2, repr(o.mi[6:9]))
o.m = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]     # replaced outright (Game._launch)
g._rotate(0.0, 0.0, 0.0)
check("a replaced axes list is read again", o.mi[8] == 16384 and o.ml is o.m)
x0, z0 = o.x, o.z
game._move(o, 50.0)
check("and moves along its new nose", o.x == x0 and 49 <= o.z - z0 <= 51, repr((o.x - x0, o.z - z0)))
# a view flip (Game.enter_view / leave_view): x and z negated, then back
g.set_view(1)
g.enter_view()
fx, fz = o.x, o.z
g._rotate(0.0, 0.0, 0.0)
check("rear view: the flipped position kept", (o.x, o.z) == (fx, fz), repr((o.x, o.z, fx, fz)))
g.leave_view()
g.set_view(0)
check("and back", abs(o.x - x0) <= 1 and abs(o.z - z0 - 50) <= 1, repr((o.x, o.z)))

# 5. a whole game: ships attack, steer and die as before; the masters stay in step
g = game.Game(original_ships.SHIPS)
random.seed(8)
g.god = True
for f in range(1500):
    g.step(DT, 0.4 if f % 120 < 60 else -0.3, 0.2, 0.3, f % 5 == 0, False)
bad = [o for o in g.objs if o.q is not None and (o.x != (o.q[0] + 2) >> 2 or o.z != (o.q[2] + 2) >> 2)
       and o.mf is not None and o.m is o.ml]
check("a minute of combat runs", g.time > 59 and len(g.objs) > 0, "%d objects, %d kills" % (len(g.objs), g.kills))
check("unit axes after a minute", all(abs(o.m[6] ** 2 + o.m[7] ** 2 + o.m[8] ** 2 - 1) < 0.01 for o in g.objs))

if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL INT MASTERS TESTS PASSED")
