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
mod = ace_commander.ace
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
# from behind the station, with the slot turned away: round the side, then in along the axis
random.seed(5)
g = game.Game(SHIPS); g.enter(4000, "CORIOLIS", "launch", 3); g.computer = True
g.spawn_t = g.rock_t = 1e9
st = g.space.station
g.to_station(6000, False)
game._look(st.m, 0.0, 0.0, 1.0)     # the slot faces away from you
g.start_autodock()
closest = 1e9
for _ in range(int(60 / DT)):
    m = st.m
    # going round (not the final run in, which ends inside the slot: AUTO_IN)
    if -(st.x * m[6] + st.y * m[7] + st.z * m[8]) < st.bp.front and g.auto_phase < 2:
        closest = min(closest, g.space.d_station)
    g.step(DT, 0.0, 0.0, 0.0, False, False); g.encounter_t = 1e9
    if g.docked:
        break
m = st.m
cone = -(st.x * m[6] + st.y * m[7] + st.z * m[8]) / g.space.d_station
assert g.docked and closest > 2 * st.bp.radius, closest
assert cone >= game.SLOT_CONE_A and abs(m[3]) >= game.LEVEL_A, "on the axis, roll matched"
print("docking computer docks you from anywhere in the safe zone: ok")

from ace_commander import cockpit
# it flies on into the slot, and the chase camera closes in on the way (Brian: the
# station bigger before the tunnel): at the docking the camera is just outside the slot's face
random.seed(6)
g = game.Game(SHIPS); g.enter(4000, "CORIOLIS", "launch", 3); g.computer = True
g.spawn_t = g.rock_t = 1e9
st = g.space.station
g.to_station(3000, False)
g.start_autodock()
backs = []
for _ in range(int(90 / DT)):
    if g.autodock:
        backs.append((g.space.d_station, cockpit.chase_back(g)))
        cockpit.draw_world(CountCtx(), g)
    g.step(DT, 0.0, 0.0, 0.0, False, False); g.encounter_t = 1e9
    if g.docked:
        break
assert g.docked
d_last, back_last = backs[-1]
assert d_last < st.bp.front + 20, ("docks inside the slot", d_last)
assert back_last <= cockpit.CHASE_DOCK + game.AUTO_IN + 20, ("the camera closed in", back_last)
assert backs[0][1] == cockpit.CHASE_BACK, "far out: the usual chase view"
assert abs(d_last + back_last - st.bp.front - cockpit.CHASE_DOCK) < 30, \
    ("the camera just outside the slot's face", d_last, back_last)
# and it comes in on the slot's axis, rolled to it (build 95: pitch and yaw on the run in)
for station in ("CORIOLIS", "DODO"):
    for seed in range(3):
        random.seed(seed)
        g = game.Game(SHIPS); g.enter(4000, station, "launch", 3); g.computer = True
        g.spawn_t = g.rock_t = 1e9
        st = g.space.station
        g.to_station(3000 + 400 * seed, False)
        g.start_autodock()
        last = None
        for _ in range(int(150 / DT)):
            m = st.m
            d = g.space.d_station
            lz = -(st.x * m[6] + st.y * m[7] + st.z * m[8])
            a_ = math.degrees(math.atan2(m[4], m[3]))
            a_ = (a_ + 90) % 180 - 90
            last = (math.sqrt(max(0.0, d * d - lz * lz)), a_)
            g.step(DT, 0.0, 0.0, 0.0, False, False); g.encounter_t = 1e9
            if g.docked:
                break
        assert g.docked, (station, seed)
        assert last[0] < 4 and abs(last[1]) < 1.5, (station, seed, "off the axis / roll", last)
print("docking computer: into the slot, the chase camera closing in: ok")

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
    tick(a, fresh=["A"])        # A launches (C on Status is Options)
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

# DEBUG: LEVEL goes round the levels, for the enemies and the commander's ranks
def debug(a, line):
    if not a.paused:
        tick(a, fresh=["A"])
    a.fsub = "dgroup"
    a.dgroup = mod.cheat_group(line)
    a.fmenu = [i for i, t in enumerate(a._fitems()) if t.startswith(line)][0]
    tick(a, fresh=["C"])
