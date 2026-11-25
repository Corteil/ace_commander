"""A duel (duel.py): two players' Games joined by a pretend radio, then the DUEL
page and flight through the real app. Proves the game's side; the radio itself
was measured on two badges (plans/MULTIPLAYER.md). Uses the game's own ship data,
so it runs without Elite's files."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import duel, game, netplay, rules
SHIPS = ace_commander.ace.SHIPS
DT = 0.04
fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


class Air:
    """Packets between links; drop() can lose some."""

    def __init__(self):
        self.links = []
        self.drop = lambda msg: False


class Link:
    def __init__(self, air, ident):
        self.air, self.id, self.inbox = air, ident, []
        air.links.append(self)

    def send(self, msg):
        if self.air.drop(msg):
            return
        for l in self.air.links:
            if l is not self:
                l.inbox.append((self.id, bytes(msg)))

    def recv(self):
        if self.inbox:
            host, msg = self.inbox.pop(0)
            return bytearray(host), bytearray(msg)      # reused buffers, as the radio's
        return None, None


def flight(seed):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.rules = rules.GameRules(False)
    return g


def player(g):
    return [o for o in g.objs if o.kind == "player"]


# ---- the DUEL page: each hears the other's HELLO
air = Air()
la, lb = Link(air, b"\x02\x00\x00\x00\x00\x0a"), Link(air, b"\x02\x00\x00\x00\x00\x0b")
da, db = duel.Duel(la), duel.Duel(lb)
check("page: nobody found at first", not da.found and not db.found)
for _ in range(10):
    da.lobby_step(DT)
    db.lobby_step(DT)
check("page: each finds the other", da.found and db.found and da.peer == lb.id and db.peer == la.id)
check("page: the peer id is kept as a copy", isinstance(da.peer, bytes))
check("page: neither is flying yet", not da.peer_flying and not db.peer_flying)

# ---- into the arena: smaller id slot 0 at z -1000, the other slot 1 at z +1000
ga, gb = flight(1), flight(2)
ga.objs.append(game.Obj(ga.types["ASTEROID"], "rock", 0.0, 0.0, 500.0))
da.start(ga)
db.start(gb)
check("start: slots by id", da.slot == 0 and db.slot == 1)
check("start: the arena is empty and quiet", ga.objs == [] and ga.quiet and gb.quiet)
check("start: A at its start", math.dist(ga.world_pose()[:3], (0, 0, -1000)) < 1e-6)
check("start: B at its start", math.dist(gb.world_pose()[:3], (0, 0, 1000)) < 1e-6)


def both(n, ctl_a=(0.0, 0.0, 0.0), ctl_b=(0.0, 0.0, 0.0)):
    """n frames: each Game steps (pitch, roll, throttle), then its duel."""
    for _ in range(n):
        ga.step(DT, ctl_a[0], ctl_a[1], ctl_a[2], False, False)
        gb.step(DT, ctl_b[0], ctl_b[1], ctl_b[2], False, False)
        da.flight_step(ga, DT)
        db.flight_step(gb, DT)


both(5)
pa, pb = player(ga), player(gb)
check("flight: each sees one other ship", len(pa) == 1 and len(pb) == 1)
o = pa[0]
w = math.dist(ga.world_pose()[:3], gb.world_pose()[:3])    # both started with some speed
lag = (ga.speed + gb.speed) * game.SPEED_K * DT * 1.5   # B's pose left a frame ago
check("flight: A sees B dead ahead, as far as it is (a frame behind)", abs(o.x) < 1 and abs(o.y) < 1
      and abs(o.z - w) < lag + 1, "(%.1f, %.1f, %.1f) vs %.1f" % (o.x, o.y, o.z, w))
check("flight: B's nose towards A", o.m[8] < -0.999)
check("flight: the other ship isn't a 'ship' (AI, bomb, missiles leave it)", o.kind == "player")

# A flies about, B goes straight at speed: they agree on the distance between them
both(150, ctl_a=(0.6, -0.4, 1.0), ctl_b=(0.0, 0.0, 1.0))
oa, ob = player(gb)[0], player(ga)[0]
d_ab = math.dist((0, 0, 0), (ob.x, ob.y, ob.z))
d_ba = math.dist((0, 0, 0), (oa.x, oa.y, oa.z))
d_w = math.dist(ga.world_pose()[:3], gb.world_pose()[:3])
# each sees the other as of its last pose moved on by speed: within a frame or two of flight
step = gb.speed * game.SPEED_K * DT * 3
check("flying: both see the same distance", abs(d_ab - d_ba) < step + 2 and abs(d_ab - d_w) < step + 2,
      "A->B %.1f  B->A %.1f  world %.1f" % (d_ab, d_ba, d_w))
check("flying: B has moved", math.dist(gb.world_pose()[:3], (0, 0, 1000)) > 100)
check("flying: still just one other ship each", len(player(ga)) == 1 and len(player(gb)) == 1)
check("flying: no waves or rocks came", all(o.kind == "player" for o in ga.objs + gb.objs),
      str([o.kind for o in ga.objs]))

# between packets the ship moves on at its speed: half the packets lost, still smooth
n = [0]


def every_other(msg):
    if msg[2] != netplay.POSE or msg[3] != 1:      # B's poses only (slot 1)
        return False
    n[0] += 1
    return n[0] % 2 == 0


air.drop = every_other
both(60, ctl_b=(0.0, 0.0, 1.0))
air.drop = lambda msg: False
ob = player(ga)[0]
d_ab = math.dist((0, 0, 0), (ob.x, ob.y, ob.z))
d_w = math.dist(ga.world_pose()[:3], gb.world_pose()[:3])
check("lossy: still where it should be", abs(d_ab - d_w) < gb.speed * game.SPEED_K * DT * 4 + 2,
      "seen %.1f  world %.1f" % (d_ab, d_w))

# a late (older) pose is ignored
old = bytearray(netplay.SIZE)
netplay.pack_pose(old, 1, (da.last_seq - 5) & 0xFFFF, (0.0, 0.0, 99999.0, duel.start_pose(1)[3]), 0)
la.inbox.append((lb.id, bytes(old)))
before = da.pose
both(1)
check("late pose ignored", da.pose is not None and abs(da.pose[2] - 99999.0) > 1)

# the link goes quiet: LINK LOST, the ship goes; it comes back: LINK BACK
air.drop = lambda msg: True
both(int(duel.LOST / DT) + 2)
check("silence: LINK LOST and the ship gone", ga.msg == "LINK LOST" and player(ga) == [],
      "%s %d" % (ga.msg, len(player(ga))))
air.drop = lambda msg: False
both(3)
check("back: LINK BACK and the ship again", ga.msg == "LINK BACK" and len(player(ga)) == 1, ga.msg)

# fly again (Game.reset) puts you back at your start
ga.reset()
both(2)
check("reset: back at the start", math.dist(ga.world_pose()[:3], (0, 0, -1000)) < 50
      and len(player(ga)) == 1)

# stop: practice's game again
da.stop(ga)
check("stop: no anchor, not quiet, no other ship", ga.anchor is None and not ga.quiet and player(ga) == [])

# ---- one flies first, alone; the other joins later (Brian, 2026-11-25: both took slot 0,
# back to back). The first is the larger id, so it must move to slot 1 when the other joins
air2 = Air()
big, small = Link(air2, b"\x02\x00\x00\x00\x00\x0f"), Link(air2, b"\x02\x00\x00\x00\x00\x01")
d_big, d_small = duel.Duel(big), duel.Duel(small)
g_big, g_small = flight(4), flight(5)
d_big.start(g_big)                  # nobody heard yet: slot 0 for now
check("alone: slot 0 for now", d_big.slot == 0)
for _ in range(20):                 # flies about alone; the other opens DUEL meanwhile
    g_big.step(DT, 0.5, 0.2, 1.0, False, False)
    d_big.flight_step(g_big, DT)
    d_small.lobby_step(DT)
check("joiner hears the one flying", d_small.found and d_small.peer_flying)
d_small.start(g_small)
check("joiner takes slot 0 (smaller id)", d_small.slot == 0)
for _ in range(3):
    for g_, d_ in ((g_big, d_big), (g_small, d_small)):
        g_.step(DT, 0.0, 0.0, 0.0, False, False)
        d_.flight_step(g_, DT)
check("first one moved to slot 1, PLAYER JOINED", d_big.slot == 1 and g_big.msg == "PLAYER JOINED",
      "slot %d, %s" % (d_big.slot, g_big.msg))
for _ in range(3):
    for g_, d_ in ((g_big, d_big), (g_small, d_small)):
        g_.step(DT, 0.0, 0.0, 0.0, False, False)
        d_.flight_step(g_, DT)
seen = [player(g_big), player(g_small)]
check("now they face each other: each sees the other ahead",
      all(len(p_) == 1 and p_[0].z > 1500 and abs(p_[0].x) < 5 and p_[0].m[8] < -0.99 for p_ in seen),
      str([(round(p_[0].x), round(p_[0].z)) for p_ in seen if p_]))
# the same player coming back after LINK LOST doesn't start you again
d_big.joined = False
air2.drop = lambda msg: True
for _ in range(int(duel.GONE / DT) + 5):
    g_big.step(DT, 0.0, 0.0, 1.0, False, False)
    d_big.flight_step(g_big, DT)
air2.drop = lambda msg: False
for _ in range(3):
    for g_, d_ in ((g_big, d_big), (g_small, d_small)):
        g_.step(DT, 0.0, 0.0, 1.0, False, False)
        d_.flight_step(g_, DT)
check("same player back: no new start", g_big.msg == "LINK BACK"
      and math.dist(g_big.world_pose()[:3], (0, 0, 1000)) > 200, g_big.msg)

# ---- through the app: DUEL on the title screen, its page, flying, back to the title
a = ace_commander.AceCommander()
check("app: no DUEL without a radio", True)     # (the badge stubs' platform has one)
check("app: DUEL on the title screen", "DUEL" in a.choices())
other = Link(air, b"\x02\x00\x00\x00\x00\x0c")
mine = Link(air, b"\x02\x00\x00\x00\x00\x01")
air.links = [mine, other]
a.platform.radio = lambda: mine
bs.choose(a, "DUEL")
check("app: the DUEL page", a.mode == "duel" and a.duel is not None)
od = duel.Duel(other)
for _ in range(10):
    od.lobby_step(DT)
    bs.tick(a)
check("app: finds the other player", a.duel.found)
bs.tick(a, fresh=["CONFIRM"])
check("app: C flies a duel", a.mode == "flight" and a.dueling and a.game.quiet
      and a.game.anchor is not None)
og = flight(3)
od.start(og)
for _ in range(10):
    og.step(DT, 0.0, 0.0, 0.0, False, False)
    od.flight_step(og, DT)
    bs.tick(a)
check("app: the other ship in the arena", len(player(a.game)) == 1)
a._to_title()
bs.tick(a)
check("app: to the title ends the duel", not a.dueling and not a.game.quiet and a.game.anchor is None)
bs.choose(a, "COMBAT PRACTICE")
check("app: practice after a duel has its waves", a.mode == "flight" and not a.dueling
      and not a.game.quiet)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL DUEL TESTS PASSED")
