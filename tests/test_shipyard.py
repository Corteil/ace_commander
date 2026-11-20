"""The Shipyard and Hangar tabs (build 79): buying, trading in, flying a kept
ship and selling one, cargo moving between holds, stolen ships, and Hardcore
Mode's ships staying where they were left."""
import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import commander, game, ships
mod = ace_commander.ace
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_shipyard.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


def launch(a):
    a.dock.go(0); tick(a, fresh=["A"])
    for _ in range(300):
        tick(a)
        if a.mode == "flight":
            break
    assert a.mode == "flight"


random.seed(3)
e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
assert e.mode == "docked"
d = e.dock
c = e.cmdr
here = d.here.name
assert "SHIPYARD" in d.tabs and "HANGAR" in d.tabs
assert d.tabs.index("SHIPYARD") == d.tabs.index("EQUIP SHIP") + 1 and "REPAIR SHOP" not in d.tabs
assert d.tabs.index("HANGAR") == d.tabs.index("SHIPYARD") + 1

# ---- the Shipyard: what this station sells, by its tech level
d.open("SHIPYARD")
assert d.yard == ships.for_sale(c.galaxy, c.system, d.here.tech, d.here.government)
assert d.yard and all(ships.spec(n)[ships.TECH] <= d.here.tech for n, p, st in d.yard if not st)
# page 1 is your own ship, with the Repair Shop (build 80)
tx = texts(e)
assert "SHIPYARD" in tx and here not in tx and d.ysel == 0, tx
# (the page names your ship plainly: Brian, build 81)
assert not any(t.startswith("YOUR ") for t in tx) and "C: stats   D: repair shop" in tx, tx
# C: your own ship's stats, with nothing to buy (C is stats on every page: build 82)
tick(e, fresh=["C"]); assert d.name() == "SHIP STATS" and c.ship == ships.COBRA
tx = texts(e)
assert "top speed" in tx and "40" in tx and "turning" in tx and "100%" in tx, tx
assert "C: buy   D: trade in" not in tx and "F: back to shipyard" in tx
tick(e, fresh=["C"]); tick(e, fresh=["D"]); assert c.ship == ships.COBRA and c.hangar == []
tick(e, fresh=["F"]); assert d.name() == "SHIPYARD" and d.ysel == 0
# a known stock for the rest of the test
d.yard = [("SIDEWINDER", 40000, False), ("PYTHON", 950000, False), ("VIPER", 195000, True)]
tick(e, fresh=["JOYDOWN"]); assert d.ysel == 1
tx = texts(e)
assert "C: stats and buying" in tx and "2 of 4" in tx, tx
assert any(t.startswith("speed ") for t in tx) and any(t.startswith("lasers ") for t in tx), tx
tick(e, fresh=["D"]); assert d.name() == "SHIPYARD" and c.ship == ships.COBRA, "D does nothing here"
# C: its stats; F back to the same page
tick(e, fresh=["C"]); assert d.name() == "SHIP STATS"
tx = texts(e)
assert "SIDEWINDER" in tx and "C: buy   D: trade in" in tx and "front, rear" in tx and "1 pylon" in tx, tx
assert "4t (7t with bay)" in tx and "pulse laser" in tx and "fitted" in tx and "from tech 1" in tx, tx
tick(e, fresh=["F"]); assert d.name() == "SHIPYARD" and d.ysel == 1
tick(e, fresh=["JOYUP"]); tick(e, fresh=["JOYUP"]); assert d.ysel == 3, "round the list"
assert any("(STOLEN)" in t for t in texts(e))
tick(e, fresh=["C"]); assert "from tech 12" in texts(e), "the Viper: legal at high tech (build 84)"
tick(e, fresh=["F"])
d.ysel = 1
# not enough cash
c.cash = 100
tick(e, fresh=["C"]); tick(e, fresh=["C"])
assert d.msg == "NOT ENOUGH CASH" and c.ship == ships.COBRA and d.name() == "SHIP STATS"
assert "NOT ENOUGH CASH" in texts(e)
# buy a Sidewinder: the Cobra, its beam laser and ECM go into the hangar; the
# cargo moves across and what doesn't fit the Sidewinder's 4 t hold is sold,
# its value credited (Brian, build 81)
c.cash = 10 ** 6
c.lasers[0] = "beam"; c.extras.append("ecm"); c.cargo[0] = 15
food = d.market.prices[0]; stock = d.market.stock[0]
tick(e, fresh=["C"])
assert c.ship == "SIDEWINDER" and c.cash == 10 ** 6 - 40000 + 11 * food and d.sold
assert d.market.stock[0] == stock + 11
assert d.name() == "SHIPYARD" and d.ysel == 0, "back on the Shipyard, on the new ship"
assert (c.lasers, c.missiles, c.extras, c.hold) == (["pulse", "", "", ""], 0, [], 4), "standard weapons"
assert c.cargo[0] == 4 and len(c.hangar) == 1
kept = c.hangar[0]
assert (kept["type"], kept["lasers"][0], kept["extras"], kept["cargo"][0], kept["at"]) == \
    (ships.COBRA, "beam", ["ecm"], 0, None), kept
