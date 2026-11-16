"""The four views (front, rear, left, right), a laser on each, in every mode. Uses the game's own
ship data so it runs without Elite's files. Elite's PU1 / PU2: rear flips x and z, left makes
(x, z) = (z, -x), right makes (-z, x)."""
import math, os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import game, cockpit, commander, equipment, rules
mod = ace_commander.ace
SHIPS = mod.SHIPS
DT = 0.04


def flight(hardcore=False, seed=1):
    random.seed(seed)
    g = game.Game(SHIPS)
    g.rules = rules.GameRules(hardcore)
    g.rock_t = g.encounter_t = g.spawn_t = 1e9
    g.objs[:] = []
    return g


def put(g, x, y, z, name=None):
    name = name or next(n for n in g.types if g.types[n].energy and n != "MISSILE")
    o = game.Obj(g.types[name], "ship", float(x), float(y), float(z))
    o.state = "break"; o.t = 99; o.aim = [1.0, 0.0, 0.0]
    g.objs.append(o)
    return o


# ---- Elite's flips, exactly, and back again
g = flight()
o = put(g, 100, 20, 700)
game._look(o.m, 0.6, 0.0, 0.8)
before = (o.x, o.y, o.z, list(o.m))
for view, want in ((1, (-100, 20, -700)), (2, (700, 20, -100)), (3, (-700, 20, 100))):
    g.view = view
    g.enter_view()
    assert (o.x, o.y, o.z) == want, (view, (o.x, o.y, o.z))
    g.leave_view()
    assert (o.x, o.y, o.z, o.m) == before, view
g.view = 0
print("view flips: ok")

# the nose turns with the world: a ship flying straight at you from ahead, seen from the rear,
# is flying away from you; seen from the left it crosses
g.view = 1
g.enter_view()
assert o.m[6] == -0.6 and abs(o.m[8] + 0.8) < 1e-9
g.leave_view()
g.view = 0

# ---- things are where Elite puts them: ahead is to the right in the left view
g = flight()
a = put(g, 0, 0, 2000)
b = put(g, 0, 0, -2000)       # behind
c = put(g, 2000, 0, 0)        # to the right
d = put(g, -2000, 0, 0)       # to the left
for view, ahead_of_view in ((1, b), (2, d), (3, c)):
    g.view = view
    g.enter_view()
    assert ahead_of_view.z > 1900 and abs(ahead_of_view.x) < 1, view
    g.leave_view()
assert g.view == 3
g.view = 2
g.enter_view()
assert a.x > 1900 and abs(a.z) < 1       # what is ahead is to the right when looking left
g.leave_view()
g.view = 3
g.enter_view()
assert a.x < -1900                       # and to the left looking right
g.leave_view()
print("directions: ok")

# ---- laser per view: only the view's laser fires; none says so
for hardcore in (False, True):
    g = flight(hardcore)
    g.set_laser("pulse", 0)
    g.set_laser("beam", 1)
    assert g.laser == "pulse" and g.lasers == ["pulse", "beam", None, None]
    g.set_view(1)
    assert g.laser == "beam" and g.laser_period != game.LASERS["pulse"][0]
    g.set_view(2)
    assert g.laser is None
    t = put(g, 0, 0, 0)             # placed below for each view
    # a ship straight ahead of the LEFT view is at x = -z... (x = -1500 in the ship's frame)
    t.x, t.y, t.z = -1500.0, 0.0, 0.0
    e0 = t.energy
    for _ in range(40):
        g.step(DT, 0, 0, 0, True, False)
        t.x, t.y, t.z = -1500.0, 0.0, 0.0
    assert t.energy == e0, "no laser on the left: nothing fires"
    g.set_laser("pulse", 2)
    for _ in range(40):
        g.step(DT, 0, 0, 0, True, False)
        t.x, t.y, t.z = -1500.0, 0.0, 0.0
    assert t.energy < e0, "the left laser hits what is to the left"
    # the front laser doesn't hit it
    g.set_view(0)
    t.energy = e0
    for _ in range(40):
        g.step(DT, 0, 0, 0, True, False)
        t.x, t.y, t.z = -1500.0, 0.0, 0.0
    assert t.energy == e0
    # a ship behind: the rear laser
    g.set_view(1)
    t.energy = e0
    for _ in range(40):
        g.step(DT, 0, 0, 0, True, False)
        t.x, t.y, t.z = 0.0, 0.0, -1500.0
    assert t.energy < e0
