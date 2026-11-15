"""Witchspace and Thargoids (build 49), as the disc original."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import commander, game, cockpit, chart
mod = ace_commander.ace
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_witchspace.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE
SHIPS = mod.SHIPS
DT = 0.04


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


# ---- the rules --------------------------------------------------------------
random.seed(1)
g = game.Game(SHIPS)
g.witchspace()
sp = g.space
assert sp.witch and sp.station is None and not sp.safe and g.msg == "WITCHSPACE"
tg = [o for o in g.new if o.bp.name == "THARGOID"]
tn = [o for o in g.new if o.bp.name == "THARGON"]
assert len(tg) == game.THARGOIDS and len(tn) == game.THARGOIDS, "four Thargoids, each with a Thargon"
assert all(o.role == "thargoid" and o.state == "attack" for o in tg + tn)
assert len(g.dust) == game.WITCH_DUST, "hardly any stardust"
cx = CountCtx(); cockpit.draw(cx, g)     # no planet, sun, station or compass to draw
# nothing else turns up, and the jump drive won't work
g.god = True
for _ in range(int(60 / DT)):
    g.step(DT, 0, 0, 1.0, False, False)
    assert not g.jumping
assert all(o.role == "thargoid" for o in g.objs if o.kind == "ship"), "only Thargoids"
assert g.cabin == game.COOL_CABIN, "no sun"
# a Thargoid launches Thargons, but only below half its energy
g = game.Game(SHIPS); g.witchspace(1); g.objs.extend(g.new); g.new = []; g.god = True
t = [o for o in g.objs if o.bp.name == "THARGOID"][0]
t.x, t.y, t.z = 0.0, 0.0, 3000.0; game._look(t.m, 0.0, 0.0, -1.0)
n0 = sum(1 for o in g.objs if o.bp.name == "THARGON")
for _ in range(int(20 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    t.energy = t.bp.energy
assert sum(1 for o in g.objs + g.new if o.bp.name == "THARGON") == n0, "not at full energy"
for _ in range(int(40 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    t.energy = t.bp.energy * 0.4
    t.x, t.y, t.z = 0.0, 0.0, 3000.0
assert sum(1 for o in g.objs + g.new if o.bp.name == "THARGON") > n0, "below half: Thargons"
assert t.missiles < t.bp.missiles
# kill the mothership and its Thargons drift at half speed, harmless
g._kill(t)
for _ in range(10):
    g.step(DT, 0, 0, 0, False, False)
lone = [o for o in g.objs if o.bp.name == "THARGON"]
assert lone and all(o.state == "drift" for o in lone)
hull = g.hull; shield = g.shield; g.god = False
for _ in range(int(10 / DT)):
    g.step(DT, 0, 0, 0, False, False)
assert g.shield == shield and g.hull == hull
# a Thargon scooped from below is alien items
got = []
g.scoop = lambda i: got.append(i) or "ALIEN ITEMS"
o = lone[0]; o.x, o.y, o.z = 0.0, -20.0, 10.0
g.step(DT, 0, 0, 0, False, False)
assert got == [game.ALIEN_ITEMS] and o.dead and g.msg == "ALIEN ITEMS"
# Thargoids pay their bounty
g = game.Game(SHIPS); g.witchspace(1); g.objs.extend(g.new); g.new = []
t = [o for o in g.objs if o.bp.name == "THARGOID"][0]
g._kill(t); assert g.bounty == t.bp.bounty and g.kills == 1
# the escape pod can't save you in witchspace
g = game.Game(SHIPS); g.witchspace(); g.pod = True
g._hurt(1e6); assert g.over and not g.ejected and g.msg == "GAME OVER"
# and a jump out leaves witchspace behind
g = game.Game(SHIPS); g.witchspace(); g.start_jump()
for _ in range(int(7 / DT)):
    g.step(DT, 0, 0, 0, False, False)
assert g.jumped and g.space is None and not g.objs
g.enter(6000, "CORIOLIS", "arrive", 3); assert len(g.dust) == 10 and not g.space.witch
print("witchspace: no planet, sun or station, four Thargoids, Thargons, drifting, scooped: ok")

# ---- the chart from between systems ------------------------------------------
gal = None
from ace_commander import galaxy as galaxy_mod
gd = mod.game_data
gal = galaxy_mod.Galaxy(gd.SEEDS, gd.PAIRS)
x, y = gal.xs[7], gal.ys[7]
assert gal.distance_xy(x, y, 7) == 0 and gal.distance_xy(x, y, 129) == gal.distance(7, 129)
ch = chart.Chart(gal, 7, 70, None, "JUMP", at=(x, y ^ 31))
assert ch.here is None and all(d == gal.distance_xy(x, y ^ 31, i) for _, _, i, d in ch.dots)
cx = CountCtx(); ch.draw(cx)
gc = chart.GalChart(gal, 7, 70, None, "TARGET", 3)
cx = CountCtx(); gc.draw(cx); assert "GALAXY 3" in [t[0] for t in cx.texts]
print("the local chart from a point between systems; the galactic chart's number: ok")

# ---- in the app ------------------------------------------------------------------
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
c = e.cmdr
home = c.system
e.dock.go(0); tick(e, fresh=["C"])
for _ in range(200):
    tick(e)
    if e.mode == "flight":
        break
g = e.game; g.encounter_t = g.station_t = 1e9
# DEBUG: MIS-JUMP NEXT, then jump
def debug(a, line):
    if not a.paused:
        tick(a, fresh=["A"])
    a.fsub = "dgroup"
    a.dgroup = mod.cheat_group(line)
    a.fmenu = [i for i, t in enumerate(a._fitems()) if t.startswith(line)][0]
    tick(a, fresh=["C"])
debug(e, "MIS-JUMP NEXT"); assert e.misjump
tick(e, fresh=["A"])
to = gal.in_range(c.system, c.fuel)[0]
e.target = to[1]
g.legal = 20
fuel = c.fuel
e.jump_to = (to[1], to[0]); g.start_jump()
for _ in range(400):
    tick(e)
    if e.witch is not None:
        break
assert e.witch == (gal.xs[to[1]], gal.ys[to[1]] ^ 31) and not e.misjump
assert g.space.witch and c.system == home and c.fuel == fuel - to[0]
assert g.legal == 20, "no halving: you never arrived"
tick(e, fresh=["A"]); e.fsub = "status"
assert "WITCHSPACE" in " ".join(texts(e))
e.fsub = None
assert "LOCAL CHART" in e._fitems()
e.fmenu = e._fitems().index("LOCAL CHART"); tick(e, fresh=["C"])
assert e.chart.here is None
texts(e)
tick(e, fresh=["F"])
tick(e, fresh=["A"])
# jumping out: from where you are, to anywhere the fuel reaches
c.fuel = 70
reach = [(gal.distance_xy(e.witch[0], e.witch[1], i), i) for i in range(256)]
reach = sorted(r for r in reach if 0 < r[0] <= c.fuel)
assert reach
e.target = reach[0][1]
assert e._jump_ok() == (reach[0][1], reach[0][0])
e.jump_to = e._jump_ok(); g.start_jump()
for _ in range(400):
    tick(e)
    if e.witch is None:
        break
assert e.witch is None and c.system == reach[0][1] and not g.space.witch
assert c.fuel == 70 - reach[0][0] and g.legal == 10, "this jump arrives: halved"
# destroyed in witchspace: back to the last save, out of witchspace
e.misjump = True
to = gal.in_range(c.system, c.fuel)[0]
e.jump_to = (to[1], to[0]); g.start_jump()
for _ in range(400):
    tick(e)
    if e.witch is not None:
        break
assert e.witch is not None
c.extras.append("pod"); g.pod = True
g._hurt(1e6); tick(e)
assert g.over and not g.ejected and e.witch is None, "no pod in witchspace; back to the save"
tick(e, fresh=["C"]); assert e.mode == "docked" and e.cmdr.system == home
os.remove(SAVE)
print("app: mis-jump, witchspace status and chart, jumping out, dying there: ok")
print("ALL WITCHSPACE TESTS PASSED")
