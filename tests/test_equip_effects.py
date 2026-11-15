"""The equipment's effects in flight (build 35): ECM, energy bomb, escape pod,
docking computer, galactic hyperdrive and mining laser."""
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
from ace_commander import commander, game, galaxy
mod = ace_commander.app
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_equip_effects.json")
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


def fresh(seed=1):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.spawn_t = g.rock_t = 1e9
    return g


def put(g, name, kind, x, y, z, face_player=True):
    o = game.Obj(g.types[name], kind, float(x), float(y), float(z))
    d = math.sqrt(x * x + y * y + z * z)
    if face_player:
        game._look(o.m, -x / d, -y / d, -z / d)
    g.objs.append(o)
    return o


def fly(g, seconds, **kw):
    for _ in range(int(seconds / DT)):
        g.step(DT, 0.0, 0.0, 0.0, kw.get("fire", False), False)


# ---- ECM ------------------------------------------------------------------
g = fresh()
m = put(g, "MISSILE", "missile", 0, 0, 6000); m.t = 12.0
fly(g, 2.0)
assert not m.dead and m.z < 6000, "without an ECM it keeps coming"
g.ecm = True; g.shield = 100.0
for _ in range(100):
    g.step(DT, 0.0, 0.0, 0.0, False, False)
    if m.dead:
        break
assert m.dead and g.msg == "ECM" and g.ecm_t > 0
assert g.shield < 100.0 - game.ECM_COST + 1, g.shield
assert math.sqrt(m.x * m.x + m.y * m.y + m.z * m.z) > 2000, "destroyed well short of you"
assert g.hull == 100.0, "it never reached you"
print("ECM: ok")

# ---- energy bomb ----------------------------------------------------------
g = fresh()
s1 = put(g, "SIDEWINDER", "ship", 0, 0, 3000)
s2 = put(g, "MAMBA", "ship", 2000, 500, -4000)
far = put(g, "SIDEWINDER", "ship", 0, 0, 13000)
rock = put(g, "ASTEROID", "rock", 500, 0, 2000)
can = put(g, "CANISTER", "can", 0, -30, 800)
assert g.energy_bomb() is False and g.msg == "NO ENERGY BOMB"
g.bombs = 1
assert g.energy_bomb() is True and g.bombs == 0 and g.bomb_t > 0
assert s1.dead and s2.dead and rock.dead and not far.dead and not can.dead
assert g.kills == 2 and g.bounty > 0
assert g.energy_bomb() is False, "once"
print("energy bomb: ok")

# ---- escape pod -----------------------------------------------------------
g = fresh(); g.pod = True
g._hurt(1e6)
assert g.over and g.ejected and not g.pod and g.msg == "ESCAPE POD LAUNCHED"
g = fresh(); g._hurt(1e6)
assert g.over and not g.ejected and g.msg == "GAME OVER"
print("escape pod (rules): ok")

# ---- mining laser ---------------------------------------------------------
for laser, want in (("pulse", 0), ("mining", 2)):
    g = fresh(3)
    g.set_laser(laser)
    r = put(g, "ASTEROID", "rock", 0, 0, 1500, face_player=False)
    r.speed = 0.0
    r.energy = 1.0
    for _ in range(10):
        g.step(DT, 0.0, 0.0, -1.0, True, False)
        if r.dead:
            break
    assert r.dead
    spl = [o for o in g.objs if o.kind == "can"]
    assert len(spl) >= want and (want or not spl), (laser, len(spl))
    if want:
        assert all(o.good == game.MINERALS and o.bp.name == "SPLINTER" for o in spl)
got = []
g.scoop = lambda i: got.append(i) or "MINERALS"
o = spl[0]; o.x, o.y, o.z = 0.0, -20.0, 10.0
g.step(DT, 0.0, 0.0, 0.0, False, False)
assert got == [game.MINERALS] and g.msg == "MINERALS"
print("mining laser: splinters, scooped as minerals: ok")

# ---- docking computer (rules) ---------------------------------------------
docked = 0
for seed in range(12):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.enter(4000, "CORIOLIS", "launch", 3)
    g.spawn_t = g.rock_t = 1e9
    sp = g.space; st = sp.station
    assert g.start_autodock() == "NO DOCKING COMPUTER"
    g.computer = True
    d = random.uniform(3000, sp.safe_r * 0.9)
    dx, dy, dz = game._unit(random.uniform(-1, 1), random.uniform(-1, 1), random.uniform(-1, 1))
    g._shift(dx * d - st.x, dy * d - st.y, dz * d - st.z); g._measure()
    assert g.start_autodock() is None and g.autodock
    for _ in range(int(60 / DT)):
        g.step(DT, 0.0, 0.0, 0.0, False, False)
        g.encounter_t = 1e9
        if g.docked:
            break
    docked += g.docked
    assert not g.autodock
assert docked == 12, docked
g = game.Game(SHIPS); g.enter(4000, "CORIOLIS", "launch", 3); g.computer = True
g.to_station(sp.safe_r * 3)
assert g.start_autodock() == "STATION TOO FAR"
print("docking computer docks you from anywhere in the safe zone: ok")