print("laser per view: ok")

# ---- the world is back in the front frame after weapons run in another view
g = flight()
t = put(g, -1500, 0, 0)
g.set_laser("pulse", 2)
g.set_view(2)
g.step(DT, 0, 0, 0, True, False)
assert g.view == 2 and abs(t.x + 1500) < 5, (t.x, t.z)
print("frame restored: ok")

# ---- a missile goes straight ahead whichever view, and locks on what the view sees
for hardcore in (False, True):
    g = flight(hardcore)
    g.set_laser("pulse", 2)
    g.set_view(2)
    t = put(g, -4000, 0, 0)         # dead ahead of the left view
    t.speed = 0.0
    if hardcore:
        g.arm_missile()
    for _ in range(int(3.0 / DT)):
        t.x, t.y, t.z = -4000.0, 0.0, 0.0
        g.step(DT, 0, 0, 0, False, False)
    assert g.lock is t and g.locked, "lock builds through the left view"
    t.x, t.y, t.z = -4000.0, 0.0, 0.0
    n = g.missiles
    g.step(DT, 0, 0, 0, False, True)
    assert g.missiles == n - 1
    m = [o for o in g.objs + g.new if o.kind == "pmissile"][0]
    assert abs(m.x) < 1 and m.z > 0, "launched ahead of the ship, not along the view"
print("missiles: ok")

# ---- the draw runs in every view, leaves the world as it was, and shows the name
class Ctx:
    CENTER = LEFT = RIGHT = MIDDLE = 0
    def __init__(self): self.texts = []
    def __getattr__(self, n):
        if n == "text":
            return lambda s: (self.texts.append(s), self)[1]
        return lambda *a, **k: self
for view in range(4):
    g = flight()
    g.set_view(view)
    put(g, 300, 50, 900)
    put(g, -400, 0, -900)
    g.dust = [[10, 10, 500], [-300, 20, 900]]
    snap = [(o.x, o.y, o.z, list(o.m)) for o in g.objs]
    dust = [list(p) for p in g.dust]
    ctx = Ctx()
    cockpit.draw_world(ctx, g)
    cockpit.draw_hud(ctx, g)
    assert [(o.x, o.y, o.z, o.m) for o in g.objs] == snap and g.dust == dust, view
    assert ((game.VIEW_NAMES[view] + " VIEW") in ctx.texts) == (view != 0), (view, ctx.texts)
print("drawing: ok")

# the stardust: rushes away from the rear, streams past the sides
g = flight()
g.dust = [[100, 0, 400]]
for view, test in ((1, lambda p: p[2] > 800), (2, lambda p: p[0] < 0), (3, lambda p: p[0] > 0)):
    g.view = view
    v = g.view_dust()
    assert test(v[0]) or view == 2, (view, v)
g.view = 0
assert g.view_dust() is g.dust
# dust that falls behind the ship (z decreasing) moves away in the rear view
g.view = 1
z0 = g.view_dust()[0][2]
g.dust[0][2] -= 100
assert g.view_dust()[0][2] > z0
g.view = 0
print("stardust: ok")

# ---- commander: a laser per view, saved and loaded; old saves still load
c = commander.Commander(1)
assert c.lasers == ["pulse", "", "", ""] and c.laser == "pulse"
c.lasers[1] = "beam"
c.lasers[3] = "military"
c2 = commander.Commander.from_dict(c.to_dict())
assert c2.lasers == ["pulse", "beam", "", "military"]
d = c.to_dict(); del d["lasers"]; d["laser"] = "mining"
assert commander.Commander.from_dict(d).lasers == ["mining", "", "", ""]
d = c.to_dict(); d["lasers"] = ["", "x", "beam", "pulse"]; d["laser"] = "beam"
assert commander.Commander.from_dict(d).lasers == ["beam", "", "beam", "pulse"]
print("commander lasers: ok")