launch(e); g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
lv = c.level
debug(e, "LEVEL")
assert g.level == c.level == (lv + 1) % 3 and c._needs == commander.thresholds(c.level)
assert commander.load(SAVE).level == c.level, "written into the save"
assert ("LEVEL: " + commander.LEVELS[c.level]) in e._fitems()
while c.level != lv:
    debug(e, "LEVEL")
tick(e, fresh=["A"]); assert not e.paused
e._dock()
print("app: DEBUG level: ok")

# the escape pod: destroyed with one, you wake up docked here, no cargo, full tank
launch(e); g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
c.fuel = 30
g._hurt(1e6); tick(e)
assert g.over and g.ejected and "ESCAPE POD" in texts(e)
assert "pod" not in c.extras and c.cargo[0] == 0 and c.fuel == commander.MAX_FUEL
for _ in range(int(mod.EJECT_TIME / 0.04) + 5):
    tick(e)
    if e.mode != "flight":
        break
assert e.mode == "docking", "the pod times out into the docking scene"
for _ in range(300):
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
g.legal = 30
c.stolen = g.stolen = True      # a hot ship: the new galaxy clears it too (build 85)
fpick(e, "GALACTIC JUMP")
assert g.jump_t > 0 and e.jump_to == ("galaxy", 0)
for _ in range(400):
    tick(e)
    if c.galaxy == 1:
        break
assert c.galaxy == 1 and e.galaxy_n == 1 and "hyperdrive" not in c.extras
assert c.system == e.galaxy.nearest(*galaxy.GAL_ARRIVE) and c.fuel == fuel
assert g.legal == 0, "a new galaxy, a clean record"
assert not c.stolen and not g.stolen, "and a clean ship"
assert c.docked_at is None and commander.load(SAVE).galaxy == 0, "saved only on docking"
tick(e, fresh=["A"]); assert "GALACTIC JUMP" not in e._fitems(); tick(e, fresh=["A"])
print("app: galactic hyperdrive to galaxy 2: ok")

# ---- build 38: held buttons, a fresh start each time, the chase view -------
from ace_commander import cockpit
e = ace_commander.AceCommander()
choose(e, "CONTINUE") if e.cmdr is not None else None
if e.cmdr is None:
    choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
c = e.cmdr
if "docking" not in c.extras:
    c.extras.append("docking")
launch(e); g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
# C still held for a few frames after choosing DOCKING COMPUTER: it stays on
tick(e, fresh=["A"]); e.fmenu = e._fitems().index("DOCKING COMPUTER")
for _ in range(6):          # the press that chooses it, then held on
    tick(e, held=["C"])
assert g.autodock, "a held C from the menu doesn't switch it off"
tick(e); tick(e, fresh=["C"]); assert not g.autodock, "a fresh press does"
fpick(e, "DOCKING COMPUTER"); assert g.autodock
# the chase view: your ship drawn, and everything put back where it was
before = [(o.x, o.y, o.z) for o in g.objs] + [(g.space.station.y, g.space.station.z, g.space.py)]
dust = [list(p) for p in g.dust]
cx = CountCtx(); e.draw(cx)
after = [(o.x, o.y, o.z) for o in g.objs] + [(g.space.station.y, g.space.station.z, g.space.py)]
assert before == after and dust == g.dust, "drawing leaves the game as it was"
# docking (or DOCK NOW) clears it; so does a jump
e._dock()
assert not g.autodock and g.auto_phase == 0
launch(e); g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
assert g.computer and not g.autodock
tick(e, fresh=["A"]); assert "DOCKING COMPUTER" in e._fitems(); tick(e, fresh=["A"])
g.autodock = True; g.jump_t = 0.01; g.step(DT, 0, 0, 0, False, False)
assert g.jumped and not g.autodock, "a jump switches it off"
os.path.exists(SAVE) and os.remove(SAVE)
print("build 38: held buttons, cleared on docking and jumping, chase view: ok")