# ---- galaxies -------------------------------------------------------------
gd = mod.game_data
assert galaxy.seeds_for(gd.SEEDS, 0) == tuple(gd.SEEDS)
assert galaxy.seeds_for(gd.SEEDS, 8) == tuple(gd.SEEDS), "galaxy 8 goes round to the first"
assert galaxy.seeds_for((0x5A4A, 0x0248, 0xB753), 1) == (0xB494, 0x0490, 0x6FA6)
g2 = galaxy.Galaxy(galaxy.seeds_for(gd.SEEDS, 1), gd.PAIRS)
assert g2.system(0).name != galaxy.Galaxy(gd.SEEDS, gd.PAIRS).system(0).name
c = commander.Commander(); c.galaxy = 3
assert commander.Commander.from_dict(c.to_dict()).galaxy == 3
assert commander.Commander.from_dict({}).galaxy == 0
print("galaxy seeds, saved galaxy number: ok")

# ---- in the app -----------------------------------------------------------
def launch(a):
    a.dock.go(0)
    tick(a, fresh=["C"])
    for _ in range(200):
        tick(a)
        if a.mode != "launch":
            break
    assert a.mode == "flight" and a.career


def fpick(a, label):
    if not a.paused:
        tick(a, fresh=["A"])
    a.fmenu = a._fitems().index(label)
    tick(a, fresh=["C"])


e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
assert e.mode == "docked"
c = e.cmdr
c.extras += ["ecm", "pod", "bomb", "docking", "hyperdrive"]
c.cargo[0] = 5
home = c.system
launch(e)
g = e.game
assert g.ecm and g.pod and g.bombs == 1 and g.computer, "fitted for the flight"
g.spawn_t = g.rock_t = g.encounter_t = 1e9
# the menu has the docking computer near the station and the galactic jump
tick(e, fresh=["A"])
items = e._fitems()
assert "DOCKING COMPUTER" in items and "GALACTIC JUMP" in items, items
tx = texts(e)
tick(e, fresh=["A"])
# B sets off the bomb, once, and it is gone from the ship
put(g, "SIDEWINDER", "ship", 0, 0, 3000)
tick(e, fresh=["B"])
assert g.bombs == 0 and "bomb" not in c.extras and g.kills == 1
tick(e, fresh=["B"]); assert g.msg == "NO ENERGY BOMB"
# the docking computer: on from the menu, off when you take the stick
fpick(e, "DOCKING COMPUTER")
assert g.autodock and not e.paused
tick(e, held=["F"]); assert not g.autodock and g.msg == "DOCKING COMPUTER OFF"
fpick(e, "DOCKING COMPUTER"); assert g.autodock
tick(e, fresh=["A"]); assert "DOCK COMPUTER OFF" in e._fitems()
tick(e, fresh=["A"])
for _ in range(2000):
    tick(e)
    g.encounter_t = 1e9
    if e.mode != "flight":
        break
assert e.mode in ("docking", "docked"), e.mode
for _ in range(300):
    tick(e)
    if e.mode == "docked":
        break
assert e.mode == "docked"
print("app: bomb on B, docking computer from the menu: ok")

# the escape pod: destroyed with one, you wake up docked here, no cargo, full tank
launch(e); g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
c.fuel = 30
g._hurt(1e6); tick(e)
assert g.over and g.ejected and "ESCAPE POD" in texts(e)
assert "pod" not in c.extras and c.cargo[0] == 0 and c.fuel == commander.MAX_FUEL
for _ in range(200):
    tick(e)
    if e.mode == "docked":
        break
assert e.mode == "docked" and c.system == home
saved = commander.load(SAVE)
assert "pod" not in saved.extras and saved.cargo[0] == 0 and saved.kills == c.kills >= 1, \
    "the pod keeps what was done this flight; docking saves it"
# without it: GAME OVER as before
launch(e); g = e.game
assert not g.pod
g._hurt(1e6); tick(e); assert g.over and not g.ejected and "GAME OVER" in texts(e)
tick(e, fresh=["C"]); assert e.mode == "docked"
c = e.cmdr      # back to the last save: a new Commander
assert "hyperdrive" in c.extras
print("app: escape pod: ok")

# the galactic hyperdrive: a countdown, then the next galaxy, once
launch(e); g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
fuel = c.fuel
fpick(e, "GALACTIC JUMP")
assert g.jump_t > 0 and e.jump_to == ("galaxy", 0)
for _ in range(400):
    tick(e)
    if c.galaxy == 1:
        break
assert c.galaxy == 1 and e.galaxy_n == 1 and "hyperdrive" not in c.extras
assert c.system == e.galaxy.nearest(*galaxy.GAL_ARRIVE) and c.fuel == fuel
assert c.docked_at is None and commander.load(SAVE).galaxy == 0, "saved only on docking"
tick(e, fresh=["A"]); assert "GALACTIC JUMP" not in e._fitems(); tick(e, fresh=["A"])
print("app: galactic hyperdrive to galaxy 2: ok")
os.remove(SAVE)
print("ALL EQUIPMENT EFFECT TESTS PASSED")
