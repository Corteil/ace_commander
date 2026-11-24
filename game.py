"""Ace Commander flight game logic. No badge imports, so it runs and tests on a PC.

The player sits at the origin looking along +z (x right, y up). As in the
original game the player never moves: steering rotates everything else, and
flying forward slides everything towards the player.

Each object has a position and three direction vectors (side, roof, nose)
held in a flat list m, so a ship vertex (vx, vy, vz) is at
    position + vx * side + vy * roof + vz * nose
"""
import math
import random

try:
    from .rules import GameRules
    from . import ships
except ImportError:        # run by a test as a top-level module
    from rules import GameRules
    import ships

SPEED_K = 25.0         # world units per second for one Elite speed unit
PLAYER_MAX = 40.0      # top speed, in Elite speed units, of the Cobra Mk III (others: Game.set_ship)
THROTTLE_RATE = 25.0   # speed units gained per second at full throttle
PITCH_RATE = 1.0       # radians per second at full stick
ROLL_RATE = 1.7
YAW_RATE = 0.6         # radians per second at full yaw (a host's pad only: the badge has no yaw)

# Weapon ranges as Elite's (Brian, build 78): your lasers hit any ship in
# your sights however far off (Elite's HITCH has no distance check: anything
# in the local bubble, which is DESPAWN here), as missile locks do; an enemy
# fires its laser only when you are within ENEMY_REACH of it along each of
# x, y and z (TA3: no high byte of x, y or z may reach 32, so 32 * 256), and
# launches missiles at any distance.
LASER_RANGE = 14000.0          # = DESPAWN, below
ENEMY_REACH = 8192.0
LASER_COOL = 0.16      # heat lost per second
# the front laser, by type: (seconds between hits, damage a hit, heat a hit
# (1.0 = overheated)). Damage is Elite's laser power: pulse and beam 15,
# military 23, mining 50. The pulse and mining lasers fire separate shots;
# the beam and military lasers (CONTINUOUS) are a steady beam while you hold
# fire, hitting what is in the sights every 0.09 s, until they overheat. The
# mining laser breaks rocks into splinters you can scoop (see Game._kill).
LASERS = {
    "pulse": (0.18, 15.0, 0.05),
    "beam": (0.09, 15.0, 0.04),
    "military": (0.09, 23.0, 0.045),
    "mining": (0.18, 50.0, 0.05),
}
CONTINUOUS = ("beam", "military")
ENERGY_UNIT = 2.0      # an energy unit makes the shields and hull recharge this much faster
NAVY_UNIT = 3.0        # and the naval one, mission 2's reward, this much (the original's 3 against 2)
# The rest of the equipment (phase 4). The ECM fires by itself when an enemy
# missile comes within ECM_RANGE, destroys every enemy missile about, and
# costs ECM_COST of the shields. The energy bomb, once, destroys every ship,
# missile and rock within BOMB_RANGE. The escape pod saves you (see
# Game.ejected). The docking computer flies you in from the safe zone (see
# Game._autopilot).
ECM_RANGE = 2500.0
ECM_COST = 10.0
BOMB_RANGE = 10000.0
MINERALS = 12           # the good a splinter holds (market.py's list: food is 0)
AUTO_FAST = 8000.0      # the docking computer uses the jump drive's speed this far from where it is heading
AUTO_LINE = 2500.0      # it lines up this far out in front of the slot
AUTO_NEAR = 400.0       # this close to a point on its way counts as there
AUTO_LEVEL = 1000.0     # and this close to the slot it rolls to match it
AUTO_LEAD = 0.5         # on the run in it aims at the axis this far out from the middle to you
AUTO_SPIN = 1.0         # roll matching follows the station's spin (0: not, as before build 95)
AIM_ASSIST = 0.05      # a shot hits anything within this slope of the crosshair

MISSILE_DAMAGE = 150.0
JUMP_COUNT = 5.0           # seconds of countdown before a hyperspace jump
WARP_TIME = 1.2            # seconds the streaks last on arriving
LOCK_TIME = 2.0            # seconds a ship must stay in the sights before a missile locks
ENERGY_LOW = 20.0          # energy banks (hull) below this: ENERGY LOW, as Elite's under 50 of 255
LOW_EVERY = 2.0            # seconds between ENERGY LOW warnings (Elite: every 32 main loops)
AUTO_LOCK_TIMES = (2.0, 3.0, 4.0)  # the lock with auto_missile, by level: EASY, NORMAL, HARD
                       # (no missile button; Brian, builds 112 and 114)
MISSILE_SPEED = 1100.0     # world units per second
PMISSILE_SPEED = 1700.0
TURN_RATE = 1.1            # how fast enemy ships can turn, radians per second
BREAK_DIST = 900.0         # enemies peel away when this close
DESPAWN = 14000.0
RADAR_RANGE = 10000.0
MAX_OBJECTS = 14

# A commander's flight is in a star system: a planet, a sun and a space station
# (see Space). Distances are in world units; the player's top speed is 1000 a
# second.
PLANET_SCALE = 4.0         # world units per km of the planet's radius (galaxy.System.radius)
STATION_ORBIT = 3.0        # the station's distance from the planet's centre, in planet radii
SUN_DIST = 16.0            # the sun's distance from the planet, in planet radii
SUN_SIZE = 1.0             # the sun's radius, in planet radii: the same, as in Elite
ARRIVE_DIST = 120000.0     # a jump arrives this far from the station: two minutes at full speed
LAUNCH_DIST = 700.0        # a launch leaves you this far out of the station's slot
SAFE_K = 2.0               # the safe zone round the station: this many planet radii, as in Elite
DOCK_DIST = 500.0          # docking C (automatic): this close to the station's centre and you are docked
# Docking A (authentic) and B (assisted): touching the station docks you only
# through the slot; anything else is a crash that hurts and bounces you off.
# Angles are given as their cosines.
PLAYER_R = 40.0            # your ship's size: you touch the station this far from its front face
AUTO_IN = 70.0             # the docking computer docks with your ship this far inside the slot
                           # (build 102: 40 before, so it is seen going in; 100 was too near
                           # a Dodo's middle, where it wobbled round and missed)
AUTO_SLOW = 300.0          # and this close to the slot's face it slows to AUTO_CRAWL of
AUTO_CRAWL = 0.25          # DOCK_SPEED, so the view from behind shows it going in (build 102)
DOCK_SPEED = 20.0          # faster than this (Elite speed units, top speed 40) and it's a crash
SLOT_CONE_A = 0.927        # A: you must be in front of the slot, within 22 degrees of its axis
HEAD_A = 0.9               # A: and flying into it, within 26 degrees
LEVEL_A = 0.866            # A: with the slot level on the screen, within 30 degrees (either way up)
SLOT_CONE_B = 0.82         # B: within 35 degrees of the slot's axis
HEAD_B = 0.7               # B: flying towards it within 45 degrees; the roll doesn't matter
CAPTURE_DIST = 1500.0      # B: this close, in the cone, heading in and slow enough, the station takes you
PULL = 250.0               # B: how fast the station's tractor beam draws you in, world units a second
PULL_TURN = 0.8            # B: how fast it turns its slot to face you, radians a second
STATION_HIT = 15.0         # a crash does this much damage, plus 1.5 for each unit of speed
BOUNCE = 300.0             # and leaves you this much further out than where you touched
STATION_SPIN = 0.25        # radians per second, about the station's nose
VIEW_NAMES = ("FRONT", "REAR", "LEFT", "RIGHT")     # the four space views (Elite's VIEW 0-3)
DUST_MID = 800          # the stardust field's middle, for the views to the side and back (see Game.view_dust)

MASS_LOCK_K = 2.0          # the jump drive drops out within this many radii of the planet's or sun's centre
JUMP_K = 8                 # the jump drive moves you this many times faster
# Who turns up in a star system, as in the original (read from the main game
# loop, parts 3 and 4): every ENCOUNTER_EVERY seconds outside the safe zone,
# once the last ships have gone, a roll. In an anarchy it always succeeds;
# elsewhere with chance PIRATE_ROLL, and then only if a number 0 to 7 is at
# least the government, so safer systems see fewer. Then either a lone bounty
# hunter or a pack of 1 to 4 pirates (no more than the level allows at once),
# small ships more likely; and the next rolls are skipped, one per extra ship.
ENCOUNTER_EVERY = 20.0
PIRATE_ROLL = 120 / 256.0
HUNTER_CHANCE = 100 / 256.0
PIRATES = ("SIDEWINDER", "MAMBA", "KRAIT", "ADDER", "GECKO", "COBRA MK I", "WORM",
           "COBRA MK III P")
HUNTERS = ("COBRA MK III P", "ASP MK II", "PYTHON P", "FER DE LANCE")
PACK_MOST = 4
AMBUSH_GOV = 2             # arriving from hyperspace in an anarchy or feudal system: an ambush
DODO_TECH = 10             # systems with this tech level or more have a Dodo station
# Near the sun the cabin heats up, and with fuel scoops you can skim fuel from
# it, as in the original (main flight loop, part 15): the cabin temperature is
# 285 - SUN_HEAT * (distance / sun radius)^2, never below COOL_CABIN (deep
# space), so it starts to rise within about 2.7 sun radii. At SCOOP_TEMP or
# more (within about 1.3 radii) the scoops take in speed / 8 tenths of a light
# year every SUN_CHECK seconds. Flying into the sun is the end, as before.
COOL_CABIN = 30
SUN_HEAT = 36.0
FATAL_CABIN = 255           # as Elite (main flight loop part 15): past this the heat kills you,
                            # about 0.91 sun radii from its centre; the sun has no surface to hit
SCOOP_TEMP = 224
SCOOP_ALT = 2000.0          # and no higher than this above the sun's surface (world units),
                            # whatever the cabin's heat: a fixed skimming height (Brian, build 143)
SUN_CHECK = 1.0

# Phase 5: traders, police and legal status, as the original (BBC Micro disc
# version) does them. Legal status is the original's FIST, 0 to 255: 0 clean,
# 1 to 49 an offender, FUGITIVE or more a fugitive. It changes only like this:
#   - launching ORs in the contraband in your hold, (slaves + narcotics) x 2 +
#     firearms (BAD, ILLEGAL)
#   - destroying a police ship ORs in 64 (KILL_COP): a fugitive at once
#   - each hyperspace jump halves it (SOLAR); the escape pod and the galactic
#     hyperdrive clear it
# Firing on a trader (an innocent bystander) or on the station makes the
# station hostile (ANGRY / AN2), not your record worse. A hostile station
# refuses docking: at DEATH_SPEED or more that is the end, slower a small dent
# (SLOW_CRASH, MA67); it launches police after you (STATION_COPS at most, with
# chance STATION_COP_CHANCE a second) and stays hostile until you leave.
FUGITIVE = 50
HUNT_LEGAL = 40         # bounty hunters (and the police, who are hunters too) attack at this or more
# A stolen ship (ships.py, build 84): in a law-abiding system (LAWFUL_GOV and
# up: confederacy, democracy, corporate state) a police Viper that comes
# within SPOT_DIST of you checks it once, and knows it for stolen with chance
# SPOT_CHANCE: then it attacks, as for a fugitive.
LAWFUL_GOV = 5
SPOT_DIST = 6000.0
SPOT_CHANCE = 0.5
KILL_COP = 64
ILLEGAL = {3: 2, 6: 2, 10: 1}   # good number (market.py's list): weight a tonne
DEATH_SPEED = 5         # Elite speed units: a refused docking this fast kills you
SLOW_CRASH = 5.0
STATION_COPS = 4
STATION_COP_CHANCE = 0.1
# Every ENCOUNTER_EVERY seconds (the original's once every 256 main loops),
# outside the safe zone: with chance 35/256 something harmless, half the time
# a trader (TRADERS, half of them making for the station to dock, half for the
# planet); otherwise a police Viper with chance (2 x BAD, ORed with your legal
# status if police are already about) / 256, and then, if there are no police
# about, the roll for pirates or a bounty hunter (ENCOUNTER_EVERY above).
# Nothing turns up inside the safe zone, but a station that isn't hostile
# launches a Shuttle or Transporter now and then (SHUTTLE_CHANCE a second, one
# at a time), and a pirate that follows you in loses its aggression (TN3).
TRADERS = ("COBRA MK III", "PYTHON", "BOA", "ANACONDA", "MORAY")
SHUTTLES = ("SHUTTLE", "TRANSPORTER")
BENIGN = 35 / 256.0
SHUTTLE_CHANCE = 0.018
POLICE = "VIPER"
# Pirates go for a trader rather than you when one is nearer them than you are
# (PREY_RANGE at most); a trader they destroy spills its cargo and counts for
# nobody. (Not in the original, where pirates only ever go for you.)
PREY_RANGE = 6000.0
# Keeping out of your way (not in the original, Brian asked): a friendly station
# launches no shuttles while the docking computer flies or you are within
# SLOT_CLEAR in front of its slot (inside SLOT_CLEAR_CONE of its axis), and a
# ship that isn't attacking you turns aside when it is in your path or comes
# within AVOID_DIST heading your way.
SLOT_CLEAR = 6000.0
SLOT_CLEAR_CONE = 0.7
AVOID_DIST = 1200.0
AVOID_AHEAD = 3000.0    # and one in your path this far ahead (within AVOID_SIDE of it) gets out of it
AVOID_SIDE = 300.0

# Witchspace and Thargoids, as the original (MJP, GTHG, TACTICS): one jump in
# MISJUMP_ODDS goes wrong and drops you in witchspace, short of your target,
# with no planet, sun or station and hardly any stardust, among THARGOIDS
# Thargoids, each with a Thargon. Nothing else turns up there. A Thargoid
# launches a Thargon in place of a missile, only once below half its energy;
# a Thargon with no Thargoid left drifts aimlessly at half speed. Any Thargon
# can be scooped (from below, with fuel scoops) as alien items. The escape pod
# can't save you in witchspace. You leave by hyperspace, from where you are.
MISJUMP_ODDS = 3 / 256.0
THARGOIDS = 4
ALIEN_ITEMS = 16        # the good a scooped Thargon becomes (market.py's list)
# Escape pods (build 86), as the original's TACTICS part 4: a ship that carries
# one (POD_SHIPS: bit 7 of its NEWB flags in E%), down to its last eighth of
# energy, bails out with chance POD_CHANCE each time it thinks. The pod flies
# off; the ship is left adrift with no one aboard. A pod is scooped like a
# canister (fuel scoops, from below) and holds one tonne of slaves.
POD_SHIPS = ("ADDER", "ANACONDA", "ASP MK II", "BOA", "COBRA MK I", "COBRA MK III",
             "COBRA MK III P", "FER DE LANCE", "KRAIT", "MAMBA", "PYTHON", "PYTHON P", "VIPER")
POD_CHANCE = 0.1
SLAVES = 3              # what a scooped escape pod holds (market.py's list)
DUST_X = 500            # stardust spreads this far either side (500 fills the 240 wide view;
                        # each Game's dust_x, which the layout sets for a wider view: build 107)
WITCH_DUST = 3          # stardust in witchspace (10 elsewhere)

