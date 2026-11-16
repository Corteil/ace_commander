"""Phase 5, first part (build 42): traders, police and legal status."""
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
from ace_commander import commander, game, cockpit
mod = ace_commander.ace
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_traffic.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE
SHIPS = mod.SHIPS
DT = 0.04


def system(gov=3, seed=1, legal=0):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.enter(6000, "CORIOLIS", "launch", gov)
    g.encounter_t = 1e9
    g.rock_t = 1e9
    g.legal = legal
    g.speed = 0.0       # sitting still unless a test says otherwise
    return g


def ahead(g, o, z=1500.0):
    """Put ship o dead ahead, side on, standing still."""
    o.x, o.y, o.z = 0.0, 0.0, z
    game._look(o.m, 1.0, 0.0, 0.0)
    o.speed = 0.0
    g.objs.extend(g.new); g.new = []


# ---- legal status ---------------------------------------------------------
assert [game.legal_name(n) for n in (0, 1, 49, 50, 255)] == \
    ["CLEAN", "OFFENDER", "OFFENDER", "FUGITIVE", "FUGITIVE"]
cargo = [0] * 17
assert game.bad(cargo) == 0
cargo[3] = 2; cargo[6] = 1; cargo[10] = 4      # slaves, narcotics, firearms
assert game.bad(cargo) == (2 + 1) * 2 + 4
g = system()
g.illegal_cargo(cargo); assert g.legal == 10 and g.bad == 10 and g.msg == "ILLEGAL CARGO"
g.legal = 32; g.illegal_cargo(cargo); assert g.legal == 32 | 10, "ORed in, as the original does"
print("legal status, contraband (BAD), ORed in on launch: ok")

# ---- traders --------------------------------------------------------------
# outside the safe zone, from the ticks: a trader 35/256 x 1/2 of the time
g = system(); g.to_station(g.space.safe_r + 6000)
random.seed(5); n = 0
for _ in range(2000):
    g.objs = []; g.new = []; g.pending = 0; g.skip = 99
    g._tick(0, 0)
    n += sum(1 for o in g.new if o.role == "trader")