want = 11 * food
assert d.msg == "CARGO OVER: +%d.%d Cr" % (want // 10, want % 10) and d.msg in texts(e), d.msg
assert d.ship is not None and d.ship.name == "SIDEWINDER", "the Repair Shop shows it"
# ---- the Hangar: the one you fly first, then the Cobra
d.open("HANGAR")
tx = texts(e)
assert "HANGAR" in tx and "flying" in tx and "1 of 2" in tx, tx
assert "lasers F pulse" in tx and "missiles 0/1   hold 4t, 4t used" in tx and "no other equipment" in tx, tx
tick(e, fresh=["C"]); assert d.msg == "YOU ARE FLYING IT"
tick(e, fresh=["JOYDOWN"]); assert d.hsel == 1
tx = texts(e)
assert "C: fly   D: sell" in tx and any(t.startswith("here, worth ") for t in tx), tx
assert "lasers F beam" in tx and "ECM" in tx and "missiles 3/4   hold 20t, 0t used" in tx, tx
tick(e, fresh=["C"])
assert c.ship == ships.COBRA and c.lasers[0] == "beam" and c.extras == ["ecm"]
assert c.cargo[0] == 4 and d.msg == "NOW FLYING COBRA MK III", "the cargo moves across, all of it fits"
assert [h["type"] for h in c.hangar] == ["SIDEWINDER"] and c.hangar[0]["cargo"][0] == 0
# sell the Sidewinder
cash = c.cash
v = ships.value(c.hangar[0], mod.EQUIP)
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["D"])
assert c.hangar == [] and c.cash == cash + v and d.msg.startswith("SOLD: ")
# flying a smaller kept ship sells what doesn't fit too
d.cmdr.cash = 10 ** 6
d.open("SHIPYARD"); d.yard = [("SIDEWINDER", 40000, False)]; d.ysel = 1; d.open_stats()
d.buy_ship(False)       # a second Sidewinder; the Cobra (4 t) into the hangar
d.open("HANGAR"); d.hsel = 1; d.fly_owned()     # back to the Cobra
c.cargo[0] = 10; cash = c.cash
d.hsel = 1; d.fly_owned()       # into a Sidewinder: 6 t over
assert c.ship == "SIDEWINDER" and c.cargo[0] == 4 and c.cash == cash + 6 * d.market.prices[0]
assert d.msg.startswith("CARGO OVER: ") and c.hangar[0]["cargo"][0] == 0
d.hsel = 1; d.fly_owned()       # back to the Cobra again
assert c.ship == ships.COBRA
c.hangar = []
print("shipyard: buy; hangar: fly and sell; cargo over sold: ok")

# ---- trade in: the Cobra's value comes off a Python's price
d.open("SHIPYARD"); d.yard = [("PYTHON", 950000, False)]; d.ysel = 1; d.open_stats()
c.cash = 10 ** 7; c.cargo[0] = 15
cash = c.cash
v = d.trade_in_value()
assert v == ships.value(ships.pack(c), mod.EQUIP) and v > ships.TYPES[ships.COBRA][ships.PRICE] * ships.RESALE
tick(e, fresh=["D"])
assert c.ship == "PYTHON" and c.hangar == [] and c.cash == cash + v - 950000
assert c.cargo[0] == 15 and c.hold == 60 and c.lasers[0] == "beam" and c.missiles == 3
print("trade in: ok")

