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

# ---- words (build 57) -------------------------------------------------------

# The System data sentence (describe.py): a grammar. Each <word> is replaced
# by one of its choices, picked by a random-number generator seeded from the
# system, so a system always says the same; %N is the system's name, %I its
# name as an adjective (Daenor: Daenorian) and %R a made-up name.
DESCRIBE = {
    "start": ("%N is <renowned> for <sight> and <sight>.",
              "%N is a <adj> world, <renowned> for <sight>.",
              "The <adj> planet %N is <beset> by <plague>.",
              "%N is <renowned> for <sight>, but <beset> by <plague>.",
              "<visitors> %N for <sight>.",
              "%N is a <dull> world, apart from <sight>.",
              "%N is known for <cuisine> and <sight>.",
              "The %I people are <proud> of <sight>."),
    "renowned": ("famous", "best known", "noted", "renowned", "admired"),
    "adj": ("quiet", "busy", "dusty", "frozen", "lush", "storm-swept", "ancient", "sunny",
            "remote", "crowded", "misty", "rugged"),
    "sight": ("its <size> <landscape>", "the %I <creature>", "the %I <festival>",
              "its <material> <structure>", "the %R <landmark>", "<cuisine>"),
    "size": ("vast", "endless", "towering", "deep", "glittering", "silent", "shifting"),
    "landscape": ("deserts", "ice fields", "coral seas", "salt flats", "canyons", "jungles",
                  "cloud forests", "volcanoes", "dunes", "swamps"),
    "creature": ("<beast>", "<colour> <beast>"),
    "beast": ("sand eels", "glass moths", "sky whales", "rock crabs", "singing lizards",
              "tree shrews", "marsh hounds", "fire beetles", "dune cats"),
    "colour": ("blue", "golden", "striped", "spotted", "crimson", "silver"),
    "festival": ("lantern festival", "harvest games", "zero-g dance", "moon races",
                 "midwinter fair", "kite contests"),
    "material": ("crystal", "ancient stone", "floating", "copper", "glass", "living coral"),
    "structure": ("cities", "towers", "gardens", "bridges", "temples", "markets"),
    "landmark": ("mountains", "falls", "rift", "caves", "lakes", "reef"),
    "cuisine": ("%I <food>", "spiced <food>", "its <food>"),
    "food": ("noodles", "tea", "fruit wine", "fish stew", "honey cakes", "roast beetle",
             "moss bread", "pickled roots"),
    "beset": ("plagued", "troubled", "ravaged", "haunted"),
    "plague": ("frequent <disaster>", "<colour> <beast>", "a <severe> civil war",
               "<weather>", "%R pirates"),
    "disaster": ("earthquakes", "dust storms", "floods", "solar flares", "meteor showers"),
    "weather": ("acid rain", "endless fog", "violent storms", "freezing winds"),
    "severe": ("long", "bitter", "endless", "strange"),
    "visitors": ("Visitors come to", "Tourists flock to", "Traders praise", "Poets write about"),
    "dull": ("dull", "quiet", "unremarkable", "peaceful"),
    "proud": ("proud", "fond", "protective", "boastful"),
}

# The missions' messages (missions.py's numbers: 10 mission 1's briefing, 15
# its reward, 11 mission 2's first message, 222 its briefing, 223 its
# reward): (text, the Phantom shown above it), paragraphs split by new
# lines. [NAME] is the commander's name; [TRAIL] the Phantom's whereabouts,
# which depend on the galaxy (TRAIL below).
MISSION_TEXTS = {
    10: (("Commander [NAME], this is Captain Hollis of the Commonwealth Navy. I'll be "
          "brief, as I suspect you prefer.\n"
          "The ship above is the Phantom, a prototype from our yards at Tuelve. Its shield "
          "generator is years ahead of anything flying. Four months ago a crew we trusted "
          "took it and vanished.\n"
          "[TRAIL]\n"
          "Find it and destroy it. We would rather lose it than see it copied.\n"
          "A warning: those shields shrug off anything but a military laser, and it carries "
          "an ECM, so don't count on your missiles.\n"
          "Good hunting, Commander.\n"
          "MESSAGE ENDS", True),),
    15: (("Commander, the Phantom is confirmed destroyed. Well flown.\n"
          "The Navy pays its debts. 5000 credits are already in your account.\n"
          "Keep your record clean. We may need you again sooner than you think.\n"
          "MESSAGE ENDS", False),),
    11: (("Commander [NAME], Captain Varga, Commonwealth Navy. Your name came up after the "
          "Phantom business.\n"
          "We have work that suits you. Go to Argatu and dock. You'll be met.\n"
          "It pays well, if you come back.\n"
          "MESSAGE ENDS", False),),
    222: (("Commander [NAME]. Agent Mercer, Navy Intelligence. Don't bother looking for me "
           "afterwards.\n"
           "For years the Navy has held the Vorn at the edge of known space. That is about "
           "to change: our fleets are ready to strike at their Nest Worlds.\n"
           "I've got hold of the Nest Worlds' defence plans. The Vorn know something is "
           "missing, but not what, or who has it.\n"
           "Any signal I send to our base at Vedao would be picked up. The plans have to go "
           "by hand, in a ship nobody would look at twice. Yours.\n"
           "The plans are now in your ship's computer. Get them to Vedao.\n"
           "Expect company.\n"
           "MESSAGE ENDS", False),),
    223: (("Commander, the plans are safe, and so are you, which we did not expect when the "
           "Vorn came after you.\n"
           "The Navy doesn't forget. Your ship now has a Navy Energy Unit: it recharges "
           "faster than anything you can buy.\n"
           "MESSAGE ENDS", False),),
}
# [TRAIL] in mission 1's briefing, by galaxy (0 is the first)
TRAIL = {0: "It was last reported near Rotuvaga, heading out.",
         1: "We believe it has jumped to this galaxy."}

# What a station says on System data instead of the usual sentence:
# (galaxy, system number, always: else only while the Phantom is hunted,
# words). The trail: Tuelve, Rotuvaga, Kalimii in the first galaxy; in the
# second, from where a galactic jump arrives (Linaqu) to the Phantom's
# hideout (Elnada). %N is the system's name.
SPECIAL = (
    (0, 42, False, "Our yard built the Phantom. It was last tracked heading for Rotuvaga, "
                   "Commander."),
    (0, 239, False, "A ship with no markings refuelled here and left for Kalimii without "
                    "paying the docking fee."),
    (0, 20, False, "It jumped out of the galaxy with a galactic hyperdrive. The Navy knows."),
    (1, 58, False, "A strange ship came out of a galactic jump here and made for Gaorsaka."),
    (1, 163, False, "Traders say a ship with no markings has been buying military parts. It "
                    "went on to Pamivaes."),
    (1, 83, False, "Our police chased an unmarked ship towards Soilliro. Their lasers did "
                   "nothing to it."),
    (1, 132, False, "The Phantom was seen leaving for Reorrove, Commander."),
    (1, 253, False, "A pilot here swears they saw the Phantom heading for Litudade."),
    (1, 21, False, "Something fast and quiet passed through, bound for Tudekai."),
    (1, 189, False, "They say the Phantom is hiding at Elnada. Be careful, Commander."),
    (1, 167, False, "Ships keep going missing round here. Something is out there."),
    (0, 8, True, "The colonists of %N say they are descended from a lost generation ship."),
    (1, 0, True, "Visitors to %N are warned that the local wildlife eats starship paint."),
    (2, 1, True, "%N is hosting the galactic chess finals this year."),
)
