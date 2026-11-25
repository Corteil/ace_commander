"""Multiplayer for up to four (duel.py, Brian 2026-11-25): free for all, teams, capture
the flag and the convoy modes, with up to four Games on a pretend radio. Uses the game's
own ship data, so it runs without Elite's files. Proves the rules on a PC only."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import cockpit, duel, game, rules
SHIPS = ace_commander.ace.SHIPS
DT = 0.04
fails = []


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


NAMES = ("ANN", "BEN", "CAT", "DAN")


def flight(seed):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.rules = rules.GameRules(False)
    return g


class Match:
    """n players: the first hosts mode, the rest join in order; all flying."""

    def __init__(self, mode, n, seed=1, teams=None, pirates=True):
        self.air = Air()
        self.d = [duel.Duel(Link(self.air, bytes([2, 0, 0, 0, seed, i + 1])), NAMES[i], i + 1)
                  for i in range(n)]
        h = self.d[0]
        h.host(mode)
        h.set_pirates(pirates)
        self.lobby()
        for j in self.d[1:]:
            j.join(j.hosts()[0])
            self.lobby()
        for i, t in enumerate(teams or ()):     # each picks a team in the lobby
            self.d[i].choose_team(t)
        self.lobby()
        assert h.start_game(), h.can_start()
        self.g = [flight(seed * 10 + i) for i in range(n)]
        h.start(self.g[0])
        self.lobby(2)
        for d_, g_ in zip(self.d[1:], self.g[1:]):
            assert d_.go
            d_.start(g_)
        for g_ in self.g:
            g_.speed = 0.0

    def lobby(self, n=8):
        for _ in range(n):
            for d_ in self.d:
                if not d_.flying:
                    d_.lobby_step(DT)

    def fly(self, n, ctl=None):
        """n frames; ctl: {index: (pitch, roll, throttle, fire, missile)}, others sit still."""
        ctl = ctl or {}
        for _ in range(n):
            for i, (d_, g_) in enumerate(zip(self.d, self.g)):
                if not d_.flying:
                    continue
                p, r, t, f, m = ctl.get(i, (0.0, 0.0, -1.0, False, False))
                g_.step(DT, p, r, t, f, m)
                d_.flight_step(g_, DT)


def kind(g, k):
    return [o for o in g.objs if o.kind == k and not o.dead]


def wpos(g):
    return g.world_pose()[:3]


def world_of(g, o):
    return g.world_point(o.x, o.y, o.z)


# ---- four players, free for all ----------------------------------------------------
M = Match(duel.FFA, 4)
M.fly(5)
check("ffa: slots 0-3 in the order they joined", [d_.slot for d_ in M.d] == [0, 1, 2, 3])
check("ffa: each sees the other three", all(len(kind(g_, "player")) == 3 for g_ in M.g),
      str([len(kind(g_, "player")) for g_ in M.g]))
starts = [wpos(g_) for g_ in M.g]
check("ffa: round a circle, FFA_R from the middle",
      all(abs(math.dist(p, (0, 0, 0)) - duel.FFA_R) < 30 for p in starts), str(starts))
check("ffa: everyone starts apart", min(math.dist(a, b) for i, a in enumerate(starts)
                                         for b in starts[i + 1:]) > 4000)
c_seen_by_a = [o for o in kind(M.g[0], "player") if o.label == "CAT"][0]
check("ffa: ships in their owner's paint", c_seen_by_a.rgb == cockpit.ship_rgb(3)
      and not c_seen_by_a.friend)
check("ffa: the HUD line", M.d[1].hud()[0][0] == "KILLS 0  BEST 0/%d" % duel.FFA_WIN, str(M.d[1].hud()))

# A (slot 0, at -z facing +z) and C (slot 2, at +z facing -z) face each other: A's laser hits C
before = M.g[2].shield + M.g[2].hull
M.fly(1, {0: (0.0, 0.0, -1.0, True, False)})
M.fly(2)
check("ffa: A's laser hurts C", M.g[2].shield + M.g[2].hull < before, "%.1f" % before)
check("ffa: C knows it was A", M.d[2].last_by == 0)
M.g[2]._hurt(1000.0)
M.fly(3)
check("ffa: C destroyed by A: the host scores it for A", M.d[0].scores[0] == 1)
check("ffa: everyone has the score", all(d_.scores[0] == 1 for d_ in M.d), str([d_.scores for d_ in M.d]))
check("ffa: B is told", M.g[1].msg == "CAT DESTROYED BY ANN", M.g[1].msg)
check("ffa: A is told", M.g[0].msg == "YOU DESTROYED CAT", M.g[0].msg)
lines = [l[0] for l in M.d[2].over_lines()]
check("ffa: C's end screen: by whom, and coming back", lines[:3] == ["DESTROYED", "BY ANN", "BACK IN 5"],
      str(lines))
check("ffa: C on the end screen doesn't start again (it comes back by itself)",
      not M.d[2].again_by_c())
M.fly(int(duel.RESPAWN / DT) + 3)
check("ffa: C back after RESPAWN, at its start, full energy", not M.g[2].over and M.g[2].hull == 100.0
      and math.dist(wpos(M.g[2]), starts[2]) < 150)
check("ffa: the others see C again", all(any(o.label == "CAT" for o in kind(g_, "player"))
                                         for g_ in (M.g[0], M.g[1], M.g[3])))
# a kill a long while after the last hit is nobody's
M.d[3].last_by_t = 20.0
M.g[3]._hurt(1000.0)
M.fly(3)
check("ffa: killed by nobody: no score", sum(M.d[0].scores) == 1)
# the win: A's tenth
h = M.d[0]
h.scores[0] = duel.FFA_WIN - 1
M.d[1].last_by, M.d[1].last_by_t = 0, 0.0
M.g[1]._hurt(1000.0)
M.fly(3)
check("ffa: ten kills wins: everyone sees ANN WINS", all(d_.result == 10 for d_ in M.d)
      and [l[0] for l in M.d[2].over_lines()][0] == "ANN WINS"
      and [l[0] for l in M.d[0].over_lines()][0] == "YOU WIN", str([d_.result for d_ in M.d]))
check("ffa: the end screen shows for everyone", all(d_.showing(g_) for d_, g_ in zip(M.d, M.g)))
M.fly(int(duel.RESULT_FOR / DT) + 5)
check("ffa: then the next match: scores cleared, nobody's result", all(d_.result == 0 and d_.match == 1
                                                                       and sum(d_.scores) == 0 for d_ in M.d),
      str([(d_.result, d_.match, d_.scores) for d_ in M.d]))
check("ffa: everyone back at their start", all(math.dist(wpos(g_), s) < 150 for g_, s in zip(M.g, starts)))

# ---- a guest leaves a game of three: the others carry on; the host leaves: it ends ------
M = Match(duel.FFA, 3, seed=2)
M.fly(5)
M.d[2].stop(M.g[2])
M.fly(2)
check("leave: CAT LEFT; the other two carry on", M.d[0].ended is None and M.d[1].ended is None
      and M.g[0].msg == "CAT LEFT" and len(kind(M.g[0], "player")) == 1, M.g[0].msg)
M.d[0].stop(M.g[0])
M.fly(2)
check("leave: the host leaves: it ends for the guest", M.d[1].ended == "HOST LEFT", str(M.d[1].ended))

# ---- teams: red and blue, no friendly fire -------------------------------------------
M = Match(duel.TEAMS, 4, seed=3)
M.fly(5)
a_sees = {o.label: o for o in kind(M.g[0], "player")}
check("teams: team colours; the teammate is a friend", a_sees["CAT"].rgb == duel.TEAM_RGB[0]
      and a_sees["CAT"].friend and a_sees["BEN"].rgb == duel.TEAM_RGB[1] and not a_sees["BEN"].friend)
check("teams: red at -z, blue at +z", wpos(M.g[0])[2] < 0 and wpos(M.g[2])[2] < 0
      and wpos(M.g[1])[2] > 0 and wpos(M.g[3])[2] > 0)
check("teams: the friend can't be locked", M.g[0]._pick(5.0) is not a_sees["CAT"])
# CAT (red) right in front of ANN: ANN's laser passes by
mate = a_sees["CAT"]
before = M.g[2].hull + M.g[2].shield
M.g[0].set_anchor(wpos(M.g[2])[0], 0.0, wpos(M.g[2])[2] - 600.0, duel.spawn_pose(duel.TEAMS, 0)[3])
M.fly(2)
check("teams: CAT is dead ahead of ANN", abs(mate.x) < 120 and abs(mate.y) < 120 and 0 < mate.z < 900,
      "%.0f %.0f %.0f" % (mate.x, mate.y, mate.z))
M.fly(3, {0: (0.0, 0.0, -1.0, True, False)})
M.fly(2)
check("teams: no friendly fire", M.g[2].hull + M.g[2].shield == before)
M.d[1].last_by, M.d[1].last_by_t = 2, 0.0      # CAT got BEN
M.g[1]._hurt(1000.0)
M.fly(3)
check("teams: a kill scores for the team", all(d_.team == [1, 0] for d_ in M.d), str(M.d[3].team))
check("teams: the HUD line, both teams", [h[0] for h in M.d[3].hud()] == ["RED 1", "BLUE 0"],
      str(M.d[3].hud()))
M.d[3].last_by, M.d[3].last_by_t = 1, 0.0      # BEN got DAN, his own team: nothing
M.g[3]._hurt(1000.0)
M.fly(3)
check("teams: a teammate's kill scores nothing", M.d[0].team == [1, 0])

# ---- capture the flag ----------------------------------------------------------------
M = Match(duel.CTF, 2, seed=4)
M.fly(5)
for i, g_ in enumerate(M.g):
    rings = kind(g_, "mark")
    check("ctf %d: two rings, red and blue" % i, sorted(o.rgb for o in rings) == sorted(duel.TEAM_RGB))
check("ctf: each starts behind its own ring", wpos(M.g[0])[2] < -duel.RING_Z and wpos(M.g[1])[2] > duel.RING_Z)
red = [o for o in kind(M.g[1], "mark") if o.rgb == duel.TEAM_RGB[0]][0]
rw = world_of(M.g[1], red)
check("ctf: the red ring where it should be, for BEN", math.dist(rw, (0, 0, -duel.RING_Z)) < 5, str(rw))
o, rgb = M.d[1].compass()
check("ctf: BEN's compass points at the red ring (theirs)", o is M.d[1].rings[0] and rgb == duel.TEAM_RGB[0])


def through(i, z_from, z_to, x=0.0):
    """Player i flies from z_from to z_to (world), level, through whatever is between."""
    g_, d_ = M.g[i], M.d[i]
    nz = 1.0 if z_to > z_from else -1.0
    g_.set_anchor(x, 0.0, z_from, duel._pose(0, 0, 0, 0, 0, nz)[3])
    d_.ring_rel = None
    g_.speed = g_.max_speed
    for _ in range(400):
        M.fly(1, {i: (0.0, 0.0, 1.0, False, False)})
        if (wpos(g_)[2] - z_to) * nz > 0:
            break
    g_.speed = 0.0


through(1, -duel.RING_Z + 400, -duel.RING_Z - 400)
M.fly(3)
check("ctf: BEN flew through the red ring: he has the red flag", all(d_.carrier == [1, duel.NOBODY]
                                                                    for d_ in M.d), str(M.d[0].carrier))
check("ctf: the red ring goes grey for both", all(r.rgb == duel.TAKEN_RGB for r in (M.d[0].rings[0], M.d[1].rings[0])))
check("ctf: BEN is told; ANN is told", M.g[1].msg == "YOU HAVE THE RED FLAG" and M.g[0].msg == "BEN HAS THE RED FLAG",
      "%s / %s" % (M.g[1].msg, M.g[0].msg))
check("ctf: BEN's label shows the flag", [o.label for o in kind(M.g[0], "player")] == ["BEN *FLAG*"])
o, rgb = M.d[1].compass()
check("ctf: carrying, the compass points home (blue)", o is M.d[1].rings[1])
through(1, -duel.RING_Z - 400, -duel.RING_Z + 400)
M.fly(3)
check("ctf: back through the red ring: nothing", M.d[0].carrier == [1, duel.NOBODY] and M.d[0].team == [0, 0])
through(1, duel.RING_Z - 400, duel.RING_Z + 400, x=duel.RING_PASS + 100)
M.fly(3)
check("ctf: past the blue ring, not through it: nothing", M.d[0].team == [0, 0])
through(1, duel.RING_Z - 400, duel.RING_Z + 400)
M.fly(3)
check("ctf: through his own ring with it: blue scores, the flag goes home",
      all(d_.team == [0, 1] and d_.carrier == [duel.NOBODY, duel.NOBODY] for d_ in M.d), str(M.d[1].team))
check("ctf: the red ring red again", M.d[0].rings[0].rgb == duel.TEAM_RGB[0] and M.d[1].rings[0].rgb == duel.TEAM_RGB[0])
check("ctf: told", M.g[1].msg == "YOU CAPTURED THE RED FLAG" and M.g[0].msg == "BEN CAPTURED THE RED FLAG",
      "%s / %s" % (M.g[1].msg, M.g[0].msg))
# ANN (the host) takes the blue flag and is destroyed: it goes home
through(0, duel.RING_Z - 400, duel.RING_Z + 400)
M.fly(3)
check("ctf: the host takes the blue flag", M.d[1].carrier == [duel.NOBODY, 0])
M.g[0]._hurt(1000.0)
M.fly(3)
check("ctf: the carrier destroyed: the flag goes home", all(d_.carrier == [duel.NOBODY, duel.NOBODY]
                                                          for d_ in M.d) and M.g[1].msg == "BLUE FLAG RETURNED",
      M.g[1].msg)
M.fly(int(duel.RESPAWN / DT) + 3)
check("ctf: ANN comes back behind her own ring", wpos(M.g[0])[2] < -duel.RING_Z - 1000 and not M.g[0].over)
check("ctf: the rings are still where they were, for ANN",
      math.dist(world_of(M.g[0], M.d[0].rings[0]), (0, 0, -duel.RING_Z)) < 5)
M.d[0].team[1] = duel.CTF_WIN - 1
through(1, -duel.RING_Z + 400, -duel.RING_Z - 400)
through(1, duel.RING_Z - 400, duel.RING_Z + 400)
M.fly(3)
check("ctf: three captures wins: BLUE TEAM WINS", M.d[0].result == 2
      and M.d[1].over_lines()[0][0] == "BLUE TEAM WINS", str(M.d[0].result))

# ---- the convoy, co-op -----------------------------------------------------------------
duel_wave = duel.WAVE_FIRST
M = Match(duel.COOP, 2, seed=5)
M.fly(5)
ch = kind(M.g[0], "convoy")
cg = [o for o in kind(M.g[1], "npc") if o.net_id == 0]
check("coop: the convoy for both (the host's own; the guest's a copy)", len(ch) == 1 and len(cg) == 1
      and ch[0].bp.name == "CONVOY" and ch[0].friend and cg[0].friend)
check("coop: both agree where it is", math.dist(world_of(M.g[0], ch[0]), world_of(M.g[1], cg[0])) < 5)
check("coop: the station at the end", any(o.label == "STATION" for o in kind(M.g[0], "mark")))
check("coop: everyone starts by the convoy", all(math.dist(wpos(g_), world_of(M.g[0], ch[0])) < 2500 for g_ in M.g))
check("coop: the other player is a friend", kind(M.g[0], "player")[0].friend)
check("coop: the convoy can't be hit by its defenders", M.g[0]._pick(5.0) is not ch[0])
check("coop: HUD", M.d[1].hud()[0][0].startswith("CONVOY 100%"), str(M.d[1].hud()))
M.fly(int(duel.WAVE_FIRST / DT) + 5)
pir = kind(M.g[0], "ship")
seen = kind(M.g[1], "npc")
check("coop: pirates come (the host's game flies them)", len(pir) >= 2, str(len(pir)))
check("coop: the guest sees them, where they are", len(seen) == len(pir) + 1 and all(
    min(math.dist(world_of(M.g[0], p), world_of(M.g[1], s)) for s in seen) < 120 for p in pir))
check("coop: they're hostile on the guest's radar", all(cockpit.hostile(s) for s in seen if s.net_id))
# the guest shoots one: the host's ship takes it, and scores for the guest
p = pir[0]
s = [o for o in seen if o.net_id == p.net_id][0]
e0 = p.energy
M.d[1].npc_laser(s, 10.0)
M.fly(1)
check("coop: the guest's hit hurts the host's pirate", abs(e0 - p.energy - 10.0) < 0.01, "%.1f %.1f" % (e0, p.energy))
check("coop: it turns on the guest", p.net_prey == 1)
M.d[1].npc_laser(s, 1000.0)
M.fly(3)
check("coop: destroyed: gone for both, the guest's kill", p not in M.g[0].objs and s not in M.g[1].objs
      and M.d[0].scores[1] == 1 and M.d[1].scores[1] == 1, str(M.d[0].scores))
# the pirates attack: the convoy, and the guest, are hurt
M.d[0]._spawn_pirates(M.g[0])
pir = kind(M.g[0], "ship")
for i, o in enumerate(pir):
    o.prey = None
    o.net_prey = "c" if i % 2 == 0 else 1
hp0 = ch[0].energy
hurt = M.g[1].hull + M.g[1].shield
M.fly(int(20 / DT))
check("coop: the pirates hurt the convoy", ch[0].energy < hp0, "%.0f -> %.0f" % (hp0, ch[0].energy))
check("coop: the guest sees the convoy's energy", M.d[1].hp < 255 and abs(M.d[1].hp - M.d[0].hp) <= 2,
      "%d %d" % (M.d[1].hp, M.d[0].hp))
check("coop: the host's pirates hurt the guest", M.g[1].hull + M.g[1].shield < hurt
      and M.d[1].last_by == duel.NPC_SRC, "%.0f -> %.0f" % (hurt, M.g[1].hull + M.g[1].shield))
for o in pir:
    o.prey = None
    o.net_prey = None
M.fly(int(1 / DT))
targets = set(o.net_prey for o in pir if not o.dead)
check("coop: the pirates pick for themselves", targets and None not in targets and targets <= {"c", 0, 1},
      str(targets))
# the host is destroyed and comes back: the pirates stay where they were
pir = [o for o in kind(M.g[0], "ship")]
where = [world_of(M.g[0], o) for o in pir]
M.g[0]._hurt(1000.0)
M.fly(int(duel.RESPAWN / DT) + 3)
check("coop: the host back, by the convoy", not M.g[0].over and
      math.dist(wpos(M.g[0]), world_of(M.g[0], kind(M.g[0], "convoy")[0])) < 2500)
check("coop: its pirates kept", all(o in M.g[0].objs or o.dead for o in pir))
# the convoy destroyed: CONVOY LOST
c = kind(M.g[0], "convoy")[0]
M.d[1].npc_laser([o for o in kind(M.g[1], "npc") if o.net_id == 0][0], 99999.0)
M.fly(3)
check("coop: a friend's hits don't reach the convoy... but the host's game would take them",
      c.dead and M.d[0].result == 2)
check("coop: CONVOY LOST for both", M.d[1].result == 2 and M.d[1].over_lines()[0][0] == "CONVOY LOST"
      and M.d[1].over_lines()[1][0] == "YOU LOSE")
check("coop: the guest's copy blew up", not [o for o in kind(M.g[1], "npc") if o.net_id == 0])
# arriving wins
M = Match(duel.COOP, 1, seed=6)
check("coop alone: the host can play by itself", M.d[0].flying)
M.d[0].mtime = duel.CONVOY_TIME - 0.1
M.fly(5)
check("coop: the convoy arrives: CONVOY ARRIVED, YOU WIN", M.d[0].result == 1
      and [l[0] for l in M.d[0].over_lines()][:2] == ["CONVOY ARRIVED", "YOU WIN"])

# ---- the convoy raid: red defends, blue raids ----------------------------------------------
M = Match(duel.RAID, 2, seed=7)
M.fly(5)
cg = [o for o in kind(M.g[1], "npc") if o.net_id == 0][0]
check("raid: the convoy isn't the raider's friend", not cg.friend and kind(M.g[0], "convoy")[0].friend)
check("raid: the raider starts ahead of the convoy", wpos(M.g[1])[2] > duel.convoy_z(0) + 5000)
check("raid: the other player is an enemy", not kind(M.g[0], "player")[0].friend)
hp0 = kind(M.g[0], "convoy")[0].energy
M.d[1].npc_laser(cg, 100.0)
M.fly(1)
check("raid: the raider's hit hurts the convoy", kind(M.g[0], "convoy")[0].energy == hp0 - 100.0)
M.fly(int(duel.WAVE_FIRST / DT) + 5)
seen = [o for o in kind(M.g[1], "npc") if o.net_id]
check("raid: the pirates are the raider's friends", seen and all(o.friend for o in seen))
check("raid: the pirates leave the raider alone", all(o.net_prey != 1 for o in kind(M.g[0], "ship")))

# ---- through the app: host CAPTURE FLAG with two guests -----------------------------------
air = Air()
mine = Link(air, bytes([2, 0, 0, 0, 9, 1]))
others = [duel.Duel(Link(air, bytes([2, 0, 0, 0, 9, 2 + i])), NAMES[i + 1], 2) for i in range(2)]
a = ace_commander.AceCommander()
a.platform.radio = lambda: mine
bs.choose(a, "MULTIPLAYER")
bs.tick(a, fresh=["CONFIRM"])           # HOST A GAME
check("app: hosting a duel first", a.duel.role == duel.HOST and a.duel.mode == duel.DUEL)
for _ in range(3):
    bs.tick(a, fresh=["JOYRIGHT"])
    bs.tick(a)
check("app: right picks the mode: CAPTURE FLAG", a.duel.mode == duel.CTF, duel.MODE_NAMES[a.duel.mode])
c = bs.CountCtx()
a.draw(c)
check("app: the page shows the mode", "< CAPTURE FLAG >" in [t[0] for t in c.texts])
for _ in range(10):
    for o in others:
        o.lobby_step(DT)
    bs.tick(a)
for o in others:
    o.join(o.hosts()[0])
for _ in range(10):
    for o in others:
        o.lobby_step(DT)
    bs.tick(a)
c = bs.CountCtx()
a.draw(c)
texts = [t[0] for t in c.texts]
check("app: three in the party, with teams", len(a.duel.guests) == 2 and "BEN  BLUE" in texts
      and "CAT  RED" in texts, str(texts))
bs.tick(a, fresh=["JOYDOWN"])           # down to the TEAM line; right: the host goes blue
bs.tick(a, fresh=["JOYRIGHT"])
for _ in range(8):
    for o in others:
        o.lobby_step(DT)
    bs.tick(a)
c = bs.CountCtx()
a.draw(c)
texts = [t[0] for t in c.texts]
check("app: the host changes team on its TEAM line", a.duel.my_team() == 1 and "< YOU: BLUE >" in texts
      and others[0].party()[0][3] == 1, str(texts))
bs.tick(a, fresh=["JOYLEFT"])
for _ in range(8):
    for o in others:
        o.lobby_step(DT)
    bs.tick(a)
check("app: and back to red", a.duel.my_team() == 0)
check("app: the guests see CAPTURE FLAG", others[0].host_p.mode == duel.CTF)
bs.tick(a, fresh=["CONFIRM"])
bs.tick(a)
check("app: C starts it", a.mode == "flight" and a.dueling and a.duel.mode == duel.CTF)
gs = [flight(40 + i) for i in range(2)]
for o in others:
    o.lobby_step(DT)
for o, g_ in zip(others, gs):
    o.start(g_)
for _ in range(5):
    for o, g_ in zip(others, gs):
        g_.step(DT, 0.0, 0.0, 0.0, False, False)
        o.flight_step(g_, DT)
    bs.tick(a)
check("app: rings and two other ships", len(kind(a.game, "mark")) == 2 and len(kind(a.game, "player")) == 2)
c = bs.CountCtx()
a.draw(c)
texts = [t[0] for t in c.texts]
check("app: the score line drawn", "RED 0" in texts and "BLUE 0" in texts, str(texts))
a.game._hurt(1000.0)
bs.tick(a)
for _ in range(20):
    bs.tick(a)
bs.tick(a, fresh=["CONFIRM"])
bs.tick(a)
check("app: C on the end screen doesn't restart (comes back by itself)", a.game.over)
for _ in range(int(duel.RESPAWN / DT) + 3):
    for o, g_ in zip(others, gs):
        g_.step(DT, 0.0, 0.0, 0.0, False, False)
        o.flight_step(g_, DT)
    bs.tick(a)
check("app: back after RESPAWN", not a.game.over and a.dueling)
a._to_title()
bs.tick(a)
check("app: to the title ends it", not a.dueling and a.game.anchor is None and not kind(a.game, "mark"))

# ---- choosing teams in the lobby ------------------------------------------------------
air = Air()
ds = [duel.Duel(Link(air, bytes([2, 0, 0, 0, 8, i + 1])), NAMES[i], 1) for i in range(3)]


def lob(n=8):
    for _ in range(n):
        for d_ in ds:
            d_.lobby_step(DT)


ds[0].host(duel.TEAMS)
lob()
for j in ds[1:]:
    j.join(j.hosts()[0])
    lob()
check("teams: unchosen, they alternate: red, blue, red", [e[3] for e in ds[0].party()] == [0, 1, 0])
check("teams: the guests see the same", [e[3] for e in ds[2].party()] == [0, 1, 0]
      and ds[1].my_team() == 1 and ds[2].my_team() == 0)
ds[2].choose_team(1)
lob()
check("teams: CAT asks for blue: the host takes it", [e[3] for e in ds[0].party()] == [0, 1, 1]
      and ds[2].my_team() == 1, str(ds[0].party()))
ds[1].choose_team(0)
ds[2].choose_team(0)
lob()
check("teams: everyone red: can't start", ds[0].can_start() == (False, "a player on each team"))
ds[0].choose_team(1)
lob()
check("teams: the host goes blue: 1 against 2, can start", [e[3] for e in ds[0].party()] == [1, 0, 0]
      and ds[0].can_start()[0])
check("teams: START takes the teams", ds[0].start_game())
gs = [flight(80 + i) for i in range(3)]
ds[0].start(gs[0])
lob(2)
for d_, g_ in zip(ds[1:], gs[1:]):
    d_.start(g_)
check("teams: everyone has the teams", all(d_.teams[:3] == [1, 0, 0] for d_ in ds), str([d_.teams for d_ in ds]))
check("teams: the host starts on blue's side, the two reds side by side on red's",
      wpos(gs[0])[2] > 0 and wpos(gs[1])[2] < 0 and wpos(gs[2])[2] < 0
      and abs(wpos(gs[1])[0] - wpos(gs[2])[0]) > 500)
seen = {o.label: o for o in kind(gs[1], "player")} if False else None
for _ in range(5):
    for d_, g_ in zip(ds, gs):
        g_.step(DT, 0.0, 0.0, -1.0, False, False)
        d_.flight_step(g_, DT)
b_sees = {o.label: o for o in kind(gs[1], "player")}
check("teams: BEN's teammate CAT is a friend, the host isn't", b_sees["CAT"].friend and not b_sees["ANN"].friend
      and b_sees["ANN"].rgb == duel.TEAM_RGB[1])

# ---- the raid: no pirates; and the defenders not overwhelmed ------------------------------
M = Match(duel.RAID, 2, seed=11, pirates=False)
check("raid: the guest heard PIRATES OFF", not M.d[1].pirates and not M.d[0].pirates)
M.fly(int((duel.WAVE_FIRST + 2) / DT))
check("raid, no pirates: none come", kind(M.g[0], "ship") == [] and [o for o in kind(M.g[1], "npc") if o.net_id] == [])
check("raid 1 v 1: the convoy's energy as usual", kind(M.g[0], "convoy")[0].max_energy == duel.CONVOY_ENERGY)
check("raid 1 v 1: defender back in 3 s, raider in 5", M.d[0].respawn_time() == duel.DEFEND_RESPAWN
      and M.d[1].respawn_time() == duel.RESPAWN)
M = Match(duel.RAID, 4, seed=12, teams=(0, 1, 1, 1))
check("raid 1 v 3: everyone has the teams", all(d_.teams == [0, 1, 1, 1] for d_ in M.d))
check("raid 1 v 3: the convoy three times as tough", kind(M.g[0], "convoy")[0].max_energy == duel.CONVOY_ENERGY * 3)
check("raid 1 v 3: raiders wait 5 + 2 x 2 s", M.d[2].respawn_time() == duel.RESPAWN + 2 * duel.RAID_EXTRA_RESPAWN)
check("raid 1 v 3: the three raiders start apart, ahead", all(wpos(g_)[2] > duel.convoy_z(0) + 5000 for g_ in M.g[1:])
      and min(math.dist(wpos(a_), wpos(b_)) for a_, b_ in ((M.g[1], M.g[2]), (M.g[2], M.g[3]), (M.g[1], M.g[3]))) > 1000)
M.fly(int((duel.WAVE_FIRST + 2) / DT))
check("raid 1 v 3: no pirates join the raiders", kind(M.g[0], "ship") == [])
M = Match(duel.RAID, 3, seed=13, teams=(0, 0, 1))
M.fly(int((duel.WAVE_FIRST + 2) / DT))
check("raid 2 v 1: a wave of 2 pirates on the raider's side", len(kind(M.g[0], "ship")) == 2,
      str(len(kind(M.g[0], "ship"))))
check("raid 2 v 1: both defenders by the convoy", all(wpos(g_)[2] < duel.convoy_z(M.d[0].mtime) for g_ in M.g[:2]))

# ---- the pirates' skill (build 151) --------------------------------------------------------
air = Air()
ds = [duel.Duel(Link(air, bytes([2, 0, 0, 0, 9, i + 1])), NAMES[i], 1) for i in range(2)]
ds[0].host(duel.COOP)
check("skill: co-op starts NORMAL, no OFF", ds[0].pirates_setting() == 1)
ds[0].step_pirates(1)
ds[0].step_pirates(1)
check("skill: co-op goes round HARD, EASY (never off)", ds[0].pirates_setting() == 0)
ds[0].step_pirates(-1)
for _ in range(8):
    for d_ in ds:
        d_.lobby_step(DT)
ds[1].join(ds[1].hosts()[0])
for _ in range(8):
    for d_ in ds:
        d_.lobby_step(DT)
check("skill: the guest sees HARD", (ds[1].host_p.opts >> 1) & 3 == 2)
ds[0].start_game()
gs = [flight(90), flight(91)]
ds[0].start(gs[0])
for _ in range(2):
    ds[1].lobby_step(DT)
ds[1].start(gs[1])
check("skill: the host's game flies its pirates at HARD", gs[0].level == 2 and ds[1].pirate_level == 2)
ds[0].stop(gs[0])
ds[1].stop(gs[1])
r = duel.Duel(Link(air, bytes([2, 0, 0, 0, 9, 9])), "R", 1)
r.host(duel.RAID)
seq = []
for _ in range(4):
    r.step_pirates(1)
    seq.append(r.pirates_setting())
check("skill: a raid goes NORMAL > HARD > OFF > EASY > NORMAL", seq == [2, -1, 0, 1], str(seq))

# ---- station defence (build 153) ------------------------------------------------------------
check("station: the game's own two to pick from (no Elite data here)", duel.available_stations() == [0, 1]
      and duel.station_name(0) == "DRUM STATION" and duel.station_name(1) == "HALO STATION")
air = Air()
ds = [duel.Duel(Link(air, bytes([2, 0, 0, 0, 10, i + 1])), NAMES[i], 1) for i in range(2)]
ds[0].host(duel.SCOOP)
ds[0].step_station(1)
ds[0].step_time(1)              # 3 min -> 5 min
ds[0].set_growing(False)
check("station: host picks the Halo, 5 minutes, steady waves", ds[0].station_i == 1 and ds[0].guard_time() == 300.0
      and not ds[0].growing)
ds[0].step_station(1)
check("station: and round again to the Drum", ds[0].station_i == 0)
ds[0].step_station(1)
for _ in range(8):
    for d_ in ds:
        d_.lobby_step(DT)
ds[1].join(ds[1].hosts()[0])
for _ in range(8):
    for d_ in ds:
        d_.lobby_step(DT)
o = ds[1].host_p.opts
check("station: the guest's page has them", (o >> 6) & 3 == 1 and (o >> 3) & 3 == 2 and not o & duel.OPT_GROW)

M = Match(duel.SCOOP, 2, seed=20)
M.fly(5)
sh = kind(M.g[0], "convoy")
sg = [o for o in kind(M.g[1], "npc") if o.net_id == 0]
check("station: the host's station and the guest's copy, the Drum by default",
      len(sh) == 1 and len(sg) == 1 and sh[0].bp.name == "CORIOLIS" and sh[0].label == "STATION"
      and sh[0].max_energy == duel.STATION_ENERGY)
check("station: at the middle of the world for both", math.dist(world_of(M.g[0], sh[0]), (0, 0, 0)) < 5
      and math.dist(world_of(M.g[1], sg[0]), (0, 0, 0)) < 5)
check("station: the HUD", M.d[1].hud()[0][0] in ("STATION 100%  3:00", "STATION 100%  2:59")
      and M.d[1].hud()[1][0] == "SHIELD 100%  DOCKED 0/3", str(M.d[1].hud()))
check("station: no convoy, no end-station marker", not [o for o in kind(M.g[0], "mark")])
M.fly(int((duel.WAVE_FIRST + 1) / DT))
pir = kind(M.g[0], "ship")
dockers = [o for o in pir if o.net_docker]
check("station: a wave from all round, half meaning to dock", len(pir) >= 2 and len(dockers) == (len(pir) + 1) // 2,
      "%d %d" % (len(pir), len(dockers)))
check("station: shield up: the dockers attack it first", all(o.state != "trade" and o.net_prey == "c"
                                                             for o in dockers))
s_ = sh[0]
e0 = s_.energy
o = dockers[0]
o.x, o.y, o.z = s_.x, s_.y, s_.z + 60.0     # right at the slot: shield up, no docking
o.state = "trade"
o.net_prey = "dock"
M.fly(2)
check("station: with the shield up a pirate at the slot can't dock", not o.dead and M.d[0].docked == 0
      and o.state == "attack")
# hits take the shield first, not the station's energy
s_.energy -= 300.0
M.fly(int(0.4 / DT))
check("station: hits take the shield first", s_.energy == e0 and M.d[0].shield == duel.STATION_SHIELD - 300.0
      and M.d[1].shield_b < 255, "%.0f %.0f %d" % (s_.energy, M.d[0].shield, M.d[1].shield_b))
s_.energy -= 800.0              # more than the shield has left: the rest hurts it
M.fly(3)
check("station: shield down, the rest hurts the station", M.d[0].shield == 0 and s_.energy == e0 - 100.0
      and M.d[1].shield_b == 0, "%.0f %.0f" % (M.d[0].shield, s_.energy))
check("station: SHIELDS DOWN told to both", M.g[0].msg == "STATION SHIELDS DOWN" and M.g[1].msg == "STATION SHIELDS DOWN",
      "%s / %s" % (M.g[0].msg, M.g[1].msg))
check("station: shield down: the dockers fly in to dock", all(o.state == "trade" and o.net_prey == "dock"
                                                              for o in dockers if not o.dead and o.net_prey != 1))
M.d[0]._spawn_pirates(M.g[0])     # a fresh wave, far out
M.fly(2)
fresh = [o for o in kind(M.g[0], "ship") if o.net_docker and o not in dockers]
check("station: a new wave's dockers come straight in to dock", fresh and all(o.state == "trade" for o in fresh))
z0 = [math.dist(world_of(M.g[0], o), (0, 0, 0)) for o in fresh]
M.fly(int(3 / DT))
z1 = [math.dist(world_of(M.g[0], o), (0, 0, 0)) for o in fresh if not o.dead]
check("station: the dockers close in", z1 and sum(z1) / len(z1) < sum(z0) / len(z0) - 200, "%s -> %s" % (z0, z1))
# put one at the slot: it docks
o = fresh[0]
n0 = M.d[0].docked
seen = [x for x in kind(M.g[1], "npc") if x.net_id == o.net_id]
o.x, o.y, o.z = s_.x, s_.y, s_.z + 60.0
booms = len(M.g[1].booms)
M.fly(int(0.5 / DT))
check("station: a pirate docked: gone, counted for both, told", o.dead and o.docked and M.d[0].docked == n0 + 1
      and M.d[1].docked == n0 + 1 and M.g[1].msg == "PIRATE DOCKED %d/3" % (n0 + 1),
      "%d %d %d %s" % (n0, M.d[0].docked, M.d[1].docked, M.g[1].msg))
check("station: the guest's copy went without an explosion", seen and seen[0].dead
      and len(M.g[1].booms) <= booms)
check("station: no score for a docking", sum(M.d[0].scores) == 0)
# left alone, the shield comes back, and the dockers go back to attacking
for x in kind(M.g[0], "ship"):
    x.dead = True
M.fly(int((duel.SHIELD_WAIT + 2) / DT))
check("station: unhit, the shield recharges: SHIELDS UP", M.d[0].shield > 0 and M.d[1].shield_b > 0
      and "STATION SHIELDS UP" in (M.g[1].msg, M.g[0].msg), "%.0f %s" % (M.d[0].shield, M.g[1].msg))
M.d[0].shield = 0.0
M.d[0].shield_quiet = -99.0
M.d[0]._spawn_pirates(M.g[0])
M.fly(2)
M.d[0].docked = duel.DOCK_LIMIT
d2 = [x for x in kind(M.g[0], "ship") if x.net_prey == "dock"] or [x for x in kind(M.g[0], "ship")]
x = d2[0]
x.state, x.dest, x.net_prey, x.prey = "trade", "station", "dock", None
x.x, x.y, x.z = s_.x, s_.y, s_.z + 60.0
M.fly(int(0.5 / DT))
check("station: more than 3 docked: STATION LOST", M.d[0].result == 2 and M.d[1].result == 2
      and [l[0] for l in M.d[1].over_lines()][:3] == ["STATION LOST", "YOU LOSE", "PIRATES DOCKED 4"],
      str(M.d[1].over_lines()))
M = Match(duel.SCOOP, 1, seed=21)
M.d[0].mtime = M.d[0].guard_time() - 0.1
M.fly(5)
check("station: held to the end: STATION HELD", M.d[0].result == 1
      and [l[0] for l in M.d[0].over_lines()][:2] == ["STATION HELD", "YOU WIN"])
M = Match(duel.SCOOP, 1, seed=22)
st = kind(M.g[0], "convoy")[0]
st.energy = 0
st.dead = True
M.fly(3)
check("station: destroyed: STATION LOST", M.d[0].result == 2)
# growing waves
M = Match(duel.SCOOP, 1, seed=23)
M.d[0].mtime = 125.0
M.d[0]._spawn_pirates(M.g[0])
grown = len(kind(M.g[0], "ship"))
M = Match(duel.SCOOP, 1, seed=23)
M.d[0].growing = False
M.d[0].mtime = 125.0
M.d[0]._spawn_pirates(M.g[0])
check("station: growing waves are bigger after 2 minutes (3 against 1)", grown == 3
      and len(kind(M.g[0], "ship")) == 1, "%d %d" % (grown, len(kind(M.g[0], "ship"))))
# the raid
M = Match(duel.SRAID, 2, seed=24)
M.fly(5)
sg = [o for o in kind(M.g[1], "npc") if o.net_id == 0][0]
check("station raid: the raider can shoot the station; DEFEND / RAID",
      not sg.friend and kind(M.g[0], "convoy")[0].friend and duel.team_label(duel.SRAID, 1) == "RAID")
check("station raid: the raider starts out from the station", math.dist(wpos(M.g[1]), (0, 0, 0)) > 5000)
e0 = kind(M.g[0], "convoy")[0].energy
M.d[1].npc_laser(sg, 100.0)
M.fly(1)
check("station raid: the hit counts (on the shield first)", kind(M.g[0], "convoy")[0].energy == e0
      and M.d[0].shield == M.d[0].shield_max - 100.0)
# Elite's stations, when its ship data is here
import types
fake = types.ModuleType("ace_commander.ship_data")
fake.SHIPS = (("CORIOLIS",) + tuple(e[1:5] for e in ace_commander.original_ships.SHIPS if e[0] == "CORIOLIS")[0],
              ("DODO",) + tuple(e[1:5] for e in ace_commander.original_ships.SHIPS if e[0] == "DODO")[0])
sys.modules["ace_commander.ship_data"] = fake
check("station: with Elite's data, all four", duel.available_stations() == [0, 1, 2, 3]
      and duel.station_name(2) == "CORIOLIS" and duel.station_name(3) == "DODO")
del sys.modules["ace_commander.ship_data"]
duel._STATION_BPS.clear()
check("station: a guest without it sees the game's own instead", duel.station_blueprint(3).name == "DODO"
      and duel.station_blueprint(3).title == "HALO STATION")

# ---- station modes: defenders launch from the station; one life (build 155) ---------------------
M = Match(duel.SCOOP, 2, seed=30)
M.fly(5)
M.g[1]._hurt(1000.0)
M.fly(2)
check("launch: a destroyed defender's end screen: LAUNCH IN 10", [l[0] for l in M.d[1].over_lines()][2] == "LAUNCH IN 10",
      str(M.d[1].over_lines()))
M.fly(int((duel.STATION_PENALTY - 1) / DT))
check("launch: the time penalty: still waiting after 9 s", M.g[1].over and not M.d[1].wants_launch)
M.fly(int(1.5 / DT))
check("launch: then it asks for the launch tunnel (still destroyed meanwhile)", M.d[1].wants_launch and M.g[1].over)
M.fly(int(3 / DT))
check("launch: and waits for it (no respawn by itself)", M.d[1].wants_launch and M.g[1].over)
M.d[1].launched(M.g[1])
st_w = world_of(M.g[0], kind(M.g[0], "convoy")[0])
p_ = wpos(M.g[1])
check("launch: out in front of the station's slot, facing out", not M.g[1].over
      and abs(p_[0]) < 1 and abs(p_[1]) < 1 and p_[2] > 200 and M.g[1].world_pose()[3][8] > 0.99, str(p_))
M = Match(duel.SRAID, 2, seed=31)
M.fly(5)
check("launch: a raider doesn't launch from the station", not M.d[1].launches() and M.d[0].launches())
M.g[1]._hurt(1000.0)
M.fly(int((duel.RESPAWN + 0.5) / DT))
check("launch: the raider is back by itself, out in space", not M.g[1].over and not M.d[1].wants_launch
      and math.dist(wpos(M.g[1]), (0, 0, 0)) > 4000)

# one life
air = Air()
ds = [duel.Duel(Link(air, bytes([2, 0, 0, 0, 11, i + 1])), NAMES[i], 1) for i in range(2)]
ds[0].host(duel.SCOOP)
ds[0].set_one_life(True)
for _ in range(8):
    for d_ in ds:
        d_.lobby_step(DT)
ds[1].join(ds[1].hosts()[0])
for _ in range(8):
    for d_ in ds:
        d_.lobby_step(DT)
check("one life: the guest's page has it", ds[1].host_p.opts2 & duel.OPT2_ONE_LIFE)
M = Match(duel.SCOOP, 2, seed=32)
for d_ in M.d:
    d_.one_life = True
M.fly(5)
M.g[1]._hurt(1000.0)
M.fly(int((duel.STATION_PENALTY + 2) / DT))
check("one life: destroyed, out: no launch, still destroyed", M.g[1].over and not M.d[1].wants_launch
      and [l[0] for l in M.d[1].over_lines()][2] == "OUT: ONE LIFE")
check("one life: everyone knows", all(1 in d_.out for d_ in M.d) and M.d[0].result == 0)
M.g[0]._hurt(1000.0)
M.fly(3)
check("one life: every defender out: STATION LOST, DEFENDERS ALL OUT", M.d[0].result == 2 and M.d[1].result == 2
      and [l[0] for l in M.d[1].over_lines()][:3] == ["STATION LOST", "YOU LOSE", "DEFENDERS ALL OUT"],
      str(M.d[1].over_lines()))
M.fly(int((duel.RESULT_FOR + 1) / DT))
check("one life: the next match: everyone back in", all(not g_.over and not d_.out for d_, g_ in zip(M.d, M.g)))
M = Match(duel.SRAID, 2, seed=33)
for d_ in M.d:
    d_.one_life = True
M.fly(5)
M.g[1]._hurt(1000.0)
M.fly(3)
check("one life raid: every raider out: STATION HELD, RAIDERS ALL OUT", M.d[0].result == 1
      and [l[0] for l in M.d[0].over_lines()][:3] == ["STATION HELD", "YOU WIN", "RAIDERS ALL OUT"],
      str(M.d[0].over_lines()))

# through the app: the launch tunnel
air = Air()
mine = Link(air, bytes([2, 0, 0, 0, 12, 1]))
a = ace_commander.AceCommander()
a.platform.radio = lambda: mine
bs.choose(a, "MULTIPLAYER")
bs.tick(a, fresh=["CONFIRM"])
a.duel.set_mode(duel.SCOOP)
bs.tick(a)
bs.tick(a, fresh=["CONFIRM"])
bs.tick(a)
check("app launch: station co-op alone", a.mode == "flight" and a.duel.mode == duel.SCOOP)
a.game._hurt(1000.0)
for _ in range(int((duel.STATION_PENALTY + 0.5) / DT)):
    bs.tick(a)
check("app launch: after the time penalty, the launch tunnel", a.mode == "mlaunch" and a.dueling)
c = bs.CountCtx()
a.draw(c)
t0 = a.duel.mtime
for _ in range(int(ace_commander.ace.LAUNCH_TIME / DT) + 3):
    bs.tick(a)
check("app launch: the game ran on through the tunnel", a.duel.mtime > t0 + 2)
check("app launch: out of the slot, flying", a.mode == "flight" and not a.game.over
      and wpos(a.game)[2] > 200 and a.dueling)
a._to_title()
bs.tick(a)

# ---- packet sizes: the NPCS packet fits ESP-NOW's 250 bytes --------------------------------
import struct
check("sizes: every packet fits ESP-NOW (250 bytes)",
      struct.calcsize(duel.NPCS_HEAD) + duel.NPC_SIZE * (duel.NPC_SLOTS) <= 250
      and struct.calcsize(duel.FMT) <= 250 and struct.calcsize(duel.STATE_FMT) <= 250)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL MULTIPLAYER TESTS PASSED")
