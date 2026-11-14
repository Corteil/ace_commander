"""The market rules (market.py), against the goods read from the Elite source."""
import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
import commander
import galaxy
import market
try:
    import game_data as gd
except ImportError:
    sys.exit("game_data.py is missing: run tools/import_galaxy.py on your copy of the Elite source")
G = gd.GOODS
assert len(G) == 17 and G[0][0] == "FOOD" and G[16][0] == "ALIEN ITEMS"
names = [g[0] for g in G]
FOOD, COMPUTERS, NARCOTICS, GOLD, ALIEN = (names.index(n) for n in
                                           ("FOOD", "COMPUTERS", "NARCOTICS", "GOLD", "ALIEN ITEMS"))

# prices: the economy pushes them the right way; tenths of a credit, multiples of 4
for r in (0, 0x55, 0xFF):
    for i, g in enumerate(G):
        for e in range(8):
            p = market.price(g, e, r)
            assert 0 <= p <= 1020 and p % 4 == 0
    # food is cheaper where they grow it (agricultural, 7), computers dearer
    assert market.price(G[FOOD], 7, r) < market.price(G[FOOD], 0, r)
    assert market.price(G[COMPUTERS], 7, r) > market.price(G[COMPUTERS], 0, r)
# Lave (rich agricultural): food 3.6 to 4.0, computers 89.6 to 90.8, whatever the visit
lave = galaxy.Galaxy(gd.SEEDS, gd.PAIRS).system(7)
assert lave.name == "LAVE" and lave.economy == 5
assert {market.price(G[FOOD], 5, r) for r in range(256)} == {36, 40}
assert min(market.price(G[COMPUTERS], 5, r) for r in range(256)) == 896
assert max(market.price(G[COMPUTERS], 5, r) for r in range(256)) == 908
# the 8-bit wrap: narcotics can come out very cheap, as in the original
assert min(market.price(G[NARCOTICS], 0, r) for r in range(256)) < 100

# stock: 0 to 63, never any alien items, the random byte changes it
for r in range(0, 256, 17):
    for e in range(8):
        st = [market.stock(g, i, e, r) for i, g in enumerate(G)]
        assert all(0 <= n <= 63 for n in st) and st[ALIEN] == 0
assert len({market.stock(G[FOOD], FOOD, 5, r) for r in range(256)}) > 1

# a commander trading
c = commander.Commander()
c.system = 7
c.market = market.new(G, 7, 5, 0x33)
m = market.Market(G, 5, c)
assert c.cash == 1000 and c.hold == 20 and c.cargo == [0] * 17
m.stock[FOOD] = 30
bought = 0
while m.buy(FOOD) is None:
    bought += 1
assert bought == 20 and m.buy(FOOD) == "HOLD FULL" and m.stock[FOOD] == 10
assert c.cash == 1000 - 20 * m.prices[FOOD]
m.stock[GOLD] = 63; c.cash = 10 ** 7
assert m.buy(GOLD) is None and c.cargo[GOLD] == 1, "gold doesn't use the hold"
c.cargo[GOLD] = market.UNIT_LIMIT
assert m.buy(GOLD) == "CAN'T CARRY MORE"
c.cash = 0; m.stock[COMPUTERS] = 5
assert m.buy(COMPUTERS) == "NOT ENOUGH CASH"
m.stock[COMPUTERS] = 0; c.cash = 10 ** 7
assert m.buy(COMPUTERS) == "NONE LEFT"
assert m.sell(COMPUTERS) == "NONE TO SELL"
cash = c.cash
assert m.sell(FOOD) is None and c.cargo[FOOD] == 19 and m.stock[FOOD] == 11
assert c.cash == cash + m.prices[FOOD], "sold at the price it is bought for"
assert c.market["stock"] is m.stock, "trading changes the saved market"

# saving and loading keeps cash, cargo and the market; bad values are dropped
d = commander.Commander.from_dict(c.to_dict())
assert d.cash == c.cash and d.cargo == c.cargo and d.market == c.market
assert commander.Commander.from_dict({"credits": 12.34}).cash == 123
d = commander.Commander.from_dict({"cargo": [1, 2], "market": {"system": "x"}})
assert d.cargo == [0] * 17 and d.market is None
assert c.cash_text() == "%d.%d Cr" % (c.cash // 10, c.cash % 10)
print("ALL MARKET TESTS PASSED")
