"""Multiplayer (plans/MULTIPLAYER.md): up to four players in combat practice's
arena, each seeing the others' ships with their names. Rules only: the radio is
a link the platform gives (platform.radio(), e.g. net_espnow.Link on the badge):

    link.id          this device's id (bytes), the same on every packet it sends
    link.send(msg)   send bytes to everyone listening
    link.recv()      (sender id, bytes) for the next packet heard, or (None, None)

The lobby: everyone on the MULTIPLAYER page says HELLO a few times a second with
their commander's name, ship colour (cockpit.SHIP_COLOURS) and what they are
doing: in the LOBBY, HOSTing a game, JOINing one, or FLYING. One player hosts and
picks the mode; up to three others join (MAX_PLAYERS in all); the host sees who
joined and starts: START (the mode and the guests, in order) goes to the guests
a few times, in case one is lost, and everyone flies at once. The host is slot 0,
the guests slots 1-3 in the order they joined; in team modes the even slots are
RED (team 0) and the odd ones BLUE (team 1).

Modes (MODE_NAMES; Brian, 2026-11-25):
  DUEL           two players, rounds: the one destroyed presses C for the next.
  FREE FOR ALL   everyone against everyone, FFA_WIN kills wins.
  TEAMS          red against blue, TEAM_WIN kills wins; no friendly fire.
  CAPTURE FLAG   each team has a ring, RING_Z either side of the middle. Fly
                 through the other team's ring to take its flag (the ring goes
                 grey), then back through your own to score; CTF_WIN wins. A
                 carrier destroyed drops the flag: it goes home.
  CONVOY CO-OP   everyone defends a big freighter (convoy_ship.py) on its way
                 to a station from waves of pirates the host's game flies.
  CONVOY RAID    red defends the convoy, blue are raiders (with a few pirates).
  STATION CO-OP  everyone defends a space station (the host picks which, how long and
                 whether the waves grow) from pirates: some attack it, some try to dock.
                 Lost if it is destroyed or more than DOCK_LIMIT pirates dock.
  STATION RAID   red defends the station, blue raids it.
Except in a duel, a ship destroyed comes back after RESPAWN seconds at its
team's start (behind its home ring in Capture Flag); a match won shows who won
for RESULT_FOR seconds, then the next starts.

Who decides: your own game decides what hits you (lasers: the shooter says HIT;
missiles: the target's game flies them); the host decides the score, the flags,
the convoy and the pirates, and says so in STATE a few times a second (and at
once on a change). Pirates are ordinary ships in the host's game, which sends
their poses (NPCS); the others draw them as kind "npc" and send the host their
hits. In flight each player sends its pose (netplay.py) SEND_HZ times a second.

Leaving (Brian, 2026-11-25): the host leaving ends the game for everyone; a
guest leaving drops out of it, and the game ends when nobody else is left (but
CONVOY CO-OP carries on alone).
"""
import math
import random
import struct

from . import game, netplay

# ---- packets (all start with netplay.MAGIC and a kind byte) --------------------------
HELLO = 2
START_PKT = 3
END_PKT = 4                 # leaving the game (sent END_TIMES times: one may be lost)
END_TIMES = 3
HIT_PKT = 5                 # a laser hit: target slot, who (a slot, or NPC_SRC), damage x16
HIT_FMT = "<2sBBBH"
MISSILE_PKT = 6             # a missile: number, target (a slot, or NPC_BIT | npc id), where, way
MISSILE_FMT = "<2sBBBiiihhh"
GONE_PKT = 7                # a missile is gone: number, why, whose
GONE_FMT = "<2sBBBB"
GONE_HIT, GONE_ECM = 1, 2
AGAIN = 3                   # combat packets that matter go this many times
NEXT_PKT = 8                # a duel's next round (its number)
NEXT_FMT = "<2sBBH"
NPC_HIT_PKT = 9             # a hit on one of the host's ships: npc id, damage x16
NPC_HIT_FMT = "<2sBBH"
KILLED_PKT = 10             # we were destroyed: by whom (a slot, NPC_SRC or NOBODY), our death number
KILLED_FMT = "<2sBBH"
CLAIM_PKT = 11              # through a ring (Capture Flag): TAKE or CAPTURE, the ring's team, a number
CLAIM_FMT = "<2sBBBH"
TAKE, CAPTURE = 1, 2
STATE_PKT = 12              # the host's: match, result, time x10, scores, team scores, flags, convoy
STATE_FMT = "<2sBBBHhhhhhhBBBBB"
NPCS_PKT = 13               # the host's ships: count, then NPC_FMT each
NPCS_HEAD = "<2sBB"
NPC_FMT = "<BBBBhhhhhhhhh"  # id, type (game.PIRATES), flags, speed, x y z / 8, nose, roof x 16384
NPC_SIZE = struct.calcsize(NPC_FMT)
NPC_BIT = 0x80              # a missile's target: one of the host's ships
NPC_SRC = 254               # a hit or a kill by the host's pirates
NOBODY = 255                # killed by nobody (the sun, a crash...); no flag carrier

BEAM_CONE = 0.98            # their laser drawn at you when their nose is this close to you
# MAGIC, kind, role, colour, mode, target id (the host's, for JOIN and FLYING),
# name (16 bytes, ASCII, padded with spaces), guests (the host's: 3 ids, NO_ID if none),
# the team we'd like (NO_TEAM: any), options (the host's: OPT_PIRATES), each slot's team
# (the host's: 4 bytes, slot 0 first)
FMT = "<2sBBBB6s16s18sBB4sBBB"   # ... the host's LIVES (0: unlimited), the defenders' colour,
# its team set-up (SIDES_CHOICES number, bit 4: RANDOM)
NO_TEAM = 255
OPT_PIRATES = 1             # CONVOY RAID: pirates on the raiders' side (the host's choice)
# the pirates' skill (the host's choice, build 151): the game's level, EASY / NORMAL / HARD
# (game.LEVELS: how well they aim, how hard they hit, how tough they are), in options bits 1-2
LEVEL_NAMES = ("EASY", "NORMAL", "HARD")
# options bits 3-4: the station modes' time (STATION_TIMES), bit 5: growing waves, bits 6-7:
# the station (STATIONS)
OPT_GROW = 32
# the station modes' LIVES (Brian, build 156: "or fixed lives"): 0 unlimited, else how many
# times each player may be destroyed in a match before they are out till the next
LIVES_CHOICES = (0, 1, 2, 3, 5)
LOBBY, HOST, JOIN, FLYING = 0, 1, 2, 3
NO_ID = b"\x00" * 6
HELLO_EVERY = 0.25          # seconds between HELLOs on the lobby pages
FLY_HELLO_EVERY = 1.0       # and in flight (the lobby sees who is busy)
START_FOR = 1.0             # the host repeats START this long, every START_EVERY
START_EVERY = 0.1
SEND_HZ = 15                # poses a second in flight (the link test's rate)
LOST = 3.0                  # seconds without a packet: that player's ship goes
GONE_END = 10.0             # this long without them: they have left ("... LOST")
NOTICE_FOR = 4.0            # seconds the lobby shows why a game ended
GONE = 3.0                  # on the page: seconds without a HELLO before they leave the list
NAME_LEN = 16
MAX_PLAYERS = 4

# ---- modes ---------------------------------------------------------------------------
DUEL, FFA, TEAMS, CTF, COOP, RAID, SCOOP, SRAID = range(8)
MODE_NAMES = ("DUEL", "FREE FOR ALL", "TEAMS", "CAPTURE FLAG", "CONVOY CO-OP", "CONVOY RAID",
              "STATION CO-OP", "STATION RAID")
MODE_NOTES = ("two players, rounds", "most kills wins", "red against blue",
              "take their flag home", "defend it from pirates", "red defends, blue raids",
              "hold it: don't let them dock", "red defends, blue raids")
MODE_MIN = (2, 2, 2, 2, 1, 2, 1, 2)     # players, the host included
MODE_MAX = (2, 4, 4, 4, 4, 4, 4, 4)
TEAMED = (False, False, True, True, False, True, False, True)
GUARDED = (False, False, False, False, True, True, True, True)  # something to defend
RAIDED = (False, False, False, False, False, True, False, True)    # red defends, blue raids
COOPED = (False, False, False, False, True, False, True, False)    # everyone defends
STATIONED = (False, False, False, False, False, False, True, True)  # it's a station
TEAM_NAMES = ("RED", "BLUE")
TEAM_RGB = ((1, 0.25, 0.2), (0.3, 0.55, 1))
# the raids' defenders' colour (Brian, build 157: "defenders colour should be configurable",
# build 158: "Just between red and blue is ok"): 0 red (the raiders blue) or 1 blue (the
# raiders red)
DEFEND_COLOUR = 0
# team sizes (Brian, build 159: "Team size to be defined by the host"): ANY (players pick
# freely, at most MAX_PLAYERS) or red / defenders v blue / raiders, which caps the game at
# their sum; and "random player colour selection": PICK RANDOM puts the players on the
# teams at random when the host starts (within the sizes), CHOOSE lets each pick
SIDES_CHOICES = (None, (1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1))
RANDOM_TEAMS = 16           # in the team set-up byte
UNKNOWN = 2                 # a team not known yet (RANDOM, before the start)


def raid_rgb(defend_colour, t):
    """A raid team's colour: the defenders' (team 0) as chosen, the raiders' the other."""
    return TEAM_RGB[(t ^ defend_colour) & 1]
TAKEN_RGB = (0.35, 0.35, 0.4)       # a ring whose flag is away
CONVOY_RGB = (1, 0.85, 0.2)
FFA_WIN = 10
TEAM_WIN = 10
CTF_WIN = 3
RESPAWN = 5.0               # seconds dead before coming back (not a duel)
# CONVOY RAID, so the defenders aren't overwhelmed (Brian, 2026-11-25): they come back
# sooner; each raider more than there are defenders adds RAID_EXTRA_RESPAWN to the raiders'
# wait and a defender's worth of energy to the convoy; and pirate waves (if on) are
# 1 + defenders - raiders ships, none when the raiders are more
DEFEND_RESPAWN = 3.0
RAID_EXTRA_RESPAWN = 2.0
RESULT_FOR = 10.0           # seconds a match's result shows before the next
STATE_EVERY = 0.25
NPC_EVERY = 0.1             # the host's ships' poses, ten times a second
NPC_GONE = 1.5              # a ship of the host's not heard of this long has gone
DEAD_FOR = 0.5              # a destroyed ship of the host's is sent this long (to explode)

