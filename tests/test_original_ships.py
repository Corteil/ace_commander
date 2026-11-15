"""The game's own ships (original_ships.py, build 55): sound data, every role
the game asks for, and the game playing with them, docking at both kinds
of station."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
from ace_commander import cockpit, game, original_ships
SHIPS = original_ships.SHIPS
# which way round Elite's slots are, if ship_data.py is there to compare with
ship_data_slots = []
try:
    from ace_commander import ship_data
    for e in ship_data.SHIPS:
        if e[0] in ("CORIOLIS", "DODO"):
            fr = max(v[2] for v in e[1])
            sl = [v for v in e[1] if v[2] == fr and abs(v[0]) < 40 and abs(v[1]) < 40]
            ship_data_slots.append((e[0], max(v[0] for v in sl) - min(v[0] for v in sl),
                                    max(v[1] for v in sl) - min(v[1] for v in sl)))
except ImportError:
    pass
DT = 0.04

# ---- the data ------------------------------------------------------------------
names = [e[0] for e in SHIPS]
assert len(names) == len(set(names)) == 31
need = set(game.PIRATES + game.HUNTERS + game.TRADERS + game.SHUTTLES + game.ROCKS
           + game.PARK_PIRATES + game.PARK_TRADERS + game.PARK_POLICE + game.PARK_LOW_TECH
           + game.PARK_HIGH_TECH + (game.POLICE, game.CONSTRICTOR)
           + tuple(n for tier in game.TIERS for n in tier)
           + ("CANISTER", "COBRA MK III", "CORIOLIS", "DODO", "MISSILE", "SPLINTER", "THARGOID",
              "THARGON", "ESCAPE POD", "PLATE"))
assert need <= set(names), need - set(names)
titles = [e[5] for e in SHIPS]
for e in SHIPS:
    key, verts, edges, normals, stats, title = e[:6]
    assert len(verts) <= len(cockpit._PX) and len(normals) <= len(cockpit._VIS), key
    for a, b, f1, f2 in edges:
        assert 0 <= a < len(verts) and 0 <= b < len(verts) and a != b, (key, a, b)
        assert 0 <= f1 < len(normals) and 0 <= f2 < len(normals), key
    assert len(stats) == 10 and 0 <= stats[2] < len(verts), key
    assert title and title == title.upper(), key
    bp = game.Blueprint(e)
    assert bp.title == title and bp.name == key
# none keeps Elite's name on screen (shuttles, missiles and rocks are just words)
for t in titles:
    assert t not in ("COBRA MK III", "VIPER", "SIDEWINDER", "THARGOID", "THARGON", "ADDER",
                     "ANACONDA", "ASP MK II", "BOA", "COBRA MK I", "CONSTRICTOR", "CORIOLIS",
                     "DODO", "FER DE LANCE", "GECKO", "KRAIT", "MAMBA", "MORAY", "PYTHON",
                     "WORM", "TRANSPORTER"), t
# every face of a hull points outwards: the middle of the ship is behind it
for e in SHIPS:
    key, verts, edges, normals = e[:4]
    if key in ("DODO", "PLATE"):      # the ring isn't one convex hull; the plate is two-sided
        continue
    c = [sum(v[j] for v in verts) / len(verts) for j in range(3)]
    for a, b, f1, f2 in edges:
        for f in (f1, f2):
            n = normals[f]
            if n == (0, 0, 0):
                continue
            v = verts[a]
            assert (v[0] - c[0]) * n[0] + (v[1] - c[1]) * n[1] + (v[2] - c[2]) * n[2] > -1e-6, key
# the stations: the slot is at the front, the furthest point forward, in the
# shape the tunnels draw (3:1 and 2:1)
for key in ("CORIOLIS", "DODO"):
    e = [x for x in SHIPS if x[0] == key][0]
    front = max(v[2] for v in e[1])
    slot = [v for v in e[1] if v[2] == front and abs(v[0]) < 40 and abs(v[1]) < 40]
    w = max(v[0] for v in slot) - min(v[0] for v in slot)
    h = max(v[1] for v in slot) - min(v[1] for v in slot)
    # long side up the station, as Elite's: lined up for docking it lies level
    assert abs(h / w - cockpit.SLOT_ASPECT[key]) < 0.1, (key, w, h)
    old = [x for x in ship_data_slots if x[0] == key]
    for k, ow, oh in old:
        assert (oh > ow) == (h > w), "the same way round as Elite's " + key
print("original ships: 31 roles, sound data, own names, outward faces, slots at the front: ok")

# ---- drawn from all round --------------------------------------------------------
class O:
    kind = "ship"
    hit = 0.0
for e in SHIPS:
    o = O(); o.bp = game.Blueprint(e)
    for k in range(12):
        a, b = k * 0.55, k * 0.3
        ca, sa, cb, sb = math.cos(a), math.sin(a), math.cos(b), math.sin(b)
        o.m = [ca, sa * sb, -sa * cb, 0.0, cb, sb, sa, -ca * sb, ca * cb]
        o.x, o.y, o.z = 0.0, 0.0, o.bp.size * 3
        cockpit.draw_ship(CountCtx(), o, None, 0, True)
# the ring station is drawn in convex parts, back to front: the hub always
# blacks out what is behind it, the ring's pieces only side-on, the spokes never
halo = game.Blueprint([e for e in SHIPS if e[0] == "DODO"][0])
assert halo.parts and sorted(p[2] for p in halo.parts) == [0, 0, 0, 1, 2, 2, 2, 2, 2, 2]
assert sorted(e for p in halo.parts for e in p[1]) == list(range(len(halo.edges))), \
    "every edge in exactly one part"
o = O(); o.bp = halo; o.x = o.y = 0.0; o.z = 1500.0
o.m = [-1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, -1.0]     # face on, the slot towards you
c = CountCtx(); cockpit.draw_ship(c, o, None, 0, False)
face_on = c.calls.get("fill", 0)
o.m = [0.0, 0.0, 1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 0.0]      # side on
c = CountCtx(); cockpit.draw_ship(c, o, None, 0, False)
assert face_on == 1 and c.calls.get("fill", 0) > face_on, (face_on, c.calls.get("fill", 0))
print("drawn from all round: ok")

# ---- playing with them --------------------------------------------------------------
random.seed(4)
for station in ("CORIOLIS", "DODO"):
    g = game.Game(SHIPS, 1)
    g.enter(5000, station, "arrive", 0)          # an anarchy: plenty turns up
    g.god = True
    for _ in range(int(120 / DT)):
        g.step(DT, 0.2, 0.1, 1.0, True, False)
        cockpit.draw(CountCtx(), g)
    assert g.kills >= 0 and g.space is not None
    # the docking computer flies in to each kind of station
    g = game.Game(SHIPS, 1)
    g.enter(5000, station, "launch", 3)
    g.computer = True
    g.to_station(4000.0, slot=False)
    assert g.start_autodock() is None
    for _ in range(int(60 / DT)):
        g.step(DT, 0, 0, 0, False, False)
        if g.docked:
            break
    assert g.docked, station
    # ships park in its bay, and yours fits the slot
    tun = cockpit.Tunnel(7, station)
    bps = [game.Blueprint(e) for e in SHIPS]
    assert tun.fits(game.Blueprint([e for e in SHIPS if e[0] == "COBRA MK III"][0])), station
    tun.park([b for b in bps if b.name in game.PARK_TRADERS + game.PARK_POLICE], random)
    assert tun.parked, station
    cockpit.draw_tunnel(CountCtx(), 0.5, 1.0, cockpit.WHITE, False, tun)
print("two minutes of fighting and docking at both stations, with ships in the bays: ok")
print("ALL ORIGINAL SHIP TESTS PASSED")