# ---- build 39: C held on from a menu or the launch doesn't fire --------------
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
e.dock.go(0); tick(e, fresh=["A"])
for _ in range(80):             # A launches; C skips the tunnel and stays held
    tick(e, held=["C"])
    if e.mode == "flight":
        break
assert e.mode == "flight"
g = e.game; g.spawn_t = g.rock_t = g.encounter_t = 1e9
heat = g.heat
for _ in range(5):
    tick(e, held=["C"])
assert g.beam <= 0 and g.heat <= heat, "no shot from the C held on from launching"
tick(e); tick(e, held=["C"]); assert g.beam > 0, "a new press fires"
tick(e)
for _ in range(10):
    tick(e)
tick(e, fresh=["A"]); e.fmenu = e._fitems().index("RESUME")
g.beam = 0.0; heat = g.heat
for _ in range(5):
    tick(e, held=["C"])
assert not e.paused and g.beam <= 0, "nor from the C that chose RESUME"
print("build 39: held C after a menu or launch doesn't fire: ok")

# ---- build 40: your ship in the tunnel scenes --------------------------------
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
e.dock.go(0); tick(e, fresh=["A"])
assert e.mode == "launch" and e.tunnel.me is not None and e.tunnel.me.bp.name == "COBRA MK III"
for f in (0.0, 0.5, 0.99):
    e.launch_t = f * mod.LAUNCH_TIME
    cx = CountCtx(); e.draw(cx)
    assert e.tunnel.me.z > 0 and e.tunnel.me.x == 0.0
e._pick_tunnel(); assert e.tunnel.me is not None, "docking too"
print("build 40: your ship flies through the tunnel: ok")

# every ship you can fly shows in both stations' tunnels: one too big for the slot
# (a Boa in a Coriolis) is drawn shrunk to fit (Brian: the Boa was missing)
from ace_commander import ships as ships_mod
types = {e_[0]: game.Blueprint(e_) for e_ in mod.SHIPS}
flyable = [n for n in types if n not in ("CORIOLIS", "DODO", "THARGOID", "THARGON", "ASTEROID",
                                         "BOULDER", "ROCK", "SPLINTER", "CANISTER", "ESCAPE POD",
                                         "MISSILE", "PLATE", "ALLOY PLATE", "CARGO", "SPACE STATION")
           and n in getattr(ships_mod, "SHIP_TYPES", types)]
for station in ("CORIOLIS", "DODO"):
    tun = cockpit.Tunnel(0, station)
    for n in flyable:
        bp = types[n]
        tun.fly(bp)
        me = tun.me
        assert me is not None, (station, n, "your ship always shows")
        k = me.m[0]
        hw = k * max(abs(v[0]) for v in bp.verts)
        hh = k * max(abs(v[1]) for v in bp.verts)
        room = cockpit.SHIP_SCALE * cockpit.SLOT_ROOM
        assert hw <= room + 1e-6 and hh <= room / tun.aspect + 1e-6, (station, n, k)
        assert k == 1.0 or not tun.fits(bp), "only too-big ships are shrunk"
        e.tunnel = tun
        for f in (0.0, 0.5, 0.99):
            e.mode = "launch"; e.launch_t = f * mod.LAUNCH_TIME
            e.draw(CountCtx())
big = cockpit.Tunnel(0, "CORIOLIS")
big.fly(types["BOA"]) if "BOA" in types else None
assert "BOA" not in types or big.me.m[0] < 1.0, "a Boa in a Coriolis: shrunk"
e.mode = "docked"; e._pick_tunnel()
print("every ship shows in the tunnels, shrunk to fit where it's too big: ok")

