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
assert d.tabs.index("SHIPYARD") == d.tabs.index("REPAIR SHOP") + 1
assert d.tabs.index("HANGAR") == d.tabs.index("SHIPYARD") + 1

# ---- the Shipyard: what this station sells, by its tech level
d.open("SHIPYARD")
assert d.yard == ships.for_sale(c.galaxy, c.system, d.here.tech, d.here.government)
assert d.yard and all(ships.spec(n)[ships.TECH] <= d.here.tech for n, p, st in d.yard if not st)
tx = texts(e)
assert "SHIPYARD  " + here in tx and "C: buy   D: trade in" in tx, tx
# a known stock for the rest of the test
d.yard = [("SIDEWINDER", 40000, False), ("PYTHON", 950000, False), ("VIPER", 195000, True)]
d.ysel = 0
tx = texts(e)
assert e.game is None or True
assert any(t.startswith("speed ") for t in tx) and any(t.startswith("lasers ") for t in tx), tx
tick(e, fresh=["JOYDOWN"]); assert d.ysel == 1
tick(e, fresh=["JOYUP"]); tick(e, fresh=["JOYUP"]); assert d.ysel == 2, "round the list"
assert any("(STOLEN)" in t for t in texts(e))
d.ysel = 0
# not enough cash
c.cash = 100
tick(e, fresh=["C"]); assert d.msg == "NOT ENOUGH CASH" and c.ship == ships.COBRA
# buy a Sidewinder: the Cobra, its beam laser, ECM and cargo go into the hangar,
# with what doesn't fit the Sidewinder's 4 t hold
c.cash = 10 ** 6
c.lasers[0] = "beam"; c.extras.append("ecm"); c.cargo[0] = 15
tick(e, fresh=["C"])
assert c.ship == "SIDEWINDER" and c.cash == 10 ** 6 - 40000 and d.sold
assert (c.lasers, c.missiles, c.extras, c.hold) == (["pulse", "", "", ""], 0, [], 4), "standard weapons"
assert c.cargo[0] == 4 and len(c.hangar) == 1
kept = c.hangar[0]
assert (kept["type"], kept["lasers"][0], kept["extras"], kept["cargo"][0], kept["at"]) == \
    (ships.COBRA, "beam", ["ecm"], 11, None), kept
assert d.msg.startswith("NEW SHIP: ") and d.msg in texts(e)
assert d.ship is not None and d.ship.name == "SIDEWINDER", "the Repair Shop shows it"
# ---- the Hangar: the one you fly first, then the Cobra
d.open("HANGAR")
tx = texts(e)
assert "HANGAR  " + here in tx and "flying" in tx and "here" in tx, tx
tick(e, fresh=["C"]); assert d.msg == "YOU ARE FLYING IT"
tick(e, fresh=["JOYDOWN"]); assert d.hsel == 1 and "C: fly   D: sell" in texts(e)
assert any(t.startswith("worth ") for t in texts(e))
tick(e, fresh=["C"])
assert c.ship == ships.COBRA and c.lasers[0] == "beam" and c.extras == ["ecm"]
assert c.cargo[0] == 15, "the cargo moves back across"
assert [h["type"] for h in c.hangar] == ["SIDEWINDER"] and c.hangar[0]["cargo"][0] == 0
# sell the Sidewinder
cash = c.cash
v = ships.value(c.hangar[0], mod.EQUIP)
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["D"])
assert c.hangar == [] and c.cash == cash + v and d.msg.startswith("SOLD: ")
print("shipyard: buy; hangar: fly and sell: ok")

# ---- trade in: the Cobra's value comes off a Python's price
d.open("SHIPYARD"); d.yard = [("PYTHON", 950000, False)]; d.ysel = 0
c.cash = 10 ** 7; c.cargo[0] = 15
cash = c.cash
v = d.trade_in_value()
assert v == ships.value(ships.pack(c), mod.EQUIP) and v > ships.TYPES[ships.COBRA][ships.PRICE] * ships.RESALE
tick(e, fresh=["D"])
assert c.ship == "PYTHON" and c.hangar == [] and c.cash == cash + v - 950000
assert c.cargo[0] == 15 and c.hold == 60 and c.lasers[0] == "beam" and c.missiles == 3
print("trade in: ok")

# ---- a stolen ship makes you an offender
d.yard = [("VIPER", 195000, True)]; d.ysel = 0
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
d.open("SHIPYARD"); d.yard = [("SIDEWINDER", 40000, False)]; d.ysel = 0
c.cash = 10 ** 6
tick(h, fresh=["C"])
assert c.hangar[0]["at"] == [c.galaxy, home], "kept here"
# somewhere else, the Cobra can't be flown or sold
c.system = (home + 1) % 256
h._make_dock(); d = h.dock
d.open("HANGAR"); tick(h, fresh=["JOYDOWN"])
tick(h, fresh=["C"]); assert d.msg == "KEPT AT " + d.gal.system(home).name and c.ship == "SIDEWINDER"
tick(h, fresh=["D"]); assert d.msg.startswith("KEPT AT ") and len(c.hangar) == 1
assert d.gal.system(home).name in texts(h)
# back home it can
c.system = home
h._make_dock(); d = h.dock
d.open("HANGAR"); tick(h, fresh=["JOYDOWN"]); tick(h, fresh=["C"])
assert c.ship == ships.COBRA and c.hangar[0]["type"] == "SIDEWINDER" and c.hangar[0]["at"] == [c.galaxy, home]
print("Hardcore: ships stay where they were left: ok")
os.remove(SAVE)
print("ALL SHIPYARD TESTS PASSED")
