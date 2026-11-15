"""The disc version's two missions. No badge imports, so it runs and tests on
a PC. The rules are the original's (DOENTRY, BRIEF, DEBRIEF, BRIEF2, BRIEF3,
DEBRIEF2, THERE, PDESC), written afresh:

1. The Constrictor. Dock in galaxy 1 or 2 with at least 256 kills (the
   original's TALLY; here divided by the level's RANK_DIVISOR, as the ranks
   are) and Her Majesty's Space Navy asks you to find and destroy a stolen
   prototype, the Constrictor. While you hunt it, the stations along its
   trail say where it went (the special system sentences, RUTOK). It is in
   Orarra, in galaxy 2, where it turns up in place of a lone bounty hunter
   (rare in a democracy like Orarra, as in the original) or, with the
   pause menu's CONSTRICTOR: 2 MIN (Commander.quick_con, the default), after
   QUICK_WAIT seconds outside the safe zone.
   Only a military laser hurts it, and only a quarter as much; it has an
   ECM. Dock after killing it: 5000 Cr and 256 more kills.
2. The Thargoid plans. With mission 1 done, dock in galaxy 3 with at least
   1280 kills and the Navy asks you to go to Ceerdi. Dock there and you are
   given the plans to take to Birera; until you do, Thargoids come after you.
   Dock at Birera: a naval energy unit (it recharges half as fast again as
   the usual one) and 256 more kills.

The state is kept as the original's TP byte, in Commander.mission:
  bits 0-1, mission 1: 00 not started, 01 hunting, 11 killed (not yet
  debriefed), 10 done; bits 2-3, mission 2: 00 not started, 01 started,
  10 carrying the plans, 11 done.
"""
try:
    from . import commander as _commander
except ImportError:         # imported on its own, as the PC tests do
    import commander as _commander

ORARRA = (1, 144, 33)       # (galaxy, x, y) on the chart: where the Constrictor is
CEERDI = (2, 215, 84)       # mission 2's briefing
BIRERA = (2, 63, 72)        # and where the plans go


def use(data):
    """Take the mission systems from the content in use (its MISSION_PLACES),
    if it says; otherwise they are the original's (Elite's game_data)."""
    global ORARRA, CEERDI, BIRERA
    places = getattr(data, "MISSION_PLACES", None)
    if places:
        ORARRA = places["constrictor"]
        CEERDI = places["briefing"]
        BIRERA = places["base"]
    else:
        ORARRA, CEERDI, BIRERA = (1, 144, 33), (2, 215, 84), (2, 63, 72)
QUICK_WAIT = 120.0          # seconds outside Orarra's safe zone before it comes (quick_con)
KILLS_1 = 256               # the original's kill counts for each mission
KILLS_2 = 1280
REWARD_KILLS = 256          # each mission's reward in kills
REWARD_CASH = 50000         # mission 1's, in tenths of a credit (5000 Cr)

# the texts (extended tokens in game_data.DESC_TOKENS), and whether the
# Constrictor is shown turning above them
BRIEF_1, DEBRIEF_1, BRIEF_2, BRIEF_3, DEBRIEF_2 = 10, 15, 11, 222, 223
SHOWS_SHIP = (BRIEF_1,)

# for the DEBUG page: each stage, its name, and the TP it stands for
STAGES = (
    ("NONE", 0b0000),
    ("1: HUNTING", 0b0001),
    ("1: KILLED", 0b0011),
    ("1: DONE", 0b0010),
    ("2: TO CEERDI", 0b0110),
    ("2: PLANS", 0b1010),
    ("2: DONE", 0b1110),
)


def _scaled(kills, cmdr):
    """The original's kill count for this commander's level."""
    div = _commander.RANK_DIVISOR[cmdr.level]
    return (kills + div // 2) // div


def stage_name(tp):
    for name, v in STAGES:
        if v == tp & 15:
            return name
    return "%d" % (tp & 15)


def next_stage(tp):
    """The DEBUG page's next stage after tp, round again after the last."""
    for i, (_, v) in enumerate(STAGES):
        if v == tp & 15:
            return STAGES[(i + 1) % len(STAGES)][1]
    return 0


def stage_kills(tp, cmdr):
    """For the DEBUG page: the kills that the next mission to start needs,
    so that docking after choosing a stage starts it."""
    if tp & 15 == 0:
        return _scaled(KILLS_1, cmdr)
    if tp & 15 == 0b0010:
        return _scaled(KILLS_2, cmdr)
    return 0


def where(tp):
    """Where the current stage happens, (galaxy, x, y), or None (anywhere)."""
    if tp & 3 == 1:
        return ORARRA
    if tp & 15 == 0b0110:
        return CEERDI
    if tp & 15 == 0b1010:
        return BIRERA
    return None


def hunting(tp):
    """Is the Constrictor still out there to be killed?"""
    return tp & 3 == 1


def constrictor_here(galaxy, x, y):
    """Is this the Constrictor's system (THERE)? True even after mission 1:
    the lone ships there stay as dangerous."""
    return (galaxy, x, y) == ORARRA


def carrying_plans(tp):
    """Mission 2's plans are on board: the Thargoids are after you."""
    return tp & 12 == 8


def killed(tp):
    """The Constrictor has just been destroyed: TP with that noted."""
    return tp | 2 if tp & 1 else tp


def on_docking(cmdr, x, y):
    """What docking here starts or ends (DOENTRY): the text to show (an
    extended token number), or None. Changes cmdr.mission and gives the
    rewards. x, y: the station's system's place on the chart."""
    c = cmdr
    tp = c.mission
    gal = c.galaxy
    if tp & 3 == 0:
        if c.kills >= _scaled(KILLS_1, c) and gal <= 1:
            c.mission = tp | 1
            return BRIEF_1
        return None
    if tp & 3 == 3:
        c.mission = tp & ~1
        c.kills += _scaled(REWARD_KILLS, c)
        c.cash += REWARD_CASH
        return DEBRIEF_1
    if tp & 15 == 0b0010:
        if c.kills >= _scaled(KILLS_2, c) and gal == 2:
            c.mission = tp | 4
            return BRIEF_2
        return None
    if tp & 15 == 0b0110:
        if (gal, x, y) == CEERDI:
            c.mission = (tp & 0xF0) | 0b1010
            return BRIEF_3
        return None
    if tp & 15 == 0b1010:
        if (gal, x, y) == BIRERA:
            c.mission = tp | 4
            c.kills += _scaled(REWARD_KILLS, c)
            if "energy" in c.extras:
                c.extras.remove("energy")
            if "navy" not in c.extras:
                c.extras.append("navy")
            return DEBRIEF_2
    return None


def special_sentence(game_data, tp, galaxy, index):
    """The system's special sentence (PDESC, RUTOK) when you are docked
    there, or None for the usual one: a few always, the rest only while
    mission 1 is under way."""
    own = getattr(game_data, "SPECIAL", None)
    if own:
        for n, (gal, system, always, _) in enumerate(own):
            if system == index and gal == galaxy:
                return n + 1 if always or tp & 1 else None
        return None
    ru = getattr(game_data, "DESC_RU", None)
    if not ru:
        return None
    for n, (system, gal) in enumerate(ru):
        if system == index and gal & 127 == galaxy:
            if gal & 128 or tp & 1:
                return n + 1
            return None
    return None