# where each side starts in the shared world: (x, y, z, nose x, y, z). A duel: host 0,
# guest 1, 8000 apart (Brian, 2026-11-25: 2000 started too close), as far as practice's
# ships come in (6000-9000), on the radar (10000), facing.
START_Z = 4000.0
START = ((0.0, 0.0, -START_Z, 0.0, 0.0, 1.0), (0.0, 0.0, START_Z, 0.0, 0.0, -1.0))
START_SPEED = 14.0          # as a new flight (Game.reset)
FFA_R = 4000.0              # free for all: round a circle this big, facing the middle
MATE_X = (-500.0, 500.0, -1500.0, 1500.0)  # a team's players start side by side
RING_Z = 5000.0             # Capture Flag: each team's ring this far from the middle
RING_R = 480                # its size (a Cobra Mk III is ~240 across)
RING_PASS = 460.0           # through it: within this of its middle
RING_BEHIND = 1500.0        # a team starts this far behind its ring
# the convoy: from CONVOY_Z0 along +z for CONVOY_TIME seconds, to a station
CONVOY_Z0 = -6000.0
CONVOY_SPEED = 80.0         # world units a second
CONVOY_TIME = 150.0
CONVOY_ENERGY = 1500.0
# the station modes (Brian, 2026-11-25): the station at the middle of the world, slot to +z
STATION_ENERGY = 2500.0
STATION_TIMES = (120.0, 180.0, 300.0)   # how long to hold it: the host picks (2, 3 or 5 min)
DOCK_LIMIT = 3              # more than this many pirates docked: the station is lost
# the station's shield (Brian, 2026-11-25: "the shield must be destroyed before a pirate
# ship can dock"): hits take it first; while it is up the would-be dockers attack the
# station, and only with it down do they fly in to dock. Unhit for SHIELD_WAIT seconds it
# recharges SHIELD_RECHARGE a second, and those still outside go back to attacking.
STATION_SHIELD = 1000.0
SHIELD_WAIT = 5.0
SHIELD_RECHARGE = 20.0
# a defender destroyed in a station mode waits STATION_PENALTY seconds (the time penalty),
# then launches from the station: the launch tunnel (ace.py), out of the slot (Brian,
# 2026-11-25). With fixed LIVES a player out of lives stays out: all the defenders out, the station is
# lost; in a raid, all the raiders out, it is held.
STATION_PENALTY = 10.0
LAUNCH_OUT = 300.0          # launched this far out in front of the slot
GROW_EVERY = 60.0           # growing waves: one more pirate a wave each this many seconds
DOCKED = 4                  # NPCS flags: this ship docked (gone, no explosion)
# the stations to defend: (role, whose): the game's own Drum and Halo, and Elite's Coriolis
# and Dodo when its ship data is there (on the host; a player without it sees the game's own)
STATIONS = (("CORIOLIS", "own"), ("DODO", "own"), ("CORIOLIS", "elite"), ("DODO", "elite"))
WAVE_FIRST = 8.0            # the first pirates come this long after the start
WAVE_EVERY = 25.0           # and more this often
MAX_NPCS = 8
NPC_SLOTS = MAX_NPCS + 2   # in one NPCS packet: the living and a few just destroyed (fits ESP-NOW)


def start_pose(slot):
    """A duel's (x, y, z, axes) for a starting slot: level, nose along the given way."""
    x, y, z, nx, ny, nz = START[slot]
    return _pose(x, y, z, nx, ny, nz)


def _pose(x, y, z, nx, ny, nz):
    m = [0.0] * 9
    game._look(m, *game._unit(nx, ny, nz))
    return x, y, z, m


def _name_bytes(name):
    b = bytes(ord(c) if 32 <= ord(c) < 127 else 63 for c in str(name).upper()[:NAME_LEN])
    return b + b" " * (NAME_LEN - len(b))


def colour_rgb(i):
    """A ship colour number as drawn (cockpit.ship_rgb)."""
    from . import cockpit
    return cockpit.ship_rgb(i)


def team_of(mode, slot):
    """A slot's team before anyone chooses: the even slots red (0), the odd blue (1);
    0 for all with no teams. (Duel.team_of has the teams as chosen.)"""
    return slot & 1 if TEAMED[mode] else 0


def team_label(mode, t):
    """What a team is called on the pages: RED / BLUE, or in a raid what it does."""
    if RAIDED[mode]:
        return "DEFEND" if t == 0 else "RAID"
    return TEAM_NAMES[t]


def convoy_z(t):
    """Where the convoy is along its way at match time t."""
    return CONVOY_Z0 + CONVOY_SPEED * (t if t < CONVOY_TIME else CONVOY_TIME)


def spawn_pose(mode, slot, t=0.0, team=None, mate=None):
    """Where slot starts (and comes back after being destroyed): (x, y, z, axes). team:
    its team (as chosen), mate: how many of its team have a lower slot (by default, as
    the slots alternate red, blue)."""
    if mode == DUEL:
        return start_pose(slot if slot < 2 else 1)
    if team is None:
        team = slot & 1
    if mate is None:
        mate = slot >> 1
    mx = MATE_X[mate & 3]
    if mode == FFA:
        a = slot * math.pi / 2
        x, z = FFA_R * math.sin(a), -FFA_R * math.cos(a)
        return _pose(x, 0.0, z, -x, 0.0, -z)
    s = -1.0 if team == 0 else 1.0
    if mode == TEAMS:
        return _pose(mx, 0.0, s * START_Z, 0.0, 0.0, -s)
    if mode == CTF:
        return _pose(mx, 0.0, s * (RING_Z + RING_BEHIND), 0.0, 0.0, -s)
    cz = 0.0 if STATIONED[mode] else convoy_z(t)    # the station is at the middle
    if RAIDED[mode] and team == 1:      # a raider: ahead of the convoy, off to one side
        x = mx * 6.0
        return _pose(x, 0.0, cz + 7000.0, -x, 0.0, -7000.0)
    if COOPED[mode]:
        mate = slot
    side = (-700.0, 700.0, -1100.0, 1100.0)[mate & 3]
    return _pose(side, 250.0, cz - 1800.0, 0.0, 0.0, 1.0)


_RING_BP = None


def ring_blueprint():
    """A hoop to fly through: two 12-sided rings, the inner a little smaller, four struts."""
    global _RING_BP
    if _RING_BP is None:
        n = 12
        verts = []
        for r in (RING_R, RING_R - 50):
            for k in range(n):
                a = 2 * math.pi * k / n
                verts.append((int(r * math.cos(a)), int(r * math.sin(a)), 0))
        edges = [(k, (k + 1) % n, 0, 0) for k in range(n)]
        edges += [(n + k, n + (k + 1) % n, 0, 0) for k in range(n)]
        edges += [(k, n + k, 0, 0) for k in range(0, n, 3)]
        _RING_BP = game.Blueprint(("RING", tuple(verts), tuple(edges), ((0, 0, 0),), None, "RING"))
    return _RING_BP


_STATION_BPS = {}


def _station_entry(i):
    """STATIONS[i]'s ship entry, or None if its content isn't here."""
    role, whose = STATIONS[i]
    try:
        if whose == "own":
            from .original_ships import SHIPS
        else:
            from .ship_data import SHIPS
    except ImportError:
        return None
    for e in SHIPS:
        if e[0] == role:
            return e
    return None


def available_stations():
    """The stations this device can show (STATIONS numbers): the game's own two, Elite's
    two only with its ship data."""
    out = [i for i in range(len(STATIONS)) if _station_entry(i) is not None]
    return out or [0]


def station_name(i):
    e = _station_entry(i)
    if e is None:
        return STATIONS[i][0]
    return e[5] if len(e) > 5 else e[0]


def station_blueprint(i):
    """The station to draw for STATIONS[i]: the same role from the other content if this
    device hasn't that one (a guest without Elite's data sees the game's own)."""
    if i not in _STATION_BPS:
        e = _station_entry(i) or _station_entry(i ^ 2) or _station_entry(i & 1)
        _STATION_BPS[i] = game.Blueprint(e) if e is not None else convoy_blueprint()
    return _STATION_BPS[i]


_CONVOY_BP = None


def convoy_blueprint():
    global _CONVOY_BP
    if _CONVOY_BP is None:
        from . import convoy_ship
        _CONVOY_BP = game.Blueprint(convoy_ship.SHIP)
    return _CONVOY_BP


class Player:
    """Someone heard: their name, colour, what they are doing, and for whom; in a
    game, their slot and ship."""

    def __init__(self, ident):
        self.id = ident
        self.name = "?"
        self.colour = 0
        self.role = LOBBY
        self.mode = DUEL
        self.target = NO_ID
        self.guests = ()        # a host's guests' ids
        self.team_pref = NO_TEAM    # the team they'd like
        self.teams = (0, 1, 0, 1)   # a host's: each slot's team
        self.opts = OPT_PIRATES     # a host's options
        self.opts2 = 0
        self.defend_colour = DEFEND_COLOUR
        self.teamopt = 0        # a host's team set-up (SIDES_CHOICES number, RANDOM_TEAMS)
        self.t = 0.0            # seconds since last heard
        self.slot = 0
        self.ship = None        # their ship in our game (an Obj, kind "player")
        self.pose = None        # (x, y, z, speed) of their last pose
        self.pose_m = [0.0] * 9     # its axes (filled by read_pose)
        self.pose_age = 0.0
        self.last_seq = None
        self.flags = 0          # their last pose's flags (netplay.FIRING, DEAD)
        self.lost = False

    def open_slots(self):
        sides = SIDES_CHOICES[self.teamopt & 15] if TEAMED[self.mode] and (self.teamopt & 15) < len(
            SIDES_CHOICES) else None
        most = sides[0] + sides[1] if sides else MAX_PLAYERS
        return most - 1 - len(self.guests)


