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

SPEED_K = 25.0         # world units per second for one Elite speed unit
PLAYER_MAX = 40.0      # top speed, in Elite speed units
THROTTLE_RATE = 25.0   # speed units gained per second at full throttle
PITCH_RATE = 1.0       # radians per second at full stick
ROLL_RATE = 1.7

LASER_RANGE = 7000.0
LASER_COOL = 0.16      # heat lost per second
# the front laser, by type: (seconds between shots, damage a hit, heat a shot
# (1.0 = overheated)). The beam laser fires twice as fast and heats faster;
# the military laser hits harder too (Elite's power 23 against the pulse
# laser's 15). The mining laser fires like the pulse laser, a little harder, and
# breaks rocks into splinters you can scoop (see Game._kill).
LASERS = {
    "pulse": (0.18, 12.0, 0.05),
    "beam": (0.09, 12.0, 0.04),
    "military": (0.09, 18.0, 0.045),
    "mining": (0.18, 15.0, 0.05),
}
ENERGY_UNIT = 2.0      # an energy unit makes the shields and hull recharge this much faster
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
AIM_ASSIST = 0.05      # a shot hits anything within this slope of the crosshair

MISSILE_DAMAGE = 150.0
JUMP_COUNT = 5.0           # seconds of countdown before a hyperspace jump
WARP_TIME = 1.2            # seconds the streaks last on arriving
LOCK_TIME = 2.0            # seconds a ship must stay in the sights before a missile locks
MISSILE_SPEED = 1100.0     # world units per second
PMISSILE_SPEED = 1700.0
TURN_RATE = 1.1            # how fast enemy ships can turn, radians per second
BREAK_DIST = 900.0         # enemies peel away when this close
FIRE_RANGE = 5500.0
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
SCOOP_TEMP = 224
SUN_CHECK = 1.0

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
MAX_MISSILES = 4       # missiles the player's ship carries
PICKUP_MISSILE = 0.5   # combat practice: how often a canister holds a missile as well

# What the level changes: (most hostile ships at once, how often enemy lasers
# hit compared with level 1, how much damage they and their missiles do
# compared with level 1). Level 1 is the game as it was before levels.
LEVELS = (
    (3, 0.7, 0.7),
    (4, 1.0, 1.0),
    (5, 1.3, 1.3),
)


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
    """One ship type from ship_data.py."""

    def __init__(self, entry):
        self.name = entry[0]
        self.verts = entry[1]
        self.edges = entry[2]
        self.normals = entry[3]
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
        self.state = "attack"   # ships: "attack", "break" or "flee"
        self.t = 0.0
        self.cool = _rnd(0.5, 2.0)
        self.spin = 0.0
        self.aim = None     # [dx, dy, dz] heading used while breaking away
        self.target = None  # what a player missile is chasing
        self.good = None    # a splinter: the good it holds (a canister: None, any of several)
        self.missiles = bp.missiles
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
        self.sun = 2            # which colour the sun is (cockpit.SUN_COLOURS): yellow
        self.planet = 0         # and the planet (cockpit.PLANET_COLOURS): blue
        self.d_station = 1e9    # distance to the station
        self.safe_r = radius * SAFE_K   # the safe zone round the station
        self.safe = False       # within it


