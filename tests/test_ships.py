"""Ship types (ships.py, build 78): the table, what each ship flies like, the
shipyard's stock, owning several ships, and the equipment limits they set.
Uses the game's own ships and equipment, so it needs no Elite files."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import commander
import equipment as eq
import game
import ships
import original_data
import original_ships

E = original_data.EQUIPMENT
BP = {e[0]: game.Blueprint(e) for e in original_ships.SHIPS}
cobra = BP[ships.COBRA]

# every type in the table is a ship in the data, and the Cobra is as before
for name in ships.TYPES:
    assert name in BP, name
assert ships.flight(cobra, cobra) == (game.PLAYER_MAX, 1.0, 1.0)
assert ships.flight(None, cobra) == (game.PLAYER_MAX, 1.0, 1.0)
assert (ships.base_hold(ships.COBRA), ships.big_hold(ships.COBRA)) == (20, 35), "as the original"
assert ships.pylons(ships.COBRA) == eq.MAX_MISSILES and ships.mounts(ships.COBRA) == 4
assert ships.standard_laser(cobra) == "pulse"
assert ships.standard_missiles(ships.COBRA, cobra) == commander.START_MISSILES
# small and fast against big and slow
side = ships.flight(BP["SIDEWINDER"], cobra)
boa = ships.flight(BP["BOA"], cobra)
assert side[0] > game.PLAYER_MAX > boa[0], (side, boa)
assert side[1] > 1.0 > boa[1] and boa[2] > 1.0 > side[2], (side, boa)
for name in ships.TYPES:
    s, t, k = ships.flight(BP[name], cobra)
    assert 0.6 <= t <= 1.4 and k >= 0.4 and s > 0, name
assert ships.standard_laser(BP["CONSTRICTOR"]) == "military"
print("the ship table and flight stats: ok")

# a shipyard: by tech level, its own few, stolen ships only on pirate worlds
low = ships.for_sale(0, 7, 1, 5)
assert low and all(ships.spec(n)[ships.TECH] <= 1 and not st for n, p, st in low), low
high = ships.for_sale(0, 7, 15, 5)
assert 0 < len(high) <= ships.SHOWN and not any(st for n, p, st in high)
assert all(not ships.spec(n)[ships.STOLEN_ONLY] for n, p, st in high), "no police or navy ships"
assert [p for n, p, st in high] == sorted(p for n, p, st in high), "cheapest first"
assert ships.for_sale(0, 7, 15, 5) == high, "the same each visit"
assert any(ships.for_sale(0, s, 15, 5) != high for s in range(8)), "each station its own"
seen_stolen = False
for s in range(40):
    stock = ships.for_sale(0, s, 3, 0)          # an anarchy
    stolen = [(n, p) for n, p, st in stock if st]
    assert 1 <= len(stolen) <= 2, stock
    for n, p in stolen:
        assert p == int(ships.TYPES[n][ships.PRICE] * ships.STOLEN_PRICE)
        seen_stolen = seen_stolen or ships.spec(n)[ships.STOLEN_ONLY] or ships.spec(n)[ships.TECH] > 3
assert seen_stolen, "pirate worlds sell what the tech level or the law wouldn't"
fits = lambda n: n != "BOA"
assert all(n != "BOA" for s in range(40) for n, p, st in ships.for_sale(0, s, 15, 0, fits))
print("shipyard stock: ok")

# owning ships: pack and unpack, a new ship's standard fit, cargo moving
c = commander.Commander()
c.lasers = ["beam", "pulse", "", ""]
c.extras = ["ecm", "scoops"]
c.cargo[0] = 12
old = ships.pack(c, (0, 7))
assert old["type"] == ships.COBRA and old["at"] == [0, 7] and old["cargo"][0] == 12
ships.new_ship(c, "SIDEWINDER", BP["SIDEWINDER"])
assert (c.ship, c.lasers, c.missiles, c.extras, c.hold) == ("SIDEWINDER", ["pulse", "", "", ""], 0, [], 4)
assert not any(c.cargo)
ships.move_cargo(old["cargo"], c.cargo, c.hold)
assert c.cargo[0] == 4 and old["cargo"][0] == 8, "what fits moves, the rest stays"
ships.unpack(c, old)
assert c.ship == ships.COBRA and c.lasers[0] == "beam" and c.extras == ["ecm", "scoops"]
# value: resale of the price, half for stolen, plus half the equipment
bare = {"type": "SIDEWINDER", "lasers": ["", "", "", ""], "missiles": 0, "extras": [],
        "hold": 4, "cargo": [0] * 17, "stolen": False}
assert ships.value(bare, E) == int(ships.TYPES["SIDEWINDER"][ships.PRICE] * ships.RESALE)
assert ships.value(dict(bare, stolen=True), E) == int(ships.TYPES["SIDEWINDER"][ships.PRICE] * ships.RESALE * 0.5)
fitted = dict(bare, lasers=["pulse", "", "", ""], extras=["ecm"])
assert ships.value(fitted, E) == ships.value(bare, E) + (E[eq.PULSE][1] + E[eq.ECM][1]) // 2
# where a kept ship can be flown from
assert ships.here({"at": [0, 7]}, 0, 7, True) and not ships.here({"at": [0, 7]}, 0, 8, True)
assert ships.here({"at": [0, 7]}, 0, 8, False), "outside Hardcore the hangar goes with you"
print("owning ships: ok")

# saving: the ship and the hangar; a bad entry is dropped; old saves fly a Cobra
c = commander.Commander()
c.ship = "PYTHON"; c.hold = 60; c.missiles = 4; c.stolen = True
c.hangar = [old, {"type": "NO SUCH SHIP"}, dict(bare)]
d = commander.Commander.from_dict(c.to_dict())
assert (d.ship, d.hold, d.missiles, d.stolen) == ("PYTHON", 60, 4, True)
assert [h["type"] for h in d.hangar] == [ships.COBRA, "SIDEWINDER"], d.hangar
assert d.hangar[0]["at"] == [0, 7] and d.hangar[1]["at"] is None
o = commander.Commander.from_dict({"level": 1})
assert (o.ship, o.hangar, o.stolen) == (ships.COBRA, [], False)
x = commander.Commander.from_dict({"ship": "SIDEWINDER", "hold": 35, "missiles": 4})
assert (x.hold, x.missiles) == (ships.big_hold("SIDEWINDER"), 1), "the ship's own limits"
print("saving ships: ok")

# the equipment limits a ship sets
c = commander.Commander()
ships.new_ship(c, "SIDEWINDER", BP["SIDEWINDER"])
c.cash = 10 ** 7
assert eq.buy(E, eq.MISSILE, c) is None and c.missiles == 1
assert eq.buy(E, eq.MISSILE, c) == "MISSILES FULL" and eq.have(eq.MISSILE, c) == "1/1"
assert eq.buy(E, eq.BEAM, c, 1) is None and c.lasers[1] == "beam", "rear mount"
assert eq.buy(E, eq.BEAM, c, 2) == "NO LEFT MOUNT" and c.lasers[2] == ""
assert eq.buy(E, eq.CARGO_BAY, c) is None and c.hold == ships.big_hold("SIDEWINDER")
assert eq.have(eq.CARGO_BAY, c) == "fitted"
ships.new_ship(c, "SHUTTLE", BP["SHUTTLE"])
assert eq.buy(E, eq.MISSILE, c) == "NO PYLONS"
assert eq.buy(E, eq.PULSE, c, 1) == "NO REAR MOUNT"
print("equipment by ship: ok")

# in flight: top speed, turning, toughness and pylons
g = game.Game(original_ships.SHIPS)
g.set_ship("SIDEWINDER", ships.pylons("SIDEWINDER"))
assert g.ship_name == "SIDEWINDER" and g.max_speed == side[0] and g.max_missiles == 1
assert g.missiles <= 1
g.speed = 1000.0
g.step(0.05, 1.0, 0.0, 0.0, False, False)
assert g.speed == g.max_speed
g.set_ship("BOA", 5)
assert g.speed == g.max_speed == boa[0] and g.tough == boa[2]
g.shield = 100.0; g.hull = 100.0
g._hurt(50.0)
assert abs(g.shield - (100.0 - 50.0 / boa[2])) < 1e-6, "a tougher ship soaks up more"
g.set_ship(ships.COBRA)
assert (g.max_speed, g.turn_k, g.tough, g.max_missiles) == (game.PLAYER_MAX, 1.0, 1.0, 4)
print("ALL SHIP TESTS PASSED")