assert 70 < n < 210, n
# in the safe zone nothing turns up but the station's shuttles (out of the
# slot, so not with you lined up in front of it)
g = system(); assert g.space.safe
g.to_station(3000.0, False); game._look(g.space.station.m, 0.0, 0.0, 1.0)
seen = []
for _ in range(int(240 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    seen += [o for o in g.objs if o.kind == "ship" and o not in seen]
assert seen and all(o.bp.name in game.SHUTTLES and o.role == "trader" for o in seen), \
    [o.bp.name for o in seen]
assert len([o for o in g.objs if o.bp.name in game.SHUTTLES]) <= 1
# traders make for the station (and dock) or the planet
g = system()
t = g.add_trader("station"); g.objs.extend(g.new); g.new = []
st = g.space.station
t.x, t.y, t.z = st.x + 3000.0, st.y, st.z
for _ in range(int(60 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    if t.dead:
        break
d = math.sqrt((t.x - st.x) ** 2 + (t.y - st.y) ** 2 + (t.z - st.z) ** 2)
assert t.dead and d < 1500 and g.kills == 0, ("it reaches the station and docks", d)
g = system(); t = g.add_trader("planet")
assert t.dest == "planet" and t.m[6] * g.space.px + t.m[7] * g.space.py + t.m[8] * g.space.pz > 0
# fire on one: it fights back and the station turns hostile; your record is clean
g = system()
t = g.add_trader(); ahead(g, t); t.energy = 1000.0
g.step(DT, 0, 0, 0, True, False)
assert t.state == "attack" and g.space.hostile and g.legal == 0 and g.msg == "STATION HOSTILE"
t.energy = 1.0; g.cool = 0.0; g.heat = 0.0
g.step(DT, 0, 0, 0, True, False)
assert t.dead and g.legal == 0 and g.kills == 1 and g.bounty == t.bp.bounty
# one with no laser runs
g = system()
t = g.add_trader(); ahead(g, t)
t.bp = game.Blueprint(next(e for e in SHIPS if e[0] == t.bp.name)); t.bp.laser = 0
g.step(DT, 0, 0, 0, True, False)
assert t.state == "flee"
print("traders: from the ticks, shuttles from the station, dock or land, fired on: ok")

# ---- the hostile station ----------------------------------------------------
g = system()
g.to_station(3000.0)
g.step(DT, 0, 0, 0, True, False)
assert g.space.hostile and g.legal == 0, "firing on the station angers it"
# it launches police after you, four at most
g = system(); g.god = True; g.anger_station()
for _ in range(int(90 / DT)):
    g.step(DT, 0, 0, 0, False, False)
cops = [o for o in g.objs if o.role == "police"]
assert 1 <= len(cops) <= game.STATION_COPS and all(o.state in ("attack", "break") for o in cops)
assert not any(o.bp.name in game.SHUTTLES for o in g.objs), "no shuttles from a hostile station"
# docking refused: fast, the end; slow, a dent and a bounce
for style in ("A", "B", "C"):
    g = system(); g.set_docking(style); g.anger_station()
    g.to_station(400.0)
    g.speed = 10.0
    for _ in range(int(3 / DT)):
        g.step(DT, 0, 0, 0, False, False)
        if g.over or g.docked:
            break
    assert g.over and not g.docked, style
g = system(); g.set_docking("C"); g.anger_station()
g.to_station(game.DOCK_DIST - 50.0)
g.speed = 2.0
g.step(DT, 0, 0, 0, False, False)
assert not g.over and not g.docked and g.speed <= 1.0 and g.space.d_station > game.DOCK_DIST
assert g.msg == "DOCKING REFUSED" and g.shield == 100.0 - game.SLOW_CRASH
# the docking computer won't take you in, and switches off if the station turns
g = system(); g.computer = True; g.anger_station()
g.to_station(6000.0, False)
assert g.start_autodock() == "STATION HOSTILE" and not g.autodock
g = system(); g.computer = True; g.to_station(6000.0, False)
assert g.start_autodock() is None and g.autodock
g.anger_station(); assert not g.autodock
# nor does the tractor beam take hold (docking B)
g = system(); g.set_docking("B"); g.anger_station()
g.to_station(1200.0); g.speed = 10.0
g.step(DT, 0, 0, 0, False, False)
assert not g.tractor
g = system(); g.set_docking("B"); g.to_station(1200.0); g.speed = 10.0
g.step(DT, 0, 0, 0, False, False); assert g.tractor
g.anger_station(); assert not g.tractor, "it lets go"
# leaving the safe zone ends the lockdown (the original makes a new station)
g = system(); g.anger_station(); assert g.space.safe and g.space.hostile
g.to_station(g.space.safe_r + 1000.0); g.step(DT, 0, 0, 0, False, False)
assert not g.space.safe and not g.space.hostile
g.to_station(3000.0); g.step(DT, 0, 0, 0, False, False)
assert g.space.safe and not g.space.hostile
# so does a new system (or launch)
g = system(); g.anger_station()
g.reset(); g.enter(6000, "CORIOLIS", "launch", 3); assert not g.space.hostile
print("hostile station: refuses docking (fatal at speed 5+), launches police: ok")

# ---- police and bounty hunters ------------------------------------------------
# police from the ticks: only with contraband (or your record, once police are about)
g = system(); g.to_station(g.space.safe_r + 6000)
random.seed(2); g.legal = 60
cops = 0
for _ in range(500):
    g.objs = []; g.new = []; g.pending = 0; g.skip = 99
    g._tick(1, 0)
    cops += sum(1 for o in g.new if o.role == "police")
assert cops == 0, "a fugitive with an empty hold and no police about: none from the ticks"
g.bad = 40; cops = 0
for _ in range(500):
    g.objs = []; g.new = []; g.pending = 0
    g._tick(1, 0)
    cops += sum(1 for o in g.new if o.role == "police")
assert 100 < cops < 300, cops      # 80/256 of the 87% that aren't harmless
# they are hunters too: after you at 40 or more, on patrol below
g = system(legal=39); p = g.add_police(False); assert p.state == "patrol"
g.legal = 40; g.objs.extend(g.new); g.new = []
for _ in range(4):
    g.step(DT, 0, 0, 0, False, False)
assert p.state in ("attack", "break")
# fire on one: it turns on you; destroy it: a fugitive (64 ORed in)
g = system(); p = g.add_police(False); ahead(g, p); p.energy = 1000.0
g.step(DT, 0, 0, 0, True, False)
assert p.state == "attack" and g.legal == 0, "hitting a Viper only angers it"
p.energy = 1.0; g.cool = 0.0; g.heat = 0.0
g.step(DT, 0, 0, 0, True, False)
assert p.dead and g.legal == game.KILL_COP and g.msg == "FUGITIVE"
g = system(legal=3); g.objs.append(game.Obj(g.types["VIPER"], "ship", 0.0, 0.0, 3000.0))
g.objs[-1].role = "police"; g._kill(g.objs[-1]); assert g.legal == 3 | 64
# out of the slot when the station sends it
g = system(); p = g.add_police(True, True); st = g.space.station
d = math.sqrt((p.x - st.x) ** 2 + (p.y - st.y) ** 2 + (p.z - st.z) ** 2)
assert d < st.bp.front + p.bp.radius + 200 and p.state == "attack"
# hunters: 40 or more
g = system(); g.space.safe = False
h = g.add_hunter(); g.objs.extend(g.new); g.new = []
assert h.role == "hunter" and h.state == "patrol"
g.legal = 39
for _ in range(int(5 / DT)):
    g.step(DT, 0, 0, 0, False, False)
assert h.state == "patrol" and g.hull == 100.0, "an offender under 40 is left alone"
g.legal = 40
for _ in range(4):
    g.step(DT, 0, 0, 0, False, False)
assert h.state in ("attack", "break")
g = system(legal=45); assert g.add_hunter().state == "attack"
g = system(); h = g.add_hunter(); ahead(g, h); h.energy = 1000.0
g.step(DT, 0, 0, 0, True, False)
assert h.state == "attack" and g.legal == 0 and not g.space.hostile
# the encounter roll's hunters
g = system(gov=0); g.to_station(g.space.safe_r + 5000)
g._new_group(["ASP MK II"], "hunter"); g.spawn_t = 0.0
g.step(DT, 0, 0, 0, False, False)
hs = [o for o in g.objs + g.new if o.role == "hunter"]
assert hs and hs[0].state == "patrol"
# hostile counts only the ones attacking
g = system()
g.add_trader(); g.add_police(False); g.objs.extend(g.new); g.new = []
assert sum(1 for o in g.objs if o.kind == "ship" and o.state in ("attack", "break")) == 0
cx = CountCtx(); cockpit.draw_hud(cx, g)
print("police and hunters: contraband, 40 or more, killing a Viper makes a fugitive: ok")

# ---- keeping out of your way (build 47) -----------------------------------------
g = system()        # launch: just out of the slot, lined up in front of it
assert not g._slot_clear(), "nothing comes out at you"
g.to_station(3000.0, False)
game._look(g.space.station.m, 0.0, 0.0, 1.0)    # slot facing away: you're behind it
assert g._slot_clear()
game._look(g.space.station.m, 0.0, 0.0, -1.0)   # facing you, 3 km out
assert not g._slot_clear()
g.to_station(game.SLOT_CLEAR + 2000.0, False); game._look(g.space.station.m, 0.0, 0.0, -1.0)
assert g._slot_clear(), "far enough out"
g.to_station(3000.0, False); game._look(g.space.station.m, 0.0, 0.0, 1.0)
g.computer = True; g.start_autodock(); assert not g._slot_clear(), "not while the computer flies"
# the station holds its shuttles while the docking computer brings you in
real = game.SHUTTLE_CHANCE; game.SHUTTLE_CHANCE = 1.0
try:
    for seed in range(6):
        g = system(seed=seed); g.computer = True
        g.to_station(5000.0, False)
        game._look(g.space.station.m, *game._unit(random.uniform(-1, 1), random.uniform(-1, 1),
                                                   random.uniform(-1, 1)))
        hull = g.hull; shield = g.shield
        assert g.start_autodock() is None
        for _ in range(int(60 / DT)):
            g.step(DT, 0, 0, 0, False, False)
            assert not any(o.bp.name in game.SHUTTLES for o in g.objs + g.new), "none launched"
            if g.docked:
                break
        assert g.docked and g.shield == shield and g.hull == hull, seed
finally:
    game.SHUTTLE_CHANCE = real
# one already on its way out turns aside rather than fly into you
hits = 0
for seed in range(8):
    g = system(seed=seed); g.computer = True
    st = g.space.station
    g.to_station(5000.0, False); game._look(st.m, 0.0, 0.0, -1.0)   # slot facing you
    sh = g.add_shuttle(); g.objs.extend(g.new); g.new = []
    sh.dest = "planet"
    shield = g.shield
    g.start_autodock()
    for _ in range(int(60 / DT)):
        g.step(DT, 0, 0, 0, False, False)
        if g.docked:
            break
    hits += g.shield < shield
assert hits == 0, hits
# a trader heading straight at you turns away
g = system()
t = g.add_trader(); g.objs.extend(g.new); g.new = []
t.x, t.y, t.z = 0.0, 0.0, 2500.0; game._look(t.m, 0.0, 0.0, -1.0); t.speed = t.bp.speed
t.dest = "planet"
closest = 1e9
for _ in range(int(10 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    closest = min(closest, math.sqrt(t.x * t.x + t.y * t.y + t.z * t.z))
assert g.hull == 100.0 and g.shield == 100.0 and closest > 300, closest
print("out of your way: no launches when lined up or docking by computer, ships turn aside: ok")

# ---- pirates ------------------------------------------------------------------
# a pirate that follows you into the safe zone loses its nerve
g = system(); assert g.space.safe
pir = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0); g.objs.append(pir)
for _ in range(4):
    g.step(DT, 0, 0, 0, False, False)
assert pir.state == "patrol"
for _ in range(int(10 / DT)):
    g.step(DT, 0, 0, 0, False, False)
assert g.hull == 100.0
# they go for a nearer trader
g = system(); g.to_station(g.space.safe_r + 6000); g.god = True
t = g.add_trader(); g.objs.extend(g.new); g.new = []
t.x, t.y, t.z = 2500.0, 0.0, 5000.0; t.speed = 0.0; t.energy = 20.0
pir = game.Obj(g.types["SIDEWINDER"], "ship", 2500.0, 0.0, 3500.0)
game._look(pir.m, 0.0, 0.0, 1.0); g.objs.append(pir)
for _ in range(10):
    g.step(DT, 0, 0, 0, False, False)
assert pir.prey is t
for _ in range(int(60 / DT)):
    g.step(DT, 0, 0, 0, False, False); g.encounter_t = 1e9
    t.speed = 0.0
    if t.dead:
        break
assert t.dead and g.kills == 0 and g.legal == 0 and g.bounty == 0 and not g.space.hostile
for _ in range(4):
    g.step(DT, 0, 0, 0, False, False)
assert pir.prey is None or pir.dead
g = system(); g.to_station(g.space.safe_r + 6000)
t = g.add_trader(); g.objs.extend(g.new); g.new = []
t.x, t.y, t.z = 0.0, 0.0, -9000.0
pir = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0); g.objs.append(pir)
assert g._pick_prey(pir, 3000.0) is None
print("pirates: calm in the safe zone, go for a nearer trader: ok")

# ---- in the app: saved, carried, halved by jumps, cleared by the pod ---------
c = commander.Commander(); c.legal = 70
assert commander.Commander.from_dict(c.to_dict()).legal == 70
assert commander.Commander.from_dict({}).legal == 0
assert commander.Commander.from_dict({"legal": 999}).legal == 255
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
c = e.cmdr
c.cargo[3] = 5          # five tonnes of slaves
e.dock.go(0); tick(e, fresh=["C"])
for _ in range(200):
    tick(e)
    if e.mode == "flight":
        break
g = e.game
g.encounter_t = 1e9; g.station_t = 1e9
tick(e)
assert g.legal == 10 and c.legal == 10 and g.bad == 10, "launching with slaves"
# DEBUG: LEGAL goes round CLEAN, OFFENDER, FUGITIVE
def debug(a, line):
    if not a.paused:
        tick(a, fresh=["A"])
    a.fsub = "dgroup"
    a.dgroup = mod.cheat_group(line)
    a.fmenu = [i for i, t in enumerate(a._fitems()) if t.startswith(line)][0]
    tick(a, fresh=["C"])
debug(e, "LEGAL"); assert g.legal == game.FUGITIVE
debug(e, "LEGAL"); assert g.legal == 0
debug(e, "LEGAL"); assert g.legal == 20
n = len(g.objs) + len(g.new)
debug(e, "ADD A TRADER"); debug(e, "ADD POLICE")
assert len(g.objs) + len(g.new) == n + 2
debug(e, "ANGER STATION"); assert g.space.hostile
tick(e, fresh=["A"]); tick(e)
assert c.legal == 20
# a jump halves it
g.legal = 40; tick(e)
e.jump_to = (e.galaxy.in_range(c.system, c.fuel)[0][1], 1)
g.start_jump()
for _ in range(400):
    tick(e)
    if g.warp > 0:
        break
assert g.legal == 20 and c.legal == 20, (g.legal, c.legal)
# the status screens show it (in flight a screen, the game running on)
e._open("status")
cx = CountCtx(); e.draw(cx)
assert any("OFFENDER" in t[0] for t in cx.texts)
tick(e, fresh=["F"]); assert e.fsub is None
# the escape pod clears your record
c.extras.append("pod"); g.pod = True
g._hurt(1e6); tick(e)
assert g.ejected and c.legal == 0 and g.legal == 0
for _ in range(400):
    tick(e)
    if e.mode == "docked":
        break
assert e.mode == "docked" and commander.load(SAVE).legal == 0
cx = CountCtx(); e.dock.draw(cx); assert any("CLEAN" in t[0] for t in cx.texts)
# practice has none of it
p = ace_commander.AceCommander()
choose(p, "COMBAT PRACTICE")
tick(p, fresh=["A"])
every = [t for g_ in p._cheat_groups(True) for t in p._cheats(g_, True)]
assert not any(t.startswith(("LEGAL", "ADD A TRADER", "ADD POLICE", "ANGER")) for t in every)
os.remove(SAVE)
print("app: legal status saved, from illegal cargo, halved by jumps, cleared by the pod: ok")
print("ALL TRAFFIC TESTS PASSED")