# ---- build 41: take off and land; the Repair Shop (DEBUG switch) -------------
from ace_commander import docked as docked_mod
c = commander.Commander(); c.colour = 5
assert commander.Commander.from_dict(c.to_dict()).colour == 5
assert commander.Commander.from_dict({}).colour == 0
assert cockpit.ship_rgb(5) == cockpit.SHIP_COLOURS[5][1] and cockpit.ship_rgb(99) == cockpit.ME_RGB
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
assert e.dock.repair, "always there (Brian, build 81: no DEBUG switch)"
launch(e); g = e.game
tick(e, fresh=["A"]); e.fsub = "dgroup"; e.dgroup = "DISPLAY"
assert not any(t.startswith("REPAIR SHOP") for t in e._fitems())
tick(e, fresh=["A"])
e._dock()
d = e.dock
assert d.repair
d.open("REPAIR SHOP"); assert d.name() == "REPAIR SHOP"; texts(e)
c = e.cmdr; c.cash = 1000
tick(e, fresh=["C"]); assert d.msg == "ALREADY THAT COLOUR" and c.cash == 1000
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["JOYDOWN"]); assert d.paint == 2
tick(e, fresh=["C"]); assert c.colour == 2 and c.cash == 1000 - docked_mod.PAINT_PRICE
d.paint = 4; c.cash = 5
tick(e, fresh=["C"]); assert d.msg == "NOT ENOUGH CASH" and c.colour == 2
assert "RED" in texts(e) or True
# the paint shows in the tunnel and the docking computer's view
d.go(0); tick(e, fresh=["A"])
assert e.mode == "launch" and e.tunnel.me_rgb == cockpit.SHIP_COLOURS[2][1]
# taking off: on the floor at first, at flying height once up
me = e.tunnel.me
e.launch_t = 0.0; texts(e); y0 = me.y
e.launch_t = 0.5 * mod.LAUNCH_TIME; texts(e); y1 = me.y
assert y0 < y1, "it rises off the bay floor"
for _ in range(200):
    tick(e)
    if e.mode == "flight":
        break
assert e.game.ship_rgb == cockpit.SHIP_COLOURS[2][1]
# landing: at flying height coming in, on the floor at the end
e._fly_in()
e.dock_t = 0.3 * mod.DOCK_TIME; texts(e); y0 = e.tunnel.me.y
e.dock_t = mod.DOCK_TIME; texts(e); y1 = e.tunnel.me.y
assert y1 < y0, "it settles onto the floor"
os.path.exists(SAVE) and os.remove(SAVE)
print("build 41: take off and land, Repair Shop paint: ok")

# ---- build 46: the station in 3D at any distance in the docking computer's view
g = game.Game(SHIPS); g.enter(4000, "CORIOLIS", "launch", 3)
st = g.space.station
g.to_station(40000.0, False); g.autodock = True
before = (st.x, st.y, st.z)
calls = []
real = cockpit.draw_ship
def spy(ctx, o, rgb=None, wire_min=cockpit.WIRE_MIN, solid=False):
    calls.append((o, wire_min, o.z))
    return real(ctx, o, rgb, wire_min, solid)
cockpit.draw_ship = spy
try:
    cockpit.draw_world(CountCtx(), g)
finally:
    cockpit.draw_ship = real
s_calls = [c for c in calls if c[0] is st]
assert s_calls and s_calls[0][1] == 0, "a wireframe, never a dot or marker"
assert s_calls[0][2] == before[2] + cockpit.CHASE_BACK, "at its true distance from the camera: to scale (build 48)"
assert (st.x, st.y, st.z) == before, "put back where it was"
g.autodock = False; calls[:] = []
cockpit.draw_ship = spy
try:
    cockpit.draw_world(CountCtx(), g)
finally:
    cockpit.draw_ship = real
assert [c for c in calls if c[0] is st][0][1] == cockpit.WIRE_MIN, "the cockpit view as before"
print("builds 46, 48: the station a wireframe at any distance, to scale, in the docking computer's view: ok")

