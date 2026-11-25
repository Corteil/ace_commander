"""Multiplayer poses (plans/MULTIPLAYER.md): the shared world's anchor (Game.set_anchor,
world_pose, place) and the 32-byte pose packet (netplay.py). Two Games stand in for
two badges: each flies, sends its world pose, and places the other's ship from it.
Uses the game's own ship data, so it runs without Elite's files."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import game, netplay, rules
SHIPS = ace_commander.ace.SHIPS
DT = 0.04
fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


def flight(seed=1):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.rules = rules.GameRules(False)
    g.rock_t = g.encounter_t = g.spawn_t = 1e9
    g.objs[:] = []
    return g


def ship(g):
    name = next(n for n in g.types if g.types[n].energy and n != "MISSILE")
    return game.Obj(g.types[name], "ship", 0.0, 0.0, 0.0)


def facing(dx, dy, dz):
    m = [0.0] * 9
    game._look(m, *game._unit(dx, dy, dz))
    return m


def close(a, b, tol):
    return all(abs(p - q) <= tol for p, q in zip(a, b))


def fly(g, n, seed, yaw=True):
    """n frames of random steering, as a player would: the world turns and slides."""
    r = random.Random(seed)
    pitch = roll = yw = 0.0
    for i in range(n):
        if i % 15 == 0:
            pitch, roll, yw = r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)
        g._rotate(pitch * game.PITCH_RATE * DT, roll * game.ROLL_RATE * DT, r.uniform(0, 30))
        if yaw:
            g._yaw(yw * game.YAW_RATE * DT)


# ---- the anchor gives back the pose it was set from
g = flight()
m0 = facing(0.3, 0.2, 0.9)
g.set_anchor(120.0, -40.0, 900.0, m0)
x, y, z, m = g.world_pose()
check("set_anchor then world_pose: same position", close((x, y, z), (120, -40, 900), 1e-6), str((x, y, z)))
check("set_anchor then world_pose: same axes", close(m, m0, 1e-9))
check("no anchor: world_pose is None", flight().world_pose() is None)

# ---- flying straight moves you along your nose in the world
g = flight()
g.set_anchor(0.0, 0.0, 0.0, facing(1, 0, 0))     # nose along the world's x
g._rotate(0.0, 0.0, 250.0)
x, y, z, m = g.world_pose()
check("straight 250: moved 250 along the nose", close((x, y, z), (250, 0, 0), 1e-6), str((x, y, z)))

# ---- the anchor follows your flying exactly: fly a random path, then the same
# path backwards (each step undone in reverse order), and you are back where you
# started in the shared world
g = flight()
start = (-300.0, 50.0, 0.0)
m0 = facing(0.2, -0.1, 1)
g.set_anchor(*start, m0)
r = random.Random(3)
steps = []
for i in range(400):
    if i % 15 == 0:
        pitch, roll, yw = r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(-1, 1)
    st = (pitch * game.PITCH_RATE * DT, roll * game.ROLL_RATE * DT, r.uniform(0, 30),
          yw * game.YAW_RATE * DT)
    steps.append(st)
    g._rotate(st[0], st[1], st[2])
    g._yaw(st[3])
x, y, z, m = g.world_pose()
travelled = math.dist(start, (x, y, z))
for a_, b_, f_, y_ in reversed(steps):
    g._yaw(-y_)
    g._rotate(0.0, 0.0, -f_)
    g._rotate(0.0, -b_, 0.0)
    g._rotate(-a_, 0.0, 0.0)
x, y, z, m = g.world_pose()
d = math.dist(start, (x, y, z))
check("fly 400 frames and back: home again", travelled > 1000 and d < 0.01,
      "%.0f units out, %.5f off" % (travelled, d))
check("  facing the same way", close(m, m0, 1e-6))

# ---- two badges: A at z -1000 facing +z, B at z +1000 facing -z (a duel's start)
a, b = flight(1), flight(2)
a.set_anchor(0.0, 0.0, -1000.0, facing(0, 0, 1))
b.set_anchor(0.0, 0.0, 1000.0, facing(0, 0, -1))
ob = ship(a)                # B's ship as A sees it
a.place(ob, *b.world_pose())
check("start: A sees B dead ahead, 2000 away", close((ob.x, ob.y, ob.z), (0, 0, 2000), 1e-6),
      str((ob.x, ob.y, ob.z)))
check("start: B's nose points back at A", close(ob.m[6:9], (0, 0, -1), 1e-9))
oa = ship(b)
b.place(oa, *a.world_pose())
check("start: B sees A dead ahead too", close((oa.x, oa.y, oa.z), (0, 0, 2000), 1e-6))

# both fly about; each still sees the other at the same distance, and A's view of
# B, turned into the world, is where B says it is
fly(a, 300, seed=11)
fly(b, 300, seed=12)
pa, pb = a.world_pose(), b.world_pose()
a.place(ob, *pb)
b.place(oa, *pa)
da = math.dist((0, 0, 0), (ob.x, ob.y, ob.z))
db = math.dist((0, 0, 0), (oa.x, oa.y, oa.z))
dw = math.dist(pa[:3], pb[:3])
check("after flying: the same distance both ways", abs(da - db) < 0.5 and abs(da - dw) < 0.5,
      "A->B %.1f  B->A %.1f  world %.1f" % (da, db, dw))
# B ahead of A in A's view <=> A behind B... check by direction: A's nose in the world
# dotted with (B - A) equals ob.z / distance
nose_a = pa[3][6:9]
cos_w = sum(n * (q - p) for n, p, q in zip(nose_a, pa[:3], pb[:3])) / dw
check("after flying: the angle off A's nose matches", abs(cos_w - ob.z / da) < 1e-3,
      "%.4f vs %.4f" % (cos_w, ob.z / da))

# ---- the packet: 32 bytes, through and back
buf = bytearray(netplay.SIZE)
pose = a.world_pose()
netplay.pack_pose(buf, 7, 65537, pose, speed=31.6, flags=netplay.FIRING)
check("packet: 32 bytes", len(buf) == 32 and netplay.struct.calcsize(netplay.FMT) == 32)
r = netplay.read_pose(buf)
check("packet: player, seq (wrapped), speed, flags", r is not None and r[0] == 7 and r[1] == 1
      and r[6] == 31 and r[7] == netplay.FIRING, str(r and r[:2] + r[6:]))
check("packet: position to a quarter unit", close(r[2:5], pose[:3], 0.126))
check("packet: axes to 1/16384, side remade", close(r[5], pose[3], 3e-4),
      str([round(p - q, 5) for p, q in zip(r[5], pose[3])]))
ob2 = ship(a)
b_pose = b.world_pose()
netplay.pack_pose(buf, 2, 0, b_pose)
_, _, x, y, z, m, _, _ = netplay.read_pose(buf)
a.place(ob2, x, y, z, m)
a.place(ob, *b_pose)
d = math.dist((ob.x, ob.y, ob.z), (ob2.x, ob2.y, ob2.z))
check("packet: B placed from the packet is where B is", d < 0.5, "%.3f units" % d)
check("packet: not ours ignored", netplay.read_pose(b"AC" + bytes(30)) is None
      and netplay.read_pose(None) is None and netplay.read_pose(buf[:20]) is None)
m9 = [0.0] * 9
check("packet: fills a given axes list (no new list)", netplay.read_pose(buf, m9)[5] is m9)
check("sequence: newer across the wrap", netplay.newer(2, 65530) and not netplay.newer(65530, 2)
      and not netplay.newer(5, 5))

# ---- the anchor is cleared with the world, and costs nothing without one
g = flight()
g.set_anchor(0.0, 0.0, 0.0, facing(0, 0, 1))
g.reset()
check("reset clears the anchor", g.anchor is None)
g._rotate(0.1, 0.1, 10.0)
g._yaw(0.1)
check("no anchor: turning still fine", g.anchor is None)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL NET POSE TESTS PASSED")
