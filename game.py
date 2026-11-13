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
LASER_DAMAGE = 12.0
LASER_PERIOD = 0.18    # seconds between shots
LASER_HEAT = 0.05      # heat added per shot (1.0 = overheated)
LASER_COOL = 0.16      # heat lost per second
AIM_ASSIST = 0.05      # a shot hits anything within this slope of the crosshair

MISSILE_DAMAGE = 150.0
JUMP_COUNT = 5.0           # seconds of countdown before a hyperspace jump
DOCK_TIME = 3.0            # seconds between the last ship going and being docked
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

# What the level changes: (most hostile ships at once, how often enemy lasers
# hit compared with level 1, how much damage they and their missiles do
# compared with level 1). Level 1 is the game as it was before levels.
LEVELS = (
    (3, 0.7, 0.7),
    (4, 1.0, 1.0),
    (5, 1.3, 1.3),
)


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


class Game:
    def __init__(self, ships, level=1):
        self.set_level(level)
        self.god = False    # a cheat: hits flash but do no damage
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
        self.missiles = 4 if self.missile_bp else 0
        self.kills = 0
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
        # After a jump there is no station to fly to yet, so you are docked
        # once the ships that meet you are dealt with.
        self.arriving = None   # ships still to destroy before docking; None: not arriving
        self.dock_t = 0.0      # > 0 while "docking" counts down
        self.docked = False    # set when it has; whoever is watching takes over
        self.again = "C: fly again"     # what C does on the GAME OVER screen

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
        self.objs = []
        self.new = []
        self.booms = []
        self.lock = None
        self.lock_t = 0.0
        self.locked = False
        self.beam = 0.0
        self.warp = WARP_TIME
        self.jumped = True
        self.spawn_t = _rnd(5.0, 8.0)   # a quiet moment on arriving
        self.arriving = self.max_hostile    # as many ships as can attack at once
        self.dock_t = 0.0
        self.rock_t = _rnd(6, 12)
        self.msg_t = 0.0

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
        self._rotate(pitch * PITCH_RATE * dt, roll * ROLL_RATE * dt, self.speed * SPEED_K * dt)
        for o in self.objs:
            if not o.dead:
                self._think(o, dt)
        self._booms(dt)
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
        if a == 0.0 and b == 0.0:       # flying straight: no turning to work out
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
            if o.kind == "can":
                o.dead = True
                self.cargo += 1
                self.score += 25
                self.say("CARGO SCOOPED")
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
            self.cool = LASER_PERIOD
            self.beam = 0.07
            self.heat += LASER_HEAT
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
                best.energy -= LASER_DAMAGE
                best.hit = 0.12
                if best.energy <= 0:
                    self._kill(best)

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

    def _kill(self, o):
        if o.dead:
            return
        o.dead = True
        bp = o.bp
        self._boom(o.x, o.y, o.z, 8 + 2 * min(bp.explosions, 6))
        if o.kind == "ship":
            self.kills += 1
            self.wave_kills += 1
            if self.arriving:
                self.arriving -= 1
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
            if self.wave_kills >= 2 + self.wave:
                self.wave += 1
                self.wave_kills = 0
                if self.missile_bp and self.missiles < 4:
                    self.missiles += 1
                self.say("WAVE %d" % self.wave, 2.5)
            elif self.kills % 8 == 0:
                self.say("RIGHT ON COMMANDER!", 2.5)
        elif o.kind == "missile":
            self.score += 5
        elif o.kind == "rock":
            self.score += 2

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
            self.lock = None
            self.locked = False
            self._boom(0.0, 0.0, 150.0, 20)
            self.say("GAME OVER", 1e9)

    def _regen(self, dt):
        self.since_hit += dt
        if self.since_hit > 3.0:
            if self.shield < 100.0:
                self.shield = min(100.0, self.shield + 4.0 * dt)
            if self.hull < 100.0:
                self.hull = min(100.0, self.hull + 0.8 * dt)

    # ---- what turns up ----------------------------------------------------

    def _director(self, dt):
        hostile = 0
        for o in self.objs:
            if o.kind == "ship" and o.state != "flee" and not o.dead:
                hostile += 1
        count = len(self.objs) + len(self.new)
        self.spawn_t -= dt
        # more ships at once in later waves, and the longer the game goes on
        want = min(self.max_hostile, 1 + (self.wave + int(self.time / 60)) // 2)
        if self.arriving is not None:
            want = min(self.max_hostile, max(want, 2))
            if self.arriving <= 0:      # no more come; dock when the last has gone
                want = 0
                if hostile == 0:
                    if self.dock_t <= 0:
                        self.dock_t = DOCK_TIME
                        self.say("ALL CLEAR: DOCKING", DOCK_TIME)
                    else:
                        self.dock_t -= dt
                        if self.dock_t <= 0:
                            self.dock_t = 0.0
                            self.arriving = None
                            self.docked = True
        if self.spawn_t <= 0 and hostile < want and count < MAX_OBJECTS:
            self.spawn_t = _rnd(2.0, 5.0)
            self._spawn_ship()
        self.rock_t -= dt
        if self.rock_t <= 0:
            self.rock_t = _rnd(9, 18)
            if count < MAX_OBJECTS - 3:
                self._spawn_rocks()

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

    def _spawn_ship(self):
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