class Game:
    def __init__(self, ships, level=1):
        self.set_level(level)
        self.god = False    # a cheat: hits flash but do no damage
        self.docking = "C"  # how docking works: see set_docking
        self.set_laser("pulse")
        self.energy_unit = False    # recharge ENERGY_UNIT times faster
        self.fuel_scoops = True     # without them a canister is hit, not scooped
        self.ecm = False            # fires by itself at incoming missiles
        self.pod = False            # an escape pod: being destroyed isn't the end
        self.bombs = 0              # energy bombs (one at most, used once)
        self.computer = False       # a docking computer
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
        self.missile_bp = self.types.get("MISSILE")
        self.can_bp = self.types.get("CANISTER")
        tiered = set()
        for tier in TIERS:
            tiered.update(tier)
        # used if none of the named enemy ships are in the ship data
        self.fallback = [bp for bp in self.types.values()
                         if bp.laser and bp.speed and bp.name not in tiered]
        self.reset()

    def set_docking(self, style):
        """"A" authentic, "B" assisted or "C" automatic (commander.DOCKING)."""
        self.docking = style if style in ("A", "B", "C") else "C"
        self.tractor = False

    def set_laser(self, kind):
        """The front laser: a key of LASERS."""
        self.laser = kind if kind in LASERS else "pulse"
        self.laser_period, self.laser_damage, self.laser_heat = LASERS[self.laser]

    def set_level(self, level):
        """0 easiest to 2 hardest. Takes effect straight away."""
        self.level = max(0, min(len(LEVELS) - 1, int(level)))
        self.max_hostile, self.aim_k, self.damage_k = LEVELS[self.level]

    def reset(self):
        self.objs = []
        self.new = []      # objects created during a step, added at its end
        self.booms = []
        self.tick = 0
        self.frame = 0
        # dust and explosion dots are whole numbers: see _rotate
        self.dust = [[random.randint(-500, 500), random.randint(-500, 500),
                      random.randint(100, 1500)] for _ in range(10)]
        self.speed = 14.0
        self.shield = 100.0
        self.hull = 100.0
        self.heat = 0.0
        self.hot = False       # laser overheated
        self.cool = 0.0
        self.beam = 0.0        # > 0 while the player's laser is drawn
        self.missiles = MAX_MISSILES if self.missile_bp else 0
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
        self.over = False
        self.msg = "WAVE 1"
        self.msg_t = 2.5
        self.lock = None       # the ship in the missile sights
        self.lock_t = 0.0      # how long it has been there
        self.locked = False    # long enough: a missile can be fired at it
        self.jump_t = 0.0      # > 0 while the hyperspace countdown runs
        self.warp = 0.0        # > 0 while the streaks of a jump are drawn
        self.jumped = False    # set when a jump happens; whoever started it clears it
        self.space = None      # the star system (Space), or None: open space, waves of ships
        self.jumping = False   # the jump drive is on
        self.fwd = 0           # how far everything slid towards you last step (whole units)
        self.pending = 0       # ships of the current encounter still to turn up
        self.group = []        # their types (names), in the order they come
        self.encounter_t = 0.0  # time until the next roll for an encounter
        self.skip = 0          # rolls still to skip after the last encounter
        self.docked = False    # set on reaching the station; whoever is watching takes over
        self.cabin = COOL_CABIN  # the cabin temperature, 30 in deep space to 255
        self.scooping = False  # skimming fuel from the sun just now
        self.sun_t = SUN_CHECK  # time to the next fuel scoop
        self.tractor = False   # docking B: the station is drawing you in
        self.bump_t = 0.0      # > 0 just after hitting the station (no second hit meanwhile)
        self.again = "C: fly again"     # what C does on the GAME OVER screen
        self.ejected = False   # destroyed, but the escape pod got away: whoever is watching docks you
        self.ecm_t = 0.0       # > 0 just after the ECM fired
        self.bomb_t = 0.0      # > 0 just after the energy bomb went off
        self.autodock = False  # the docking computer is flying
        self.auto_phase = 0    # where it has got to: see start_autodock
        self.auto_far = False  # it is far from where it is heading: the jump drive's speed
        self.auto_level = False  # it is matching the slot's roll
        self.auto_stick = (0.0, 0.0)    # its last pitch and roll

    def say(self, msg, t=2.0):
        self.msg = msg
        self.msg_t = t

    # ---- hyperspace -------------------------------------------------------

    def start_jump(self):
        """Start (or restart) the countdown to a hyperspace jump. Where the
        jump goes is the caller's business: it watches for self.jumped."""
        if not self.over:
            self.jump_t = JUMP_COUNT
            self.say("HYPERSPACE %d" % int(JUMP_COUNT), 1.5)

    def _hyper(self, dt):
        if self.jump_t <= 0:
            return
        before = int(self.jump_t + 0.999)
        self.jump_t -= dt
        if self.jump_t > 0:
            left = int(self.jump_t + 0.999)
            if left != before:
                self.say("HYPERSPACE %d" % left, 1.5)
            return
        # the jump: everything here is left behind
        self.jump_t = 0.0
        self.autodock = False   # a new system: the docking computer is off
        self.objs = []
        self.new = []
        self.booms = []
        self.lock = None
        self.lock_t = 0.0
        self.locked = False
        self.beam = 0.0
        self.warp = WARP_TIME
        self.jumped = True
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
        self.autodock = False
        self.auto_phase = 0
        self.auto_level = False
        self.encounter_t = ENCOUNTER_EVERY
        self.skip = 0
        if self.msg == "WAVE 1":    # waves are for combat practice only
            self.msg_t = 0.0
        self._measure()

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
        sp.safe = sp.d_station < sp.safe_r

    def _near(self):
        """True if a ship or missile is within radar range. In comparisons
        only, so no new numbers are made."""
        r = RADAR_RANGE
        for o in self.objs:
            if ((o.kind == "ship" or o.kind == "missile") and -r < o.x < r
                    and -r < o.y < r and -r < o.z < r):
                return True
        return False

    def _space(self, dt):
        """The station turns; reaching it docks you, and flying into the
        planet or the sun is the end."""
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
                if self.auto_phase == 2 and sp.d_station < st.bp.front + PLAYER_R + 60.0:
                    self._docked()
                    return
            elif self.docking == "C":
                if sp.d_station < DOCK_DIST:
                    self._docked()
                    return
            elif sp.d_station < CAPTURE_DIST:
                if self._approach(sp, st, dt):
                    return
        self._sun(sp, dt)
        if not self.god:
            for x, y, z, r in ((sp.px, sp.py, sp.pz, sp.pr), (sp.sx, sp.sy, sp.sz, sp.sr)):
                if x * x + y * y + z * z < r * r:
                    self._hurt(1e6)
                    return

    def _sun(self, sp, dt):
        """The cabin temperature near the sun, and skimming fuel from it."""
        k = (sp.sx * sp.sx + sp.sy * sp.sy + sp.sz * sp.sz) / (sp.sr * sp.sr)
        t = 285.0 - SUN_HEAT * k
        self.cabin = int(t) if t > COOL_CABIN else COOL_CABIN
        if self.cabin > 255:
            self.cabin = 255
        if self.cabin < SCOOP_TEMP:
            self.scooping = False       # out of the band: stops at once
        self.sun_t -= dt
        if self.sun_t > 0:
            return
        self.sun_t = SUN_CHECK
        self.scooping = False
        if (self.cabin >= SCOOP_TEMP and self.fuel_scoops and self.refuel is not None
                and not self.over):
            n = int(self.speed) // 8
            if n > 0 and self.refuel(n) > 0:
                self.scooping = True
                self.say("FUEL SCOOPS ON", 1.2)

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
            elif slow and cone >= SLOT_CONE_B and head >= HEAD_B:
                self.tractor = True
                self.say("TRACTOR BEAM")
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
                want = max(DOCK_SPEED * 0.5, min(PLAYER_MAX, d / 60.0))
        else:
            pitch, roll, off = self._aim(st.x, st.y, st.z)
            self.auto_far = False
            if (off < 0.15 and self.space.d_station < st.bp.front + AUTO_LEVEL) or self.auto_level:
                # on the axis: roll to match the slot, from then on (its roof straight across the screen)
                a = math.atan2(m[4], m[3])
                if a > math.pi / 2:
                    a -= math.pi
                elif a < -math.pi / 2:
                    a += math.pi
                roll = max(-1.0, min(1.0, -a * 3.0))
                self.auto_level = True
            want = DOCK_SPEED * 0.7
        throttle = max(-1.0, min(1.0, (want - self.speed) * 0.5))
        self.auto_stick = (pitch, roll)     # for the view from behind your ship
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
        return True

    # ---- one step of the simulation ---------------------------------------

    def step(self, dt, pitch, roll, throttle, fire, missile):
        """Advance by dt seconds. pitch > 0 is nose up, roll > 0 is right wing
        down, throttle is -1..1; fire and missile are True or False."""
        if dt > 0.1:
            dt = 0.1
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
        if self.over:
            self.jump_t = 0.0
            pitch = roll = 0.0
            throttle = -1.0
            fire = missile = False

        self.speed += throttle * THROTTLE_RATE * dt
        if self.speed < 0.0:
            self.speed = 0.0
        elif self.speed > PLAYER_MAX:
            self.speed = PLAYER_MAX

        self.frame += 1
        fwd = self.speed * SPEED_K * dt
        sp = self.space
        # the jump drive: speed up held at full speed, with no ships about
        self.jumping = (sp is not None and not self.over and throttle > 0
                        and self.speed >= PLAYER_MAX and not sp.safe and self.jump_t <= 0
                        and self.cabin <= COOL_CABIN    # not near the sun
                        and not self._near())
        if self.jumping or (self.autodock and self.speed >= PLAYER_MAX and self.auto_far):
            fwd *= JUMP_K
        self.fwd = int(fwd)
        self._rotate(pitch * PITCH_RATE * dt, roll * ROLL_RATE * dt, fwd)
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
            for boom in self.booms:
                for p in boom.parts:
                    p[2] -= ifwd
            for p in self.dust:
                p[2] -= ifwd
                if p[2] < 40:
                    p[0] = random.randint(-500, 500)
                    p[1] = random.randint(-500, 500)
                    p[2] = random.randint(900, 1500)
            return
        # sines and cosines times 8192 (for positions) and 16384 (for directions)
        ca = round(math.cos(a) * 16384)
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
            if z < 40 or z > 1600 or abs(p[0]) > 700 or abs(p[1]) > 700:
                p[0] = random.randint(-500, 500)
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
            tx, ty, tz = -o.x / d, -o.y / d, -o.z / d   # direction to the player
            turn = TURN_RATE * dt
            want = bp.speed
            if o.state == "attack":
                if d < BREAK_DIST:
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
                    if not self.over and d < FIRE_RANGE:
                        if bp.laser and aim > 0.96 and o.cool <= 0:
                            o.cool = _rnd(0.5, 1.1)
                            o.beam = 0.2
                            if random.random() < min(0.7, 0.3 + 0.05 * self.wave) * self.aim_k:
                                self._hurt((3.0 + bp.laser * 2.5) * self.damage_k)
                        if (o.missiles and self.missile_bp and aim > 0.9
                                and random.random() < 0.12 * dt):
                            o.missiles -= 1
                            self._launch(o)
                    if o.energy < bp.energy * 0.25:
                        o.state = "flee"
            elif o.state == "break":
                v = o.aim
                _turn(m, v[0], v[1], v[2], turn * 1.3)
                o.t -= dt
                if o.t <= 0:
                    o.state = "attack"
                    o.aim = None
            else:   # flee
                _turn(m, -tx, -ty, -tz, turn)
            o.speed += (want - o.speed) * min(1.0, 2.0 * dt)
            v = o.speed * SPEED_K * dt / THINK_EVERY    # this frame's share
        elif kind == "missile":
            if self.ecm and d < ECM_RANGE and not self.over:
                self._ecm()
                return
            o.t -= dt
            if o.t <= 0 or (d < 150 and not self.over):
                if o.t > 0:
                    self._hurt(30.0 * self.damage_k)
                self._boom(o.x, o.y, o.z, 8)
                o.dead = True
                return
            _turn(m, -o.x / d, -o.y / d, -o.z / d, 2.2 * dt)
            v = MISSILE_SPEED * dt
        elif kind == "pmissile":
            o.t -= dt
            if o.t <= 0:
                self._boom(o.x, o.y, o.z, 8)
                o.dead = True
                return
            t = o.target
            if t is not None and not t.dead:
                dx, dy, dz = t.x - o.x, t.y - o.y, t.z - o.z
                dd = math.sqrt(dx * dx + dy * dy + dz * dz)
                if dd < t.bp.radius + 90:
                    self._boom(o.x, o.y, o.z, 8)
                    o.dead = True
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
            if o.kind == "can" and (self.fuel_scoops and o.y < 0 or self.scoop is None):
                o.dead = True
                if self.scoop is None:      # practice: a pick-up instead of cargo
                    self.cargo += 1
                    self.score += 25
                    self._pickup()
                    continue
                # a canister holds one of the first SCOOP_GOODS goods, as in the
                # original; with no room for it, it is lost
                name = self.scoop(random.randrange(SCOOP_GOODS) if o.good is None else o.good)
                if name:
                    self.cargo += 1
                    self.score += 25
                    self.say(name)
                else:
                    self._boom(o.x, o.y, o.z, 6)
                    self.say("HOLD FULL")
                continue
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
        if (self.missile_bp and self.missiles < MAX_MISSILES
                and random.random() < PICKUP_MISSILE):
            self.missiles += 1
            self.say("MISSILE + SHIELDS")
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
        self.heat -= LASER_COOL * dt
        if self.heat < 0:
            self.heat = 0.0
        if self.hot and self.heat < 0.5:
            self.hot = False
        self.cool -= dt
        t = self._pick(0.35)
        if t is None or t is not self.lock:    # a new ship, or none: start again
            self.lock = t
            self.lock_t = 0.0
            self.locked = False
        elif not self.locked:
            self.lock_t += dt
            if self.lock_t >= LOCK_TIME:
                self.locked = True

        if fire and not self.hot and self.cool <= 0:
            self.cool = self.laser_period
            self.beam = 0.07
            self.heat += self.laser_heat
            if self.heat >= 1.0:
                self.heat = 1.0
                self.hot = True
                self.say("LASER OVERHEAT")
            best = None
            best_z = LASER_RANGE
            for o in self.objs:
                if o.dead or o.kind == "pmissile" or o.z <= 30 or o.z >= best_z:
                    continue
                lim = o.z * AIM_ASSIST
                lim *= lim
                if lim < o.bp.area:
                    lim = o.bp.area
                if o.x * o.x + o.y * o.y < lim:
                    best = o
                    best_z = o.z
            if best is not None:
                best.energy -= self.laser_damage
                best.hit = 0.12
                if best.energy <= 0:
                    self._kill(best, self.laser == "mining")

        if missile and self.missiles > 0:
            t = self.lock
            if t is None or t.dead:
                self.say("NO TARGET", 1.0)
            elif not self.locked:
                self.say("NO LOCK", 1.0)
            else:
                self.missiles -= 1
                o = Obj(self.missile_bp, "pmissile", 0.0, -40.0, 80.0)
                o.target = t
                o.t = 8.0
                self.new.append(o)
                self.say("MISSILE AWAY", 1.0)

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

    def _kill(self, o, mine=False):
        """o is destroyed. mine: by the mining laser, so a rock breaks into
        splinters you can scoop for minerals."""
        if o.dead:
            return
        o.dead = True
        bp = o.bp
        self._boom(o.x, o.y, o.z, 8 + 2 * min(bp.explosions, 6))
        self.bounty += bp.bounty    # tenths of a credit; rocks have small ones too
        if o.kind == "ship":
            self.kills += 1
            self.wave_kills += 1
            self.score += 10 + bp.bounty // 5
            if self.can_bp and bp.canisters:
                for _ in range(random.randint(0, min(bp.canisters, 2))):
                    c = Obj(self.can_bp, "can", o.x + _rnd(-80, 80),
                            o.y + _rnd(-80, 80), o.z + _rnd(-80, 80))
                    dx, dy, dz = _unit(_rnd(-1, 1), _rnd(-1, 1), _rnd(-1, 1))
                    _look(c.m, dx, dy, dz)
                    c.speed = _rnd(1, 4)
                    c.spin = _rnd(-2, 2)
                    self.new.append(c)
            if self.space is None and self.wave_kills >= 2 + self.wave:     # practice only
                self.wave += 1
                self.wave_kills = 0
                if self.missile_bp and self.missiles < MAX_MISSILES:
                    self.missiles += 1
                self.say("WAVE %d" % self.wave, 2.5)
            elif self.kills % 8 == 0:
                self.say("RIGHT ON COMMANDER!", 2.5)
        elif o.kind == "missile":
            self.score += 5
        elif o.kind == "rock":
            self.score += 2
            if mine:
                self._splinters(o)

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
        self.flash = 0.3
        if self.god:
            return
        self.since_hit = 0.0
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
            if self.pod:        # the escape pod gets away; the ship and its cargo are lost
                self.pod = False
                self.ejected = True
                self.say("ESCAPE POD LAUNCHED", 1e9)
            else:
                self.say("GAME OVER", 1e9)

    def _regen(self, dt):
        self.since_hit += dt
        if self.since_hit > 3.0:
            k = ENERGY_UNIT * dt if self.energy_unit else dt
            if self.shield < 100.0:
                self.shield = min(100.0, self.shield + 4.0 * k)
            if self.hull < 100.0:
                self.hull = min(100.0, self.hull + 0.8 * k)

    # ---- what turns up ----------------------------------------------------

    def _director(self, dt):
        hostile = 0
        for o in self.objs:
            if o.kind == "ship" and o.state != "flee" and not o.dead:
                hostile += 1
        count = len(self.objs) + len(self.new)
        if self.space is not None:
            self._encounters(dt, hostile, count)
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
        if self.space.safe:
            self.pending = 0
            return
        if self.pending > 0:
            self.spawn_t -= dt
            if self.spawn_t <= 0 and count < MAX_OBJECTS:
                self.spawn_t = _rnd(0.8, 2.0)
                name = self.group.pop(0) if self.group else None
                if self._spawn_ship(self.types.get(name)) is None:
                    self.pending = 0
                    self.group = []
                else:
                    self.pending -= 1
        elif hostile == 0:
            self.encounter_t -= dt
            if self.encounter_t <= 0:
                self.encounter_t = ENCOUNTER_EVERY
                self._roll()
        self.rock_t -= dt
        if self.rock_t <= 0:
            self.rock_t = _rnd(9, 18)
            if count < MAX_OBJECTS - 3:
                self._spawn_rocks()

    def _roll(self):
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
            self._new_group([random.choice(HUNTERS)])
        else:
            n = min(random.randint(1, PACK_MOST), self.max_hostile)
            self.skip = n - 1
            self._new_group([self._pirate() for _ in range(n)])

    @staticmethod
    def _pirate():
        """A pirate ship's name: smaller ones more often (two random bytes
        ANDed together, as in the original)."""
        return PIRATES[random.randint(0, 255) & random.randint(0, 255) & 7]

    def _new_group(self, names):
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