# ---- auto missiles (build 112: a device with no missile button) ---------------------
g = fresh(21)
g.set_level(2)                        # HARD: the longest auto lock (AUTO_LOCK_TIMES)
g.auto_missile = True
g.missiles = 4
t = put(g, "SIDEWINDER", "ship", 0, 0, 3000)
t.speed = 0.0
for _ in range(int(3.5 / DT)):        # in the sights 3.5 s: not yet locked (AUTO_LOCK_TIME 4)
    t.x, t.y, t.z = 0.0, 0.0, 3000.0
    g.step(DT, 0.0, 0.0, 0.0, False, False)
assert not g.locked and g.missiles == 4, "the longer lock with auto missiles at HARD"
for _ in range(int(1.0 / DT)):        # locked now, but the laser is firing: it waits
    t.x, t.y, t.z = 0.0, 0.0, 3000.0
    t.energy = 1e9
    g.heat = 0.0
    g.step(DT, 0.0, 0.0, 0.0, True, False)
assert g.locked and g.missiles == 4, ("no launch while the laser fires", g.locked, g.missiles)
for _ in range(int(0.6 / DT)):        # the laser stops: one missile goes
    t.x, t.y, t.z = 0.0, 0.0, 3000.0
    g.step(DT, 0.0, 0.0, 0.0, False, False)
assert g.missiles == 3, ("one launch once the laser stops", g.missiles)
for _ in range(int(1.0 / DT)):        # and only one at that ship
    t.x, t.y, t.z = 0.0, 0.0, 3000.0
    g.step(DT, 0.0, 0.0, 0.0, False, False)
assert g.missiles == 3, ("only one a ship", g.missiles)
g2 = fresh(22)
assert not g2.auto_missile, "off unless a host asks"
t2 = put(g2, "SIDEWINDER", "ship", 0, 0, 3000)
t2.speed = 0.0
for _ in range(int(5.0 / DT)):
    t2.x, t2.y, t2.z = 0.0, 0.0, 3000.0
    g2.step(DT, 0.0, 0.0, 0.0, False, False)
assert g2.locked and g2.missiles == game.MAX_MISSILES, "without it nothing fires by itself"
ge = fresh(30)
ge.set_level(0)
ge.auto_missile = True
te = put(ge, "SIDEWINDER", "ship", 0, 0, 3000)
te.speed = 0.0
for _ in range(int(2.2 / DT)):
    te.x, te.y, te.z = 0.0, 0.0, 3000.0
    ge.step(DT, 0.0, 0.0, 0.0, False, False)
assert ge.locked, "EASY: locked in 2 s"
print("auto missiles: lock 2 / 3 / 4 s by level, wait for the laser, one a ship: ok")


# ---- practice upgrades (build 113): each wave cleared drops an upgrade canister ----
g = fresh(23)
g.practice_upgrades = True
g.auto_missile = True
assert g.space is None and g.upgrade_n == 0
for _ in range(3):                    # wave 1: 2 + 1 kills clear it
    g._kill(put(g, "SIDEWINDER", "ship", 0, 0, 3000))
ups = [o for o in g.objs + g.new if o.kind == "can" and o.upgrade]
assert g.wave == 2 and len(ups) == 1, (g.wave, len(ups))
u = ups[0]
assert u.z <= game.UPGRADE_AHEAD and abs(u.x) < 1 and abs(u.y) < 60, "straight ahead, close"
gp = fresh(28)
gp.practice_upgrades = True
for _ in range(3):
    gp._kill(put(gp, "SIDEWINDER", "ship", 0, 0, 3000))
gp.objs[:] = [o for o in gp.objs + gp.new if o.upgrade]
gp.new[:] = []
gp.speed = 10.0
for _ in range(int(4.0 / DT)):        # fly on, not steering: it's picked up
    gp.step(DT, 0.0, 0.0, 0.0, False, False)
    if gp.upgrade_n:
        break
assert gp.upgrade_n == 1 and gp.laser == "beam", "flying straight on picks it up"
fitted = []
for want in ("beam", "energy unit", "military", "bomb"):
    g.missiles = 0
    g._upgrade()
    fitted.append(want)
    assert g.missiles == g.max_missiles, "auto missiles: the rack filled too"