# The missions (missions.py; the app sets the flags from the commander). In
# the Constrictor's system the lone bounty hunter of an encounter roll is
# hostile whoever you are, and while the mission is on it is the Constrictor
# instead, if there isn't one about already. Only the military laser hurts
# the Constrictor, at a quarter of its power, and its ECM destroys your
# missiles. Carrying mission 2's plans, each encounter tick brings a Thargoid
# with chance PLANS_THARGOID (the original's 56 in 256).
CONSTRICTOR = "CONSTRICTOR"
CONSTRICTOR_LASER = 0.25
PLANS_THARGOID = 56 / 256.0

# The ships parked in a station's docking bay depend on the system: pirate
# craft where the government is weak, traders and police where it is strong,
# shuttles where the tech level is low, the newest ships where it is high.
# Only ships small enough for the bay.
PARK_PIRATES = ("SIDEWINDER", "MAMBA", "KRAIT", "WORM", "GECKO", "COBRA MK I")
PARK_TRADERS = ("COBRA MK III", "BOA", "ADDER", "MORAY")
PARK_POLICE = ("VIPER",)
PARK_LOW_TECH = ("SHUTTLE", "TRANSPORTER")      # below PARK_LOW tech level
PARK_HIGH_TECH = ("ASP MK II", "FER DE LANCE")  # at DODO_TECH or more
PARK_LOW = 5
PARK_MOST = 4

# enemy ships by difficulty; later waves draw from further down the list
TIERS = (
    ("SIDEWINDER", "GECKO", "COBRA MK I", "WORM"),
    ("MAMBA", "KRAIT", "ADDER", "VIPER", "MORAY"),
    ("COBRA MK III", "FER DE LANCE", "ASP MK II", "COBRA MK III P"),
    ("PYTHON", "BOA", "ANACONDA", "CONSTRICTOR", "PYTHON P"),
    ("THARGOID",),
)
ROCKS = ("ASTEROID", "BOULDER")
_INV14 = 1.0 / 16384
THINK_EVERY = 3        # a ship re-plans on one frame in this many (see Game._think)
SCOOP_GOODS = 8        # a canister holds one of the first this many goods (food to computers)
MAX_MISSILES = 4       # missiles the Cobra Mk III carries (others: Game.max_missiles)
PICKUP_MISSILE = 0.5   # combat practice: how often a canister holds a missile as well
# combat practice with upgrades (Game.practice_upgrades, build 113): each wave cleared
# drops an upgrade canister (green); scooped, it fits the next of these, in order; after
# the last, a used energy bomb comes back, else the shields are filled
UPGRADES = ("beam", "energy unit", "military", "bomb")
WAVE_WAIT = 5.0         # seconds of countdown before the next wave (with the upgrades)
UPGRADE_WAIT = 20.0     # the countdown waits for the upgrade canister to be collected (Brian),
                        # this long at most: a canister missed goes, and the countdown starts
UPGRADE_AHEAD = 400.0   # the upgrade canister appears this far straight ahead, drifting
                        # towards you, for an easy pick-up (Brian; it was 1200)
UPGRADE_NAMES = {"beam": "BEAM LASER", "energy unit": "ENERGY UNIT", "military": "MILITARY LASER",
                 "bomb": "ENERGY BOMB"}

# What the level changes: (most hostile ships at once, how often enemy lasers
# hit compared with level 1, how much damage they and their missiles do
# compared with level 1, how much energy every ship has compared with its
# blueprint: how many hits it takes). Level 1 (NORMAL) is the original's.
LEVELS = (
    (3, 0.7, 0.7, 0.75),
    (4, 1.0, 1.0, 1.0),
    (5, 1.3, 1.3, 1.25),
)


def bad(cargo):
    """How bad the contraband in a hold is (BAD): (slaves + narcotics) x 2 +
    firearms, in tonnes."""
    w = 0
    for i, k in ILLEGAL.items():
        if i < len(cargo):
            w += k * cargo[i]
    return min(255, w)


def legal_name(legal):
    """CLEAN, OFFENDER or FUGITIVE for a legal status of 0 to 255."""
    if legal <= 0:
        return "CLEAN"
    return "OFFENDER" if legal < FUGITIVE else "FUGITIVE"


def parked_ships(gov, tech, rnd=random):
    """Names of 1 to PARK_MOST ships parked in the docking bay of a system
    with this government (0 anarchy to 7 corporate state) and tech level,
    drawn at random from the kinds that system would have. gov None: a mix."""
    if gov is None:
        gov = 3
    # how many of each kind go in the hat: pirates fade out and police come
    # in as the government gets safer
    pool = []
    for names, n in ((PARK_PIRATES, max(0, 4 - gov)), (PARK_TRADERS, 2 + gov // 2),
                     (PARK_POLICE, max(0, gov - 2) * 2)):
        for name in names:
            pool.extend([name] * n)
    if tech is not None and tech < PARK_LOW:
        pool.extend(PARK_LOW_TECH * 4)
    if tech is not None and tech >= DODO_TECH:
        pool.extend(PARK_HIGH_TECH * 3)
    return [pool[rnd.randrange(len(pool))] for _ in range(rnd.randint(1, PARK_MOST))]


def _rnd(a, b):
    return a + (b - a) * random.random()


def _unit(x, y, z):
    d = math.sqrt(x * x + y * y + z * z)
    if d < 1e-9:
        return 0.0, 0.0, 1.0
    return x / d, y / d, z / d


def _ortho(m):
    """Make side, roof and nose unit length and at right angles again."""
    nx, ny, nz = _unit(m[6], m[7], m[8])
    k = m[3] * nx + m[4] * ny + m[5] * nz
    rx, ry, rz = m[3] - nx * k, m[4] - ny * k, m[5] - nz * k
    if rx * rx + ry * ry + rz * rz < 1e-9:
        _look(m, nx, ny, nz)
        return
    rx, ry, rz = _unit(rx, ry, rz)
    m[0] = ry * nz - rz * ny
    m[1] = rz * nx - rx * nz
    m[2] = rx * ny - ry * nx
    m[3], m[4], m[5] = rx, ry, rz
    m[6], m[7], m[8] = nx, ny, nz


def _look(m, dx, dy, dz):
    """Point the nose along the unit vector (dx, dy, dz)."""
    if abs(dy) > 0.9:
        ux, uy, uz = 1.0, 0.0, 0.0
    else:
        ux, uy, uz = 0.0, 1.0, 0.0
    k = ux * dx + uy * dy + uz * dz
    rx, ry, rz = _unit(ux - dx * k, uy - dy * k, uz - dz * k)
    m[0] = ry * dz - rz * dy
    m[1] = rz * dx - rx * dz
    m[2] = rx * dy - ry * dx
    m[3], m[4], m[5] = rx, ry, rz
    m[6], m[7], m[8] = dx, dy, dz


def _turn(m, dx, dy, dz, max_angle):
    """Swing the nose towards the unit vector (dx, dy, dz), by at most max_angle."""
    nx, ny, nz = m[6], m[7], m[8]
    dot = nx * dx + ny * dy + nz * dz
    if dot > 0.9999:
        return
    if dot < -1.0:
        dot = -1.0
    angle = math.acos(dot)
    k = 1.0 if angle <= max_angle else max_angle / angle
    x, y, z = nx + (dx - nx) * k, ny + (dy - ny) * k, nz + (dz - nz) * k
    if x * x + y * y + z * z < 1e-6:
        return
    m[6], m[7], m[8] = x, y, z
    _ortho(m)


def _roll(m, a):
    """Spin about the nose."""
    c, s = math.cos(a), math.sin(a)
    for i in (0, 1, 2):
        side, roof = m[i], m[3 + i]
        m[i] = side * c + roof * s
        m[3 + i] = roof * c - side * s


class Blueprint:
    """One ship type from ship_data.py (or original_ships.py)."""

    def __init__(self, entry):
        self.name = entry[0]    # the role the game knows it by
        self.title = entry[5] if len(entry) > 5 else entry[0]   # the name shown
        # convex parts, for a shape that isn't convex (the ring station):
        # (vertex numbers, edge numbers, when it hides what is behind: 0 never,
        # 1 always, 2 seen side-on) each, drawn back to front
        self.parts = entry[6] if len(entry) > 6 else None
        self.verts = entry[1]
        self.edges = entry[2]
        self.normals = entry[3]
        # a vertex on each face (-1: none), for the hidden-line test
        self.face_vert = [-1] * len(self.normals)
        for a, b, f1, f2 in self.edges:
            if self.face_vert[f1] < 0:
                self.face_vert[f1] = a
            if self.face_vert[f2] < 0:
                self.face_vert[f2] = a
        stats = entry[4] if len(entry) > 4 else None
        size2 = 1.0
        for x, y, z in self.verts:
            d = x * x + y * y + z * z
            if d > size2:
                size2 = d
        self.size = math.sqrt(size2)   # distance of the furthest vertex
        self.isize = int(self.size + 0.5)
        # its furthest vertex along the nose: for a station, how far the slot
        # face is from its centre (160 for the Coriolis, 196 for the Dodo)
        self.front = float(max([v[2] for v in self.verts] or [0]))
        if stats:
            (self.canisters, area, self.gun, self.explosions, self.bounty,
             self.vis, self.energy, self.speed, self.laser, self.missiles) = stats
        else:
            self.canisters = self.gun = self.bounty = self.missiles = 0
            self.explosions = 4
            self.vis = 30
            self.energy = 80
            self.speed = 25
            self.laser = 2
            area = size2 * 0.4
        self.area = float(max(area, 400))   # hit area: radius squared
        self.radius = math.sqrt(self.area)


def _view_xz(view, x, z):
    """Elite's PU1 / PU2 for one point (see Game.enter_view)."""
    if view == 1:
        return -x, -z
    if view == 2:
        return z, -x
    return -z, x


def _view_obj(o, view):
    o.x, o.z = _view_xz(view, o.x, o.z)
    m = o.m
    for i in (0, 3, 6):     # side, roof and nose: their x and z
        m[i], m[i + 2] = _view_xz(view, m[i], m[i + 2])


class Obj:
    """A ship, missile, rock or cargo canister."""
    count = 0

    def __init__(self, bp, kind, x, y, z):
        self.bp = bp
        self.kind = kind    # "ship", "missile", "pmissile", "rock" or "can"
        self.x = x
        self.y = y
        self.z = z
        self.m = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
        self.speed = 0.0    # Elite speed units, along the nose
        self.energy = float(bp.energy)
        self.max_energy = self.energy   # its full energy (the level scales a ship's: Game.step)
        self.leveled = False
        self.state = "attack"   # ships: "attack", "break", "flee", or "trade" / "patrol" (leaving you alone)
        self.t = 0.0
        self.cool = _rnd(0.5, 2.0)
        self.spin = 0.0
        self.aim = None     # [dx, dy, dz] heading used while breaking away
        self.target = None  # what a player missile is chasing
        self.good = None    # a splinter: the good it holds (a canister: None, any of several)
        self.upgrade = False    # a practice upgrade canister (Game.practice_upgrades)
        self.role = "pirate"    # ships: "pirate", "trader", "police" or "hunter"
        self.dest = "station"   # a trader's: where it is making for, "station" or "planet"
        self.prey = None        # a pirate's: the trader it is after (None: you)
        self.checked = False    # a police ship's: it has looked at your ship (a stolen one: Game.stolen)
        self.has_pod = bp.name in POD_SHIPS     # its crew can bail out (Game._bail)
        self.missiles = bp.missiles
        self.ecm = False    # an enemy ECM (the Constrictor's): destroys your missiles
        self.beam = 0.0     # > 0 while this ship's laser is drawn
        self.hit = 0.0      # > 0 while flashing from a hit
        self.dead = False
        # ships work out their steering every THINK_EVERY frames, not all on
        # the same one
        Obj.count += 1
        self.slot = Obj.count % THINK_EVERY
        self.think_t = 0.0  # time since this ship last did


class Boom:
    """An explosion: a cloud of dots flying apart."""

    def __init__(self, x, y, z, n, spread):
        self.t = 0.0
        self.life = 1.3
        # each dot is [x, y, z, vx, vy, vz] in whole numbers: see Game._rotate
        x = int(x)
        y = int(y)
        z = int(z)
        spread = int(spread)
        self.parts = [
            [x, y, z, random.randint(-spread, spread), random.randint(-spread, spread),
             random.randint(-spread, spread)]
            for _ in range(n)
        ]


def _rot3(x, y, z, ca, sa, cb, sb):
    """Pitch a point by the angle with cosine ca and sine sa, then roll it by
    cb, sb: the same turn as Game._rotate does in whole numbers."""
    y, z = y * ca - z * sa, y * sa + z * ca
    return x * cb - y * sb, x * sb + y * cb, z


class Anchor:
    """Multiplayer (plans/MULTIPLAYER.md): where a world shared with other players
    is. You never move (as Elite), so each device keeps the shared world's origin
    (x, y, z) and its axes (m: its x, y and z axes as rows, in your coordinates,
    the layout of Obj.m) and turns and slides them with everything else
    (Game._rotate, _yaw). Then your pose in the shared world, and anyone else's in
    yours, are a matrix product away: Game.world_pose, Game.place. Floats: one
    object, so no garbage worth counting on the badge."""

    def __init__(self):
        self.x = self.y = self.z = 0.0
        self.m = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]


class Space:
    """The star system a commander flies in: a planet and a sun (spheres, as a
    centre and a radius) and a space station, an Obj that is kept out of
    Game.objs. They are far bigger and further away than anything else, beyond
    the whole numbers Game._rotate uses, so they are turned in floats; there
    are only three of them."""

    def __init__(self, station_bp, radius, gov):
        self.px = self.py = self.pz = 0.0   # the planet's centre
        self.pr = radius
        self.sx = self.sy = self.sz = 0.0   # the sun's centre
        self.sr = radius * SUN_SIZE
        self.station = Obj(station_bp, "station", 0.0, 0.0, 0.0) if station_bp else None
        self.gov = gov          # the system's government (0 to 7), for the station's colour
        self.hostile = False    # you fired on it, or on an innocent ship: it refuses docking
        self.sun = 2            # which colour the sun is (cockpit.SUN_COLOURS): yellow
        self.planet = 0         # and the planet (cockpit.PLANET_COLOURS): blue
        self.d_station = 1e9    # distance to the station
        self.safe_r = radius * SAFE_K   # the safe zone round the station
        self.safe = False       # within it
        self.witch = False      # witchspace: no planet, sun or station (see Game.witchspace)


