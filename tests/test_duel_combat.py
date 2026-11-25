"""Duel combat (duel.py, Brian 2026-11-25): lasers, missiles and ramming between two
players, the ECM by hand, being destroyed and flying again. Two Games on a pretend
radio; they start 2000 apart here (not 8000) so missiles arrive quickly. Uses the
game's own ship data, so it runs without Elite's files."""
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
duel.START = ((0.0, 0.0, -1000.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1000.0, 0.0, 0.0, -1.0))
duel.START_Z = 1000.0


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


class Air:
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
            return bytearray(host), bytearray(msg)
        return None, None


def flight(seed):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.rules = rules.GameRules(False)
    g.ecm = True                # practice flies with an ECM
    g.missiles = 4
    return g


def pair():
    air = Air()
    h = duel.Duel(Link(air, bytes([2, 0, 0, 0, 0, 1])), "ANN", 2)
    j = duel.Duel(Link(air, bytes([2, 0, 0, 0, 0, 2])), "BEN", 5)
    h.host()
    for _ in range(10):
        h.lobby_step(DT)
        j.lobby_step(DT)
    j.join(j.hosts()[0])
    for _ in range(10):
        h.lobby_step(DT)
        j.lobby_step(DT)
    h.start_game()
    ga, gb = flight(1), flight(2)
    h.start(ga)
    j.lobby_step(DT)
    j.start(gb)
    return air, h, ga, j, gb


def player(g):
    return [o for o in g.objs if o.kind == "player"]


def frames(n, a_ctl=None, b_ctl=None):
    """n frames; a_ctl / b_ctl: (pitch, roll, throttle, fire, missile) or None (sit still)."""
    for _ in range(n):
        for g_, d_, c in ((ga, da, a_ctl), (gb, db, b_ctl)):
            p, r, t, f, m = c or (0.0, 0.0, -1.0, False, False)
            g_.step(DT, p, r, t, f, m)
            d_.flight_step(g_, DT)


def energy(g):
    return g.shield + g.hull


air, da, ga, db, gb = pair()
ga.speed = gb.speed = 0.0
frames(5)
check("start: the ECM is by hand in a duel", ga.rules.manual_ecm and gb.rules.manual_ecm)
check("start: each game knows its duel", ga.net is da and gb.net is db)
check("start: each sees the other ahead", len(player(ga)) == 1 and player(ga)[0].z > 1500)

# ---- lasers: A fires at B, dead ahead: B takes the damage, A sees its hit
before = energy(gb)
frames(1, a_ctl=(0.0, 0.0, -1.0, True, False))
frames(2)
check("laser: B takes A's laser damage", abs((before - energy(gb)) - ga.laser_damage / gb.tough) < 0.01,
      "%.2f lost, laser %.2f" % (before - energy(gb), ga.laser_damage))
hits = []
for _ in range(3):
    frames(1, a_ctl=(0.0, 0.0, -1.0, True, False))
    hits.append(player(ga)[0].hit)
check("laser: A's view shows the hit", max(hits) > 0, str(hits))
# B sees A's laser, aimed at it
frames(1, a_ctl=(0.0, 0.0, -1.0, True, False))
frames(1, a_ctl=(0.0, 0.0, -1.0, True, False))
check("laser: B sees A's beam (A is aiming at B)", player(gb)[0].beam > 0)
# A turned well away: B sees no beam at it
ob = player(gb)[0]
ob.beam = 0.0
frames(25, a_ctl=(1.0, 0.0, -1.0, False, False))
frames(1, a_ctl=(0.0, 0.0, -1.0, True, False))
frames(1)
check("laser: aimed away, no beam drawn at B", player(gb)[0].beam <= 0)

# ---- missiles: A locks on to B and fires; B's game flies it at B; it hits; A's copy goes
air, da, ga, db, gb = pair()
ga.speed = gb.speed = 0.0
frames(int(game.LOCK_TIME / DT) + 5)
check("missile: A locks on to B's ship", ga.locked and ga.lock is not None and ga.lock.kind == "player")
before = energy(gb)
frames(1, a_ctl=(0.0, 0.0, -1.0, False, True))
frames(1)
mb = [o for o in gb.objs if o.kind == "missile"]
ma = [o for o in ga.objs if o.kind == "pmissile"]
check("missile: B has an incoming missile, A a copy", len(mb) == 1 and len(ma) == 1 and ma[0].ghost,
      "%d %d" % (len(mb), len(ma)))
check("missile: INCOMING MISSILE on B", gb.msg == "INCOMING MISSILE", gb.msg)
check("missile: one missile used", ga.missiles == 3)
frames(int(3.0 / DT))
check("missile: it hit B (the ECM didn't fire by itself)", energy(gb) < before - 20 and not mb[0].ecmed,
      "%.1f -> %.1f" % (before, energy(gb)))
check("missile: A's copy is gone", not [o for o in ga.objs if o.kind == "pmissile" and not o.dead]
      and da.ghosts == {})
check("missile: B's game said GONE (no missile left on its list)", db.incoming == {})

# ---- the ECM by hand: B destroys A's missile; A hears "ECM"
air, da, ga, db, gb = pair()
ga.speed = gb.speed = 0.0
frames(int(game.LOCK_TIME / DT) + 5)
frames(1, a_ctl=(0.0, 0.0, -1.0, False, True))
frames(3)
before = energy(gb)
check("ecm: B fires its ECM", gb.fire_ecm())
frames(3)
check("ecm: the missile is destroyed, B unhurt (but for the ECM's cost)",
      not [o for o in gb.objs if o.kind == "missile" and not o.dead] and energy(gb) >= before - game.ECM_COST - 0.01)
check("ecm: A hears ECM and its copy goes", ga.msg == "ECM" and da.ghosts == {}, ga.msg)

# repeated missile packets don't make two missiles
air, da, ga, db, gb = pair()
ga.speed = gb.speed = 0.0
frames(int(game.LOCK_TIME / DT) + 5)
frames(1, a_ctl=(0.0, 0.0, -1.0, False, True))
frames(2)
check("missile sent 3 times: one missile at B", len([o for o in gb.objs if o.kind == "missile"]) == 1)

# ---- ramming: each game hurts its own ship, once, not every frame
air, da, ga, db, gb = pair()
ga.speed = gb.speed = 0.0
frames(3)
o = player(ga)[0]
o.x, o.y, o.z = 0.0, 0.0, 40.0
before = energy(ga)
ga._collide()
hurt = before - energy(ga)
ga._collide()
check("ram: A's ship is hurt", hurt > 5, "%.1f" % hurt)
check("ram: not again at once", abs((before - energy(ga)) - hurt) < 0.01)

# ---- destroyed: B blows up; A sees it and the score; B flies again from its end
air, da, ga, db, gb = pair()
ga.speed = gb.speed = 0.0
frames(5)
gb._hurt(1000.0)
check("dead: B's game is over", gb.over)
frames(3)
check("dead: A sees B destroyed, with the score", ga.msg.startswith("BEN DESTROYED  1-0")
      and player(ga) == [], ga.msg)
gb.reset()
frames(5)
check("again: B is back at its end, A sees it again", len(player(ga)) == 1 and
      math.dist(gb.world_pose()[:3], (0, 0, 1000)) < 50 and db.deaths == 1)
check("again: the ECM is still by hand after flying again", gb.rules.manual_ecm)

# ---- stop: practice's rules again
da.stop(ga)
check("stop: the ECM back to practice's own, no duel hooked in",
      not ga.rules.manual_ecm and ga.net is None)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL DUEL COMBAT TESTS PASSED")