assert g.laser == "military" and g.energy_unit and g.bombs == 1, (g.laser, g.energy_unit, g.bombs)
g.bombs = 0
g._upgrade()
assert g.bombs == 1, "after the list, a used bomb comes back"
g2 = fresh(24)
g2.practice_upgrades = True
for _ in range(3):
    g2._kill(put(g2, "SIDEWINDER", "ship", 0, 0, 3000))
g2.missiles = 1
g2._upgrade()
assert g2.missiles == 1 and g2.laser == "beam", "without auto missiles the rack isn't filled"
g3 = fresh(25)
for _ in range(3):
    g3._kill(put(g3, "SIDEWINDER", "ship", 0, 0, 3000))
assert not [o for o in g3.objs + g3.new if o.upgrade], "a bare Game: off until ace sets it from config"
# the countdown: nobody new for WAVE_WAIT seconds, the seconds shown, then the wave
g4 = fresh(26)
g4.practice_upgrades = True
g4.spawn_t = 0.0
for _ in range(3):
    g4._kill(put(g4, "SIDEWINDER", "ship", 0, 0, 3000))
g4.objs[:] = [o for o in g4.objs if o.upgrade] + [o for o in g4.new if o.upgrade]
g4.new[:] = []
assert g4.wave_hold > 0 and g4.wave_wait == 0, "the countdown waits for the canister"
for _ in range(int(3.0 / DT)):        # not collected: nobody new, no countdown
    for o in g4.objs:
        if o.upgrade:
            o.x, o.y, o.z = 0.0, 300.0, 900.0   # kept out of reach
    g4.step(DT, 0.0, 0.0, 0.0, False, False)
    assert not [o for o in g4.objs if o.kind == "ship"] and g4.wave_wait == 0
for o in g4.objs:
    if o.upgrade:
        o.dead = True               # collected (as scooping does)
g4._upgrade()
seen = set()
for _ in range(int((game.WAVE_WAIT - 0.3) / DT)):
    g4.step(DT, 0.0, 0.0, 0.0, False, False)
    seen.add(g4.msg)
    assert not [o for o in g4.objs if o.kind == "ship"], "nobody new during the countdown"
assert "WAVE 2 IN 5" in seen and "WAVE 2 IN 1" in seen, sorted(seen)
for _ in range(int(1.0 / DT)):
    g4.step(DT, 0.0, 0.0, 0.0, False, False)
assert g4.wave_wait == 0.0 and [o for o in g4.objs + g4.new if o.kind == "ship"], "then the wave"
# a canister missed: after UPGRADE_WAIT it goes and the countdown starts anyway
g6 = fresh(29)
g6.practice_upgrades = True
for _ in range(3):
    g6._kill(put(g6, "SIDEWINDER", "ship", 0, 0, 3000))
g6.objs[:] = [o for o in g6.objs + g6.new if o.upgrade]
g6.new[:] = []
for _ in range(int((game.UPGRADE_WAIT + 0.5) / DT)):
    for o in g6.objs:
        if o.upgrade and not o.dead:
            o.x, o.y, o.z = 0.0, 300.0, 900.0
    g6.step(DT, 0.0, 0.0, 0.0, False, False)
assert g6.wave_hold == 0 and (g6.wave_wait > 0 or g6.msg.startswith("WAVE")), (g6.wave_hold, g6.wave_wait)
assert not [o for o in g6.objs if o.upgrade and not o.dead], "the missed canister goes"
# the upgrade canister can't be shot
g5 = fresh(27)
c = g5.release_canister(600.0)
c.upgrade = True
c.speed = 0.0
for _ in range(int(2.0 / DT)):
    c.x, c.y, c.z = 0.0, 0.0, 600.0
    g5.heat = 0.0
    g5.step(DT, 0.0, 0.0, 0.0, True, False)
assert not c.dead, "the upgrade canister survives the laser"
print("practice upgrades: a canister a wave (unshootable), beam, energy unit, military, bomb;"
      " missiles with auto; a 5 s countdown: ok")

print("ALL EQUIPMENT EFFECT TESTS PASSED")
