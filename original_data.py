"""Ace Commander's own galaxy, market and equipment (build 56), so the game
runs without anything from Elite. With your own game_data.py (from
tools/import_galaxy.py) and Options > CONTENT: ELITE, the game uses that
instead. Free to use with the game.

How systems and prices are worked out from these numbers is in galaxy.py
and market.py.
"""
# the three seeds every star system in the first galaxy is worked out from
SEEDS = (0x7CBF, 0x1FAB, 0xE606)
# the letter pairs system names are built from (pair 0 is never used; ? is
# an empty letter)
PAIRS = "..KAROVETULINASOMIDEZUBAORENARI?VAESQUANREILONGAPAHUXILOSAO?ELDA"
# where a new commander starts: Daenor, a Confederacy, and how much fuel
START_XY = (128, 141)
START_FUEL = 70
# the market's goods: (name, base price, economic factor, unit, base
# quantity, mask). Each place in the list has a job the game knows: 0-7 can
# be found in cargo canisters, 3, 6 and 10 are illegal, 12 is what mining
# gives, 13-15 are sold by the kilogram or gram and need no hold space, and
# 16 is what a scooped alien drone becomes.
GOODS = (
    ('GRAIN', 18, -2, 't', 7, 1),
    ('FABRICS', 22, -1, 't', 9, 3),
    ('ISOTOPES', 62, -3, 't', 3, 7),
    ('CONTRABAND', 42, -5, 't', 224, 15),
    ('SPIRITS', 80, -4, 't', 250, 15),
    ('LUXURIES', 190, 8, 't', 52, 7),
    ('STIMS', 230, 27, 't', 10, 63),
    ('ELECTRONICS', 150, 13, 't', 58, 3),
    ('MACHINERY', 114, 6, 't', 42, 7),
    ('ALLOYS', 75, 2, 't', 19, 15),
    ('WEAPONS', 120, 12, 't', 30, 7),
    ('SILKS', 172, -8, 't', 218, 31),
    ('ORE', 30, -1, 't', 55, 3),
    ('GOLD', 95, -1, 'k', 64, 7),
    ('PLATINUM', 168, -2, 'k', 57, 15),
    ('GEMS', 48, -1, 'g', 248, 15),
    ('ALIEN RELICS', 56, 14, 't', 190, 7),
)
# the equipment: (name, price in tenths of a credit; fuel's is worked out),
# in the order the game knows them
EQUIPMENT = (
    ('FUEL', 1),
    ('MISSILE', 280),
    ('LARGE CARGO BAY', 3800),
    ('E.C.M. SYSTEM', 5600),
    ('EXTRA PULSE LASERS', 3800),
    ('EXTRA BEAM LASERS', 9800),
    ('FUEL SCOOPS', 5000),
    ('ESCAPE POD', 9500),
    ('ENERGY BOMB', 8800),
    ('ENERGY UNIT', 14500),
    ('DOCKING COMPUTER', 9800),
    ('GALACTIC HYPERDRIVE', 48000),
    ('EXTRA MILITARY LASERS', 58000),
    ('EXTRA MINING LASERS', 7600),
)
# where the missions happen: (galaxy, x, y) on the chart (missions.py).
# Mission 1: the Phantom was built at Tuelve and last seen at Rotuvaga, and
# hides at Elnada; mission 2's briefing is at Argatu and its base Vedao.
MISSION_PLACES = {
    "shipyard": (0, 154, 161),
    "last_seen": (0, 73, 152),
    "constrictor": (1, 251, 108),
    "briefing": (2, 126, 43),
    "base": (2, 250, 226),
}