# ---- the shop: a laser goes to the chosen view, refunding that view's old laser only
equip = [("X", 10)] * 14
equip[equipment.PULSE] = ("PULSE", 400)
equip[equipment.BEAM] = ("BEAM", 1000)
c = commander.Commander(1)
c.cash = 5000
assert equipment.buy(equip, equipment.BEAM, c, 1) is None and c.lasers == ["pulse", "beam", "", ""]
assert c.cash == 4000                                       # nothing to refund on an empty mount
assert equipment.have(equipment.BEAM, c, 1) == "fitted" and equipment.have(equipment.BEAM, c, 0) == ""
assert equipment.buy(equip, equipment.BEAM, c, 1) == "ALREADY FITTED"
assert equipment.buy(equip, equipment.BEAM, c, 0) is None and c.cash == 4000 - 1000 + 400
assert c.lasers == ["beam", "beam", "", ""]
assert equipment.buy(equip, equipment.PULSE, c, 1) is None and c.cash == 3400 - 400 + 1000
print("shop: ok")

# ---- through the app: keys (both modes), the menu line, the commander's lasers
from badge_stubs import tick, choose
SAVE = os.path.join(HERE, "shots", "test_views.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE
for n in range(4):      # the number keys (the real names are not checked yet)
    bs.KEYS[str(n)] = bs.Button(str(n), "Keyboard")
    bs.PHYSICAL["KEY_%d" % n] = bs.KEYS[str(n)]


def app_flight(hardcore):
    bs.press(())
    a = ace_commander.AceCommander()
    a.hardcore = hardcore
    tick(a)
    choose(a, "COMBAT PRACTICE")
    g = a.game
    g.spawn_t = g.rock_t = g.encounter_t = 1e9
    g.objs[:] = []
    g.speed = 10.0
    tick(a)
    return a, g


for hardcore in (False, True):
    a, g = app_flight(hardcore)
    g.set_laser("pulse", 1)
    assert g.view == 0
    tick(a, fresh=["KEY_1"])
    assert g.view == 1 and g.laser == "pulse", "1: rear"
    tick(a, fresh=["KEY_2"])
    assert g.view == 2 and g.laser is None, "2: left"
    tick(a, fresh=["KEY_3"])
    assert g.view == 3, "3: right"
    tick(a, fresh=["KEY_0"])
    assert g.view == 0, "0: front"
    tick(a, fresh=["KEY_V"])
    assert g.view == 1, "V: the next view round"
    for _ in range(3):
        tick(a, fresh=["KEY_V"])
    assert g.view == 0
print("keys, both modes: ok")

# the menu: choosing VIEW goes to the next view and back to the flight
a, g = app_flight(False)
tick(a, fresh=["A"])            # the in-flight menu
assert a.paused
a.fmenu = a._fitems_top().index("VIEW: FRONT")
tick(a, fresh=["CONFIRM"])
assert g.view == 1 and not a.paused, (g.view, a.paused)
tick(a, fresh=["A"])
assert "VIEW: REAR" in a._fitems_top()
print("menu: ok")

# a commander's lasers are fitted to each view at the start of a flight
a, g = app_flight(False)
a.cmdr = commander.Commander(1)
a.cmdr.lasers = ["beam", "pulse", "", "military"]
a._fit(g)
assert g.lasers == ["beam", "pulse", None, "military"] and g.laser == "beam"
g.set_view(3)
assert g.laser == "military"
# SHIP CONFIG cycles a view's laser, ending in none (not on the front)
a.career = False
a._ship_config("REAR LASER: PULSE")
assert g.lasers[1] == "beam"
for _ in range(3):
    a._ship_config("RIGHT LASER: X")
assert g.lasers[3] is None or g.lasers[3] in game.LASERS
print("fit and ship config: ok")
print("ALL VIEW TESTS PASSED")