# ---- a stolen ship makes you an offender
d.yard = [("VIPER", 195000, True)]; d.ysel = 1; d.open_stats()
assert c.legal == 0
tick(e, fresh=["C"])
assert c.ship == "VIPER" and c.stolen and game.legal_name(c.legal) == "OFFENDER", c.legal
assert len(c.hangar) == 1 and c.hangar[0]["type"] == "PYTHON"
print("stolen ships: ok")

# ---- flying it: the Viper's speed and pylons; the hangar is saved
launch(e)
g = e.game
assert g.ship_name == "VIPER" and g.max_missiles == ships.pylons("VIPER")
assert g.max_speed == ships.flight(g.types["VIPER"], g.types[ships.COBRA])[0]
assert e.tunnel is not None
# the HUD has a missile slot for each pylon (build 82)
from ace_commander import cockpit


class Rec(CountCtx):
    def rectangle(self, *a):
        self.calls.setdefault("rects", []).append(a)
        return self


def slots(game_):
    r = Rec(); cockpit.draw_hud(r, game_)
    return len([a for a in r.calls.get("rects", []) if a[1:] == (56, 6, 4)])


assert slots(g) == g.max_missiles == 2, slots(g)
for name, n in (("SHUTTLE", 0), ("SIDEWINDER", 1), (ships.COBRA, 4), ("BOA", 5)):
    g.set_ship(name, ships.pylons(name))
    assert slots(g) == n, (name, slots(g))
g.set_ship("VIPER", ships.pylons("VIPER"))
saved = commander.load(SAVE)
assert saved.ship == "VIPER" and [h["type"] for h in saved.hangar] == ["PYTHON"]
print("flying the new ship, saved: ok")

# ---- Hardcore: a ship stays at the station where it was left
h = ace_commander.AceCommander()
choose(h, "NEW COMMANDER"); tick(h, fresh=["C"])
c = h.cmdr
c.hardcore = True
h._make_dock(); d = h.dock
home = c.system
d.open("SHIPYARD"); d.yard = [("SIDEWINDER", 40000, False)]; d.ysel = 1; d.open_stats()
c.cash = 10 ** 6
tick(h, fresh=["C"])
assert c.hangar[0]["at"] == [c.galaxy, home], "kept here"
# somewhere else, the Cobra can't be flown or sold
c.system = (home + 1) % 256
h._make_dock(); d = h.dock
d.open("HANGAR"); tick(h, fresh=["JOYDOWN"])
tick(h, fresh=["C"]); assert d.msg == "KEPT AT " + d.gal.system(home).name and c.ship == "SIDEWINDER"
tick(h, fresh=["D"]); assert d.msg.startswith("KEPT AT ") and len(c.hangar) == 1
d.msg = None
assert "kept at " + d.gal.system(home).name.lower() in texts(h)
# back home it can
c.system = home
h._make_dock(); d = h.dock
d.open("HANGAR"); tick(h, fresh=["JOYDOWN"]); tick(h, fresh=["C"])
assert c.ship == ships.COBRA and c.hangar[0]["type"] == "SIDEWINDER" and c.hangar[0]["at"] == [c.galaxy, home]
print("Hardcore: ships stay where they were left: ok")
# ---- jump ranges (build 83): an in-system ship, and never stranded
j = ace_commander.AceCommander()
choose(j, "NEW COMMANDER"); tick(j, fresh=["C"])
c = j.cmdr; d = j.dock
c.cash = 10 ** 7
d.open("SHIPYARD"); d.yard = [("SHUTTLE", 30000, False)]; d.ysel = 1; d.open_stats()
tx = texts(j)
assert "jump range" in tx and "in-system only" in tx, tx
d.back(); assert any("no jumps" in t for t in texts(j))
d.open_stats()
tick(j, fresh=["D"])        # trading in the only ship that jumps
assert d.msg == "NEED A SHIP THAT JUMPS" and c.ship == ships.COBRA and "NEED A SHIP THAT JUMPS" in texts(j)
tick(j, fresh=["C"])        # buying, so the Cobra stays in the hangar
assert c.ship == "SHUTTLE" and c.fuel == 0 and c.hangar[0]["type"] == ships.COBRA
d.open("HANGAR"); tx = texts(j)
assert "no hyperdrive" in tx, tx
d.pick_owned(1); tx = texts(j)
assert "fuel 7.0 of 7.0 LY" in tx, tx
tick(j, fresh=["D"]); assert d.msg == "NEED A SHIP THAT JUMPS" and len(c.hangar) == 1, "can't sell the way out"
# flying it: no HYPERSPACE line, H says so, no fuel gauge's tank
launch(j)
g = j.game
assert g.fuel_max == 0 and not any(t.startswith("HYPERSPACE") for t in j._fitems_top())
tick(j, fresh=["KEY_H"]); assert g.msg == "NO HYPERDRIVE", g.msg
print("jump ranges: in-system ships, never stranded: ok")