class Duel:
    def __init__(self, link, name="JAMESON", colour=0):
        self.link = link
        self.name = "JAMESON"
        self.colour = 0
        self.set_me(name, colour)
        self.role = LOBBY       # what we are doing: LOBBY, HOST or JOIN
        self.mode = DUEL        # the game's mode (the host picks it)
        self.players = {}       # id -> Player, everyone heard lately
        self.guests = []        # hosting: the Players who joined, in order
        self.host_p = None      # joining: the host's Player
        self.start_ids = ()     # the guests' ids when the game started
        self.team_pref = NO_TEAM    # the team we'd like (team modes)
        self.pirates = True     # hosting CONVOY RAID: pirates on the raiders' side
        self.pirate_level = 1   # their skill: game.LEVELS (0 EASY, 1 NORMAL, 2 HARD)
        self.time_i = 1         # the station modes: how long (STATION_TIMES), 3 minutes
        self.growing = True     # and whether the waves grow
        self.station_i = 0      # and which station (STATIONS)
        self.lives = 0          # and LIVES (LIVES_CHOICES; 0: unlimited)
        self.defend_colour = DEFEND_COLOUR  # a raid's defenders' colour: 0 red, 1 blue (raid_rgb)
        self.sides_i = 0        # team modes: team sizes (SIDES_CHOICES), 0 ANY
        self.random_teams = False   # and PICK: RANDOM
        self.wants_launch = False   # destroyed, penalty served: ace shows the launch tunnel
        self.teams = [0, 1, 0, 1]   # in a game: each slot's team
        self.roster = {}        # in a game: slot -> Player, everyone but us
        self.by_id = {}         # and id -> Player
        self.go = False         # START said (by us as host, or to us as guest): fly
        self.slot = 0
        self.flying = False
        self.hello_t = 0.0
        self.start_t = 0.0      # host: how long START is still repeated
        self.start_gap = 0.0
        self.buf = bytearray(netplay.SIZE)     # made once: no garbage per packet
        self.hello = bytearray(struct.calcsize(FMT))
        self.pkt = bytearray(struct.calcsize(MISSILE_FMT))     # combat packets, made once
        self.state_buf = bytearray(struct.calcsize(STATE_FMT))
        self.npc_buf = bytearray(struct.calcsize(NPCS_HEAD) + NPC_SIZE * (NPC_SLOTS))
        self.seq = 0
        self.send_t = 0.0
        self.g = None           # the Game while flying (hits and missiles arrive any time)
        self.missile_n = 0      # numbers for our missiles
        self.ghosts = {}        # number -> our missile's harmless copy, till they say GONE
        self.incoming = {}      # (slot, number) -> their missile, flown here at us
        self.seen_missiles = []     # (sender, number) already launched here (repeats ignored)
        self.dead_here = False  # we are destroyed (counted once)
        self.kills = 0          # a duel: times we destroyed them, and they us
        self.deaths = 0
        self.round = 1
        self.ended = None       # why the game ended for us: the game goes back
        self.notice = None      # to the lobby, which shows this for NOTICE_FOR seconds
        self.notice_t = 0.0
        self._match_reset()

    def _match_reset(self):
        """A new match's score, flags and convoy (everything the host decides)."""
        self.match = getattr(self, "match", 0)
        self.result = 0         # 0 playing; 1 + team won; 10 + slot won (free for all)
        self.result_t = 0.0
        self.mtime = 0.0        # seconds since the match started
        self.scores = [0, 0, 0, 0]      # per slot: kills, captures or pirates destroyed
        self.team = [0, 0]
        self.carrier = [NOBODY, NOBODY]     # who has each team's flag
        self.hp = 255           # the convoy's (or station's) energy, 0-255
        self.docked = 0         # the station modes: pirates that have docked
        self.out = set()        # LIVES: the slots out of lives this match
        self.lives_lost = [0, 0, 0, 0]  # and how many times each has been destroyed
        self.shield_b = 255     # and the station's shield, 0-255 (STATE)
        self.shield = self.shield_max = STATION_SHIELD  # the host's, in energy
        self.shield_quiet = 0.0     # host: seconds since the station was last hit
        self.last_energy = None     # host: its energy last frame (to see hits)
        self.respawn_t = 0.0
        self.last_by = NOBODY   # who last hurt us, and how long ago
        self.last_by_t = 99.0
        self.death_no = getattr(self, "death_no", 0)
        self.seen_kills = []
        self.claim_no = getattr(self, "claim_no", 0)
        self.seen_claims = []
        self.state_t = 0.0
        self.npc_t = 0.0
        self.wave_t = WAVE_FIRST
        self.npcs = {}          # host: id -> its ship; others: id -> the ship drawn ("npc")
        self.npc_seen = {}      # others: id -> seconds since its pose
        self.npc_dead = []      # host: [id, type, world pose, seconds] of ships just destroyed
        self.npc_n = 0
        self.npc_missiles = {}  # host: (slot, number) -> a missile flown for a guest at its ship
        self.marks = []         # rings and the station (kind "mark")
        self.rings = [None, None]
        self.convoy = None
        self.ring_rel = None    # how far we were through each ring's plane last frame
        self.mark_t = 0.0
        self.hud_t = 0.0
        self.hud_cache = None

    def team_of(self, slot):
        """A slot's team in this game (as chosen in the lobby); 0 for all with no teams."""
        return self.teams[slot] & 1 if TEAMED[self.mode] else 0

    def _side_out(self, team):
        """Fixed lives: every player on team (still here) is out of lives."""
        if not (self.lives and STATIONED[self.mode]):
            return False
        slots = [self.slot] + list(self.roster)
        side = [s for s in slots if self.team_of(s) == team]
        return bool(side) and all(s in self.out for s in side)

    def _counts(self):
        """(defenders, raiders): how many players on each team now (us included)."""
        n = [0, 0]
        n[self.team_of(self.slot)] += 1
        for s in self.roster:
            n[self.team_of(s)] += 1
        return n[0], n[1]

    def _mate(self, slot):
        """How many of slot's team have a lower slot: where it starts in the line."""
        t = self.team_of(slot)
        return sum(1 for s in range(slot) if self.team_of(s) == t)

    def set_me(self, name, colour):
        """The commander's name and ship colour, sent in every HELLO."""
        self.name = str(name).upper()[:NAME_LEN] or "JAMESON"
        self.colour = colour if isinstance(colour, int) and 0 <= colour < 32 else 0

    @property
    def other(self):
        """The one other player (a duel; the first guest, or the host)."""
        if self.flying:
            for s in sorted(self.roster):
                return self.roster[s]
            return None
        if self.role == JOIN:
            return self.host_p
        return self.guests[0] if self.guests else None

    # ---- what the pages show ---------------------------------------------------------

    def hosts(self):
        """Games we could join: players hosting with room (or with us already in)."""
        me = self.link.id
        return [p for p in self.lobby() if p.role == HOST
                and (p.open_slots() > 0 or me in p.guests)]

    def lobby(self):
        """Everyone else heard lately (on the lobby pages or flying), by name."""
        return sorted((p for p in self.players.values() if p.t < GONE), key=lambda p: p.name)

    def accepted(self):
        """Joining: True once our host lists us among its guests."""
        o = self.host_p
        return (o is not None and self.role == JOIN and o.t < GONE and o.role == HOST
                and self.link.id in o.guests)

    def party(self):
        """Who is in the game we host or joined, in slot order:
        [(name, colour, slot, team)]."""
        if self.role == HOST:
            teams = self.lobby_teams()
            out = [(self.name, self.colour, 0, teams[0])]
            out += [(p.name, p.colour, i + 1, teams[i + 1]) for i, p in enumerate(self.guests)]
            return out
        h = self.host_p
        if h is None:
            return []
        out = [(h.name, h.colour, 0, h.teams[0])]
        for i, gid in enumerate(h.guests):
            if gid == self.link.id:
                out.append((self.name, self.colour, i + 1, h.teams[i + 1]))
            else:
                p = self.players.get(gid)
                out.append((p.name if p is not None else "?", p.colour if p is not None else 0,
                            i + 1, h.teams[i + 1]))
        return out

    def sides(self):
        """The team sizes the host set: (red / defenders, blue / raiders), or None (ANY)."""
        return SIDES_CHOICES[self.sides_i] if TEAMED[self.mode] else None

    def most_players(self):
        s = self.sides()
        return s[0] + s[1] if s else MAX_PLAYERS

    def teamopt(self):
        return (self.sides_i & 15) | (RANDOM_TEAMS if self.random_teams else 0)

    def _take_teamopt(self, b):
        self.sides_i = (b & 15) if (b & 15) < len(SIDES_CHOICES) else 0
        self.random_teams = bool(b & RANDOM_TEAMS)

    def step_sides(self, step):
        self.sides_i = (self.sides_i + step) % len(SIDES_CHOICES)
        self.hello_t = 0.0

    def set_random_teams(self, on):
        self.random_teams = bool(on)
        self.hello_t = 0.0

    def lobby_teams(self, final=False):
        """Hosting: each slot's team, four, slot 0 (us) first: as its player chose if that
        team has room (SIDES), or else the team with more room (red if level). With PICK
        RANDOM: UNKNOWN until final (the start), then at random within the sizes."""
        prefs = [self.team_pref] + [p.team_pref for p in self.guests]
        sides = self.sides()
        room = list(sides) if sides else [MAX_PLAYERS, MAX_PLAYERS]
        if self.random_teams and TEAMED[self.mode]:
            n = len(prefs)
            if not final:
                return [UNKNOWN] * MAX_PLAYERS
            # how many red: as near the sizes' share as fits, at least one on each side
            k0 = int(n * room[0] / float(room[0] + room[1]) + 0.5) if sides else (n + 1) // 2
            k0 = max(max(1, n - room[1]), min(k0, room[0], n - 1)) if n > 1 else 1
            order = list(range(n))
            for i in range(n - 1, 0, -1):       # shuffle (MicroPython has no random.shuffle)
                j = random.randint(0, i)
                order[i], order[j] = order[j], order[i]
            teams = [1] * n
            for s_ in order[:k0]:
                teams[s_] = 0
            return teams + [0] * (MAX_PLAYERS - n)
        teams = []
        for pref in prefs:
            if (pref == 0 or pref == 1) and room[pref] > 0:
                t = pref
            else:
                t = 0 if room[0] >= room[1] else 1
            room[t] -= 1
            teams.append(t)
        while len(teams) < MAX_PLAYERS:
            teams.append(0 if room[0] >= room[1] else 1)
            room[teams[-1]] -= 1
        return teams

    def my_team(self):
        """The team we are on in the lobby (as the host has it), None (no teams), or
        UNKNOWN (PICK RANDOM: till the start)."""
        if self.role == HOST:
            return self.lobby_teams()[0] if TEAMED[self.mode] else None
        h = self.host_p
        if h is None or not TEAMED[h.mode] or self.link.id not in h.guests:
            return None
        return h.teams[1 + h.guests.index(self.link.id)]

    def choose_team(self, t):
        """Ask for team t (0 red / defend, 1 blue / raid); the host takes it."""
        self.team_pref = t & 1
        self.hello_t = 0.0

    def set_pirates(self, on):
        self.pirates = bool(on)
        self.hello_t = 0.0

    def options(self):
        """The host's options as one byte (HELLO and START)."""
        return ((OPT_PIRATES if self.pirates else 0) | (self.pirate_level << 1) | (self.time_i << 3)
                | (OPT_GROW if self.growing else 0) | (self.station_i << 6))

    def _take_options(self, opts):
        self.pirates = bool(opts & OPT_PIRATES)
        self.pirate_level = min(2, (opts >> 1) & 3)
        self.time_i = min(len(STATION_TIMES) - 1, (opts >> 3) & 3)
        self.growing = bool(opts & OPT_GROW)
        self.station_i = (opts >> 6) & 3

    def step_defend_colour(self, step=1):
        """Left / right on the DEFENDERS line: red or blue."""
        self.defend_colour ^= 1
        self.hello_t = 0.0

    def team_rgb(self, t):
        """Team t's colour in this game (a raid's as the host chose, raid_rgb)."""
        if RAIDED[self.mode]:
            return raid_rgb(self.defend_colour, t)
        return TEAM_RGB[t]

    def step_lives(self, step):
        """Left / right on the LIVES line: UNLIMITED, 1, 2, 3, 5."""
        i = LIVES_CHOICES.index(self.lives) if self.lives in LIVES_CHOICES else 0
        self.lives = LIVES_CHOICES[(i + step) % len(LIVES_CHOICES)]
        self.hello_t = 0.0

    def lives_left(self, slot=None):
        """How many more times slot (us) may be destroyed this match; None if unlimited."""
        if not (self.lives and STATIONED[self.mode]):
            return None
        return max(0, self.lives - self.lives_lost[self.slot if slot is None else slot])

    def launches(self):
        """True if we come back by launching from the station (a station mode's defender)."""
        return STATIONED[self.mode] and self.team_of(self.slot) == 0

    def launched(self, g):
        """ace: the launch tunnel is over: out of the station's slot, into the fight."""
        self.wants_launch = False
        self._respawn(g, launch=True)

    def step_time(self, step):
        self.time_i = (self.time_i + step) % len(STATION_TIMES)
        self.hello_t = 0.0

    def set_growing(self, on):
        self.growing = bool(on)
        self.hello_t = 0.0

    def step_station(self, step):
        """Left / right on the STATION line: through the stations this device has."""
        have = available_stations()
        i = have.index(self.station_i) if self.station_i in have else 0
        self.station_i = have[(i + step) % len(have)]
        self.hello_t = 0.0

    def guard_time(self):
        """How long the defenders must hold out: the convoy's trip, or the station's time."""
        return STATION_TIMES[self.time_i] if STATIONED[self.mode] else CONVOY_TIME

    def dock_target(self, o):
        """Game: the station a docking pirate (o.net_prey "dock") is making for, or None:
        none while its shield is up."""
        c = self.convoy
        if (o.net_prey == "dock" and STATIONED[self.mode] and c is not None and not c.dead
                and self.shield_b == 0):
            return c
        return None

    @staticmethod
    def _shield_say(was, now):
        if now == 0 and was > 0:
            return "STATION SHIELDS DOWN"
        if now > 0 and was == 0:
            return "STATION SHIELDS UP"
        return None

    def _shield_step(self, g, c, dt):
        """Host: the station's shield takes its hits first (the game takes them from its
        energy; given back here), recharges when it has been left alone, and sends the
        would-be dockers in only while it is down."""
        if self.last_energy is None:
            self.last_energy = c.energy
        lost = self.last_energy - c.energy
        if lost > 0:
            self.shield_quiet = 0.0
            if self.shield > 0:
                take = lost if lost < self.shield else self.shield
                self.shield -= take
                c.energy += take
        else:
            self.shield_quiet += dt
            if self.shield_quiet >= SHIELD_WAIT and self.shield < self.shield_max:
                self.shield += SHIELD_RECHARGE * dt
                if self.shield > self.shield_max:
                    self.shield = self.shield_max
        self.last_energy = c.energy
        sb = 0 if self.shield <= 0 else max(1, int(self.shield * 255 / self.shield_max))
        if sb != self.shield_b:
            say = self._shield_say(self.shield_b, sb)
            if say:
                g.say(say, 2.5)
                self.state_t = 0.0      # tell everyone at once
            self.shield_b = sb
            self.hud_cache = None
        down = sb == 0
        for o in self.npcs.values():
            if not o.net_docker or o.dead:
                continue
            if down and (o.state == "attack" or o.state == "break") and o.net_prey == "c":
                o.state = "trade"       # in to dock
                o.net_prey = "dock"
                o.prey = None
            elif not down and o.state == "trade":
                o.state = "attack"      # shields up again: back to battering it
                o.net_prey = "c"
                o.prey = None

    def pirates_setting(self):
        """The PIRATES line: -1 off, else their level (0-2)."""
        return self.pirate_level if (self.pirates or not RAIDED[self.mode]) else -1

    def step_pirates(self, step):
        """Left / right on the PIRATES line: through OFF (a raid only), EASY, NORMAL, HARD."""
        first = -1 if RAIDED[self.mode] else 0
        v = self.pirates_setting() + step
        if v > 2:
            v = first
        elif v < first:
            v = 2
        self.pirates = v >= 0
        if v >= 0:
            self.pirate_level = v
        self.hello_t = 0.0

    def can_start(self):
        """Hosting: (True, "") if the mode can start with these players, else (False, why)."""
        n = 1 + len([p for p in self.guests if p.t < GONE])
        if n < MODE_MIN[self.mode]:
            return False, "needs %d players" % MODE_MIN[self.mode]
        if n > MODE_MAX[self.mode]:
            return False, "%d players only" % MODE_MAX[self.mode]
        if TEAMED[self.mode]:
            if n > self.most_players():
                return False, "%d players only" % self.most_players()
            if n < 2:
                return False, "a player on each team"
            teams = self.lobby_teams()[:n]
            if not self.random_teams and (0 not in teams or 1 not in teams):
                return False, "a player on each team"
        return True, ""

    # ---- the lobby -------------------------------------------------------------------

    def host(self, mode=None):
        """Host a game: wait for guests."""
        self.role = HOST
        if mode is not None:
            self.mode = mode
        self.guests = []
        self.host_p = None
        self.go = False
        self.hello_t = 0.0      # say so at once

    def set_mode(self, mode):
        self.mode = mode % len(MODE_NAMES)
        self.hello_t = 0.0

    def join(self, p):
        """Ask to join host p (a Player from hosts())."""
        self.role = JOIN
        self.host_p = p
        self.guests = []
        self.go = False
        self.hello_t = 0.0

    def leave(self):
        """Back to the lobby (stop hosting, or stop waiting for a host)."""
        self.role = LOBBY
        self.guests = []
        self.host_p = None
        self.go = False
        self.hello_t = 0.0

    def start_game(self):
        """The host presses start: START to the guests, then fly. False if it can't."""
        if self.role != HOST or not self.can_start()[0]:
            return False
        self.guests = [p for p in self.guests if p.t < GONE]
        self.start_ids = tuple(p.id for p in self.guests)
        self.teams = self.lobby_teams(final=True)     # (RANDOM: drawn now)
        self.start_t = START_FOR
        self.start_gap = START_EVERY
        self._send_start()
        self.go = True
        return True

    def lobby_step(self, dt):
        """The lobby pages, each frame: say HELLO now and then, hear everyone."""
        self._age(dt)
        if self.notice_t > 0:
            self.notice_t -= dt
            if self.notice_t <= 0:
                self.notice = None
        self.hello_t -= dt
        if self.hello_t <= 0:
            self.hello_t = HELLO_EVERY
            self._say(self.role)
        self._hear()
        if self.role == HOST:
            self.guests = [p for p in self.guests if p.t < GONE]    # gone away: room again

    def _age(self, dt):
        for p in self.players.values():
            p.t += dt

    def _ids(self):
        b = b""
        if self.role == HOST or (self.flying and self.slot == 0):
            ids = self.start_ids if self.flying else tuple(p.id for p in self.guests)
            for i in ids[:MAX_PLAYERS - 1]:
                b += bytes(i)
        return b + NO_ID * (3 - len(b) // 6)

    def _say(self, role, kind=HELLO):
        if role == JOIN or (role == FLYING and self.slot != 0):
            target = self.host_p.id if self.host_p is not None else NO_ID
        elif role == FLYING:
            target = self.link.id
        else:
            target = NO_ID
        hosting = role == HOST or (role == FLYING and self.slot == 0)
        if hosting:
            teams = self.teams if (self.flying or kind == START_PKT) else self.lobby_teams()
        else:
            teams = (0, 1, 0, 1)
        struct.pack_into(FMT, self.hello, 0, netplay.MAGIC, kind, role, self.colour, self.mode,
                         target, _name_bytes(self.name), self._ids(), self.team_pref,
                         self.options(), bytes(teams[:MAX_PLAYERS]),
                         self.lives & 0xFF, self.defend_colour & 0xFF, self.teamopt())
        self.link.send(self.hello)

    def _send_start(self):
        self._say(HOST, START_PKT)

    def _end(self, why):
        """The game is over for us (ace sees .ended and goes back to the lobby)."""
        if self.ended is None:
            self.ended = why

    def _hear(self):
        """Read every packet waiting."""
        size = struct.calcsize(FMT)
        me = self.link.id
        while True:
            host, msg = self.link.recv()
            if msg is None:
                return
            if len(msg) < 4 or bytes(msg[0:2]) != netplay.MAGIC:
                continue
            if host == me:
                continue        # our own (a UDP broadcast comes back)
            kind = msg[2]
            if kind == netplay.POSE:
                self._hear_pose(host, msg)
                continue
            if kind >= HIT_PKT:
                self._hear_game(host, kind, msg)
                continue
            if (kind != HELLO and kind != START_PKT and kind != END_PKT) or len(msg) < size:
                continue
            (_, _, role, colour, mode, target, name, ids, pref, opts,
             teams, opts2, dcol, topt) = struct.unpack_from(FMT, msg, 0)
            hid = bytes(host)
            p = self.players.get(hid)
            if p is None:
                p = Player(hid)     # a copy: the radio reuses its buffer
                self.players[hid] = p
            p.t = 0.0
            p.name = name.decode().strip() or "?"
            p.colour = colour
            if kind == END_PKT:
                if self.flying and self.by_id.get(hid) is p:
                    self._drop(p, "LEFT")   # leaving: they are out of our game
                continue
            guests = tuple(bytes(ids[i:i + 6]) for i in range(0, 18, 6) if bytes(ids[i:i + 6]) != NO_ID)
            if kind == START_PKT:
                if (self.role == JOIN and self.host_p is p and me in guests and not self.flying):
                    self.go = True          # our host started: fly
                    self.mode = mode
                    self.start_ids = guests
                    self.teams = [t & 1 for t in bytes(teams)]   # (at the start, all known)
                    self._take_options(opts)
                    self.lives = opts2
                    self.defend_colour = dcol & 1
                    self._take_teamopt(topt)
                continue
            p.role = role
            p.mode = mode
            p.team_pref = pref
            if role == HOST or role == FLYING:
                p.teams = tuple(t if t <= UNKNOWN else 0 for t in bytes(teams))
                p.opts = opts
                p.opts2 = opts2
                p.defend_colour = dcol & 1
                p.teamopt = topt
            p.target = bytes(target)
            p.guests = guests if role == HOST or role == FLYING else ()
            if self.role == HOST and not self.flying:
                if role == JOIN and p.target == me:
                    if p not in self.guests and len(self.guests) < self.most_players() - 1:
                        self.guests.append(p)       # a guest (the first three to ask)
                elif p in self.guests:
                    self.guests.remove(p)           # gone back to the lobby, or elsewhere
            elif self.flying and self.by_id.get(hid) is p and role != FLYING:
                hid0 = self.roster[0].id if 0 in self.roster else me
                # a HELLO from before START (hosting, or joining our host) isn't leaving
                if not ((role == HOST and p.slot == 0) or (role == JOIN and p.target == hid0)):
                    self._drop(p, "LEFT")           # back in the lobby: their END was lost

    def _drop(self, p, word):
        """Player p has left our game (word: LEFT or LOST)."""
        if self.by_id.get(p.id) is not p:
            return
        g = self.g
        if p.slot == 0:                 # the host: the game ends for everyone (Brian)
            self._end("HOST " + word)
            return
        del self.by_id[p.id]
        self.roster.pop(p.slot, None)
        self._remove_ship(p)
        if self.slot == 0:
            for k in (0, 1):
                if self.carrier[k] == p.slot:   # its flag goes home
                    self.carrier[k] = NOBODY
                    self.state_t = 0.0
        if not self.roster and not COOPED[self.mode]:
            self._end(p.name + " " + word)      # nobody left to play
        elif g is not None:
            g.say(p.name + " " + word, 2.0)

    def _remove_ship(self, p):
        s = p.ship
        if s is not None:
            s.dead = True
            g = self.g
            if g is not None and s in g.objs:
                g.objs.remove(s)
        p.ship = None

    def _hear_game(self, host, kind, msg):
        """Combat and the host's word, from players in our game only."""
        g = self.g
        p = self.by_id.get(bytes(host)) if self.flying else None
        if p is None or g is None:
            return              # not someone in our game, or not flying
        p.t = 0.0
        if kind == HIT_PKT and len(msg) >= struct.calcsize(HIT_FMT):
            _, _, to, src, d = struct.unpack_from(HIT_FMT, msg, 0)
            if to == self.slot and not g.over:
                g._hurt(d / 16.0)
                self.last_by = p.slot if src != NPC_SRC else NPC_SRC
                self.last_by_t = 0.0
        elif kind == MISSILE_PKT and len(msg) >= struct.calcsize(MISSILE_FMT):
            self._hear_missile(p, msg)
        elif kind == NEXT_PKT and len(msg) >= struct.calcsize(NEXT_FMT):
            n = struct.unpack_from(NEXT_FMT, msg, 0)[3]
            if n > self.round:          # they pressed C: both back to the start
                self.round = n
                g.reset()
                self.start(g)
                g.say("ROUND %d" % n, 2.0)
        elif kind == GONE_PKT and len(msg) >= struct.calcsize(GONE_FMT):
            _, _, n, why, whose = struct.unpack_from(GONE_FMT, msg, 0)
            if whose != self.slot:
                return
            gm = self.ghosts.pop(n, None)
            if gm is not None and not gm.dead:
                gm.dead = True
                g._boom(gm.x, gm.y, gm.z, 8)
                if why == GONE_ECM:
                    g.say("ECM")
                    g.sfx("ecm")
        elif kind == KILLED_PKT and len(msg) >= struct.calcsize(KILLED_FMT):
            _, _, by, no = struct.unpack_from(KILLED_FMT, msg, 0)
            key = (p.slot, no)
            if key in self.seen_kills:
                return
            self.seen_kills.append(key)
            if len(self.seen_kills) > 16:
                self.seen_kills.pop(0)
            self._killed(p.slot, by)
        elif kind == STATE_PKT and p.slot == 0 and len(msg) >= struct.calcsize(STATE_FMT):
            v = struct.unpack_from(STATE_FMT, msg, 0)
            self._set_state(v[2], v[3], v[4] / 10.0, v[5:9], v[9:11], v[11:13], v[13], v[14], v[15])
        elif kind == NPCS_PKT and p.slot == 0:
            self._hear_npcs(msg)
        elif self.slot == 0 and kind == NPC_HIT_PKT and len(msg) >= struct.calcsize(NPC_HIT_FMT):
            _, _, n, d = struct.unpack_from(NPC_HIT_FMT, msg, 0)
            self._npc_hurt(n, d / 16.0, p.slot)
        elif self.slot == 0 and kind == CLAIM_PKT and len(msg) >= struct.calcsize(CLAIM_FMT):
            _, _, what, ring, no = struct.unpack_from(CLAIM_FMT, msg, 0)
            key = (p.slot, no)
            if key not in self.seen_claims:
                self.seen_claims.append(key)
                if len(self.seen_claims) > 16:
                    self.seen_claims.pop(0)
                self._claim(p.slot, what, ring)

    def _hear_missile(self, p, msg):
        g = self.g
        _, _, n, to, x, y, z, nx, ny, nz = struct.unpack_from(MISSILE_FMT, msg, 0)
        key = (p.slot, n)
        if key in self.seen_missiles or g.missile_bp is None:
            return              # a repeat
        if to & NPC_BIT:
            if self.slot != 0:
                return          # at one of the host's ships: the host flies it
            t = self.convoy if (to & 0x7F) == 0 else self.npcs.get(to & 0x7F)
            if t is None or t.dead:
                return
        elif to != self.slot or g.over:
            return
        else:
            t = None
        self.seen_missiles.append(key)
        if len(self.seen_missiles) > 16:
            self.seen_missiles.pop(0)
        k = 1.0 / 16384
        m = [0.0] * 9
        game._look(m, *game._unit(nx * k, ny * k, nz * k))
        if t is not None:       # the host flies a guest's missile at its own ship
            mo = game.Obj(g.missile_bp, "pmissile", 0.0, 0.0, 0.0)
            g.place(mo, x * 0.25, y * 0.25, z * 0.25, m)
            mo.target = t
            mo.t = 8.0
            mo.net_id = n
            t.net_killer = p.slot
            g.objs.append(mo)
            self.npc_missiles[key] = mo
            return
        mo = game.Obj(g.missile_bp, "missile", 0.0, 0.0, 0.0)
        g.place(mo, x * 0.25, y * 0.25, z * 0.25, m)
        mo.t = 12.0
        mo.net_id = n
        g.objs.append(mo)
        self.incoming[key] = mo
        g.say("INCOMING MISSILE")
        g.sfx("incoming")

    # called by the Game (g.net) ------------------------------------------------------

    def laser_hit(self, o, damage):
        """Our laser hit another player's ship o: they take the damage."""
        d = int(damage * 16)
        struct.pack_into(HIT_FMT, self.pkt, 0, netplay.MAGIC, HIT_PKT, o.net_slot, self.slot,
                         0 if d < 0 else (65535 if d > 65535 else d))
        self.link.send(memoryview(self.pkt)[:struct.calcsize(HIT_FMT)])

    def npc_laser(self, o, damage):
        """Our laser hit one of the host's ships (kind "npc"): the host's game takes it."""
        d = int(damage * 16)
        struct.pack_into(NPC_HIT_FMT, self.pkt, 0, netplay.MAGIC, NPC_HIT_PKT, o.net_id,
                         0 if d < 0 else (65535 if d > 65535 else d))
        self.link.send(memoryview(self.pkt)[:struct.calcsize(NPC_HIT_FMT)])

    def npc_hits(self, o, damage):
        """The host's pirate hit another player's ship o (host only)."""
        d = int(damage * 16)
        struct.pack_into(HIT_FMT, self.pkt, 0, netplay.MAGIC, HIT_PKT, o.net_slot, NPC_SRC,
                         0 if d < 0 else (65535 if d > 65535 else d))
        self.link.send(memoryview(self.pkt)[:struct.calcsize(HIT_FMT)])

    def missile_fired(self, o, t):
        """We launched missile o at t (another player's ship, or one of the host's):
        their game flies it (o is a harmless copy)."""
        g = self.g
        if g is None or g.anchor is None:
            return
        self.missile_n = self.missile_n % 255 + 1
        n = o.net_id = self.missile_n
        self.ghosts[n] = o
        to = t.net_slot if t.kind == "player" else (NPC_BIT | t.net_id)
        x, y, z = g.world_point(o.x, o.y, o.z)
        m = g.world_pose()[3]
        struct.pack_into(MISSILE_FMT, self.pkt, 0, netplay.MAGIC, MISSILE_PKT, n, to,
                         int(x * 4), int(y * 4), int(z * 4),
                         netplay._s(m[6]), netplay._s(m[7]), netplay._s(m[8]))
        for _ in range(AGAIN):
            self.link.send(self.pkt)

    def prey_for(self, o):
        """The host's pirate o picks whom to go after: an Obj (the convoy, or another
        player's ship), or None for the host. Kept until it is gone (o.net_prey)."""
        t = self._prey(o.net_prey)
        if t is not False:
            return t
        g = self.g
        choice = []
        if self.convoy is not None and not self.convoy.dead and self.result == 0:
            choice += ["c", "c"]
        if g is not None and not g.over and self.team_of(0) == 0:
            choice.append(0)
        for s, p in self.roster.items():
            if p.ship is not None and not (RAIDED[self.mode] and self.team_of(s) == 1):
                choice.append(s)
        if not choice:
            o.net_prey = 0
            return None
        o.net_prey = random.choice(choice)
        t = self._prey(o.net_prey)
        return None if t is False else t

    def _prey(self, w):
        """What w (o.net_prey) means now: an Obj, None (the host), or False if it is gone."""
        if w is None:
            return False
        if w == "c":
            c = self.convoy
            return c if c is not None and not c.dead and self.result == 0 else False
        if w == 0:
            g = self.g
            return None if g is not None and not g.over else False
        p = self.roster.get(w)
        return p.ship if p is not None and p.ship is not None and not p.ship.dead else False

    def _gone(self, n, why, whose):
        struct.pack_into(GONE_FMT, self.pkt, 0, netplay.MAGIC, GONE_PKT, n, why, whose)
        for _ in range(AGAIN):
            self.link.send(memoryview(self.pkt)[:struct.calcsize(GONE_FMT)])

    def _hear_pose(self, host, msg):
        p = self.by_id.get(bytes(host)) if self.flying else None
        if p is None:
            return              # not someone in our game
        p.t = 0.0
        r = netplay.read_pose(msg, p.pose_m)
        if r is None:
            return
        seq = r[1]
        if p.last_seq is not None and not netplay.newer(seq, p.last_seq):
            return              # late: an older pose than the one we have
        p.last_seq = seq
        p.pose = (r[2], r[3], r[4], r[6])
        p.flags = r[7]
        p.pose_age = 0.0

    # ---- the host's ships, as the others see them -----------------------------------------

    def _hear_npcs(self, msg):
        g = self.g
        hs = struct.calcsize(NPCS_HEAD)
        if len(msg) < hs:
            return
        n = msg[3]
        if len(msg) < hs + n * NPC_SIZE:
            return
        k = 1.0 / 16384
        for i in range(n):
            v = struct.unpack_from(NPC_FMT, msg, hs + i * NPC_SIZE)
            ident, typ, flags, speed = v[0], v[1], v[2], v[3]
            o = self.npcs.get(ident)
            if flags & (netplay.DEAD | DOCKED):
                if o is not None:
                    del self.npcs[ident]
                    self.npc_seen.pop(ident, None)
                    if o in g.objs:
                        g.objs.remove(o)
                        if not flags & DOCKED:      # docked: just gone (STATE says so)
                            g._boom(o.x, o.y, o.z, 8 + 2 * min(o.bp.explosions, 6))
                            g.sfx("explode")
                    o.dead = True
                continue
            if o is None:
                name = game.PIRATES[typ] if typ < len(game.PIRATES) else None
                bp = g.types.get(name) if name else None
                if bp is None:
                    bp = next((b for b in g.types.values() if b.energy and b.name != "MISSILE"), None)
                if bp is None:
                    continue
                o = game.Obj(bp, "npc", 0.0, 0.0, 0.0)
                o.net_id = ident
                o.pose_m = [0.0] * 9
                o.pose = (0.0, 0.0, 0.0)
                o.pose_age = 0.0
                o.firing = 0
                o.friend = RAIDED[self.mode] and self.team_of(self.slot) == 1   # a raider's pirates
                self.npcs[ident] = o
                g.objs.append(o)
            elif o not in g.objs:
                g.objs.append(o)
            m = o.pose_m
            m[6], m[7], m[8] = v[7] * k, v[8] * k, v[9] * k
            m[3], m[4], m[5] = v[10] * k, v[11] * k, v[12] * k
            m[0] = m[4] * m[8] - m[5] * m[7]
            m[1] = m[5] * m[6] - m[3] * m[8]
            m[2] = m[3] * m[7] - m[4] * m[6]
            o.pose = (v[4] * 8.0, v[5] * 8.0, v[6] * 8.0)
            o.speed = speed
            o.pose_age = 0.0
            o.firing = flags & netplay.FIRING
            self.npc_seen[ident] = 0.0

    def _show_npcs(self, g, dt):
        for ident in list(self.npc_seen):
            t = self.npc_seen[ident] + dt
            self.npc_seen[ident] = t
            o = self.npcs.get(ident)
            if o is None:
                continue
            if t > NPC_GONE:            # heard of no more: gone without a word
                del self.npc_seen[ident]
                del self.npcs[ident]
                o.dead = True
                if o in g.objs:
                    g.objs.remove(o)
                continue
            o.pose_age += dt
            x, y, z = o.pose
            m = o.pose_m
            v = o.speed * game.SPEED_K * o.pose_age
            g.place(o, x + m[6] * v, y + m[7] * v, z + m[8] * v, m)
            if o.firing:
                self._beam_at_me(o)

    def _beam_at_me(self, s):
        d = (s.x * s.x + s.y * s.y + s.z * s.z) ** 0.5
        sm = s.m        # its nose as we see it
        if d > 1 and -(s.x * sm[6] + s.y * sm[7] + s.z * sm[8]) / d > BEAM_CONE:
            s.beam = 0.1

    def _npc_hurt(self, n, damage, slot):
        """Host: a guest's laser hit our ship n (0: the convoy)."""
        g = self.g
        o = self.convoy if n == 0 else self.npcs.get(n)
        if o is None or o.dead:
            return
        o.energy -= damage
        o.hit = 0.12
        o.net_killer = slot
        if n:
            o.net_prey = slot           # it turns on whoever shot it
            o.prey = None
            if o.state == "trade" or o.state == "patrol":
                o.state = "attack"
        if o.energy <= 0:
            o.dead = True
            g._boom(o.x, o.y, o.z, 8 + 2 * min(o.bp.explosions, 6))
            g.sfx("explode")

    def _spawn_pirates(self, g):
        """Host: a wave of pirates round the convoy, mostly ahead of it; or from all
        round the station, every other one making to dock with it."""
        alive = len(self.npcs)
        station = STATIONED[self.mode]
        if self.mode == COOP:
            n = 1 + len(self.roster) + (1 if self.mtime > CONVOY_TIME * 0.5 else 0)
        elif self.mode == SCOOP:
            n = 1 + len(self.roster)
        else:           # a raid: the pirates help the raiders, only while they are fewer
            if not self.pirates:
                return
            d, r = self._counts()
            n = max(0, 1 + d - r)
        if station and self.growing and n > 0:
            n += int(self.mtime / GROW_EVERY)   # one more a wave each minute
        n = min(n, MAX_NPCS - alive)
        cz = 0.0 if station else convoy_z(self.mtime)
        for i in range(n):
            names = [s for s in game.PIRATES if s in g.types]
            if not names:
                return
            name = game.PIRATES[random.randint(0, 255) & random.randint(0, 255) & 7]
            if name not in g.types:
                name = random.choice(names)
            bp = g.types[name]
            if station:         # from anywhere round it
                dx, dy, dz = game._unit(game._rnd(-1, 1), game._rnd(-0.5, 0.5), game._rnd(-1, 1))
            else:               # mostly ahead of the convoy
                dx, dy, dz = game._unit(game._rnd(-1, 1), game._rnd(-0.4, 0.4),
                                        game._rnd(0.2, 1.0))
            d = game._rnd(5000, 7000)
            x, y, z = dx * d, dy * d, cz + dz * d
            o = game.Obj(bp, "ship", 0.0, 0.0, 0.0)
            g.place(o, x, y, z, _pose(0, 0, 0, -dx, -dy, -dz)[3])
            o.role = "pirate"
            o.state = "attack"
            if station and i % 2 == 0:  # means to dock: attacks the station till its shield
                o.net_docker = True     # is down, then docks (_shield_step, Duel.dock_target)
                o.dest = "station"
                o.net_prey = "c"
            o.speed = bp.speed * 0.5
            o.leveled = True            # as the game does for its own (Game.step)
            o.energy *= g.energy_k
            o.max_energy = o.energy
            self.npc_n = self.npc_n % 120 + 1
            while self.npc_n in self.npcs:
                self.npc_n = self.npc_n % 120 + 1
            o.net_id = self.npc_n
            o.net_type = game.PIRATES.index(name)
            self.npcs[o.net_id] = o
            g.objs.append(o)
        if n > 0:
            g.say("PIRATES INBOUND", 2.0)

    def _send_npcs(self, g):
        """Host: our ships' poses (and those just destroyed, to explode) to the others."""
        k = 0
        hs = struct.calcsize(NPCS_HEAD)
        buf = self.npc_buf
        a = g.anchor
        for ident, o in self.npcs.items():
            if k >= NPC_SLOTS:
                break
            x, y, z = g.world_point(o.x, o.y, o.z)
            nx, ny, nz = self._world_axis(a, o.m, 6)
            rx, ry, rz = self._world_axis(a, o.m, 3)
            flags = netplay.FIRING if (o.beam > 0 or o.shot > 0) else 0
            struct.pack_into(NPC_FMT, buf, hs + k * NPC_SIZE, ident, o.net_type, flags,
                             min(255, int(o.speed)), _c16(x / 8), _c16(y / 8), _c16(z / 8),
                             netplay._s(nx), netplay._s(ny), netplay._s(nz),
                             netplay._s(rx), netplay._s(ry), netplay._s(rz))
            k += 1
        for d in self.npc_dead:
            if k >= NPC_SLOTS:
                break
            struct.pack_into(NPC_FMT, buf, hs + k * NPC_SIZE, d[0], d[1], d[3],
                             0, 0, 0, 0, 0, 0, 16384, 0, 16384, 0)
            k += 1
        if k == 0:
            return
        struct.pack_into(NPCS_HEAD, buf, 0, netplay.MAGIC, NPCS_PKT, k)
        self.link.send(memoryview(buf)[:hs + k * NPC_SIZE])

    @staticmethod
    def _world_axis(a, m, i):
        """Row i of an object's axes (m, ours) in the shared world's coordinates."""
        w = a.m
        p, q, r = m[i], m[i + 1], m[i + 2]
        return (p * w[0] + q * w[1] + r * w[2], p * w[3] + q * w[4] + r * w[5],
                p * w[6] + q * w[7] + r * w[8])

    # ---- the score, the flags and the convoy (the host decides) ----------------------

    def _name(self, slot):
        if slot == self.slot:
            return self.name
        p = self.roster.get(slot)
        return p.name if p is not None else "?"

    def _is_out(self, slot):
        return bool(self.lives) and STATIONED[self.mode] and slot in self.out

    def _killed(self, victim, by):
        """Someone (victim, a slot) was destroyed by `by`: the host scores it; all say it."""
        g = self.g
        if self.mode == DUEL:
            return              # a duel counts what it sees (flight_step)
        if self.lives and STATIONED[self.mode] and victim < MAX_PLAYERS:
            self.lives_lost[victim] += 1
            if self.lives_lost[victim] >= self.lives:
                self.out.add(victim)    # no lives left: out till the next match
        if self.slot == 0 and self.result == 0:
            scores, team, carrier = list(self.scores), list(self.team), list(self.carrier)
            if by < MAX_PLAYERS and by != victim:
                if self.mode == FFA:
                    scores[by] += 1
                elif self.mode == TEAMS and self.team_of(by) != self.team_of(victim):
                    scores[by] += 1
                    team[self.team_of(by)] += 1
            for k in (0, 1):
                if carrier[k] == victim:
                    carrier[k] = NOBODY     # its flag goes home
            self._set_state(self.match, self._winner(scores, team), self.mtime, scores, team,
                            carrier, self.hp)
        if g is not None:
            if victim == self.slot:
                return
            if by == self.slot:
                g.say("YOU DESTROYED " + self._name(victim), 2.5)
            elif by < MAX_PLAYERS:
                g.say("%s DESTROYED BY %s" % (self._name(victim), self._name(by)), 2.5)
            else:
                g.say(self._name(victim) + " DESTROYED", 2.5)

    def _winner(self, scores, team):
        if self.result:
            return self.result
        if self.mode == FFA:
            for s in range(MAX_PLAYERS):
                if scores[s] >= FFA_WIN:
                    return 10 + s
        elif self.mode == TEAMS or self.mode == CTF:
            win = TEAM_WIN if self.mode == TEAMS else CTF_WIN
            for k in (0, 1):
                if team[k] >= win:
                    return 1 + k
        return 0

    def _claim(self, slot, what, ring):
        """Host: slot flew through ring (a team's): taking that flag, or bringing one home."""
        if self.mode != CTF or self.result:
            return
        t = self.team_of(slot)
        scores, team, carrier = list(self.scores), list(self.team), list(self.carrier)
        if what == TAKE and ring != t and carrier[ring] == NOBODY and carrier[t] != slot:
            carrier[ring] = slot
        elif what == CAPTURE and ring == t and carrier[1 - t] == slot:
            carrier[1 - t] = NOBODY
            scores[slot] += 1
            team[t] += 1
        else:
            return
        self._set_state(self.match, self._winner(scores, team), self.mtime, scores, team,
                        carrier, self.hp)

    def _set_state(self, match, result, t, scores, team, carrier, hp, docked=None, shield=None):
        """The host's word (made here if we host, or heard in STATE): say what changed."""
        g = self.g
        if self.slot != 0:
            if match < self.match and self.match - match < 128:
                return          # an old STATE
            if abs(t - self.mtime) > 0.3 or match != self.match:
                self.mtime = t
        else:
            self.state_t = 0.0  # tell everyone at once
        new_match = match != self.match
        if new_match:
            self.match = match
            self.result = 0
            self.result_t = 0.0
            if self.slot != 0 and g is not None:
                self._new_match(g)
        say = None
        if not new_match:
            for k in (0, 1):
                was, now = self.carrier[k], carrier[k]
                if was == now:
                    continue
                flag = TEAM_NAMES[k] + " FLAG"
                if now != NOBODY:
                    say = "YOU HAVE THE " + flag if now == self.slot else (
                        self._name(now) + " HAS THE " + flag)
                elif team[1 - k] > self.team[1 - k]:
                    say = ("YOU" if was == self.slot else self._name(was)) + " CAPTURED THE " + flag
                else:
                    say = flag + " RETURNED"
            if hp == 0 and self.hp > 0 and self.convoy is not None:
                c = self.convoy
                if not c.dead and g is not None:
                    c.dead = True
                    if c in g.objs:
                        g.objs.remove(c)
                        g._boom(c.x, c.y, c.z, 20)
                        g.sfx("explode")
        if shield is not None and shield != self.shield_b:
            if not new_match:
                say = self._shield_say(self.shield_b, shield) or say
            self.shield_b = shield
        if docked is not None and docked != self.docked:
            if docked > self.docked and not new_match:
                say = "PIRATE DOCKED %d/%d" % (docked, DOCK_LIMIT)
            self.docked = docked
        if result and not self.result:
            self.result_t = RESULT_FOR
            say = None          # the result's own screen says it
        self.result = result
        self.scores = list(scores)
        self.team = list(team)
        self.carrier = list(carrier)
        self.hp = hp
        self.hud_cache = None
        if self.rings[0] is not None:
            for k in (0, 1):        # a ring goes grey while its flag is away
                self.rings[k].rgb = TEAM_RGB[k] if carrier[k] == NOBODY else TAKEN_RGB
        if say and g is not None:
            g.say(say, 2.5)

    def _send_state(self):
        struct.pack_into(STATE_FMT, self.state_buf, 0, netplay.MAGIC, STATE_PKT,
                         self.match & 0xFF, self.result, min(65535, int(self.mtime * 10)),
                         self.scores[0], self.scores[1], self.scores[2], self.scores[3],
                         self.team[0], self.team[1], self.carrier[0], self.carrier[1], self.hp,
                         min(255, self.docked), self.shield_b)
        self.link.send(self.state_buf)

    def _new_match(self, g):
        """A new match: score, flags and convoy afresh; everyone back to their start."""
        match = self.match
        keep = (self.death_no, self.claim_no)
        for o in list(self.npcs.values()) + self.marks + ([self.convoy] if self.convoy else []):
            o.dead = True
        g.objs[:] = [o for o in g.objs if not o.dead]
        self._match_reset()
        self.match = match
        self.death_no, self.claim_no = keep
        self._respawn(g, keep_npcs=False)
        if self.mode != DUEL:
            g.say("MATCH %d" % (match + 1), 2.0)

    # ---- flying ----------------------------------------------------------------------

    def start(self, g):
        """Into the arena: an empty one, you at your start."""
        me = self.link.id
        if not self.flying:     # the roster: slot 0 the host, then the guests in order
            self.roster = {}
            self.by_id = {}
            if self.role == JOIN and self.host_p is not None:
                self.slot = 1 + list(self.start_ids).index(me) if me in self.start_ids else 1
                self.host_p.slot = 0
                self.roster[0] = self.host_p
            else:
                self.slot = 0
            for i, gid in enumerate(self.start_ids):
                if gid == me:
                    continue
                p = self.players.get(gid)
                if p is None:
                    p = self.players[gid] = Player(gid)
                p.slot = i + 1
                self.roster[i + 1] = p
            for p in self.roster.values():
                self.by_id[p.id] = p
                p.ship = None
                p.pose = None
                p.last_seq = None
                p.lost = False
                p.flags = 0
            self.match = 0          # a new game: its first match
            self._match_reset()
            self.kills = self.deaths = 0
            self.round = 1
        self.flying = True
        self.go = False
        self.ended = None
        self.send_t = 0.0
        g.quiet = True
        g.objs[:] = []
        g.net = self
        g.rules.manual_ecm = True   # the ECM by hand in multiplayer (Brian, 2026-11-25)
        g.set_level(self.pirate_level)  # how the host's pirates fight (build 151)
        self.g = g
        self._respawn(g, keep_npcs=False)
        o = self.other
        if self.mode == DUEL:
            if o is not None and not self.deaths and not self.kills:
                g.say("VS " + o.name, 2.0)
        elif TEAMED[self.mode]:
            t = self.team_of(self.slot)
            thing = "STATION" if STATIONED[self.mode] else "CONVOY"
            what = ("DEFEND THE " if t == 0 else "RAID THE ") + thing if RAIDED[self.mode] else (
                TEAM_NAMES[t] + " TEAM")
            g.say(what, 2.5)
        else:
            g.say(MODE_NAMES[self.mode], 2.0)

    def _respawn(self, g, keep_npcs=True, launch=False):
        """You at your start (after being destroyed, or a new match); the arena's rings,
        convoy and the host's ships kept where they are in the shared world."""
        keep = []
        if keep_npcs and g.anchor is not None:
            for o in self.npcs.values():
                if not o.dead and o in g.objs and o.kind == "ship":
                    x, y, z = g.world_point(o.x, o.y, o.z)
                    a = g.anchor
                    m = list(self._world_axis(a, o.m, 0) + self._world_axis(a, o.m, 3)
                             + self._world_axis(a, o.m, 6))
                    keep.append((o, x, y, z, m))
        if g.over or g.anchor is not None:
            g.reset()
        g.msg_t = 0.0           # (not reset's WAVE 1)
        g.quiet = True
        g.objs[:] = []
        g.speed = START_SPEED
        if launch and self.convoy is not None:     # out of the station's slot (+z), facing out
            z = self.convoy.bp.front + LAUNCH_OUT + 250.0 * self._mate(self.slot)
            g.set_anchor(*_pose(0.0, 0.0, z, 0.0, 0.0, 1.0))
        else:
            g.set_anchor(*spawn_pose(self.mode, self.slot, self.mtime, self.team_of(self.slot),
                                     self._mate(self.slot)))
        self.loadout(g)
        self.ghosts = {}
        self.incoming = {}
        self.dead_here = False
        self.wants_launch = False
        self.respawn_t = 0.0
        self.last_by = NOBODY
        self.last_by_t = 99.0
        self.ring_rel = None
        for p in self.roster.values():
            self._remove_ship(p)
        for o, x, y, z, m in keep:
            g.place(o, x, y, z, m)
            g.objs.append(o)
        for ident in list(self.npcs):
            if self.slot != 0:          # the others' copies come back with the next poses
                o = self.npcs[ident]
                g.objs.append(o)
        self._make_marks(g)

    def _make_marks(self, g):
        """The rings (Capture Flag), the convoy and its station: placed in the shared world."""
        self.marks = []
        self.rings = [None, None]
        if self.mode == CTF:
            bp = ring_blueprint()
            for k in (0, 1):
                o = game.Obj(bp, "mark", 0.0, 0.0, 0.0)
                o.rgb = TEAM_RGB[k]
                o.label = TEAM_NAMES[k] + " FLAG"
                o.world = (0.0, 0.0, RING_Z if k else -RING_Z)
                self.rings[k] = o
                self.marks.append(o)
        if GUARDED[self.mode] and not STATIONED[self.mode]:
            st = g.types.get("CORIOLIS") or g.types.get("DODO")
            if st is not None:
                o = game.Obj(st, "mark", 0.0, 0.0, 0.0)
                o.world = (0.0, 0.0, convoy_z(CONVOY_TIME) + 1500.0)
                o.label = "STATION"
                self.marks.append(o)
        if GUARDED[self.mode]:
            c = self.convoy
            if c is None:
                bp = station_blueprint(self.station_i) if STATIONED[self.mode] else convoy_blueprint()
                if self.slot == 0:
                    c = game.Obj(bp, "convoy", 0.0, 0.0, 0.0)
                    c.energy = c.max_energy = self.convoy_energy()
                    if STATIONED[self.mode]:    # its shield, as much tougher in a raid
                        self.shield = self.shield_max = STATION_SHIELD * c.max_energy / STATION_ENERGY
                        self.last_energy = c.energy
                else:
                    c = game.Obj(bp, "npc", 0.0, 0.0, 0.0)
                    c.net_id = 0
                c.role = "trader"
                c.state = "trade"
                c.rgb = CONVOY_RGB
                c.label = "STATION" if STATIONED[self.mode] else "CONVOY"
                c.friend = not (RAIDED[self.mode] and self.team_of(self.slot) == 1)
                self.convoy = c
            if not c.dead and self.hp > 0:
                g.objs.append(c)
        for o in self.marks:
            g.objs.append(o)
        self._place_marks(g)

    def _place_marks(self, g):
        for o in self.marks:
            x, y, z = o.world
            g.place(o, x, y, z, _IDENT)
        if self.rings[0] is not None:
            for k in (0, 1):
                self.rings[k].rgb = TEAM_RGB[k] if self.carrier[k] == NOBODY else TAKEN_RGB

    def loadout(self, g):
        """Every life starts the same for everyone (Brian): shields and energy full, an
        ECM, a full missile rack, the lasers cool, nothing armed or locked."""
        g.ecm = True
        g.missiles = g.max_missiles if g.missile_bp else 0
        g.shield = 100.0
        g.hull = 100.0
        g.heat = 0.0
        g.hot = False
        g.armed = False
        g.lock = None
        g.locked = False
        g.bombs = 0             # no energy bomb: B is the ECM

    def respawn_time(self):
        """How long we wait to come back: RESPAWN, but in a raid the defenders sooner and
        the raiders longer for each one they have more (so the defenders aren't overwhelmed)."""
        if self.launches():
            return STATION_PENALTY      # the time penalty, then the launch tunnel
        if not RAIDED[self.mode]:
            return RESPAWN
        if self.team_of(self.slot) == 0:
            return DEFEND_RESPAWN
        d, r = self._counts()
        return RESPAWN + RAID_EXTRA_RESPAWN * max(0, r - d)

    def convoy_energy(self):
        """The convoy's energy: CONVOY_ENERGY, and in a raid a defender's worth more (the
        same again) for each raider more than there are defenders."""
        base = STATION_ENERGY if STATIONED[self.mode] else CONVOY_ENERGY
        if not RAIDED[self.mode]:
            return base
        d, r = self._counts()
        return base * (1 + max(0, r - d) / max(1, d))

    def again_by_c(self):
        """True if C on the end screen starts again (a duel's next round); otherwise
        a destroyed ship comes back by itself (RESPAWN)."""
        return self.mode == DUEL

    def showing(self, g):
        """True while the end screen (over_lines) is up: destroyed, or a match result."""
        return g.over or (self.result != 0 and self.result_t > 0)

    def over_lines(self):
        """The end screen: (text, size, rgb) lines."""
        from . import cockpit as ck
        g = self.g
        if self.result and self.result_t > 0:
            return self._result_lines(ck)
        if self.mode == DUEL:
            o = self.other
            return (("DESTROYED", 24, ck.RED),
                    ("BY " + (o.name if o is not None else "?"), 13,
                     ck.ship_rgb(o.colour) if o is not None else ck.WHITE),
                    ("%d - %d" % (self.kills, self.deaths), 14, ck.WHITE),
                    ("C: next round", 12, ck.GREY), ("F: leave duel", 12, ck.GREY))
        by = self.last_by if self.last_by_t < 10 else NOBODY
        who = ("BY " + self._name(by)) if by < MAX_PLAYERS else ("BY PIRATES" if by == NPC_SRC else "")
        left = self.lives_left()
        if self._is_out(self.slot):
            when = ("OUT: NO LIVES LEFT", 14, ck.YELLOW)
        elif self.launches():
            when = ("LAUNCH IN %d" % (int(self.respawn_t) + 1), 14, ck.WHITE)
        else:
            when = ("BACK IN %d" % (int(self.respawn_t) + 1), 14, ck.WHITE)
        last = ("F: leave game", 12, ck.GREY) if left is None or left == 0 else (
            ("%d %s LEFT   F: leave" % (left, "LIFE" if left == 1 else "LIVES")), 12, ck.GREY)
        return (("DESTROYED", 24, ck.RED), (who, 13, self._rgb(by) if by < MAX_PLAYERS else ck.WHITE),
                when, last)

    def _result_lines(self, ck):
        r = self.result
        nxt = ("NEXT MATCH IN %d" % (int(self.result_t) + 1), 12, ck.GREY)
        if self.mode == FFA:
            s = r - 10
            return (("YOU WIN" if s == self.slot else self._name(s) + " WINS", 20, self._rgb(s)),
                    ("YOUR KILLS %d" % self.scores[self.slot], 13, ck.WHITE), nxt,
                    ("F: leave game", 12, ck.GREY))
        k = r - 1
        if GUARDED[self.mode]:
            if STATIONED[self.mode]:
                head = "STATION HELD" if k == 0 else "STATION LOST"
                why = ("PIRATES DOCKED %d" % self.docked) if self.docked > DOCK_LIMIT else (
                    "DEFENDERS ALL OUT" if k == 1 and self._side_out(0) else (
                        "RAIDERS ALL OUT" if k == 0 and self._side_out(1) else
                        "PIRATES DESTROYED %d" % sum(self.scores)))
            else:
                head = "CONVOY ARRIVED" if k == 0 else "CONVOY LOST"
                why = "PIRATES DESTROYED %d" % sum(self.scores)
            mine = self.team_of(self.slot) == k
            return ((head, 18, CONVOY_RGB), ("YOU WIN" if mine else "YOU LOSE", 16,
                                             ck.GREEN if mine else ck.RED),
                    (why, 12, ck.WHITE), nxt)
        return ((TEAM_NAMES[k] + " TEAM WINS", 18, TEAM_RGB[k]),
                ("%d - %d" % (self.team[0], self.team[1]), 16, ck.WHITE), nxt,
                ("F: leave game", 12, ck.GREY))

    def _rgb(self, slot):
        """How a slot's ship is drawn: its team's colour, or its owner's paint."""
        if TEAMED[self.mode]:
            return self.team_rgb(self.team_of(slot))
        if slot == self.slot:
            return colour_rgb(self.colour)
        p = self.roster.get(slot)
        return colour_rgb(p.colour if p is not None else 0)

    def hud(self):
        """The line along the top in flight: [(text, x, rgb)] (with a fourth, how far below
        the first line, for a second), or () (a duel). Made again only when something
        changes, or each second for the clock."""
        if self.mode == DUEL:
            return ()
        c = self.hud_cache
        if c is not None and self.hud_t > 0:
            return c
        self.hud_t = 1.0
        from . import cockpit as ck
        m = self.mode
        if m == FFA:
            best = max(self.scores)
            c = (("KILLS %d  BEST %d/%d" % (self.scores[self.slot], best, FFA_WIN), 0, ck.WHITE),)
        elif m == TEAMS or m == CTF:
            c = (("%s %d" % (TEAM_NAMES[0], self.team[0]), -30, TEAM_RGB[0]),
                 ("%s %d" % (TEAM_NAMES[1], self.team[1]), 30, TEAM_RGB[1]))
        elif STATIONED[m]:
            left = max(0, int(self.guard_time() - self.mtime))
            c = (("STATION %d%%  %d:%02d" % (self.hp * 100 // 255, left // 60, left % 60), 0, CONVOY_RGB),
                 ("SHIELD %d%%  DOCKED %d/%d" % (self.shield_b * 100 // 255, self.docked, DOCK_LIMIT), 0,
                  ck.RED if self.docked >= DOCK_LIMIT or self.shield_b == 0 else ck.WHITE, 13))
        else:
            left = max(0, int(CONVOY_TIME - self.mtime))
            c = (("CONVOY %d%%  %d:%02d" % (self.hp * 100 // 255, left // 60, left % 60), 0,
                  CONVOY_RGB),)
        self.hud_cache = c
        return c

    def compass(self):
        """What the compass points at: an Obj in our game, and its colour; or None."""
        if self.mode == CTF and self.rings[0] is not None:
            t = self.team_of(self.slot)
            k = t if self.carrier[1 - t] == self.slot else 1 - t   # carrying: home
            return self.rings[k], TEAM_RGB[k]
        if GUARDED[self.mode] and self.convoy is not None and not self.convoy.dead:
            return self.convoy, CONVOY_RGB
        return None

    def stop(self, g):
        """Out of the arena (to the title, or the game ended): practice's game again; back
        to the lobby. Leaving, say so (END), so the others know at once."""
        if self.flying and self.roster and self.ended is None:
            for _ in range(END_TIMES):
                self._say(FLYING, END_PKT)
        if self.ended is not None:
            self.notice = self.ended
            self.notice_t = NOTICE_FOR
        self.ended = None
        if g is not None:
            g.quiet = False
            g.anchor = None
            g.net = None
            g.rules.manual_ecm = g.rules.hardcore   # practice's own again
            g.objs[:] = [o for o in g.objs if o.kind not in _NET_KINDS
                         and getattr(o, "net_id", 0) == 0]
        for p in self.roster.values():
            p.ship = None
        self.g = None
        self.kills = self.deaths = 0
        self.round = 1
        self.flying = False
        self.start_t = 0.0
        self.roster = {}
        self.by_id = {}
        self._match_reset()
        self.leave()

    def flight_step(self, g, dt):
        """Each flight frame, after Game.step (paused too, so the link stays up)."""
        if g.anchor is None:            # the game was reset: C after being destroyed (a duel)
            o = self.other
            if self.mode == DUEL and self.dead_here and o is not None:  # the next round, for both
                self.round += 1
                struct.pack_into(NEXT_FMT, self.pkt, 0, netplay.MAGIC, NEXT_PKT, 0, self.round)
                for _ in range(AGAIN):
                    self.link.send(memoryview(self.pkt)[:struct.calcsize(NEXT_FMT)])
                self.start(g)
                g.say("ROUND %d" % self.round, 2.0)
            else:
                self.start(g)
        self._age(dt)
        self._hear()
        if self.ended is not None or g.anchor is None:
            return
        host = self.slot == 0
        self.mtime += dt
        self.last_by_t += dt
        self.hud_t -= dt
        if self.start_t > 0:            # host: START again, in case a guest missed it
            self.start_t -= dt
            self.start_gap -= dt
            if self.start_gap <= 0:
                self.start_gap = START_EVERY
                self._send_start()
        self.hello_t -= dt
        if self.hello_t <= 0:           # now and then, so the lobby knows we are busy
            self.hello_t = FLY_HELLO_EVERY
            self._say(FLYING)
        # send our pose SEND_HZ times a second
        self.send_t -= dt
        if self.send_t <= 0:
            self.send_t += 1.0 / SEND_HZ
            if self.send_t < 0:
                self.send_t = 0.0
            self.seq = (self.seq + 1) & 0xFFFF
            flags = (netplay.DEAD if g.over else 0) | (netplay.FIRING if g.beam > 0 else 0)
            netplay.pack_pose(self.buf, self.slot, self.seq, g.world_pose(), g.speed, flags)
            self.link.send(self.buf)
        for key in list(self.incoming):     # their missiles here: hit us, or our ECM got them
            mo = self.incoming[key]
            if mo.dead:
                del self.incoming[key]
                if not mo.ecmed:
                    self.last_by = key[0]
                    self.last_by_t = 0.0
                self._gone(key[1], GONE_ECM if mo.ecmed else GONE_HIT, key[0])
        for n in list(self.ghosts):     # our copies that reached them, or ran out
            if self.ghosts[n].dead:
                del self.ghosts[n]
        if g.over and not self.dead_here:
            self.dead_here = True
            self.deaths += 1
            if self.mode != DUEL:
                self.respawn_t = self.respawn_time()
                by = self.last_by if self.last_by_t < 10 else NOBODY
                self.death_no = (self.death_no + 1) & 0xFFFF
                struct.pack_into(KILLED_FMT, self.pkt, 0, netplay.MAGIC, KILLED_PKT, by, self.death_no)
                for _ in range(AGAIN):
                    self.link.send(memoryview(self.pkt)[:struct.calcsize(KILLED_FMT)])
                self._killed(self.slot, by)
        elif not g.over:
            self.dead_here = False
        if g.over and self.mode != DUEL and not self._is_out(self.slot) and not self.wants_launch:
            self.respawn_t -= dt
            if self.respawn_t <= 0:
                if self.launches():
                    self.wants_launch = True    # ace: the launch tunnel, then launched()
                else:
                    self._respawn(g)
                    return
        if self.result and self.result_t > 0:
            self.result_t -= dt
            if self.result_t <= 0 and host:     # the next match
                self.match = (self.match + 1) & 0xFF
                self._new_match(g)
                self.state_t = 0.0
        if host:
            self._host_step(g, dt)
        else:
            self._show_npcs(g, dt)
        self._mode_step(g, dt)
        for p in list(self.roster.values()):
            self._show_player(g, p, dt)

    def _host_step(self, g, dt):
        m = self.mode
        if GUARDED[m]:
            c = self.convoy
            if self.result == 0:
                if c is not None and c.dead:
                    self._set_state(self.match, 2, self.mtime, self.scores, self.team,
                                    self.carrier, 0)
                elif self._side_out(0):         # fixed lives, every defender out: lost
                    self._set_state(self.match, 2, self.mtime, self.scores, self.team,
                                    self.carrier, self.hp)
                elif RAIDED[m] and self._side_out(1):   # every raider out: held
                    self._set_state(self.match, 1, self.mtime, self.scores, self.team,
                                    self.carrier, self.hp)
                elif self.docked > DOCK_LIMIT:      # too many got in: the station is lost
                    self._set_state(self.match, 2, self.mtime, self.scores, self.team,
                                    self.carrier, self.hp)
                elif self.mtime >= self.guard_time():
                    self._set_state(self.match, 1, self.mtime, self.scores, self.team,
                                    self.carrier, self.hp)
                elif c is not None:
                    if STATIONED[m]:
                        self._shield_step(g, c, dt)
                    hp = max(1, int(c.energy * 255 / c.max_energy)) if c.energy > 0 else 0
                    if hp != self.hp:
                        self.hp = hp
                        self.hud_cache = None
                self.wave_t -= dt
                if self.wave_t <= 0:
                    self.wave_t = WAVE_EVERY
                    self._spawn_pirates(g)
            scores = None
            for ident in list(self.npcs):   # ours destroyed: send them (to explode), score them
                o = self.npcs[ident]
                if o.dead or o not in g.objs:
                    del self.npcs[ident]
                    if not o.dead:
                        continue
                    if o.docked:        # got into the station: gone, no score
                        self.npc_dead.append([ident, o.net_type, DEAD_FOR, DOCKED])
                        self.docked += 1
                        self.hud_cache = None
                        self.state_t = 0.0
                        g.say("PIRATE DOCKED %d/%d" % (self.docked, DOCK_LIMIT), 2.0)
                        continue
                    self.npc_dead.append([ident, o.net_type, DEAD_FOR, netplay.DEAD])
                    if scores is None:
                        scores = list(self.scores)
                    s = getattr(o, "net_killer", 0)
                    if s < MAX_PLAYERS:
                        scores[s] += 1
            if scores is not None:
                self._set_state(self.match, self.result, self.mtime, scores, self.team,
                                self.carrier, self.hp)
            for d in self.npc_dead:
                d[2] -= dt
            self.npc_dead = [d for d in self.npc_dead if d[2] > 0]
            for key in list(self.npc_missiles):
                mo = self.npc_missiles[key]
                if mo.dead:
                    del self.npc_missiles[key]
                    self._gone(key[1], GONE_HIT, key[0])
            self.npc_t -= dt
            if self.npc_t <= 0:
                self.npc_t = NPC_EVERY
                self._send_npcs(g)
        self.state_t -= dt
        if self.state_t <= 0:
            self.state_t = STATE_EVERY
            self._send_state()

    def _mode_step(self, g, dt):
        """The rings (and passing through them) and the convoy, each frame."""
        self.mark_t -= dt
        if self.mark_t <= 0:            # the world's turning drifts them a little: put back
            self.mark_t = 0.5
            self._place_marks(g)
        c = self.convoy
        if c is not None and not c.dead:
            g.place(c, 0.0, 0.0, 0.0 if STATIONED[self.mode] else convoy_z(self.mtime), _IDENT)
            if c not in g.objs and self.hp > 0:
                g.objs.append(c)
        if self.mode != CTF or g.over or self.result:
            return
        x, y, z = g.world_pose()[:3]
        rel = (z + RING_Z, z - RING_Z)  # through each ring's plane (team 0's at -RING_Z)
        was = self.ring_rel
        self.ring_rel = rel
        if was is None or x * x + y * y >= RING_PASS * RING_PASS:
            return
        t = self.team_of(self.slot)
        for k in (0, 1):
            if (was[k] < 0) != (rel[k] < 0):
                if k != t and self.carrier[k] == NOBODY:
                    self._send_claim(TAKE, k)
                elif k == t and self.carrier[1 - t] == self.slot:
                    self._send_claim(CAPTURE, k)

    def _send_claim(self, what, ring):
        if self.slot == 0:
            self._claim(0, what, ring)
            return
        self.claim_no = (self.claim_no + 1) & 0xFFFF
        struct.pack_into(CLAIM_FMT, self.pkt, 0, netplay.MAGIC, CLAIM_PKT, what, ring, self.claim_no)
        for _ in range(AGAIN):
            self.link.send(memoryview(self.pkt)[:struct.calcsize(CLAIM_FMT)])

    def _show_player(self, g, p, dt):
        """Another player's ship, where their last pose and speed put it now."""
        p.pose_age += dt
        if p.t >= GONE_END:
            self._drop(p, "LOST")       # not heard for a long while: gone without a word
            return
        duel = self.mode == DUEL
        if p.pose is None or p.t >= LOST:
            if p.ship is not None:
                self._remove_ship(p)
                if p.pose is not None and not p.lost:
                    p.lost = True
                    g.say("LINK LOST" if duel else p.name + " LINK LOST", 2.0)
            return
        if p.lost:
            p.lost = False
            g.say("LINK BACK" if duel else p.name + " LINK BACK", 1.5)
        if p.flags & netplay.DEAD:      # they are destroyed: an explosion, once
            s = p.ship
            if s is not None:
                self._remove_ship(p)
                g._boom(s.x, s.y, s.z, 8 + 2 * min(s.bp.explosions, 6))
                g.sfx("explode")
                if duel:
                    self.kills += 1
                    g.say("%s DESTROYED  %d-%d" % (p.name, self.kills, self.deaths), 3.0)
            return
        s = p.ship
        if s is None:
            bp = g.types.get(g.ship_name)     # practice flies a Cobra Mk III: so do they
            if bp is None:
                bp = next(b for b in g.types.values() if b.energy and b.name != "MISSILE")
            s = p.ship = game.Obj(bp, "player", 0.0, 0.0, 0.0)
            s.net_slot = p.slot
            s.rgb = self._rgb(p.slot)
            s.friend = (TEAMED[self.mode] and self.team_of(p.slot) == self.team_of(self.slot)) \
                or COOPED[self.mode]
        if s not in g.objs:
            g.objs.append(s)
        carrying = self.mode == CTF and p.slot in self.carrier
        s.label = p.name + " *FLAG*" if carrying else p.name
        x, y, z, speed = p.pose
        m = p.pose_m
        # where it is now: its last pose, moved on along its nose at its speed
        v = speed * game.SPEED_K * p.pose_age
        g.place(s, x + m[6] * v, y + m[7] * v, z + m[8] * v, m)
        s.speed = speed
        if p.flags & netplay.FIRING:    # their laser: drawn at you if they are aiming at you
            self._beam_at_me(s)


_IDENT = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
_NET_KINDS = ("player", "npc", "convoy", "mark")


def _c16(v):
    v = int(v)
    return 32767 if v > 32767 else (-32768 if v < -32768 else v)