class Game:
    def __init__(self, ships, level=1):
        self.set_level(level)
        self.god = False    # a cheat: hits flash but do no damage
        self.sounds = []    # sounds asked for this frame (sfx.py's names), which ace.py plays
        self.docking = "C"  # how docking works: see set_docking
        self.view = 0               # 0 front, 1 rear, 2 left, 3 right (Elite's VIEW)
        self.ship_name = "COBRA MK III"     # the ship you fly (ace.py's _ship_name), for the chase view
        self.looking = True         # a space view is showing (Elite's QQ11 = 0); False on a
                                    # status, market or chart screen: lasers fire but can't hit
        self.lasers = [None, None, None, None]  # the laser on each view (a key of LASERS), or None
        self.laser = None           # the laser on the current view
        self.set_laser("pulse")
        self.energy_unit = False    # recharge ENERGY_UNIT times faster
        self.navy = False           # the naval energy unit: NAVY_UNIT times instead
        self.orarra = False         # in the Constrictor's system (missions.constrictor_here)
        self.hunt = False           # and the Constrictor is there to be found
        self.con_wait = None        # seconds outside the safe zone before it comes; None: only by the roll
        self.con_t = 0.0            # time spent outside the safe zone towards that
        self.plans = False          # carrying mission 2's plans: Thargoids come after you
        self.got_constrictor = False    # set when you destroy it; the app notes it
        self.fuel_scoops = True     # without them a canister is hit, not scooped
        self.ecm = False            # fires by itself at incoming missiles (or by its key: see rules)
        self.rules = GameRules()    # standard mode; Hardcore Mode swaps in GameRules(True)
        self.armed = False          # Hardcore: a missile is armed (see arm_missile)
        self.pod = False            # an escape pod: being destroyed isn't the end
        self.bombs = 0              # energy bombs (one at most, used once)
        self.computer = False       # a docking computer
        self.legal = 0              # legal status, 0 to 255: see FUGITIVE
        self.stolen = False         # flying a stolen ship: lawful police may spot it (SPOT_CHANCE)
        # what skimmed fuel goes into: a function given tenths of a light year
        # that returns how many fitted in the tank; None: nowhere (practice)
        self.refuel = None
        self.fuel = None    # the commander's fuel (tenths of a LY), for the HUD; None: none
        # what a scooped canister goes into: a function given the good's number
        # that returns its name, or None if there is no room; None in practice
        self.scoop = None
        self.types = {}
        for entry in ships:
            bp = Blueprint(entry)
            self.types[bp.name] = bp
        # the ship you fly (build 78): see set_ship; the Cobra Mk III until then
        self.max_speed = PLAYER_MAX
        self.turn_k = 1.0           # turn rates times this
        self.tough = 1.0            # damage divided by this
        self.max_missiles = MAX_MISSILES
        self.missile_bp = self.types.get("MISSILE")
        self.can_bp = self.types.get("CANISTER")
        tiered = set()
        for tier in TIERS:
            tiered.update(tier)
        # used if none of the named enemy ships are in the ship data
        self.fallback = [bp for bp in self.types.values()
                         if bp.laser and bp.speed and bp.name not in tiered]
        self.reset()

    def set_ship(self, name, pylons=MAX_MISSILES):
        """Fly a ship of this type (ships.py): its top speed, turning and
        toughness from its blueprint against the Cobra Mk III's, and pylons
        for missiles. Missiles above the pylons are dropped."""
        self.ship_name = name
        self.max_speed, self.turn_k, self.tough = ships.flight(
            self.types.get(name), self.types.get(ships.COBRA))
        self.max_missiles = pylons
        if self.missiles > pylons:
            self.missiles = pylons
        if self.speed > self.max_speed:
            self.speed = self.max_speed

    def set_docking(self, style):
        """"A" authentic, "B" assisted or "C" automatic (commander.DOCKING).
        Hardcore Mode is always "A": by hand, or with a docking computer."""
        self.docking = "A" if self.rules.manual_docking else (style if style in ("A", "B", "C") else "C")
        self.tractor = False

    def set_laser(self, kind, view=0):
        """The laser on a view (0 front, 1 rear, 2 left, 3 right): a key of
        LASERS, or None for none. Elite has one laser a view, as this does."""
        self.lasers[view] = None if kind is None else (kind if kind in LASERS else "pulse")
        self._aim_laser()

    def _aim_laser(self):
        """self.laser and its numbers are the current view's laser."""
        self.laser = self.lasers[self.view]
        if self.laser is not None:
            self.laser_period, self.laser_damage, self.laser_heat = LASERS[self.laser]

    def set_view(self, view):
        """Look front (0), rear (1), left (2) or right (3), as Elite's
        f0-f3 do. Not while the docking computer flies. Returns True if it
        changed."""
        if view == self.view or not 0 <= view < 4 or self.autodock:
            return False
        self.view = view
        self._aim_laser()
        self.beam = 0.0
        self.lock = None
        self.lock_t = 0.0
        self.locked = False
        self.say(VIEW_NAMES[view] + " VIEW", 1.0)
        return True

    def next_view(self):
        """The next view round (the menu's and one key's way of changing it)."""
        self.set_view((self.view + 1) % 4)

    # Elite's PU1 / PU2: the world is kept as seen from the front, and flipped
    # or swapped into the view you are looking through only to draw it and to
    # aim at it. Rear: x and z change sign. Left: the new x is z and the new z
    # is minus x. Right: the new x is minus z and the new z is x. Whole-number
    # exact, so going there and back changes nothing.
    def enter_view(self):
        """Everything from the front frame into the current view's."""
        if self.view:
            self._into_view(self.view)

    def leave_view(self):
        """Everything from the current view's frame back to the front's."""
        if self.view:
            self._into_view(self.view, True)

    def set_anchor(self, x, y, z, m):
        """Start a shared world with you at (x, y, z) in it, your side, roof and
        nose (m, rows, as Obj.m) given in its coordinates."""
        a = self.anchor = Anchor()
        # the world's axes in yours: the transpose of your axes in the world's
        a.m[:] = [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]]
        # the world's origin in yours: minus your position, in your axes
        a.x = -(x * m[0] + y * m[1] + z * m[2])
        a.y = -(x * m[3] + y * m[4] + z * m[5])
        a.z = -(x * m[6] + y * m[7] + z * m[8])

    def world_pose(self):
        """Your (x, y, z) and axes (side, roof, nose as rows, 9 numbers) in the
        shared world, or None without one (set_anchor)."""
        a = self.anchor
        if a is None:
            return None
        m = a.m
        # a point v of yours is at (v.side, v.roof, v.nose) in the world, the
        # world's axes being m's rows; you are at minus the origin, so:
        x = -(a.x * m[0] + a.y * m[1] + a.z * m[2])
        y = -(a.x * m[3] + a.y * m[4] + a.z * m[5])
        z = -(a.x * m[6] + a.y * m[7] + a.z * m[8])
        # your axes are (1,0,0), (0,1,0), (0,0,1): in the world, m's columns
        return x, y, z, [m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8]]

    def place(self, o, x, y, z, m):
        """Put o (an Obj) where a pose in the shared world puts it in yours:
        (x, y, z) and axes m (rows, the world's coordinates)."""
        a = self.anchor
        w = a.m
        o.x = a.x + x * w[0] + y * w[3] + z * w[6]
        o.y = a.y + x * w[1] + y * w[4] + z * w[7]
        o.z = a.z + x * w[2] + y * w[5] + z * w[8]
        om = o.m
        for i in (0, 3, 6):
            p, q, r = m[i], m[i + 1], m[i + 2]
            om[i] = p * w[0] + q * w[3] + r * w[6]
            om[i + 1] = p * w[1] + q * w[4] + r * w[7]
            om[i + 2] = p * w[2] + q * w[5] + r * w[8]

    def _into_view(self, view, back=False):
        if back and view >= 2:
            view = 5 - view         # left undoes right and right undoes left
        sp = self.space
        for o in self.objs:
            _view_obj(o, view)
        for o in self.new:
            _view_obj(o, view)
        for boom in self.booms:
            for p in boom.parts:
                p[0], p[2] = _view_xz(view, p[0], p[2])
        if sp is not None:
            sp.px, sp.pz = _view_xz(view, sp.px, sp.pz)
            sp.sx, sp.sz = _view_xz(view, sp.sx, sp.sz)
            if sp.station is not None:
                _view_obj(sp.station, view)

    def view_dust(self):
        """The stardust as the current view sees it: a copy, since the dust
        is kept in front of you. From the rear it rushes away, from the
        sides it streams past (Elite has its own stardust for each view)."""
        v = self.view
        if v == 0:
            return self.dust
        out = []
        for x, y, z in self.dust:
            if v == 1:
                out.append([-x, y, 2 * DUST_MID - z])
            elif v == 2:
                out.append([z - DUST_MID, y, DUST_MID - x])
            else:
                out.append([DUST_MID - z, y, DUST_MID + x])
        return out

    def set_level(self, level):
        """0 easiest to 2 hardest. Takes effect straight away."""
        self.level = max(0, min(len(LEVELS) - 1, int(level)))
        self.max_hostile, self.aim_k, self.damage_k, self.energy_k = LEVELS[self.level]

    def reset(self):
        self.view = 0       # a flight starts looking ahead
        self.looking = True
        self._aim_laser()
        self.objs = []
        self.new = []      # objects created during a step, added at its end
        self.booms = []
        self.anchor = None  # multiplayer: the shared world's origin and axes (set_anchor)
        self.tick = 0
        self.frame = 0
        # dust and explosion dots are whole numbers: see _rotate
        if not hasattr(self, "dust_x"):
            self.dust_x = DUST_X    # cockpit.draw_world sets it from the layout
        dx = self.dust_x
        self.dust = [[random.randint(-dx, dx), random.randint(-500, 500),
                      random.randint(100, 1500)] for _ in range(10)]
        self.speed = 14.0
        self.shield = 100.0
        self.hull = 100.0
        self.heat = 0.0
        self.hot = False       # laser overheated
        self.cool = 0.0
        self.beam = 0.0        # > 0 while the player's laser is drawn
        self.missiles = self.max_missiles if self.missile_bp else 0
        self.kills = 0
        self.bounty = 0        # bounties earned this flight, in tenths of a credit
        self.score = 0
        self.cargo = 0
        self.wave = 1
        self.wave_kills = 0
        self.spawn_t = 1.5
        self.rock_t = _rnd(6, 12)
        self.time = 0.0
        self.since_hit = 9.0
        self.flash = 0.0       # > 0 just after the player is hit
        self.refused = None    # what stops the jump drive while speed is held up (_blocker)
        self.low_t = 0.0       # until ENERGY LOW is said again
        self.over = False
        self.msg = "WAVE 1"
        self.msg_t = 2.5
        self.lock = None       # the ship in the missile sights
        self.lock_t = 0.0      # how long it has been there
        self.locked = False    # long enough: a missile can be fired at it
        self.armed = False     # Hardcore: a missile is armed (see arm_missile)
        if not hasattr(self, "auto_missile"):
            self.auto_missile = False   # fire one at each ship once it is locked (ace sets it)
            self.pickup_missile = PICKUP_MISSILE    # practice canisters' missile odds (ace sets it)
        self.auto_done = None  # the last ship auto_missile fired at
        if not hasattr(self, "practice_upgrades"):
            self.practice_upgrades = False  # waves drop upgrade canisters (ace sets it)
        self.upgrade_n = 0     # the upgrades fitted so far (UPGRADES)
        self.wave_hold = 0.0   # waiting for the upgrade canister to be collected (UPGRADE_WAIT)
        self.wave_wait = 0.0   # the countdown to the next wave (WAVE_WAIT), while > 0
        self.wave_shown = 0    # the second it last showed
        self.jump_t = 0.0      # > 0 while the hyperspace countdown runs
        self.warp = 0.0        # > 0 while the streaks of a jump are drawn
        self.jumped = False    # set when a jump happens; whoever started it clears it
        self.space = None      # the star system (Space), or None: open space, waves of ships
        self.jumping = False   # the jump drive is on
        self.fwd = 0           # how far everything slid towards you last step (whole units)
        self.pending = 0       # ships of the current encounter still to turn up
        self.group = []        # their types (names), in the order they come
        self.group_role = "pirate"  # and who they are: "pirate" or "hunter"
        self.encounter_t = 0.0  # time until the next roll for an encounter
        self.skip = 0          # rolls still to skip after the last encounter
        self.docked = False    # set on reaching the station; whoever is watching takes over
        self.cabin = COOL_CABIN  # the cabin temperature, 30 in deep space to 255
        self.scooping = False  # skimming fuel from the sun just now
        self.full_said = False # FUEL FULL said on this pass through the scooping band
        self.sun_t = SUN_CHECK  # time to the next fuel scoop
        self.tractor = False   # docking B: the station is drawing you in
        self.bump_t = 0.0      # > 0 just after hitting the station (no second hit meanwhile)
        self.again = "C: fly again"     # what C does on the GAME OVER screen
        self.ejected = False   # destroyed, but the escape pod got away: whoever is watching docks you
        self.ecm_t = 0.0       # > 0 just after the ECM fired
        self.bomb_t = 0.0      # > 0 just after the energy bomb went off
        self.autodock = False  # the docking computer is flying
        self.station_t = 1.0   # time to the station's next chance to launch a ship
        self.bad = 0           # the contraband in the hold (BAD), set by whoever runs the game
        self.auto_phase = 0    # where it has got to: see start_autodock
        self.auto_far = False  # it is far from where it is heading: the jump drive's speed
        self.auto_level = False  # it is matching the slot's roll
        self.auto_stick = (0.0, 0.0)    # its last pitch and roll
        self.stick_pitch = 0.0  # the pitch and roll last given to step (build 105)
        self.stick_roll = 0.0
        self.auto_yaw = 0.0     # and yaw (on the run in, rolled to the slot: build 95)

    def say(self, msg, t=2.0):
        self.msg = msg
        self.msg_t = t

    def sfx(self, name):
        """Ask for a sound (sfx.py): ace.py hands it to the device each frame."""
        if len(self.sounds) < 4:
            self.sounds.append(name)

    # ---- hyperspace -------------------------------------------------------

    def start_jump(self):
        """Start (or restart) the countdown to a hyperspace jump. Where the
        jump goes is the caller's business: it watches for self.jumped."""
        if not self.over:
            self.jump_t = JUMP_COUNT
            self.say("HYPERSPACE %d" % int(JUMP_COUNT), 1.5)
            self.sfx("tick")

    def _hyper(self, dt):
        if self.jump_t <= 0:
            return
        before = int(self.jump_t + 0.999)
        self.jump_t -= dt
        if self.jump_t > 0:
            left = int(self.jump_t + 0.999)
            if left != before:
                self.say("HYPERSPACE %d" % left, 1.5)
                self.sfx("tick")
            return
        # the jump: everything here is left behind
        self.jump_t = 0.0
        self.sfx("jump")
        self.autodock = False   # a new system: the docking computer is off
        self.objs = []
        self.new = []
        self.booms = []
        self.lock = None
        self.lock_t = 0.0
        self.locked = False
        self.armed = False
        self.beam = 0.0
        self.warp = WARP_TIME
        self.jumped = True
        # out of hyperspace (or into witchspace) looking ahead, as Elite's
        # TT110 and MJP do (LOOK1 with X = 0): the streaks rush out ahead
        self.view = 0
        self._aim_laser()
        self.space = None       # left behind too; whoever started the jump sets the new one
        self.jumping = False
        self.pending = 0
        self.group = []
        self.spawn_t = _rnd(5.0, 8.0)   # a quiet moment on arriving
        self.rock_t = _rnd(6, 12)
        self.msg_t = 0.0

    # ---- the star system --------------------------------------------------

    def enter(self, radius_km, station, how, gov=None, sun=2, planet=0):
        """Put the player in a star system. radius_km is the planet's radius
        (galaxy.System.radius), station the station's ship name, gov the
        government, for its colour. how is "launch": just out of the
        station's slot, which faces the planet, so the planet is ahead; or
        "arrive": out of hyperspace, ARRIVE_DIST from the station, with the
        planet beyond it, and in an anarchy or a feudal system as many
        pirates as can attack at once waiting (gov None: no ambush)."""
        self.con_t = 0.0        # a new visit: the quick Constrictor's wait starts again
        bp = self.types.get(station) or self.types.get("CORIOLIS")
        r = max(4000.0, radius_km * PLANET_SCALE)
        sp = Space(bp, r, gov)
        sp.sun = sun
        sp.planet = planet
        if how == "launch":
            sx, sy, sz = 0.0, 0.0, -LAUNCH_DIST
            ux, uy, uz = 0.0, 0.0, 1.0      # from the station to the planet
            self.pending = 0
            self.group = []
        else:
            dx, dy, dz = _unit(_rnd(-0.25, 0.25), _rnd(-0.15, 0.15), 1.0)
            sx, sy, sz = dx * ARRIVE_DIST, dy * ARRIVE_DIST, dz * ARRIVE_DIST
            # the planet is beyond the station and off to one side, so the
            # station isn't lost against it
            side = _rnd(0.3, 0.6) * random.choice((-1, 1))
            ux, uy, uz = _unit(dx + side, dy + _rnd(-0.3, 0.3), dz)
            # an ambush on arriving, but only where the government is weak
            self.pending = 0
            self.group = []
            if gov is not None and gov < AMBUSH_GOV:
                self._new_group([self._pirate() for _ in range(self.max_hostile)])
            self.spawn_t = _rnd(5.0, 8.0)
        k = STATION_ORBIT * r
        sp.px, sp.py, sp.pz = sx + ux * k, sy + uy * k, sz + uz * k
        # the sun is on the station's side of the planet, off to one side, so
        # it is behind you on launching and in view as you turn
        ax, ay, az = _rnd(-1, 1), _rnd(-0.5, 0.5), _rnd(-1, 1)
        k = ax * ux + ay * uy + az * uz
        ax, ay, az = _unit(ax - ux * k, ay - uy * k, az - uz * k)     # at right angles to u
        k = _rnd(0.5, 1.2)
        wx, wy, wz = _unit(ax * k - ux, ay * k - uy, az * k - uz)
        k = SUN_DIST * r
        sp.sx, sp.sy, sp.sz = sp.px + wx * k, sp.py + wy * k, sp.pz + wz * k
        st = sp.station
        if st is not None:
            st.x, st.y, st.z = sx, sy, sz
            _look(st.m, ux, uy, uz)         # the slot is on the nose
        self.space = sp
        while len(self.dust) < 10:      # all the stardust again, after witchspace
            self.dust.append([random.randint(-self.dust_x, self.dust_x), random.randint(-500, 500),
                              random.randint(100, 1500)])
        self.autodock = False
        self.auto_phase = 0
        self.auto_level = False
        self.encounter_t = ENCOUNTER_EVERY
        self.skip = 0
        if self.msg == "WAVE 1":    # waves are for combat practice only
            self.msg_t = 0.0
        self._measure()

    def witchspace(self, n=THARGOIDS):
        """A mis-jump: put the player in witchspace (MJP), with n Thargoids
        about, each with a Thargon. The planet and sun are put out of reach
        and there is no station."""
        sp = Space(None, 4000.0, None)
        far = 1e9
        sp.px = sp.py = sp.pz = far
        sp.sx, sp.sy, sp.sz = -far, far, far
        sp.witch = True
        self.space = sp
        self.dust = self.dust[:WITCH_DUST]
        self.autodock = False
        self.tractor = False
        self.pending = 0
        self.group = []
        for _ in range(n):
            self.add_thargoid()
        self._measure()
        self.say("WITCHSPACE", 3.0)
        self.sfx("incoming")

    def add_thargoid(self):
        """A Thargoid round you (GTHG), with a Thargon beside it."""
        bp = self.types.get("THARGOID")
        if bp is None or len(self.objs) + len(self.new) >= MAX_OBJECTS - 1:
            return None
        o = self._spawn_ship(bp)
        o.role = "thargoid"
        o.state = "attack"
        self._thargon(o)
        return o

    def _make_constrictor(self, o):
        o.role = "constrictor"
        o.state = "attack"
        o.ecm = True

    def add_constrictor(self):
        """The stolen Constrictor round you (a cheat, or the mission)."""
        bp = self.types.get(CONSTRICTOR)
        if bp is None or len(self.objs) + len(self.new) >= MAX_OBJECTS:
            return None
        o = self._spawn_ship(bp)
        self._make_constrictor(o)
        return o

    def _any(self, name):
        for o in self.objs + self.new:
            if o.bp.name == name and not o.dead:
                return True
        return False

    def _thargon(self, parent):
        """A Thargon launched from its Thargoid mothership."""
        bp = self.types.get("THARGON")
        if bp is None or len(self.objs) + len(self.new) >= MAX_OBJECTS:
            return None
        k = parent.bp.radius + bp.radius + 60
        m = parent.m
        t = Obj(bp, "ship", parent.x + m[0] * k, parent.y + m[1] * k, parent.z + m[2] * k)
        t.m = list(m)
        t.speed = bp.speed * 0.5
        t.role = "thargoid"
        t.state = "attack"
        self.new.append(t)
        return t

    def _any_thargoid(self):
        for o in self.objs:
            if o.bp.name == "THARGOID" and not o.dead:
                return True
        for o in self.new:
            if o.bp.name == "THARGOID":
                return True
        return False

    def to_station(self, dist=4000.0, slot=True):
        """A cheat: move the star system so the station is dist ahead, with
        its slot facing you unless slot is False."""
        sp = self.space
        if sp is None or sp.station is None:
            return
        st = sp.station
        self._shift(-st.x, -st.y, dist - st.z)
        if slot:
            _look(st.m, 0.0, 0.0, -1.0)
        self.tractor = False
        self._measure()

    def to_sun(self, k=1.15, ahead=0.0):
        """A cheat: move the star system so the sun's centre is k sun radii
        to your right and ahead sun radii in front: with ahead 0 you are
        flying past it at that distance; with ahead > 0 flying on takes you
        down to k sun radii and out again."""
        sp = self.space
        if sp is None or sp.station is None:
            return
        self._shift(sp.sr * k - sp.sx, -sp.sy, sp.sr * ahead - sp.sz)
        self._measure()

    def _shift(self, dx, dy, dz):
        """Move the planet, sun and station together (you never move)."""
        sp = self.space
        st = sp.station
        st.x += dx
        st.y += dy
        st.z += dz
        sp.px += dx
        sp.py += dy
        sp.pz += dz
        sp.sx += dx
        sp.sy += dy
        sp.sz += dz

    def _measure(self):
        """How far the station is, and so whether this is the safe zone."""
        sp = self.space
        st = sp.station
        if st is None:
            sp.d_station = 1e9
        else:
            sp.d_station = math.sqrt(st.x * st.x + st.y * st.y + st.z * st.z)
        safe = sp.d_station < sp.safe_r
        if sp.safe and not safe and sp.hostile:
            # out of the safe zone the original drops the station from the local
            # bubble (the sun takes its slot) and makes a new one, not hostile,
            # when you come back (NWSPS): the lockdown is over
            sp.hostile = False
        sp.safe = safe

    def _near(self):
        """True if a ship or missile is within radar range. In comparisons
        only, so no new numbers are made."""
        r = RADAR_RANGE
        for o in self.objs:
            if ((o.kind == "ship" or o.kind == "missile") and -r < o.x < r
                    and -r < o.y < r and -r < o.z < r):
                return True
        return False

    def condition(self):
        """Elite's condition, for the status screen: "RED" with a missile or a
        hostile ship in radar range, or the shields low; "YELLOW" with any
        other ship about; else "GREEN"."""
        r = RADAR_RANGE
        near = False
        for o in self.objs:
            if o.dead or (o.kind != "ship" and o.kind != "missile"):
                continue
            if not (-r < o.x < r and -r < o.y < r and -r < o.z < r):
                continue
            if o.kind == "missile" or o.role == "pirate" or o.state in ("attack", "break"):
                return "RED"
            near = True
        if self.shield < 50:
            return "RED"
        return "YELLOW" if near else "GREEN"

    def _blocker(self, sp):
        """What keeps the jump drive off just now: "station" (its safe zone), "planet" or
        "sun" (a mass lock), "heat" (near the sun), "ships" (something in radar range), or
        None. Each is its own field: the refusal beeps again only when it changes."""
        if sp.safe:
            return "station"
        for name, x, y, z, r in (("planet", sp.px, sp.py, sp.pz, sp.pr),
                                 ("sun", sp.sx, sp.sy, sp.sz, sp.sr)):
            k = r * MASS_LOCK_K
            if x * x + y * y + z * z < k * k:
                return name
        if self.cabin > COOL_CABIN:
            return "heat"
        if self._near():
            return "ships"
        return None

    def _massed(self, sp):
        """True within MASS_LOCK_K radii of the planet's or the sun's centre (the mass lock: the
        jump drive won't run near a big mass; the station's mass is its safe zone). Squares only."""
        if sp is None:
            return False
        for x, y, z, r in ((sp.px, sp.py, sp.pz, sp.pr), (sp.sx, sp.sy, sp.sz, sp.sr)):
            k = r * MASS_LOCK_K
            if x * x + y * y + z * z < k * k:
                return True
        return False

    def _space(self, dt):
        """The station turns; reaching it docks you, and flying into the
        planet, or too deep into the sun's heat (_sun), is the end."""
        sp = self.space
        st = sp.station
        if st is not None:
            _roll(st.m, STATION_SPIN * dt)
            if self.frame % 32 == 0:
                _ortho(st.m)
        self._measure()
        if self.over:
            return
        if self.bump_t > 0:
            self.bump_t -= dt
        if st is not None:
            if self.autodock:
                # it flies on into the slot (Brian: the station bigger before
                # the tunnel; the chase camera closes in meanwhile: cockpit.chase_back)
                if self.auto_phase == 2 and sp.d_station < st.bp.front - AUTO_IN:
                    if sp.hostile:
                        self._refused(sp, st)
                        return
                    self._docked()
                    return
            elif self.docking == "C":
                if sp.d_station < DOCK_DIST and self.bump_t <= 0:
                    if sp.hostile:
                        self._refused(sp, st)
                        return
                    self._docked()
                    return
            elif sp.d_station < CAPTURE_DIST:
                if self._approach(sp, st, dt):
                    return
        self._sun(sp, dt)
        if self.over:
            return
        if not self.god:
            if sp.px * sp.px + sp.py * sp.py + sp.pz * sp.pz < sp.pr * sp.pr:
                self._hurt(1e6)
                return

    def _sun(self, sp, dt):
        """The cabin temperature near the sun, and skimming fuel from it."""
        k = (sp.sx * sp.sx + sp.sy * sp.sy + sp.sz * sp.sz) / (sp.sr * sp.sr)
        t = 285.0 - SUN_HEAT * k
        self.cabin = int(t) if t > COOL_CABIN else COOL_CABIN
        if t > FATAL_CABIN:
            self.cabin = FATAL_CABIN
            if not self.god and not self.over:
                self._hurt(1e6)         # too hot: as Elite, the end
                return
        alt = math.sqrt(k) * sp.sr - sp.sr      # height above the surface
        low = self.cabin >= SCOOP_TEMP and alt <= SCOOP_ALT
        if not low:
            self.scooping = False       # out of the band: stops at once
            self.full_said = False
        self.sun_t -= dt
        if self.sun_t > 0:
            return
        self.sun_t = SUN_CHECK
        self.scooping = False
        if low and self.fuel_scoops and self.refuel is not None and not self.over:
            n = int(self.speed) // 8
            if n > 0 and self.refuel(n) > 0:
                self.scooping = True
                self.say("FUEL SCOOPS ON", 1.2)
                self.sfx("beep")    # Elite's message has a beep in it
            elif n > 0 and not self.full_said:
                self.full_said = True       # the tank is full: said once a pass (Brian, build 143)
                self.say("FUEL FULL", 2.0)

    def _refused(self, sp, st):
        """Docking at a hostile station: it fails, as in the original. At
        DEATH_SPEED or more you are killed; slower, a small dent, a sudden
        stop, and a bounce clear of it."""
        self.autodock = False
        self.tractor = False
        if self.speed >= DEATH_SPEED:
            self.say("STATION HOSTILE")
            self._hurt(1e6)
            if not self.over:       # invincible: bounce off instead
                self.speed = 0.0
            else:
                return
        else:
            self._hurt(SLOW_CRASH)
            self.say("DOCKING REFUSED")
            self.speed = 1.0
        self.bump_t = 1.0
        d = sp.d_station
        # clear of where it would try again (docking C docks anywhere within DOCK_DIST)
        out = (DOCK_DIST if self.docking == "C" else st.bp.front + PLAYER_R) + BOUNCE
        if d > 1.0:
            k = out / d - 1.0
            self._shift(st.x * k, st.y * k, st.z * k)
        else:
            self._shift(0.0, 0.0, out)
        self._measure()

    def _docked(self):
        self.docked = True
        self.autodock = False
        self.jumping = False
        self.tractor = False

    def _approach(self, sp, st, dt):
        """Docking A or B near the station: the tractor beam (B), and what
        touching the station does. Returns True if you docked."""
        d = sp.d_station
        m = st.m
        # where you are and which way you face, in the station's own terms
        # (x along its side, y its roof, z its nose, which the slot is on)
        lz = -(st.x * m[6] + st.y * m[7] + st.z * m[8])
        cone = lz / d if d > 1.0 else 1.0     # 1: straight out of the slot
        head = -m[8]                          # 1: flying straight into the slot
        slow = self.speed <= DOCK_SPEED
        if self.docking == "B":
            if self.tractor:
                if not slow or d > CAPTURE_DIST * 1.2:
                    self.tractor = False
                    self.say("TRACTOR LOST" if slow else "TOO FAST")
            elif slow and cone >= SLOT_CONE_B and head >= HEAD_B and not sp.hostile:
                self.tractor = True
                self.say("TRACTOR BEAM")
                self.sfx("tractor")
            if self.tractor and d > 1.0:
                # the slot swings round to face you and the station closes in
                ux, uy, uz = -st.x / d, -st.y / d, -st.z / d
                _turn(m, ux, uy, uz, PULL_TURN * dt)
                k = PULL * dt
                self._shift(ux * k, uy * k, uz * k)
                self._measure()
                d = sp.d_station
        front = st.bp.front
        if d >= front + PLAYER_R or self.bump_t > 0:
            return False
        if sp.hostile:          # checked first, as in the original (ISDK check 1)
            self._refused(sp, st)
            return False
        if self.docking == "A":
            ok = cone >= SLOT_CONE_A and head >= HEAD_A and abs(m[3]) >= LEVEL_A
        else:
            ok = cone >= SLOT_CONE_B and (self.tractor or head >= HEAD_B)
        if ok and slow:
            self._docked()
            return True
        # a crash: it hurts, and you bounce off
        self.say("TOO FAST" if ok else "STATION HIT")
        self._hurt(STATION_HIT + self.speed * 1.5)
        self.speed = 0.0
        self.tractor = False
        self.bump_t = 1.0
        if d > 1.0:
            k = (front + PLAYER_R + BOUNCE) / d - 1.0
            self._shift(st.x * k, st.y * k, st.z * k)
        else:
            self._shift(0.0, 0.0, front + PLAYER_R + BOUNCE)
        self._measure()
        return False

    # ---- the docking computer, ECM and energy bomb ------------------------

    def start_autodock(self):
        """Switch the docking computer on. Returns None, or why not."""
        sp = self.space
        if not self.computer:
            return "NO DOCKING COMPUTER"
        if sp is None or sp.station is None or not sp.safe or self.over:
            return "STATION TOO FAR"
        if sp.hostile:      # it would only fly you in to a refused docking
            return "STATION HOSTILE"
        self.set_view(0)        # it flies by the chase view, looking ahead
        self.autodock = True
        self.auto_phase = 0     # 0: round to the front, 1: out in front of the slot, 2: in
        self.auto_far = False
        self.auto_level = False  # matching the slot's roll
        self.jump_t = 0.0
        self.tractor = False
        self.say("DOCKING COMPUTER ON")
        return None

    def stop_autodock(self):
        if self.autodock:
            self.autodock = False
            self.say("DOCKING COMPUTER OFF")

    def _aim(self, x, y, z):
        """Stick to turn onto the point (x, y, z): roll it up (or down) over
        the crosshair, then pitch onto it. Returns (pitch, roll, off), off
        being the angle between the nose and the point (0: dead ahead)."""
        if y >= 0:
            phi = math.atan2(x, y)      # 0: straight above the crosshair
            up = 1.0
        else:
            phi = math.atan2(-x, -y)    # 0: straight below it
            up = -1.0
        off = math.atan2(math.sqrt(x * x + y * y), z)
        roll = max(-1.0, min(1.0, phi * 3.0)) if off > 0.02 else 0.0
        k = 1.0 if abs(phi) < 0.4 else 0.3
        return up * k * max(-1.0, min(1.0, off * 4.0)), roll, off

    def _autopilot(self):
        """The docking computer's stick and throttle, as the original's does
        it: first out to a point AUTO_LINE straight out from the slot (going
        round the side of the station if you are behind it), then turn onto
        the station and fly in along its axis, slowly, rolling to match the
        slot. Returns (pitch, roll, throttle)."""
        st = self.space.station
        m = st.m
        yaw = 0.0
        nx, ny, nz = m[6], m[7], m[8]       # the slot faces along the station's nose
        lz = -(st.x * nx + st.y * ny + st.z * nz)   # how far out in front of the slot you are
        line = AUTO_LINE + st.bp.front
        if self.auto_phase == 0:
            if lz >= line * 0.5:
                self.auto_phase = 1
            else:       # beside or behind: out to the side first
                px, py, pz = -st.x - nx * lz, -st.y - ny * lz, -st.z - nz * lz
                r = math.sqrt(px * px + py * py + pz * pz)
                if r < 1.0:
                    px, py, pz, r = m[0], m[1], m[2], 1.0
                k = line / r
                wx, wy, wz = st.x + px * k + nx * line * 0.6, st.y + py * k + ny * line * 0.6, \
                    st.z + pz * k + nz * line * 0.6
        if self.auto_phase == 1:
            wx, wy, wz = st.x + nx * line, st.y + ny * line, st.z + nz * line
        if self.auto_phase < 2:
            d = math.sqrt(wx * wx + wy * wy + wz * wz)
            if self.auto_phase == 1 and d < AUTO_NEAR:
                self.auto_phase = 2
            elif self.auto_phase == 0 and d < AUTO_NEAR:
                self.auto_phase = 1
        if self.auto_phase < 2:
            pitch, roll, off = self._aim(wx, wy, wz)
            self.auto_far = d > AUTO_FAST and off < 0.1
            if off > 0.5:
                want = DOCK_SPEED * 0.5
            else:       # slowing as the point comes up, so as to turn onto the station there
                want = max(DOCK_SPEED * 0.5, min(self.max_speed, d / 60.0))
        else:
            # in along the slot's axis (build 95, Brian: it "did not line up to the
            # face"): aim at a point on the axis AUTO_LEAD of the way from the
            # station's middle out to you, so any sideways offset dies away before
            # the face, rather than at the middle itself, which came in at a slant
            k = max(0.0, lz) * AUTO_LEAD
            ax, ay, az = st.x + nx * k, st.y + ny * k, st.z + nz * k
            pitch, roll, off = self._aim(ax, ay, az)
            self.auto_far = False
            if (off < 0.15 and self.space.d_station < st.bp.front + AUTO_LEVEL) or self.auto_level:
                # rolled to the slot, it can't roll onto the point any more: it
                # pitches and yaws onto it instead (yaw: build 95)
                if az > 1.0:
                    pitch = max(-1.0, min(1.0, math.atan2(ay, az) * 4.0))
                    yaw = max(-1.0, min(1.0, math.atan2(ax, az) * 4.0 * PITCH_RATE / YAW_RATE))
                # on the axis: roll to match the slot, from then on (its roof straight
                # across the screen), turning with the station as it spins
                a = math.atan2(m[4], m[3])
                if a > math.pi / 2:
                    a -= math.pi
                elif a < -math.pi / 2:
                    a += math.pi
                ff = AUTO_SPIN * STATION_SPIN / (ROLL_RATE * self.turn_k) if self.turn_k else 0.0
                roll = max(-1.0, min(1.0, -a * 3.0 + ff))
                self.auto_level = True
            want = DOCK_SPEED * 0.7
            if self.space.d_station < st.bp.front + AUTO_SLOW:
                want = DOCK_SPEED * AUTO_CRAWL      # the last stretch into the slot, slowly
        throttle = max(-1.0, min(1.0, (want - self.speed) * 0.5))
        self.auto_stick = (pitch, roll)     # for the view from behind your ship
        self.auto_yaw = yaw
        return pitch, roll, throttle

    def _ecm(self):
        """The ECM: every enemy missile about is destroyed."""
        n = 0
        for o in self.objs:
            if o.kind == "missile" and not o.dead:
                o.dead = True
                self._boom(o.x, o.y, o.z, 8)
                n += 1
        if n:
            self.ecm_t = 0.5
            self.shield = max(0.0, self.shield - ECM_COST)
            self.say("ECM")
            self.sfx("ecm")

    def fire_ecm(self):
        """The ECM key (Hardcore: the only way the ECM fires). A pulse destroys every enemy
        missile about and costs ECM_COST shield whether or not there was one. Returns True if
        it pulsed."""
        if self.over:
            return False
        if not self.ecm:
            self.say("NO ECM", 1.0)
            return False
        if self.ecm_t > 0:      # still pulsing
            return False
        for o in self.objs:
            if o.kind == "missile" and not o.dead:
                o.dead = True
                self._boom(o.x, o.y, o.z, 8)
        self.ecm_t = 0.5
        self.shield = max(0.0, self.shield - ECM_COST)
        self.say("ECM")
        self.sfx("ecm")
        return True

    def arm_missile(self):
        """Hardcore: arm a missile (T). The target then locks in the usual LOCK_TIME in the
        sights, and a fire (M or D) launches it. Returns True if armed."""
        if self.over:
            return False
        if self.missiles <= 0:
            self.say("NO MISSILES", 1.0)
            return False
        if not self.armed:
            self.armed = True
            self.lock = None
            self.lock_t = 0.0
            self.locked = False
            self.say("MISSILE ARMED", 1.0)
        return True

    def unarm_missile(self):
        """Hardcore: disarm the missile (U). The lock is lost."""
        if self.armed:
            self.armed = False
            self.lock = None
            self.lock_t = 0.0
            self.locked = False
            self.say("MISSILE SAFE", 1.0)
            self.sfx("unarm")       # Elite's long low beep

    def energy_bomb(self):
        """Set off the energy bomb, if there is one: every ship, missile and
        rock within BOMB_RANGE is destroyed. Returns True if it went off."""
        if self.bombs <= 0 or self.over:
            if not self.over:
                self.say("NO ENERGY BOMB")
            return False
        self.bombs -= 1
        self.bomb_t = 0.4
        r = BOMB_RANGE
        for o in self.objs:
            if (not o.dead and o.kind in ("ship", "missile", "pmissile", "rock")
                    and -r < o.x < r and -r < o.y < r and -r < o.z < r):
                if o.kind == "pmissile":
                    o.dead = True
                else:
                    self._kill(o)
        self.say("ENERGY BOMB")
        self.sfx("bomb")
        return True

    # ---- one step of the simulation ---------------------------------------

    def step(self, dt, pitch, roll, throttle, fire, missile, yaw=0.0):
        """Advance by dt seconds. pitch > 0 is nose up, roll > 0 is right wing
        down, throttle is -1..1; fire and missile are True or False. yaw > 0
        turns the nose right (a host's analogue pad; Elite and the badge have
        none, so it is 0 there and costs nothing)."""
        if dt > 0.1:
            dt = 0.1
        self.stick_pitch = pitch    # as given, for a dashboard's roll and dive meters
        self.stick_roll = roll
        self.time += dt
        if self.msg_t > 0:
            self.msg_t -= dt
        if self.flash > 0:
            self.flash -= dt
        if self.beam > 0:
            self.beam -= dt
        if self.warp > 0:
            self.warp -= dt
        if self.ecm_t > 0:
            self.ecm_t -= dt
        if self.bomb_t > 0:
            self.bomb_t -= dt
        if self.autodock:
            if self.over or self.space is None or not self.space.safe:
                self.autodock = False
            else:
                pitch, roll, throttle = self._autopilot()
                fire = missile = False
                yaw = self.auto_yaw
        if self.over:
            self.jump_t = 0.0
            pitch = roll = yaw = 0.0
            throttle = -1.0
            fire = missile = False

        self.speed += throttle * THROTTLE_RATE * dt
        if self.speed < 0.0:
            self.speed = 0.0
        elif self.speed > self.max_speed:
            self.speed = self.max_speed

        self.frame += 1
        fwd = self.speed * SPEED_K * dt
        sp = self.space
        # the jump drive: speed up held at full speed, with no ships about
        self.jumping = (sp is not None and not sp.witch and not self.over and throttle > 0
                        and self.speed >= self.max_speed and not sp.safe and self.jump_t <= 0
                        and self.cabin <= COOL_CABIN    # not near the sun
                        and not self._near()
                        and not self._massed(sp))
        if (sp is not None and not sp.witch and not self.over
                and throttle > 0 and self.speed >= self.max_speed and self.msg_t <= 0
                and not self.jumping and self._massed(sp)):
            self.say("MASS LOCKED", 1.0)
        if (sp is not None and not sp.witch and not self.over and throttle > 0
                and self.speed >= self.max_speed and not self.jumping and self.jump_t <= 0):
            why = self._blocker(sp)
            if why is not None and why != self.refused:
                self.sfx("boop")    # the jump drive refused: Elite's long low beep (WA1), once
            self.refused = why      # a hold, and again only for a new mass field (Brian, build 144)
        else:
            self.refused = None
        if not self.over:       # Elite: ENERGY LOW, with a beep, while the banks are low
            self.low_t -= dt
            if self.hull < ENERGY_LOW and self.low_t <= 0:
                self.say("ENERGY LOW", 1.5)
                self.sfx("beep")
                self.low_t = LOW_EVERY
        if self.jumping or (self.autodock and self.speed >= self.max_speed and self.auto_far):
            fwd *= JUMP_K
        self.fwd = int(fwd)
        self._rotate(pitch * PITCH_RATE * self.turn_k * dt, roll * ROLL_RATE * self.turn_k * dt, fwd)
        if yaw:
            self._yaw(yaw * YAW_RATE * self.turn_k * dt)
        for o in self.objs:
            if not o.dead:
                self._think(o, dt)
        self._booms(dt)
        if sp is not None:
            self._space(dt)
        if not self.over:
            self._collide()
            self._weapons(dt, fire, missile)
            self._regen(dt)
            self._director(dt)
            self._hyper(dt)

        if self.new:
            k = self.energy_k
            for o in self.new:      # the level makes ships tougher or weaker
                if o.kind == "ship" and not o.leveled:
                    o.leveled = True
                    o.energy *= k
                    o.max_energy = o.energy
            self.objs.extend(self.new)
            self.new = []
        self.objs = [o for o in self.objs if not o.dead]
        if self.lock is not None and self.lock.dead:
            self.lock = None
            self.locked = False

    def _rotate(self, a, b, fwd):
        """Steer: pitch everything by a, roll it by b, and slide it fwd closer.

        On the badge every float result is a new object for the garbage
        collector, and this touches every number of every object, so the
        turning is done in whole numbers: positions in quarter units and
        directions times 16384. Dust and explosion dots are whole numbers
        throughout."""
        ifwd = int(fwd)
        sp = self.space
        if a == 0.0 and b == 0.0:       # flying straight: no turning to work out
            if sp is not None:
                sp.pz -= fwd
                sp.sz -= fwd
                if sp.station is not None:
                    sp.station.z -= fwd
            for o in self.objs:
                o.z -= fwd
            if self.anchor is not None:
                self.anchor.z -= fwd
            for boom in self.booms:
                for p in boom.parts:
                    p[2] -= ifwd
            dx = self.dust_x
            for p in self.dust:
                p[2] -= ifwd
                if p[2] < 40:
                    p[0] = random.randint(-dx, dx)
                    p[1] = random.randint(-500, 500)
                    p[2] = random.randint(900, 1500)
            return
        # sines and cosines times 8192 (for positions) and 16384 (for directions)
        ca = round(math.cos(a) * 16384)
        dx = self.dust_x
        dx_far = dx * 7 // 5
        sa = round(math.sin(a) * 16384)
        cb = round(math.cos(b) * 16384)
        sb = round(math.sin(b) * 16384)
        ca2 = ca >> 1
        sa2 = sa >> 1
        cb2 = cb >> 1
        sb2 = sb >> 1
        if sp is not None:      # in floats: see Space
            fca = ca * _INV14
            fsa = sa * _INV14
            fcb = cb * _INV14
            fsb = sb * _INV14
            sp.px, sp.py, sp.pz = _rot3(sp.px, sp.py, sp.pz, fca, fsa, fcb, fsb)
            sp.pz -= fwd
            sp.sx, sp.sy, sp.sz = _rot3(sp.sx, sp.sy, sp.sz, fca, fsa, fcb, fsb)
            sp.sz -= fwd
            st = sp.station
            if st is not None:
                st.x, st.y, st.z = _rot3(st.x, st.y, st.z, fca, fsa, fcb, fsb)
                st.z -= fwd
                m = st.m
                for i in (0, 3, 6):
                    m[i], m[i + 1], m[i + 2] = _rot3(m[i], m[i + 1], m[i + 2],
                                                     fca, fsa, fcb, fsb)
        an = self.anchor
        if an is not None:
            # exact sines, not the rounded whole-number ones: those don't quite square
            # to 1, so what they turn slowly grows or shrinks (unseen alone, but two
            # badges' worlds would drift apart)
            fca = math.cos(a)
            fsa = math.sin(a)
            fcb = math.cos(b)
            fsb = math.sin(b)
            an.x, an.y, an.z = _rot3(an.x, an.y, an.z, fca, fsa, fcb, fsb)
            an.z -= fwd
            m = an.m
            for i in (0, 3, 6):
                m[i], m[i + 1], m[i + 2] = _rot3(m[i], m[i + 1], m[i + 2], fca, fsa, fcb, fsb)
            if self.tick % 32 == 0:
                _ortho(an.m)
        for o in self.objs:
            x = int(o.x * 4)
            y = int(o.y * 4)
            z = int(o.z * 4)
            y, z = (y * ca2 - z * sa2 + 4096) >> 13, (y * sa2 + z * ca2 + 4096) >> 13
            o.x = ((x * cb2 - y * sb2 + 4096) >> 13) * 0.25
            o.y = ((x * sb2 + y * cb2 + 4096) >> 13) * 0.25
            o.z = z * 0.25 - fwd
            m = o.m
            for i in (0, 3, 6):
                x = int(m[i] * 16384)
                y = int(m[i + 1] * 16384)
                z = int(m[i + 2] * 16384)
                y, z = (y * ca - z * sa + 8192) >> 14, (y * sa + z * ca + 8192) >> 14
                m[i] = ((x * cb - y * sb + 8192) >> 14) * _INV14
                m[i + 1] = ((x * sb + y * cb + 8192) >> 14) * _INV14
                m[i + 2] = z * _INV14
            v = o.aim
            if v is not None:
                x = int(v[0] * 16384)
                y = int(v[1] * 16384)
                z = int(v[2] * 16384)
                y, z = (y * ca - z * sa + 8192) >> 14, (y * sa + z * ca + 8192) >> 14
                v[0] = ((x * cb - y * sb + 8192) >> 14) * _INV14
                v[1] = ((x * sb + y * cb + 8192) >> 14) * _INV14
                v[2] = z * _INV14
        for boom in self.booms:
            for p in boom.parts:
                for i in (0, 3):
                    x = p[i]
                    y = p[i + 1]
                    z = p[i + 2]
                    y, z = (y * ca - z * sa + 8192) >> 14, (y * sa + z * ca + 8192) >> 14
                    p[i] = (x * cb - y * sb + 8192) >> 14
                    p[i + 1] = (x * sb + y * cb + 8192) >> 14
                    p[i + 2] = z
                p[2] -= ifwd
        for p in self.dust:
            x = p[0]
            y = p[1]
            z = p[2]
            y, z = (y * ca - z * sa + 8192) >> 14, (y * sa + z * ca + 8192) >> 14
            p[0] = (x * cb - y * sb + 8192) >> 14
            p[1] = (x * sb + y * cb + 8192) >> 14
            p[2] = z = z - ifwd
            if z < 40 or z > 1600 or abs(p[0]) > dx_far or abs(p[1]) > 700:
                p[0] = random.randint(-dx, dx)
                p[1] = random.randint(-500, 500)
                p[2] = random.randint(100, 1500)
        # the whole-number turning lets directions drift a little out of
        # true; ships are squared up by their own steering, so every so often
        # do the same for one of the things that just drift
        self.tick += 1
        n = len(self.objs)
        if n:
            o = self.objs[self.tick % n]
            if o.kind == "rock" or o.kind == "can":
                _ortho(o.m)

    def _yaw(self, c):
        """Turn the nose right by c radians: everything turns the other way
        about the up axis. In floats, as only a host with an analogue pad
        yaws (the badge's _rotate is whole numbers for its garbage collector).
        Whole-number things (dust, explosion dots) stay whole numbers."""
        cc = math.cos(c)
        sc = math.sin(c)

        def turn(x, z):
            return x * cc - z * sc, x * sc + z * cc

        sp = self.space
        if sp is not None:
            sp.px, sp.pz = turn(sp.px, sp.pz)
            sp.sx, sp.sz = turn(sp.sx, sp.sz)
            st = sp.station
            if st is not None:
                st.x, st.z = turn(st.x, st.z)
                m = st.m
                for i in (0, 3, 6):
                    m[i], m[i + 2] = turn(m[i], m[i + 2])
        an = self.anchor
        if an is not None:
            an.x, an.z = turn(an.x, an.z)
            m = an.m
            for i in (0, 3, 6):
                m[i], m[i + 2] = turn(m[i], m[i + 2])
        for o in self.objs:
            o.x, o.z = turn(o.x, o.z)
            m = o.m
            for i in (0, 3, 6):
                m[i], m[i + 2] = turn(m[i], m[i + 2])
            v = o.aim
            if v is not None:
                v[0], v[2] = turn(v[0], v[2])
        for boom in self.booms:
            for p in boom.parts:
                for i in (0, 3):
                    x, z = turn(p[i], p[i + 2])
                    p[i] = int(round(x))
                    p[i + 2] = int(round(z))
        for p in self.dust:
            x, z = turn(p[0], p[2])
            p[0] = int(round(x))
            p[2] = int(round(z))

    def _think(self, o, dt):
        if o.hit > 0:
            o.hit -= dt
        if o.beam > 0:
            o.beam -= dt
        m = o.m
        kind = o.kind
        if kind == "ship":
            # Steering is the costly part, and makes a lot of work for the
            # garbage collector, so a ship only re-plans every few frames,
            # for all the time since it last did. It still moves every frame.
            o.think_t += dt
            if (self.frame + o.slot) % THINK_EVERY:
                v = o.speed * SPEED_K * dt
                o.x += m[6] * v
                o.y += m[7] * v
                o.z += m[8] * v
                return
            dt = o.think_t
            o.think_t = 0.0
        d = math.sqrt(o.x * o.x + o.y * o.y + o.z * o.z)
        if d > DESPAWN:
            o.dead = True
            return
        if d < 1.0:
            d = 1.0
        if kind == "ship":
            bp = o.bp
            if o.state == "drift":      # a Thargon with no mothership: adrift
                o.speed = bp.speed * 0.25
                v = o.speed * SPEED_K * dt / THINK_EVERY
                o.x += m[6] * v
                o.y += m[7] * v
                o.z += m[8] * v
                return
            if bp.name == "THARGON" and not self._any_thargoid():
                o.state = "drift"       # half speed, aimless (TACTICS part 1)
                o.prey = None
                return
            if (o.has_pod and o.energy * 8 < o.max_energy and o.role != "constrictor"
                    and random.random() < POD_CHANCE):
                self._bail(o)           # out of energy and out of luck (TACTICS part 4)
                return
            if (o.role == "pirate" and self.space is not None and self.space.safe
                    and (o.state == "attack" or o.state == "break")):
                o.state = "patrol"      # near the station a pirate loses its nerve (TN3)
                o.prey = None
            prey = o.prey
            if prey is not None and (prey.dead or (o.state != "attack" and o.state != "break")):
                o.prey = prey = None
            if prey is None and o.role == "pirate" and o.state == "attack" and self.space is not None:
                prey = o.prey = self._pick_prey(o, d)
            if prey is not None:    # after a trader
                px, py, pz = prey.x - o.x, prey.y - o.y, prey.z - o.z
                dist = math.sqrt(px * px + py * py + pz * pz)
                if dist < 1.0:
                    dist = 1.0
                tx, ty, tz = px / dist, py / dist, pz / dist
            else:
                dist = d
                tx, ty, tz = -o.x / d, -o.y / d, -o.z / d   # direction to the player
            turn = TURN_RATE * dt
            want = bp.speed
            if o.state == "attack":
                if dist < BREAK_DIST:
                    o.state = "break"
                    o.t = _rnd(1.2, 2.4)
                    o.aim = list(_unit(_rnd(-1, 1) - tx * 0.5,
                                       _rnd(-1, 1) - ty * 0.5,
                                       _rnd(-1, 1) - tz * 0.5))
                else:
                    _turn(m, tx, ty, tz, turn)
                    want = bp.speed * 0.75
                    aim = m[6] * tx + m[7] * ty + m[8] * tz
                    o.cool -= dt
                    if prey is not None:
                        if (abs(px) < ENEMY_REACH and abs(py) < ENEMY_REACH and abs(pz) < ENEMY_REACH
                                and bp.laser and aim > 0.96 and o.cool <= 0):
                            o.cool = _rnd(0.5, 1.1)
                            if random.random() < 0.5:
                                prey.energy -= 3.0 + bp.laser * 2.5
                                prey.hit = 0.12
                                if prey.state == "trade":
                                    prey.state = "flee"     # running for it
                                if prey.energy <= 0:
                                    self._kill(prey, credit=False)
                    elif not self.over:
                        if (bp.laser and aim > 0.96 and o.cool <= 0 and abs(o.x) < ENEMY_REACH
                                and abs(o.y) < ENEMY_REACH and abs(o.z) < ENEMY_REACH):
                            o.cool = _rnd(0.5, 1.1)
                            o.beam = 0.2
                            if random.random() < min(0.7, 0.3 + 0.05 * self.wave) * self.aim_k:
                                self._hurt((3.0 + bp.laser * 2.5) * self.damage_k)
                        if o.role == "thargoid" and bp.name == "THARGOID":
                            # a Thargon instead of a missile, once below half energy
                            if (o.missiles and o.energy < o.max_energy * 0.5
                                    and random.random() < 0.5 * dt):
                                o.missiles -= 1
                                self._thargon(o)
                        elif (o.missiles and self.missile_bp and aim > 0.9
                                and random.random() < 0.12 * dt):
                            o.missiles -= 1
                            self._launch(o)
                    if o.energy < o.max_energy * 0.25:
                        o.state = "flee"
            elif o.state == "break":
                v = o.aim
                _turn(m, v[0], v[1], v[2], turn * 1.3)
                o.t -= dt
                if o.t <= 0:
                    o.state = "attack"
                    o.aim = None
            elif o.state == "trade" or o.state == "patrol":
                want = bp.speed * 0.6
                sp = self.space
                st = sp.station if sp is not None else None
                if o.state == "trade" and st is not None:
                    # on its way to the station (reaching it, it docks) or the planet
                    if o.dest == "station":
                        dx, dy, dz = st.x - o.x, st.y - o.y, st.z - o.z
                        reach = st.bp.front + bp.radius + 150
                    else:
                        dx, dy, dz = sp.px - o.x, sp.py - o.y, sp.pz - o.z
                        reach = sp.pr + bp.radius
                    ds = math.sqrt(dx * dx + dy * dy + dz * dz)
                    if ds < reach:
                        o.dead = True
                        return
                    if ds > 1.0:
                        _turn(m, dx / ds, dy / ds, dz / ds, turn * 0.5)
                if ((o.role == "police" or o.role == "hunter") and self.legal >= HUNT_LEGAL
                        and not self.over):
                    o.state = "attack"      # there's a price on your head (TN1)
                elif (o.role == "police" and self.stolen and not o.checked and d < SPOT_DIST
                      and sp is not None and sp.gov is not None and sp.gov >= LAWFUL_GOV
                      and not self.over):
                    o.checked = True        # one look at your ship
                    if random.random() < SPOT_CHANCE:
                        o.state = "attack"
                        self.say("STOLEN SHIP SPOTTED", 2.0)
                elif (0 < o.z < AVOID_AHEAD and o.x * o.x + o.y * o.y < (bp.radius + AVOID_SIDE) ** 2
                      or d < AVOID_DIST and m[6] * tx + m[7] * ty + m[8] * tz > 0):
                    # in your path, or coming your way: sideways out of it (not
                    # straight away from you, which is back down your path)
                    lx, ly = o.x, o.y
                    r = math.sqrt(lx * lx + ly * ly)
                    if r < 1.0:
                        lx, ly, r = m[0], m[1], math.sqrt(m[0] * m[0] + m[1] * m[1]) or 1.0
                    _turn(m, lx / r, ly / r, 0.0, turn * 2.5)
                    want = bp.speed
            else:   # flee
                _turn(m, -tx, -ty, -tz, turn)
            o.speed += (want - o.speed) * min(1.0, 2.0 * dt)
            v = o.speed * SPEED_K * dt / THINK_EVERY    # this frame's share
        elif kind == "missile":
            if self.ecm and d < ECM_RANGE and not self.over and not self.rules.manual_ecm:
                self._ecm()
                return
            o.t -= dt
            if o.t <= 0 or (d < 150 and not self.over):
                if o.t > 0:
                    self._hurt(30.0 * self.damage_k)
                self._boom(o.x, o.y, o.z, 8)
                self.sfx("crash")       # a missile exploding: Elite's EXNO3 (TA34)
                o.dead = True
                return
            _turn(m, -o.x / d, -o.y / d, -o.z / d, 2.2 * dt)
            v = MISSILE_SPEED * dt
        elif kind == "pmissile":
            o.t -= dt
            if o.t <= 0:
                self._boom(o.x, o.y, o.z, 8)
                self.sfx("crash")       # a missile exploding: Elite's EXNO3 (TA34)
                o.dead = True
                return
            t = o.target
            if t is not None and not t.dead:
                dx, dy, dz = t.x - o.x, t.y - o.y, t.z - o.z
                dd = math.sqrt(dx * dx + dy * dy + dz * dz)
                if t.ecm and dd < ECM_RANGE:     # its ECM destroys your missile
                    self._boom(o.x, o.y, o.z, 8)
                    o.dead = True
                    self.say("ECM")
                    self.sfx("ecm")
                    return
                if dd < t.bp.radius + 90:
                    self._boom(o.x, o.y, o.z, 8)
                    self.sfx("crash")   # a missile exploding: Elite's EXNO3 (TA34)
                    o.dead = True
                    self._provoke(t)
                    t.energy -= MISSILE_DAMAGE
                    t.hit = 0.2
                    if t.energy <= 0:
                        self._kill(t)
                    return
                _turn(m, dx / dd, dy / dd, dz / dd, 3.0 * dt)
            v = PMISSILE_SPEED * dt
        else:   # rocks and canisters drift and tumble
            if o.spin:
                _roll(m, o.spin * dt)
            v = o.speed * SPEED_K * dt
        o.x += m[6] * v
        o.y += m[7] * v
        o.z += m[8] * v

    def _launch(self, ship):
        o = Obj(self.missile_bp, "missile", ship.x, ship.y, ship.z)
        o.m = list(ship.m)
        o.t = 12.0
        self.new.append(o)
        self.say("INCOMING MISSILE")
        self.sfx("incoming")

    def _booms(self, dt):
        keep = False
        for boom in self.booms:
            boom.t += dt
            if boom.t < boom.life:
                keep = True
                k = int(dt * 1024)
                for p in boom.parts:
                    p[0] += (p[3] * k) >> 10
                    p[1] += (p[4] * k) >> 10
                    p[2] += (p[5] * k) >> 10
        if self.booms and not keep:
            self.booms = []
        elif self.booms:
            self.booms = [b for b in self.booms if b.t < b.life]

    def _boom(self, x, y, z, n):
        if len(self.booms) >= 4:
            self.booms.pop(0)
        self.booms.append(Boom(x, y, z, n, 350.0))

    def _collide(self):
        for o in self.objs:
            if o.dead or o.kind == "missile" or o.kind == "pmissile":
                continue
            r = o.bp.radius * 0.7 + 60.0
            if abs(o.z) > r:
                continue
            d2 = o.x * o.x + o.y * o.y + o.z * o.z
            if d2 >= r * r:
                continue
            # a canister is scooped, but only with fuel scoops and from below
            # (it passes under the ship), as in the original; otherwise it is
            # hit like anything else
            if (o.kind == "ship" and o.bp.name == "THARGON" and self.fuel_scoops and o.y < 0
                    and self.scoop is not None):
                o.kind = "can"          # scooped like cargo: alien items
                o.good = ALIEN_ITEMS
            if o.kind == "can" and (self.fuel_scoops and o.y < 0 or self.scoop is None):
                o.dead = True
                if self.scoop is None:      # practice: a pick-up instead of cargo
                    self.cargo += 1
                    self.score += 25
                    if o.upgrade:
                        self._upgrade()
                    else:
                        self._pickup()
                    continue
                # a canister holds one of the first SCOOP_GOODS goods, as in the
                # original; with no room for it, it is lost
                name = self.scoop(random.randrange(SCOOP_GOODS) if o.good is None else o.good)
                if name:
                    self.cargo += 1
                    self.score += 25
                    self.say(name)
                    self.sfx("scoop")
                else:
                    self._boom(o.x, o.y, o.z, 6)
                    self.say("HOLD FULL")
                    self.sfx("crash")   # a canister lost: Elite's EXNO3
                continue
            self.sfx("crash")
            self._hurt(10.0 + self.speed * 0.5)
            self.speed *= 0.4
            o.energy -= 60.0
            if o.energy <= 0:
                self._kill(o)
            else:   # bounce it clear
                d = math.sqrt(d2)
                if d < 1.0:
                    o.x, o.y, o.z = 0.0, 0.0, r + 150.0
                else:
                    s = (r + 150.0) / d
                    o.x *= s
                    o.y *= s
                    o.z *= s

    def _pickup(self):
        """Combat practice: a scooped canister recharges the shields, and
        sometimes holds a missile too (while there is room on the rack)."""
        self.shield = 100.0
        if (self.missile_bp and self.missiles < self.max_missiles
                and random.random() < self.pickup_missile):
            self.missiles += 1
            self.say("MISSILE + SHIELDS")
        else:
            self.say("SHIELDS RECHARGED")
        self.sfx("scoop")

    def _upgrade(self):
        """Combat practice: an upgrade canister fits the next of UPGRADES (and
        fills the shields); after the last, a used energy bomb comes back,
        else the shields are filled. With auto_missile (no missile button) it
        also fills the missile rack (Brian, build 113)."""
        self.shield = 100.0
        self.sfx("upgrade")
        if self.auto_missile and self.missile_bp:
            self.missiles = self.max_missiles
        if self.upgrade_n < len(UPGRADES):
            u = UPGRADES[self.upgrade_n]
            self.upgrade_n += 1
            if u == "beam" or u == "military":
                self.set_laser(u)
            elif u == "energy unit":
                self.energy_unit = True
            elif u == "bomb":
                self.bombs = 1
            self.say(UPGRADE_NAMES[u] + " FITTED", 2.5)
        elif self.bombs == 0:
            self.bombs = 1
            self.say("ENERGY BOMB FITTED", 2.5)
        else:
            self.say("SHIELDS RECHARGED")

    def _pick(self, cone):
        """The ship nearest the crosshair, within the given slope of it."""
        best = None
        best_r = cone * cone
        for o in self.objs:
            if o.kind != "ship" or o.dead or o.z < 100:
                continue
            r = (o.x * o.x + o.y * o.y) / (o.z * o.z)
            if r < best_r:
                best = o
                best_r = r
        return best

    def _weapons(self, dt, fire, missile):
        """Aim and fire through the current view: the world is turned into it
        for the picking and the shots, and back again before anything is
        added that is in the front's frame (the missile)."""
        self.enter_view()
        try:
            launch = self._weapons_view(dt, fire, missile)
        finally:
            self.leave_view()
        if launch is not None:
            o = Obj(self.missile_bp, "pmissile", 0.0, -40.0, 80.0)     # straight ahead, whichever view
            o.target = launch
            o.t = 8.0
            self.new.append(o)
            self.say("MISSILE AWAY", 1.0)
            self.sfx("missile")

    def _weapons_view(self, dt, fire, missile):
        self.heat -= LASER_COOL * dt
        if self.heat < 0:
            self.heat = 0.0
        if self.hot and self.heat < 0.5:
            self.hot = False
        self.cool -= dt
        if self.looking:        # Elite skips missile and laser locking off a space view (MA15)
            t = self._pick(0.35) if (self.armed or not self.rules.missile_lock_required) else None
            if t is None or t is not self.lock:    # a new ship, or none: start again
                self.lock = t
                self.lock_t = 0.0
                self.locked = False
            elif not self.locked:
                self.lock_t += dt
                if self.lock_t >= (AUTO_LOCK_TIMES[self.level] if self.auto_missile else LOCK_TIME):
                    self.locked = True
                    self.sfx("lock")

        if fire and self.laser is None:
            if self.msg_t <= 0:
                self.say("NO LASER", 1.0)
            fire = False
        if fire and not self.hot and self.laser in CONTINUOUS:
            self.beam = max(self.beam, 0.1)     # a steady beam while fire is held
        if fire and not self.hot and self.cool <= 0:
            self.cool = self.laser_period
            self.beam = 0.07
            self.heat += self.laser_heat
            self.sfx("laser")
            if self.heat >= 1.0:
                self.heat = 1.0
                self.hot = True
                self.say("LASER OVERHEAT")
                self.sfx("overheat")
            best = None
            best_z = LASER_RANGE
            for o in (self.objs if self.looking else ()):   # off a space view: no hits
                if o.dead or o.kind == "pmissile" or o.z <= 30 or o.z >= best_z or o.upgrade:
                    continue    # (a practice upgrade canister can't be shot)
                lim = o.z * AIM_ASSIST
                lim *= lim
                if lim < o.bp.area:
                    lim = o.bp.area
                if o.x * o.x + o.y * o.y < lim:
                    best = o
                    best_z = o.z
            if best is None and self.space is not None and self.looking:
                self._hit_station()
            if best is not None and best.role == "constrictor" and self.laser != "military":
                self._provoke(best)     # its shields shrug off anything but a military laser
                best = None
            if best is not None:
                self._provoke(best)
                best.energy -= self.laser_damage * (CONSTRICTOR_LASER
                                                    if best.role == "constrictor" else 1)
                best.hit = 0.12
                if best.energy <= 0:
                    self._kill(best, self.laser == "mining")
                else:
                    self.sfx("hit")     # a strike that didn't kill (Elite's EXNO)

        if (self.auto_missile and self.locked and self.missiles > 0 and self.lock is not None
                and self.lock is not self.auto_done and not self.lock.dead
                and not fire and self.beam <= 0):
            missile = True      # no missile button: one goes at each locked ship, once the
            self.auto_done = self.lock      # laser has stopped (Brian, build 112)
        if missile and self.missiles > 0:
            t = self.lock
            if self.rules.missile_lock_required and not self.armed:
                self.say("MISSILE NOT ARMED", 1.0)
            elif t is None or t.dead:
                self.say("NO TARGET", 1.0)
            elif not self.locked:
                self.say("NO LOCK", 1.0)
            else:
                self.missiles -= 1
                self.armed = False      # each missile is armed afresh (Hardcore)
                return t                # the caller launches it
        return None

    def release_canister(self, dist=700.0):
        """A cheat: a cargo canister just ahead, a little below the
        crosshair, drifting towards you. Returns it, or None if there are
        already as many objects as there can be."""
        if self.can_bp is None or len(self.objs) + len(self.new) >= MAX_OBJECTS:
            return None
        c = Obj(self.can_bp, "can", 0.0, -30.0, dist)
        _look(c.m, 0.0, 0.0, -1.0)
        c.speed = 3.0
        c.spin = _rnd(-2, 2)
        self.new.append(c)
        return c

    def _bail(self, o):
        """Ship o's crew launch their escape pod: it flies off, and the ship
        is left adrift (no one aboard: it neither fights nor flees)."""
        o.has_pod = False
        o.state = "drift"
        o.prey = None
        o.beam = 0.0
        bp = self.types.get("ESCAPE POD")
        if bp is None or len(self.objs) + len(self.new) >= MAX_OBJECTS:
            return None
        dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-1, 1), _rnd(-1, 1))
        p = Obj(bp, "can", o.x + dx * 120, o.y + dy * 120, o.z + dz * 120)
        _look(p.m, dx, dy, dz)
        p.speed = bp.speed
        p.spin = _rnd(-2, 2)
        p.good = SLAVES         # scooped: a tonne of slaves, as the original
        self.new.append(p)
        return p

    def release_pod(self, dist=700.0):
        """A cheat: an escape pod just ahead, as release_canister does."""
        bp = self.types.get("ESCAPE POD")
        if bp is None or len(self.objs) + len(self.new) >= MAX_OBJECTS:
            return None
        p = Obj(bp, "can", 0.0, -30.0, dist)
        _look(p.m, 0.0, 0.0, -1.0)
        p.speed = 3.0
        p.spin = _rnd(-2, 2)
        p.good = SLAVES
        self.new.append(p)
        return p

    def bail_nearest(self):
        """A cheat: the nearest ship with an escape pod bails out now.
        Returns the pod, or None."""
        best = None
        for o in self.objs:
            if o.kind == "ship" and o.has_pod and not o.dead and o.state != "drift":
                if best is None or o.x * o.x + o.y * o.y + o.z * o.z < \
                        best.x * best.x + best.y * best.y + best.z * best.z:
                    best = o
        return self._bail(best) if best is not None else None

    def _kill(self, o, mine=False, credit=True):
        """o is destroyed. mine: by the mining laser, so a rock breaks into
        splinters you can scoop for minerals. credit False: not by you (a
        pirate got a trader), so no kill, bounty or crime, but its cargo
        still spills."""
        if o.dead:
            return
        o.dead = True
        bp = o.bp
        self._boom(o.x, o.y, o.z, 8 + 2 * min(bp.explosions, 6))
        self.sfx("explode")
        if o.role == "constrictor":
            self.got_constrictor = True
        if credit:
            self.bounty += bp.bounty    # tenths of a credit (the police and most traders: none)
            if o.role == "police":
                self._crime(KILL_COP)   # you shot the sheriff
        if o.kind == "ship" and not credit:
            self._spill(o)
        elif o.kind == "ship":
            self.kills += 1
            self.wave_kills += 1
            self.score += 10 + bp.bounty // 5
            self._spill(o)
            if self.space is None and self.wave_kills >= 2 + self.wave:     # practice only
                self.wave += 1
                self.wave_kills = 0
                if self.missile_bp and self.missiles < self.max_missiles:
                    self.missiles += 1
                if self.practice_upgrades:
                    c = self.release_canister(UPGRADE_AHEAD)    # just ahead: easy to pick up
                    self.wave_shown = 0
                    if c is not None:
                        c.upgrade = True    # (it can't be shot: see _weapons_view)
                        self.wave_hold = UPGRADE_WAIT   # the countdown once it's collected
                        self.say("UPGRADE AHEAD", 2.5)
                    else:
                        self.wave_wait = WAVE_WAIT      # a breather, counted down (_director)
                else:
                    self.say("WAVE %d" % self.wave, 2.5)
            elif self.kills % 8 == 0:
                self.say("RIGHT ON COMMANDER!", 2.5)
        elif o.kind == "missile":
            self.score += 5
        elif o.kind == "rock":
            self.score += 2
            if mine:
                self._splinters(o)

    def _spill(self, o):
        """A destroyed ship's cargo: up to two canisters."""
        bp = o.bp
        if self.can_bp and bp.canisters:
            for _ in range(random.randint(0, min(bp.canisters, 2))):
                c = Obj(self.can_bp, "can", o.x + _rnd(-80, 80),
                        o.y + _rnd(-80, 80), o.z + _rnd(-80, 80))
                dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-1, 1), _rnd(-1, 1))
                _look(c.m, dx, dy, dz)
                c.speed = _rnd(1, 4)
                c.spin = _rnd(-2, 2)
                self.new.append(c)

    def _splinters(self, rock):
        """A rock broken up by the mining laser: an asteroid into two or three
        splinters, a boulder into one or two, each holding minerals."""
        bp = self.types.get("SPLINTER") or self.can_bp
        if bp is None:
            return
        n = random.randint(2, 3) if rock.bp.name == "ASTEROID" else random.randint(1, 2)
        for _ in range(n):
            if len(self.objs) + len(self.new) >= MAX_OBJECTS:
                return
            c = Obj(bp, "can", rock.x + _rnd(-60, 60), rock.y + _rnd(-60, 60),
                    rock.z + _rnd(-60, 60))
            dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-1, 1), _rnd(-1, 1))
            _look(c.m, dx, dy, dz)
            c.speed = _rnd(1, 3)
            c.spin = _rnd(-2, 2)
            c.good = MINERALS
            self.new.append(c)

    def _hurt(self, damage):
        if self.over:
            return
        if self.flash <= 0.1:   # (not again on every frame of a long hit)
            # lasers on the shields, or Elite's crash sound with none left (EXNO3)
            self.sfx("hurt" if self.shield > 0 else "crash")
        self.flash = 0.3
        if self.god:
            return
        self.since_hit = 0.0
        damage /= self.tough        # a bigger ship's shields and hull soak up more (set_ship)
        s = damage if damage < self.shield else self.shield
        self.shield -= s
        self.hull -= damage - s
        if self.hull <= 0:
            self.hull = 0.0
            self.over = True
            self.autodock = False
            self.lock = None
            self.locked = False
            self._boom(0.0, 0.0, 150.0, 20)
            self.sfx("die")
            if self.pod and self.space is not None and self.space.witch:
                self.pod = False        # no station to reach from witchspace
                self.say("GAME OVER", 1e9)
            elif self.pod:      # the escape pod gets away; the ship and its cargo are lost
                self.pod = False
                self.ejected = True
                self.say("ESCAPE POD LAUNCHED", 1e9)
            else:
                self.say("GAME OVER", 1e9)

    def eject(self):
        """Launch the escape pod by choice (Elite's ESCAPE key, Brian): the ship
        is lost as if destroyed and you wake up docked (ace.py does that, as
        for a pod launched as the ship dies). Not from witchspace: there is no
        station to reach. Returns True if it went."""
        if self.over:
            return False
        if not self.pod:
            self.say("NO ESCAPE POD", 1.0)
            return False
        if self.space is not None and self.space.witch:
            self.say("NO STATION IN RANGE", 1.0)
            return False
        self.over = True
        self.autodock = False
        self.lock = None
        self.locked = False
        self._boom(0.0, 0.0, 150.0, 20)
        self.pod = False
        self.ejected = True
        self.say("ESCAPE POD LAUNCHED", 1e9)
        return True

    def _regen(self, dt):
        self.since_hit += dt
        if self.since_hit > 3.0:
            k = (NAVY_UNIT if self.navy else ENERGY_UNIT) * dt if self.energy_unit else dt
            if self.shield < 100.0:
                self.shield = min(100.0, self.shield + 4.0 * k)
            if self.hull < 100.0:
                self.hull = min(100.0, self.hull + 0.8 * k)

    # ---- legal status -----------------------------------------------------

    def legal_name(self):
        return legal_name(self.legal)

    def _crime(self, bits):
        """OR bits into the legal status, as the original does with FIST;
        say so if that makes it worse."""
        before = legal_name(self.legal)
        self.legal = (self.legal | int(bits)) & 255
        now = legal_name(self.legal)
        if now != before:
            self.say(now, 2.5)

    def anger_station(self):
        """The station turns hostile (AN2): it refuses docking and sends
        police after you, until you leave its safe zone. Its tractor beam
        lets go and the docking computer switches off and won't start (in
        the original the computer flew you in to a refused docking)."""
        sp = self.space
        if sp is not None and not sp.hostile:
            sp.hostile = True
            self.tractor = False        # no help from it now
            self.autodock = False       # nor from the docking computer
            self.say("STATION HOSTILE", 2.5)

    def _provoke(self, o):
        """You fired on o (ANGRY). A trader, a hunter or the police turns on
        you (one without a laser runs). Firing on an innocent trader makes
        the station hostile; your record is unchanged."""
        if o.kind != "ship":
            return
        o.prey = None           # whatever it was after, now it's after you
        if o.state == "trade" or o.state == "patrol":
            o.state = "attack" if o.bp.laser else "flee"
        if o.role == "trader":
            self.anger_station()

    def _pick_prey(self, o, d):
        """The trader pirate o should go for instead of you: the nearest one
        to it, if nearer than you and within PREY_RANGE; else None."""
        best = None
        best_d2 = min(d, PREY_RANGE)
        best_d2 *= best_d2
        for t in self.objs:
            if t.role == "trader" and not t.dead and t.kind == "ship":
                dx, dy, dz = t.x - o.x, t.y - o.y, t.z - o.z
                d2 = dx * dx + dy * dy + dz * dz
                if d2 < best_d2:
                    best = t
                    best_d2 = d2
        return best

    def _hit_station(self):
        """A shot that hit nothing else: did it hit the station? Then the
        station is hostile."""
        st = self.space.station
        if st is None or st.z <= 0 or st.z > LASER_RANGE:
            return
        r = st.bp.radius
        if st.x * st.x + st.y * st.y < r * r:
            self.anger_station()

    def illegal_cargo(self, cargo):
        """Launching with these goods (tonnes by good number): their weight
        (BAD) is ORed into the legal status, as in the original."""
        w = bad(cargo)
        self.bad = w
        if w and (self.legal | w) != self.legal:
            self._crime(w)
            self.say("ILLEGAL CARGO", 2.5)

    def _count(self, role):
        n = 0
        for o in self.objs:
            if o.kind == "ship" and not o.dead and o.role == role:
                n += 1
        return n

    def _station_ships(self, dt):
        """What the station launches, in or out of the safe zone (TACTICS for
        the station): police after you while it is hostile, and otherwise a
        Shuttle or Transporter now and then."""
        sp = self.space
        if sp.station is None or sp.d_station > DESPAWN * 0.6:
            return
        self.station_t -= dt
        if self.station_t > 0:
            return
        self.station_t = 1.0
        if len(self.objs) + len(self.new) >= MAX_OBJECTS:
            return
        if sp.hostile:      # these are coming for you: they don't wait for a clear slot
            if self._count("police") < STATION_COPS and random.random() < STATION_COP_CHANCE:
                self.add_police(True, True)
        elif random.random() < SHUTTLE_CHANCE and self._slot_clear():
            for o in self.objs:
                if o.role == "trader" and o.bp.name in SHUTTLES and not o.dead:
                    return
            self.add_shuttle()

    def _slot_clear(self):
        """True if a ship can come out of the station's slot without flying
        into you: the docking computer isn't bringing you in and you aren't
        lined up in front of the slot (SLOT_CLEAR, SLOT_CLEAR_CONE)."""
        if self.autodock:
            return False
        sp = self.space
        st = sp.station
        d = sp.d_station
        m = st.m
        lz = -(st.x * m[6] + st.y * m[7] + st.z * m[8])     # how far out in front of the slot
        return not (0 < lz < SLOT_CLEAR + st.bp.front and lz > d * SLOT_CLEAR_CONE)

    def _tick(self, hostile, count):
        """Once every ENCOUNTER_EVERY seconds outside the safe zone: maybe a
        trader, maybe the police, maybe pirates (main game loop parts 2 to 4)."""
        if random.random() < BENIGN:
            if random.random() < 0.5 and count < MAX_OBJECTS - 2:
                self.add_trader()
            return
        cops = self._count("police")
        t = min(255, 2 * self.bad)
        if cops:
            t |= self.legal
        if random.random() * 256 < t and count < MAX_OBJECTS - 1:
            self.add_police(False)
            cops += 1
        if cops:
            return
        if self.plans and random.random() < PLANS_THARGOID:
            self.add_thargoid()     # they know you have the plans
        if hostile == 0 and self.pending == 0:
            self._encounter()

    def add_trader(self, dest=None):
        """A trader somewhere round you, making for the station or the
        planet (dest, or either at random)."""
        names = [n for n in TRADERS if n in self.types]
        if not names:
            return None
        o = self._spawn_ship(self.types[random.choice(names)])
        o.role = "trader"
        o.state = "trade"
        o.dest = dest or random.choice(("station", "planet"))
        o.speed = o.bp.speed * 0.6
        sp = self.space
        st = sp.station if sp is not None else None
        if st is not None:      # facing where it is going, not you
            if o.dest == "station":
                dx, dy, dz = _unit(st.x - o.x, st.y - o.y, st.z - o.z)
            else:
                dx, dy, dz = _unit(sp.px - o.x, sp.py - o.y, sp.pz - o.z)
            _look(o.m, dx, dy, dz)
        else:
            dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-0.3, 0.3), _rnd(-1, 1))
            _look(o.m, dx, dy, dz)
        return o

    def add_hunter(self):
        """A bounty hunter round you: after you if you are wanted, else flying by."""
        names = [n for n in HUNTERS if n in self.types]
        if not names:
            return None
        o = self._spawn_ship(self.types[random.choice(names)])
        o.role = "hunter"
        o.state = "attack" if self.legal >= HUNT_LEGAL else "patrol"
        return o

    def _from_station(self, bp):
        """A ship launched out of the station's slot, heading out."""
        st = self.space.station
        m = st.m
        k = st.bp.front + bp.radius + 100
        o = Obj(bp, "ship", st.x + m[6] * k, st.y + m[7] * k, st.z + m[8] * k)
        _look(o.m, m[6], m[7], m[8])
        o.speed = bp.speed
        self.new.append(o)
        return o

    def add_shuttle(self):
        """A Shuttle or Transporter out of the station, making for the planet."""
        names = [n for n in SHUTTLES if n in self.types]
        sp = self.space
        if not names or sp is None or sp.station is None:
            return None
        o = self._from_station(self.types[random.choice(names)])
        o.role = "trader"
        o.state = "trade"
        o.dest = "planet"
        o.speed = o.bp.speed * 0.6
        return o

    def add_police(self, hunt, station=False):
        """A police Viper: out of the station's slot (station, and it is near
        enough), or arriving near you. hunt: after you; otherwise after you
        only if your legal status is HUNT_LEGAL or more (they are bounty
        hunters too), and on patrol until then."""
        bp = self.types.get(POLICE)
        if bp is None:
            return None
        sp = self.space
        st = sp.station if sp is not None else None
        if station and st is not None and sp.d_station < DESPAWN * 0.6:
            o = self._from_station(bp)
        else:
            o = self._spawn_ship(bp)
        o.role = "police"
        hunt = hunt or self.legal >= HUNT_LEGAL
        o.state = "attack" if hunt else "patrol"
        if hunt:
            self.say("POLICE", 1.5)
        return o

    # ---- what turns up ----------------------------------------------------

    def _director(self, dt):
        hostile = 0
        for o in self.objs:
            if o.kind == "ship" and (o.state == "attack" or o.state == "break") and not o.dead:
                hostile += 1
        count = len(self.objs) + len(self.new)
        if self.space is not None:
            self._encounters(dt, hostile, count)
            return
        if self.wave_hold > 0:      # the upgrade canister not yet collected: nobody new comes
            self.wave_hold -= dt
            waiting = False
            for o in self.objs:
                if o.upgrade and not o.dead:
                    waiting = True
                    break
            if waiting and self.wave_hold > 0:
                return
            for o in self.objs:     # collected, or too long: any left goes, the countdown starts
                if o.upgrade:
                    o.dead = True
            self.wave_hold = 0.0
            self.wave_wait = WAVE_WAIT
            self.wave_shown = 0
        if self.wave_wait > 0:      # the countdown to the next wave: nobody new comes
            self.wave_wait -= dt
            if self.wave_wait <= 0:
                self.wave_wait = 0.0
                self.spawn_t = 0.0
                self.say("WAVE %d" % self.wave, 2.0)
                self.sfx("wave")
            else:
                n = int(self.wave_wait) + 1
                if n != self.wave_shown:
                    self.wave_shown = n
                    self.say("WAVE %d IN %d" % (self.wave, n), 1.2)
                    self.sfx("tick")
                return
        self.spawn_t -= dt
        # more ships at once in later waves, and the longer the game goes on
        want = min(self.max_hostile, 1 + (self.wave + int(self.time / 60)) // 2)
        if self.spawn_t <= 0 and hostile < want and count < MAX_OBJECTS:
            self.spawn_t = _rnd(2.0, 5.0)
            self._spawn_ship()
        self.rock_t -= dt
        if self.rock_t <= 0:
            self.rock_t = _rnd(9, 18)
            if count < MAX_OBJECTS - 3:
                self._spawn_rocks()

    def _encounters(self, dt, hostile, count):
        """In a star system ships come in groups, a while apart, and none
        come near the station. The group's ships turn up a second or so
        apart."""
        if self.space.witch:    # nothing turns up in witchspace: the Thargoids are already here
            return
        self._station_ships(dt)
        if self.space.safe:
            self.pending = 0
            return
        if self.hunt and self.con_wait is not None and not self._any(CONSTRICTOR):
            self.con_t += dt
            if self.con_t >= self.con_wait and self.add_constrictor() is not None:
                self.con_t = 0.0
        if self.pending > 0:
            self.spawn_t -= dt
            if self.spawn_t <= 0 and count < MAX_OBJECTS:
                self.spawn_t = _rnd(0.8, 2.0)
                name = self.group.pop(0) if self.group else None
                o = self._spawn_ship(self.types.get(name))
                if o is None:
                    self.pending = 0
                    self.group = []
                else:
                    self.pending -= 1
                    if self.group_role == "constrictor":
                        self._make_constrictor(o)
                    elif self.group_role == "hunter" and self.orarra:
                        o.role = "hunter"
                        o.state = "attack"      # nasty, in the Constrictor's system
                    elif self.group_role == "hunter":
                        o.role = "hunter"
                        # after serious offenders and fugitives; flies by the rest (TN1)
                        o.state = "attack" if self.legal >= HUNT_LEGAL else "patrol"
        self.encounter_t -= dt
        if self.encounter_t <= 0:
            self.encounter_t = ENCOUNTER_EVERY
            self._tick(hostile, count)
        self.rock_t -= dt
        if self.rock_t <= 0:
            self.rock_t = _rnd(9, 18)
            if count < MAX_OBJECTS - 3:
                self._spawn_rocks()

    def _encounter(self):
        """Every ENCOUNTER_EVERY seconds: maybe pirates or a bounty hunter,
        more likely the more dangerous the government (see ENCOUNTER_EVERY)."""
        if self.skip > 0:
            self.skip -= 1
            return
        gov = self.space.gov
        if gov is None:
            gov = 3
        if gov != 0:
            if random.random() >= PIRATE_ROLL or random.randint(0, 7) < gov:
                return
        if random.random() < HUNTER_CHANCE:
            self.skip = 1
            if self.hunt and not self._any(CONSTRICTOR) and CONSTRICTOR in self.types:
                self._new_group([CONSTRICTOR], "constrictor")
            else:
                self._new_group([random.choice(HUNTERS)], "hunter")
        else:
            n = min(random.randint(1, PACK_MOST), self.max_hostile)
            self.skip = n - 1
            self._new_group([self._pirate() for _ in range(n)])

    @staticmethod
    def _pirate():
        """A pirate ship's name: smaller ones more often (two random bytes
        ANDed together, as in the original)."""
        return PIRATES[random.randint(0, 255) & random.randint(0, 255) & 7]

    def _new_group(self, names, role="pirate"):
        self.group_role = role
        self.group = list(names)
        self.pending = len(names)
        self.spawn_t = 0.0

    def _pick_type(self):
        top = min(len(TIERS) - 1, self.wave // 2)
        t = int(random.random() * random.random() * (top + 1))
        while t >= 0:
            names = [n for n in TIERS[t] if n in self.types]
            if names:
                return self.types[random.choice(names)]
            t -= 1
        if self.fallback:
            return random.choice(self.fallback)
        return None

    def _spawn_ship(self, bp=None):
        """A ship of type bp (or picked by wave) somewhere round you."""
        if bp is None:
            bp = self._pick_type()
        if bp is None:
            return None
        if random.random() < 0.7:   # usually somewhere ahead
            dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-0.6, 0.6), _rnd(0.4, 1))
        else:
            dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-1, 1), _rnd(-1, 1))
        d = _rnd(6000, 9000)
        o = Obj(bp, "ship", dx * d, dy * d, dz * d)
        _look(o.m, -dx, -dy, -dz)
        o.speed = bp.speed * 0.5
        self.new.append(o)
        return o

    def _spawn_rocks(self):
        names = [n for n in ROCKS if n in self.types]
        if not names:
            return
        for _ in range(random.randint(1, 3)):
            bp = self.types[random.choice(names)]
            x, y, z = _rnd(-2500, 2500), _rnd(-1500, 1500), _rnd(5000, 8000)
            o = Obj(bp, "rock", x, y, z)
            dx, dy, dz = _unit(_rnd(-600, 600) - x, _rnd(-400, 400) - y, -z)
            _look(o.m, dx, dy, dz)
            o.speed = _rnd(3, 10)
            o.spin = _rnd(-1.5, 1.5)
            self.new.append(o)