# ---- a hot ship (build 84): an offender while you fly it, lawful police spot it,
# a new transponder on a pirate world clears it; DEBUG STOLEN
k = ace_commander.AceCommander()
choose(k, "NEW COMMANDER"); tick(k, fresh=["C"])
c = k.cmdr; d = k.dock
c.cash = 10 ** 7
d.open("SHIPYARD"); d.yard = [("VIPER", 195000, True)]; d.ysel = 1; d.open_stats()
tick(k, fresh=["C"])
assert c.stolen and c.legal == ships.STOLEN_LEGAL
launch(k); g = k.game
assert g.stolen and g.legal == ships.STOLEN_LEGAL
g.legal //= 2; k._hot(); assert g.legal == ships.STOLEN_LEGAL, "jumps don't clean it"
c.legal = 0; k._hot(); assert c.legal == ships.STOLEN_LEGAL
# DEBUG > SHIP CONFIG > STOLEN, in flight
assert "STOLEN: ON" in k._ship_items()
k._ship_config("STOLEN: ON")
assert not c.stolen and not g.stolen and commander.load(SAVE).stolen is False
k._ship_config("STOLEN: OFF"); assert c.stolen and g.stolen and g.legal >= ships.STOLEN_LEGAL
# docked at a law-abiding world: no transponder on offer
k._dock(); d = k.dock
assert d.here.government >= ships.PIRATE_GOV and d.transponder_price() is None
d.open("REPAIR SHOP"); tick(k, fresh=["D"]); assert c.stolen
# at a pirate world: D buys a new transponder for a quarter of the ship's price
anarchy = [i for i in range(256) if k.galaxy.system(i).government == 0][0]
c.system = anarchy; c.market = None
k._make_dock(); d = k.dock
d.open("REPAIR SHOP")
tp = d.transponder_price()
assert tp == int(ships.TYPES["VIPER"][ships.PRICE] * 0.25)
assert "D: new transponder %d Cr" % (tp // 10) in texts(k)
c.cash = 10; tick(k, fresh=["D"]); assert d.msg == "NOT ENOUGH CASH" and c.stolen
c.cash = 10 ** 6; tick(k, fresh=["D"])
assert not c.stolen and c.cash == 10 ** 6 - tp and d.msg == "NEW TRANSPONDER FITTED"
assert d.msg in texts(k) and d.transponder_price() is None
c.legal = 0; k._hot(); assert c.legal == 0, "a clean ship: jumps clear the record again"
# DEBUG > SHIP CONFIG > STOLEN away from a flight
assert "STOLEN: OFF" in k._ship_items_c()
k._ship_config_c("STOLEN: OFF"); assert c.stolen and commander.load(SAVE).stolen
print("a hot ship: offender while flown, spotted, new transponder, DEBUG STOLEN: ok")
# the docking computer's view from behind shows the ship you fly now, after
# buying another one (Brian, 2026-11-20: it showed the old one, because the
# same Game is kept between flights and the view cached its blueprint per Game)
from ace_commander import cockpit
g = game.Game(mod.SHIPS, 1)
g.set_ship(ships.COBRA)
assert cockpit._my_ship(g).bp is g.types[ships.COBRA]
other = [n for n in ships.TYPES if n != ships.COBRA and n in g.types][0]
g.set_ship(other)
assert cockpit._my_ship(g).bp is g.types[other], "the view behind still shows the old ship"
print("docking computer view: the new ship after buying one: ok")
os.remove(SAVE)
print("ALL SHIPYARD TESTS PASSED")
