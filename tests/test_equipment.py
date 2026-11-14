"""The equipment rules (equipment.py), against the prices read from the Elite source."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import commander
import equipment as eq
try:
    import game_data as gd
except ImportError:
    sys.exit("game_data.py is missing: run tools/import_galaxy.py on your copy of the Elite source")
E = gd.EQUIPMENT
assert len(E) == 14 and E[eq.FUEL][0] == "FUEL" and E[eq.MISSILE][0] == "MISSILE"
names = [eq.name(E, i) for i in range(14)]
assert names[eq.PULSE] == "PULSE LASER" and names[eq.MILITARY] == "MILITARY LASER", names
assert names[eq.SCOOPS] == "FUEL SCOOPS" and names[eq.ENERGY] == "ENERGY UNIT", names

# what a station sells: tech level + 2 items, all 14 from tech level 10
assert [eq.on_sale(t) for t in range(1, 16)] == [3, 4, 5, 6, 7, 8, 9, 10, 11, 14, 14, 14, 14, 14, 14]

c = commander.Commander()
assert (c.missiles, c.laser, c.hold, c.extras, c.fuel) == (3, "pulse", 20, [], 70)
# fuel: 2 Cr a light year, filling the tank
c.fuel = 0
assert eq.price(E, eq.FUEL, c) == 140, "a full tank from empty is 14.0 Cr"
c.cash = 50
assert eq.buy(E, eq.FUEL, c) == "NOT ENOUGH CASH" and c.fuel == 0
c.cash = 1000
assert eq.buy(E, eq.FUEL, c) is None and c.fuel == 70 and c.cash == 860
assert eq.buy(E, eq.FUEL, c) == "TANK FULL" and c.cash == 860
assert eq.have(eq.FUEL, c) == "7.0LY"
# missiles to 4
c.cash = 10 ** 6
assert eq.buy(E, eq.MISSILE, c) is None and c.missiles == 4 and eq.have(eq.MISSILE, c) == "4/4"
assert eq.buy(E, eq.MISSILE, c) == "MISSILES FULL"
# one of each
for i, check in ((eq.CARGO_BAY, lambda: c.hold == 35), (eq.SCOOPS, lambda: "scoops" in c.extras),
                 (eq.ENERGY, lambda: "energy" in c.extras)):
    cash = c.cash
    assert eq.buy(E, i, c) is None and check() and c.cash == cash - E[i][1]
    assert eq.have(i, c) == "fitted"
    assert eq.buy(E, i, c) == "ALREADY FITTED" and c.cash == cash - E[i][1]
# lasers: the old one's price comes back; the one you have is "fitted"
assert eq.buy(E, eq.PULSE, c) == "ALREADY FITTED"
cash = c.cash
assert eq.buy(E, eq.MILITARY, c) is None and c.laser == "military"
assert c.cash == cash - E[eq.MILITARY][1] + E[eq.PULSE][1]
cash = c.cash
assert eq.buy(E, eq.BEAM, c) is None and c.laser == "beam"
assert c.cash == cash - E[eq.BEAM][1] + E[eq.MILITARY][1]
assert eq.have(eq.BEAM, c) == "fitted" and eq.have(eq.PULSE, c) == ""
c.cash = E[eq.MILITARY][1] - E[eq.BEAM][1]        # just enough with the refund
assert eq.buy(E, eq.MILITARY, c) is None and c.cash == 0
# not yet: shown but not sold
for i in eq.SOON:
    assert eq.buy(E, i, c) == "COMING SOON"
assert "ecm" not in c.extras and c.laser == "military"
# saved and loaded
d = commander.Commander.from_dict(c.to_dict())
assert (d.missiles, d.laser, d.hold, sorted(d.extras)) == (4, "military", 35, ["energy", "scoops"])
old = commander.Commander.from_dict({"level": 1, "credits": 50.0})
assert (old.missiles, old.laser, old.hold, old.extras) == (3, "pulse", 20, []), "older saves"
bad = commander.Commander.from_dict({"missiles": 99, "laser": "death ray", "hold": 1000, "extras": [1, "x"]})
assert (bad.missiles, bad.laser, bad.hold, bad.extras) == (4, "pulse", 35, ["x"])
print("ALL EQUIPMENT TESTS PASSED")
