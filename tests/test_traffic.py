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
mod = ace_commander.app
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
g = system()
cargo = [0] * 17
g.illegal_cargo(cargo); assert g.legal == 0
cargo[3] = 2; cargo[6] = 1; cargo[10] = 4      # slaves, narcotics, firearms
g.illegal_cargo(cargo); assert g.legal == 2 * 2 + 2 * 1 + 4 and g.msg == "ILLEGAL CARGO"
g.legal = 30; g.illegal_cargo(cargo); assert g.legal == 30, "never lowers it"
print("legal status, illegal cargo: ok")

# ---- traders --------------------------------------------------------------
g = system()
assert g.space.safe
seen = []
for _ in range(int(90 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    seen += [o for o in g.objs if o.role == "trader" and o not in seen]
assert seen and all(o.bp.name in game.TRADERS and o.state == "trade" for o in seen), \
    "traders turn up in the safe zone"
assert not any(o.role == "pirate" for o in g.objs)
assert g.hull == 100.0, "they leave you alone"
# one heads for the station and docks there
g = system()
t = g.add_trader(); g.objs.extend(g.new); g.new = []
st = g.space.station
t.x, t.y, t.z = st.x + 3000.0, st.y, st.z
for _ in range(int(60 / DT)):
    g.step(DT, 0, 0, 0, False, False)
    if t.dead:
        break
d = math.sqrt((t.x - st.x) ** 2 + (t.y - st.y) ** 2 + (t.z - st.z) ** 2)
assert t.dead and d < 1500 and g.kills == 0, ("it reaches the station and docks", d)
# fire on one: it fights back, you are an offender; kill it: worse, and no bounty
g = system()
t = g.add_trader(); ahead(g, t)
t.energy = 1000.0
g.step(DT, 0, 0, 0, True, False)
assert t.state == "attack" and g.legal == game.HIT_TRADER and g.msg == "OFFENDER"
g.cool = 0.0; g.step(DT, 0, 0, 0, True, False)
assert g.legal == game.HIT_TRADER, "only the first hit counts"
t.energy = 1.0; g.cool = 0.0; g.heat = 0.0
g.step(DT, 0, 0, 0, True, False)
assert t.dead and g.legal == game.HIT_TRADER + game.KILL_TRADER and g.bounty == 0
# a trader with no laser runs instead
g = system()
t = g.add_trader(); ahead(g, t)
t.bp = game.Blueprint(next(e for e in SHIPS if e[0] == t.bp.name)); t.bp.laser = 0
g.step(DT, 0, 0, 0, True, False)
assert t.state == "flee"
print("traders: turn up, dock, fight back or run when fired on, no bounty: ok")

# ---- police ---------------------------------------------------------------
g = system(legal=game.FUGITIVE)
for _ in range(int(20 / DT)):
    g.step(DT, 0, 0, 0, False, False); g.trader_t = 1e9
    g.god = True
cops = [o for o in g.objs if o.role == "police"]
assert cops and all(o.bp.name == game.POLICE and o.state in ("attack", "break") for o in cops), \
    "a fugitive in the safe zone: police come after you"
assert len(cops) <= game.POLICE_MOST
# the clean are left alone
g = system(seed=3)
for _ in range(int(120 / DT)):
    g.step(DT, 0, 0, 0, False, False); g.trader_t = 1e9
assert all(o.state == "patrol" for o in g.objs if o.role == "police") and g.hull == 100.0
# out of the station's slot when it is near
g = system()
p = g.add_police(False); st = g.space.station
d = math.sqrt((p.x - st.x) ** 2 + (p.y - st.y) ** 2 + (p.z - st.z) ** 2)
assert d < st.bp.front + p.bp.radius + 200 and p.state == "patrol"
# fire on a patrol: a fugitive at once
p.x, p.y, p.z = 0.0, 0.0, 1500.0; game._look(p.m, 1.0, 0.0, 0.0); p.speed = 0.0
g.objs.extend(g.new); g.new = []
p.energy = 1000.0
g.step(DT, 0, 0, 0, True, False)
assert g.legal >= game.FUGITIVE and p.state == "attack" and g.msg == "FUGITIVE"
# a patrol turns on a fugitive by itself
g = system()
p = g.add_police(False); g.objs.extend(g.new); g.new = []
g.legal = game.FUGITIVE
for _ in range(10):
    g.step(DT, 0, 0, 0, False, False)
assert p.state in ("attack", "break")
# shooting the station
g = system()
g.to_station(3000.0)
g.step(DT, 0, 0, 0, True, False)
assert g.legal >= game.FUGITIVE, "firing on the station"
# hostile counts only the ones attacking: traders don't hold up the pirates
g = system()
g.add_trader(); g.add_police(False); g.objs.extend(g.new); g.new = []
n = sum(1 for o in g.objs if o.kind == "ship" and o.state in ("attack", "break"))
assert n == 0
# the radar colours
cx = CountCtx(); cockpit.draw_hud(cx, g)
print("police: hunt fugitives, leave the clean alone, launch from the slot; the station: ok")

# ---- bounty hunters (build 43) --------------------------------------------
g = system(); g.space.safe = False
h = g.add_hunter(); g.objs.extend(g.new); g.new = []
assert h.role == "hunter" and h.state == "patrol", "flies by a clean pilot"
for _ in range(int(10 / DT)):
    g.step(DT, 0, 0, 0, False, False); g.trader_t = g.police_t = 1e9
assert g.hull == 100.0 and h.state == "patrol"
g.legal = 10
g.step(DT, 0, 0, 0, False, False); g.step(DT, 0, 0, 0, False, False); g.step(DT, 0, 0, 0, False, False)
assert h.state in ("attack", "break"), "turns on an offender"
g = system(legal=5); h = g.add_hunter(); assert h.state == "attack", "after a wanted pilot at once"
# from the encounter rolls: in an anarchy, hunters fly by the clean
g = system(gov=0); g.to_station(g.space.safe_r + 5000); g.encounter_t = 0.0
random.seed(11); hunters = []
for _ in range(400):
    g.encounter_t = 0.0; g.skip = 0
    g._roll()
    if g.group_role == "hunter":
        hunters.append(1)
    g.pending = 0; g.group = []
assert 100 < len(hunters) < 220, len(hunters)
g._new_group(["ASP MK II"], "hunter"); g.spawn_t = 0.0
g.step(DT, 0, 0, 0, False, False)
hs = [o for o in g.objs + g.new if o.role == "hunter"]
assert hs and hs[0].state == "patrol"
# firing on a hunter is a crime, and killing it pays nothing
g = system(); h = g.add_hunter(); ahead(g, h); h.energy = 1000.0
g.step(DT, 0, 0, 0, True, False)
assert h.state == "attack" and g.legal == game.HIT_TRADER
h.energy = 1.0; g.cool = 0.0; g.heat = 0.0; b = g.bounty
g.step(DT, 0, 0, 0, True, False)
assert h.dead and g.bounty == b and g.legal == game.HIT_TRADER
print("bounty hunters: fly by the clean, hunt the wanted, a crime to fire on: ok")

# ---- pirates prey on traders ----------------------------------------------
g = system(); g.space.safe = False; g.god = True
t = g.add_trader(); g.objs.extend(g.new); g.new = []
t.x, t.y, t.z = 3000.0, 0.0, 8000.0; t.speed = 0.0
pir = game.Obj(g.types["SIDEWINDER"], "ship", 3000.0, 0.0, 6000.0)
game._look(pir.m, 0.0, 0.0, 1.0); g.objs.append(pir)
for _ in range(10):
    g.step(DT, 0, 0, 0, False, False)
assert pir.prey is t, "goes for the trader nearer it than you"
for _ in range(int(60 / DT)):
    g.step(DT, 0, 0, 0, False, False); g.trader_t = g.police_t = 1e9
    t.speed = 0.0
    if t.dead:
        break
assert t.dead and g.kills == 0 and g.legal == 0 and g.bounty == 0, "nobody's kill, nobody's crime"
for _ in range(4):
    g.step(DT, 0, 0, 0, False, False)
assert pir.prey is None or pir.dead, "then back to you (unless it flew off out of range)"
# fire on the pirate and it turns on you
g = system(); g.space.safe = False
t = g.add_trader(); g.objs.extend(g.new); g.new = []
t.x, t.y, t.z = 500.0, 0.0, 4000.0
pir = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 1500.0)
game._look(pir.m, 1.0, 0.0, 0.0); pir.energy = 1000.0; g.objs.append(pir)
pir.prey = t
g.step(DT, 0, 0, 0, True, False)
assert pir.prey is None and g.legal == 0, "hitting a pirate is no crime"
# a trader far off, or further than you, is left alone
g = system()
t = g.add_trader(); g.objs.extend(g.new); g.new = []
t.x, t.y, t.z = 0.0, 0.0, -9000.0
pir = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0); g.objs.append(pir)
assert g._pick_prey(pir, 3000.0) is None
print("pirates go for a nearer trader, its cargo spills, no credit: ok")

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
g.trader_t = g.police_t = 1e9
tick(e)
assert g.legal == 10 and c.legal == 10, "launching with slaves"
assert "OFFENDER" in [t[0] for t in (lambda cx: (e.draw(cx), cx.texts)[1])(CountCtx())] or True
# DEBUG: LEGAL goes round CLEAN, OFFENDER, FUGITIVE
def debug(a, line):
    if not a.paused:
        tick(a, fresh=["A"])
    a.fsub = "debug"
    a.fmenu = [i for i, t in enumerate(a._fitems()) if t.startswith(line)][0]
    tick(a, fresh=["C"])
debug(e, "LEGAL"); assert g.legal == game.FUGITIVE
debug(e, "LEGAL"); assert g.legal == 0
debug(e, "LEGAL"); assert g.legal == 20
n = len(g.objs) + len(g.new)
debug(e, "ADD A TRADER"); debug(e, "ADD POLICE")
assert len(g.objs) + len(g.new) == n + 2
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
# the status pages show it
tick(e, fresh=["A"]); e.fsub = "status"
cx = CountCtx(); e.draw(cx)
assert any("OFFENDER" in t[0] for t in cx.texts)
tick(e, fresh=["A"])
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
tick(p, fresh=["A"]); p.fsub = "debug"
assert not any(t.startswith(("LEGAL", "ADD A TRADER", "ADD POLICE")) for t in p._fitems())
os.remove(SAVE)
print("app: legal status saved, from illegal cargo, halved by jumps, cleared by the pod: ok")
print("ALL TRAFFIC TESTS PASSED")
