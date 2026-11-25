"""A duel (duel.py): the lobby, hosting and joining, names and ship colours, then two
players' Games flying with a pretend radio between them, and the DUEL pages through
the real app. Proves the game's side; the radio itself was measured on two badges
(plans/MULTIPLAYER.md). Uses the game's own ship data, so it runs without Elite's files."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import cockpit, duel, game, netplay, rules
SHIPS = ace_commander.ace.SHIPS
DT = 0.04
fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


class Air:
    """Packets between links; drop(msg) can lose some."""

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


def lobby(duels, n=10):
    for _ in range(n):
        for d in duels:
            d.lobby_step(DT)


def ID(n):
    return bytes([2, 0, 0, 0, 0, n])


# ---- the lobby: everyone sees everyone, with names and colours
air = Air()
la, lb, lc = Link(air, ID(10)), Link(air, ID(11)), Link(air, ID(12))
da = duel.Duel(la, "Alice", 2)
db = duel.Duel(lb, "bob", 5)
dc = duel.Duel(lc, "CAROL", 0)
lobby([da, db, dc])
check("lobby: each sees the other two", [p.name for p in da.lobby()] == ["BOB", "CAROL"]
      and [p.name for p in db.lobby()] == ["ALICE", "CAROL"])
check("lobby: names in capitals, colours passed",
      next(p for p in db.lobby() if p.name == "ALICE").colour == 2
      and next(p for p in da.lobby() if p.name == "BOB").colour == 5)
check("lobby: no games to join yet", da.hosts() == [] and db.hosts() == [])

# ---- one hosts; the others see the game; one joins, the host sees who
da.host()
lobby([da, db, dc])
check("host: B and C see A's game", [p.name for p in db.hosts()] == ["ALICE"]
      and [p.name for p in dc.hosts()] == ["ALICE"])
check("host: nobody joined yet; start does nothing", da.other is None and not da.start_game())
db.join(db.hosts()[0])
lobby([da, db, dc])
check("join: the host has B as its guest, with name and colour",
      da.other is not None and da.other.name == "BOB" and da.other.colour == 5)
check("join: B knows it is accepted", db.accepted())
check("join: the game is full: C no longer sees it", dc.hosts() == [])
dc.join(next(p for p in dc.lobby() if p.name == "ALICE"))     # tries anyway
lobby([da, db, dc])
check("full: C is not taken; B stays the guest", da.other.name == "BOB" and not dc.accepted())
dc.leave()

# ---- the host starts; START reaches the guest even when the first ones are lost
lost = [0]


def lose_two_starts(msg):
    if msg[2] == duel.START_PKT and lost[0] < 2:
        lost[0] += 1
        return True
    return False


air.drop = lose_two_starts
check("start: the host can start now", da.start_game() and da.go)
ga, gb = flight(1), flight(2)
ga.objs.append(game.Obj(ga.types["ASTEROID"], "rock", 0.0, 0.0, 500.0))
da.start(ga)
for _ in range(10):                 # the host flies; the guest is still on its page
    ga.step(DT, 0.0, 0.0, 0.0, False, False)
    da.flight_step(ga, DT)
    db.lobby_step(DT)
    if db.go:
        break
air.drop = lambda msg: False
check("start: a repeated START got through", db.go and lost[0] == 2)
db.start(gb)
check("start: host at START[0], guest at START[1]", da.slot == 0 and db.slot == 1)
check("start: the arena is empty and quiet", ga.objs == [] and ga.quiet and gb.quiet)
check("start: 'VS' the other's name", gb.msg == "VS ALICE", gb.msg)


def both(n, ctl_a=(0.0, 0.0, 0.0), ctl_b=(0.0, 0.0, 0.0)):
    """n frames: each Game steps (pitch, roll, throttle), then its duel."""
    for _ in range(n):
        ga.step(DT, ctl_a[0], ctl_a[1], ctl_a[2], False, False)
        gb.step(DT, ctl_b[0], ctl_b[1], ctl_b[2], False, False)
        da.flight_step(ga, DT)
        db.flight_step(gb, DT)
        dc.lobby_step(DT)


ga.reset()                          # both from their starts at once, for the checks below
both(5)
pa, pb = player(ga), player(gb)
check("flight: each sees one other ship", len(pa) == 1 and len(pb) == 1)
o = pa[0]
w = math.dist(ga.world_pose()[:3], gb.world_pose()[:3])
lag = (ga.speed + gb.speed) * game.SPEED_K * DT * 1.5   # B's pose left a frame ago
check("flight: A sees B dead ahead, as far as it is (a frame behind)", abs(o.x) < 1 and abs(o.y) < 1
      and abs(o.z - w) < lag + 1, "(%.1f, %.1f, %.1f) vs %.1f" % (o.x, o.y, o.z, w))
check("flight: B's nose towards A", o.m[8] < -0.999)
check("flight: B's ship in B's paint, with B's name", o.rgb == cockpit.ship_rgb(5) and o.label == "BOB")
check("flight: A's ship in A's paint for B", pb[0].rgb == cockpit.ship_rgb(2) and pb[0].label == "ALICE")
check("flight: the other ship isn't a 'ship' (AI, bomb, missiles leave it)", o.kind == "player")
check("flight: the lobby sees them flying", all(p.role == duel.FLYING for p in dc.lobby()
                                                if p.name in ("ALICE", "BOB")))

# A flies about, B goes straight at speed: they agree on the distance between them
both(150, ctl_a=(0.6, -0.4, 1.0), ctl_b=(0.0, 0.0, 1.0))
oa, ob = player(gb)[0], player(ga)[0]
d_ab = math.dist((0, 0, 0), (ob.x, ob.y, ob.z))
d_ba = math.dist((0, 0, 0), (oa.x, oa.y, oa.z))
d_w = math.dist(ga.world_pose()[:3], gb.world_pose()[:3])
step = gb.speed * game.SPEED_K * DT * 3
check("flying: both see the same distance", abs(d_ab - d_ba) < step + 2 and abs(d_ab - d_w) < step + 2,
      "A->B %.1f  B->A %.1f  world %.1f" % (d_ab, d_ba, d_w))
check("flying: no waves or rocks came", all(o.kind == "player" for o in ga.objs + gb.objs),
      str([o.kind for o in ga.objs]))

# between packets the ship moves on at its speed: half of B's poses lost, still in place
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

# a late (older) pose is ignored; a stranger's pose is ignored
old = bytearray(netplay.SIZE)
netplay.pack_pose(old, 1, (da.last_seq - 5) & 0xFFFF, (0.0, 0.0, 99999.0, duel.start_pose(1)[3]), 0)
la.inbox.append((lb.id, bytes(old)))
far = bytearray(netplay.SIZE)
netplay.pack_pose(far, 1, (da.last_seq + 5) & 0xFFFF, (0.0, 0.0, 99999.0, duel.start_pose(1)[3]), 0)
la.inbox.append((lc.id, bytes(far)))
both(1)
check("late pose and a stranger's pose ignored", da.pose is not None and abs(da.pose[2] - 99999.0) > 1)

# the link goes quiet: LINK LOST, the ship goes; it comes back: LINK BACK
air.drop = lambda msg: True
both(int(duel.LOST / DT) + 2)
check("silence: LINK LOST and the ship gone", ga.msg == "LINK LOST" and player(ga) == [],
      "%s %d" % (ga.msg, len(player(ga))))
air.drop = lambda msg: False
both(3)
check("back: LINK BACK and the ship again", ga.msg == "LINK BACK" and len(player(ga)) == 1, ga.msg)

# fly again (Game.reset) puts you back at your end
ga.reset()
both(2)
check("reset: back at the start", math.dist(ga.world_pose()[:3], (0, 0, -1000)) < 50
      and len(player(ga)) == 1)

# stop: practice's game again, and back in the lobby
da.stop(ga)
check("stop: no anchor, not quiet, no other ship", ga.anchor is None and not ga.quiet and player(ga) == [])
check("stop: back in the lobby", da.role == duel.LOBBY and da.other is None and not da.flying)

# ---- through the app: DUEL, the lobby, hosting, the other joins, start, back to the title
air2 = Air()
mine, theirs = Link(air2, ID(1)), Link(air2, ID(9))
a = ace_commander.AceCommander()
check("app: DUEL on the title screen", "DUEL" in a.choices())
a.platform.radio = lambda: mine
bs.choose(a, "DUEL")
check("app: the lobby", a.mode == "duel" and a.duel is not None and a.duel.role == duel.LOBBY)
check("app: the commander's name goes to the others",
      a.duel.name == ace_commander.ace.cmdr_name(a.cmdr).upper()[:16])
od = duel.Duel(theirs, "ZED", 3)
for _ in range(10):
    od.lobby_step(DT)
    bs.tick(a)
check("app: sees ZED in the lobby", [p.name for p in a.duel.lobby()] == ["ZED"])
bs.tick(a, fresh=["CONFIRM"])           # HOST A GAME
check("app: hosting", a.duel.role == duel.HOST)
for _ in range(10):
    od.lobby_step(DT)
    bs.tick(a)
od.join(od.hosts()[0])
for _ in range(10):
    od.lobby_step(DT)
    bs.tick(a)
check("app: ZED joined", a.duel.other is not None and a.duel.other.name == "ZED" and od.accepted())
bs.tick(a, fresh=["CONFIRM"])           # start
bs.tick(a)
check("app: C starts the duel", a.mode == "flight" and a.dueling and a.game.quiet
      and a.game.anchor is not None)
for _ in range(5):
    od.lobby_step(DT)
check("app: ZED was told to start", od.go)
og = flight(3)
od.start(og)
for _ in range(10):
    og.step(DT, 0.0, 0.0, 0.0, False, False)
    od.flight_step(og, DT)
    bs.tick(a)
ps = player(a.game)
check("app: ZED's ship in the arena, in ZED's paint", len(ps) == 1 and ps[0].rgb == cockpit.ship_rgb(3))
a._to_title()
bs.tick(a)
check("app: to the title ends the duel", not a.dueling and not a.game.quiet and a.game.anchor is None)
bs.choose(a, "COMBAT PRACTICE")
check("app: practice after a duel has its waves", a.mode == "flight" and not a.dueling
      and not a.game.quiet)

# ---- the joining side through the app
air3 = Air()
mine3, host3 = Link(air3, ID(2)), Link(air3, ID(8))
b = ace_commander.AceCommander()
b.platform.radio = lambda: mine3
bs.choose(b, "DUEL")
hd = duel.Duel(host3, "HAL", 1)
hd.host()
for _ in range(10):
    hd.lobby_step(DT)
    bs.tick(b)
bs.tick(b, fresh=["JOYDOWN"])           # down to JOIN HAL
check("app join: JOIN HAL is the second line", b.d_sel == 1 and b.duel.hosts()[0].name == "HAL")
bs.tick(b, fresh=["CONFIRM"])
for _ in range(10):
    hd.lobby_step(DT)
    bs.tick(b)
check("app join: accepted by HAL", b.duel.role == duel.JOIN and b.duel.accepted() and hd.other is not None)
hd.start_game()
for _ in range(3):
    bs.tick(b)
check("app join: HAL's START flies the guest from START[1]", b.mode == "flight" and b.dueling
      and b.duel.slot == 1 and math.dist(b.game.world_pose()[:3], (0, 0, 1000)) < 50)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL DUEL TESTS PASSED")
