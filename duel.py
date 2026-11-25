"""A duel (plans/MULTIPLAYER.md): two players in combat practice's arena with no
other ships, each seeing the other's ship in its owner's paint with their name.
Rules only: the radio is a link the platform gives (platform.radio(), e.g.
net_espnow.Link on the badge):

    link.id          this device's id (bytes), the same on every packet it sends
    link.send(msg)   send bytes to everyone listening
    link.recv()      (sender id, bytes) for the next packet heard, or (None, None)

The lobby (Brian, 2026-11-25): everyone on the DUEL page says HELLO a few times a
second with their commander's name, ship colour (cockpit.SHIP_COLOURS) and what
they are doing: in the LOBBY, HOSTing a game, JOINing one, or FLYING. One player
hosts; another joins that host; the host sees who joined and starts: START goes
to the guest (a few times, in case one is lost) and both fly at once, the host
from START[0], the guest from START[1], 8000 apart and facing. In flight each
sends its pose (netplay.py) SEND_HZ times a second; the other's ship (kind
"player") is drawn where its last pose and speed put it now. Nothing heard for
LOST seconds: "LINK LOST", the ship goes until it comes back. Combat: see HIT_PKT
below; the ECM is by hand; the score shows when either is destroyed. Either player
leaving (END, or GONE_END seconds unheard) ends the game for both: back to the
lobby, which says why.
"""
import struct

from . import game, netplay

HELLO = 2
START_PKT = 3
END_PKT = 4                 # leaving the duel (sent END_TIMES times: one may be lost)
END_TIMES = 3
# combat (Brian, 2026-11-25: lasers, missiles, ramming; the ECM by hand). Who decides:
# a laser hit, the shooter (HIT: damage times 16); a missile, its target, whose game flies
# it as an enemy missile (MISSILE: number, where and which way it was launched; it says
# GONE when it hit or its ECM got it; the shooter shows a harmless copy till then);
# ramming, each game for its own ship. Missile packets go AGAIN times (one may be lost).
HIT_PKT = 5
HIT_FMT = "<2sBBH"
MISSILE_PKT = 6
MISSILE_FMT = "<2sBBiiihhh"
GONE_PKT = 7
GONE_FMT = "<2sBBB"
GONE_HIT, GONE_ECM = 1, 2
AGAIN = 3
# rounds (Brian, 2026-11-25): the one destroyed presses C for the next round; NEXT (its
# number, sent AGAIN times) puts both back at their ends with a fresh loadout
NEXT_PKT = 8
NEXT_FMT = "<2sBBH"
BEAM_CONE = 0.98            # their laser drawn at you when their nose is this close to you
# MAGIC, kind, role, colour, flags, target id (6 bytes; the host's for JOIN, the guest's
# for HOST and START), name (16 bytes, ASCII, padded with spaces)
FMT = "<2sBBBB6s16s"
LOBBY, HOST, JOIN, FLYING = 0, 1, 2, 3
NO_ID = b"\x00" * 6
HELLO_EVERY = 0.25          # seconds between HELLOs on the DUEL page
FLY_HELLO_EVERY = 1.0       # and in flight (the lobby sees who is busy)
START_FOR = 1.0             # the host repeats START this long, every START_EVERY
START_EVERY = 0.1
SEND_HZ = 15                # poses a second in flight (the link test's rate)
LOST = 3.0                  # seconds without a packet: the other player is gone
GONE_END = 10.0             # this long without the other player: the game ends ("... LOST")
NOTICE_FOR = 4.0            # seconds the lobby shows why a duel ended
GONE = 3.0                  # on the page: seconds without a HELLO before they leave the list
NAME_LEN = 16
# where each side starts in the shared world: (x, y, z, nose x, y, z); host 0, guest 1.
# 8000 apart (Brian, 2026-11-25: 2000 started too close): as far as practice's ships
# come in (6000-9000), on the radar (10000), facing
START_Z = 4000.0
START = ((0.0, 0.0, -START_Z, 0.0, 0.0, 1.0), (0.0, 0.0, START_Z, 0.0, 0.0, -1.0))
START_SPEED = 14.0          # as a new flight (Game.reset)


def start_pose(slot):
    """(x, y, z, axes) for a starting slot: level, nose along the given way."""
    x, y, z, nx, ny, nz = START[slot]
    m = [0.0] * 9
    game._look(m, nx, ny, nz)
    return x, y, z, m


def _name_bytes(name):
    b = bytes(ord(c) if 32 <= ord(c) < 127 else 63 for c in str(name).upper()[:NAME_LEN])
    return b + b" " * (NAME_LEN - len(b))


def colour_rgb(i):
    """A ship colour number as drawn (cockpit.ship_rgb)."""
    from . import cockpit
    return cockpit.ship_rgb(i)


class Player:
    """Someone heard: their name, colour, what they are doing, and for whom."""

    def __init__(self, ident):
        self.id = ident
        self.name = "?"
        self.colour = 0
        self.role = LOBBY
        self.target = NO_ID
        self.t = 0.0        # seconds since last heard


class Duel:
    def __init__(self, link, name="JAMESON", colour=0):
        self.link = link
        self.name = "JAMESON"
        self.colour = 0
        self.set_me(name, colour)
        self.role = LOBBY       # what we are doing: LOBBY, HOST or JOIN
        self.players = {}       # id -> Player, everyone heard lately
        self.other = None       # the Player we duel: the guest (hosting) or the host (joining)
        self.go = False         # START said (by us as host, or to us as guest): fly
        self.slot = 0
        self.flying = False
        self.hello_t = 0.0
        self.start_t = 0.0      # host: how long START is still repeated
        self.start_gap = 0.0
        self.buf = bytearray(netplay.SIZE)     # made once: no garbage per packet
        self.hello = bytearray(struct.calcsize(FMT))
        self.seq = 0
        self.send_t = 0.0
        self.ship = None        # the other player's ship (an Obj, kind "player")
        self.pose_m = [0.0] * 9     # their last axes (filled by read_pose)
        self.pose = None        # (x, y, z, speed) of their last pose
        self.pose_age = 0.0     # seconds since that pose
        self.last_seq = None
        self.lost = False
        self.g = None           # the Game while flying (hits and missiles arrive any time)
        self.missile_n = 0      # numbers for our missiles
        self.ghosts = {}        # number -> our missile's harmless copy, till they say GONE
        self.incoming = {}      # number -> their missile, flown here at us
        self.seen_missiles = []     # numbers already launched here (repeats ignored)
        self.flags = 0          # their last pose's flags (netplay.FIRING, DEAD)
        self.dead_here = False  # we are destroyed (counted once)
        self.kills = 0          # times we destroyed them, and they us, this duel
        self.deaths = 0
        self.round = 1
        self.pkt = bytearray(struct.calcsize(MISSILE_FMT))     # combat packets, made once
        self.ended = None       # why the duel ended for us (the host left): the game goes back
        self.notice = None      # to the lobby, which shows this for NOTICE_FOR seconds
        self.notice_t = 0.0

    def set_me(self, name, colour):
        """The commander's name and ship colour, sent in every HELLO."""
        self.name = str(name).upper()[:NAME_LEN] or "JAMESON"
        self.colour = colour if isinstance(colour, int) and 0 <= colour < 32 else 0

    # ---- what the pages show ---------------------------------------------------------

    def hosts(self):
        """Games we could join: players hosting with no guest yet (or us as theirs)."""
        return [p for p in self.lobby() if p.role == HOST
                and (p.target == NO_ID or p.target == self.link.id)]

    def lobby(self):
        """Everyone else heard lately (on the DUEL page or flying), by name."""
        return sorted((p for p in self.players.values() if p.t < GONE), key=lambda p: p.name)

    def accepted(self):
        """Joining: True once our host names us as its guest."""
        o = self.other
        return (o is not None and self.role == JOIN and o.t < GONE
                and o.target == self.link.id)

    # ---- the lobby -------------------------------------------------------------------

    def host(self):
        """Host a game: wait for a guest."""
        self.role = HOST
        self.other = None
        self.go = False
        self.hello_t = 0.0      # say so at once

    def join(self, p):
        """Ask to join host p (a Player from hosts())."""
        self.role = JOIN
        self.other = p
        self.go = False
        self.hello_t = 0.0

    def leave(self):
        """Back to the lobby (stop hosting, or stop waiting for a host)."""
        self.role = LOBBY
        self.other = None
        self.go = False
        self.hello_t = 0.0

    def start_game(self):
        """The host presses start: START to the guest, then fly. False if no guest."""
        if self.role != HOST or self.other is None or self.other.t >= GONE:
            return False
        self.start_t = START_FOR
        self.start_gap = START_EVERY
        self._send_start()
        self.go = True
        return True

    def lobby_step(self, dt):
        """The DUEL page, each frame: say HELLO now and then, hear everyone."""
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
        if self.role == HOST and self.other is not None and self.other.t >= GONE:
            self.other = None       # the guest went away: wait for another

    def _age(self, dt):
        for p in self.players.values():
            p.t += dt

    def _say(self, role):
        target = self.other.id if (role != LOBBY and self.other is not None) else NO_ID
        struct.pack_into(FMT, self.hello, 0, netplay.MAGIC, HELLO, role, self.colour, 0,
                         target, _name_bytes(self.name))
        self.link.send(self.hello)

    def _send_start(self):
        self._send(START_PKT, HOST)

    def _send(self, kind, role):
        struct.pack_into(FMT, self.hello, 0, netplay.MAGIC, kind, role, self.colour, 0,
                         self.other.id, _name_bytes(self.name))
        self.link.send(self.hello)

    def _left(self, word="LEFT"):
        """'HOST LEFT' for a guest, '<NAME> LEFT' for a host."""
        o = self.other
        return ("HOST " if self.role == JOIN or o is None else o.name + " ") + word

    def _end(self, why):
        """The duel is over for us (the game sees .ended and goes back to the lobby)."""
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
                self._hear_combat(host, kind, msg)
                continue
            if (kind != HELLO and kind != START_PKT and kind != END_PKT) or len(msg) < size:
                continue
            _, _, role, colour, _, target, name = struct.unpack_from(FMT, msg, 0)
            p = self.players.get(bytes(host))
            if p is None:
                p = Player(bytes(host))     # a copy: the radio reuses its buffer
                self.players[p.id] = p
            p.t = 0.0
            p.name = name.decode().strip() or "?"
            p.colour = colour
            if kind == HELLO:
                p.role = role
                p.target = bytes(target)
                if (self.role == HOST and not self.flying and role == JOIN and target == me
                        and (self.other is None or self.other is p)):
                    self.other = p          # our guest (the first to ask)
                elif (self.flying and self.other is p and role != FLYING
                      and not (role == HOST and target == me)
                      and not (role == JOIN and target == me)):
                    self._end(self._left())     # back in the lobby: their END was lost
                    # (a HELLO naming us is from before START: not leaving)
            elif kind == END_PKT:
                if self.flying and self.other is p and target == me:
                    self._end(self._left())     # either leaving ends the game (Brian)
            elif self.role == JOIN and self.other is p and target == me and not self.flying:
                self.go = True              # our host started: fly

    def _hear_combat(self, host, kind, msg):
        o = self.other
        g = self.g
        if o is None or host != o.id or g is None or not self.flying:
            return              # not the player we duel, or not flying
        o.t = 0.0
        if kind == HIT_PKT and len(msg) >= struct.calcsize(HIT_FMT):
            g._hurt(struct.unpack_from(HIT_FMT, msg, 0)[3] / 16.0)
        elif kind == MISSILE_PKT and len(msg) >= struct.calcsize(MISSILE_FMT):
            _, _, n, x, y, z, nx, ny, nz = struct.unpack_from(MISSILE_FMT, msg, 0)
            if n in self.seen_missiles or g.missile_bp is None or g.over:
                return          # a repeat
            self.seen_missiles.append(n)
            if len(self.seen_missiles) > 16:
                self.seen_missiles.pop(0)
            k = 1.0 / 16384
            m = [0.0] * 9
            game._look(m, *game._unit(nx * k, ny * k, nz * k))
            mo = game.Obj(g.missile_bp, "missile", 0.0, 0.0, 0.0)
            g.place(mo, x * 0.25, y * 0.25, z * 0.25, m)
            mo.t = 12.0
            mo.net_id = n
            g.objs.append(mo)
            self.incoming[n] = mo
            g.say("INCOMING MISSILE")
            g.sfx("incoming")
        elif kind == NEXT_PKT and len(msg) >= struct.calcsize(NEXT_FMT):
            n = struct.unpack_from(NEXT_FMT, msg, 0)[3]
            if n > self.round:          # they pressed C: both back to the start
                self.round = n
                g.reset()
                self.start(g)
                g.say("ROUND %d" % n, 2.0)
        elif kind == GONE_PKT and len(msg) >= struct.calcsize(GONE_FMT):
            _, _, n, why = struct.unpack_from(GONE_FMT, msg, 0)
            gm = self.ghosts.pop(n, None)
            if gm is not None and not gm.dead:
                gm.dead = True
                g._boom(gm.x, gm.y, gm.z, 8)
                if why == GONE_ECM:
                    g.say("ECM")
                    g.sfx("ecm")

    # called by the Game (g.net) ------------------------------------------------------

    def laser_hit(self, damage):
        """Our laser hit their ship: they take the damage."""
        if self.other is None:
            return
        d = int(damage * 16)
        struct.pack_into(HIT_FMT, self.pkt, 0, netplay.MAGIC, HIT_PKT, 1,
                         0 if d < 0 else (65535 if d > 65535 else d))
        self.link.send(memoryview(self.pkt)[:struct.calcsize(HIT_FMT)])

    def missile_fired(self, o):
        """We launched missile o at them: their game flies it (o is a harmless copy)."""
        g = self.g
        if g is None or g.anchor is None:
            return
        self.missile_n = self.missile_n % 255 + 1
        n = o.net_id = self.missile_n
        self.ghosts[n] = o
        x, y, z = g.world_point(o.x, o.y, o.z)
        m = g.world_pose()[3]
        struct.pack_into(MISSILE_FMT, self.pkt, 0, netplay.MAGIC, MISSILE_PKT, n,
                         int(x * 4), int(y * 4), int(z * 4),
                         netplay._s(m[6]), netplay._s(m[7]), netplay._s(m[8]))
        for _ in range(AGAIN):
            self.link.send(self.pkt)

    def _gone(self, n, why):
        struct.pack_into(GONE_FMT, self.pkt, 0, netplay.MAGIC, GONE_PKT, n, why)
        for _ in range(AGAIN):
            self.link.send(memoryview(self.pkt)[:struct.calcsize(GONE_FMT)])

    def _hear_pose(self, host, msg):
        o = self.other
        if o is None or host != o.id:
            return              # not the player we duel
        o.t = 0.0
        r = netplay.read_pose(msg, self.pose_m)
        if r is None:
            return
        seq = r[1]
        if self.last_seq is not None and not netplay.newer(seq, self.last_seq):
            return              # late: an older pose than the one we have
        self.last_seq = seq
        self.pose = (r[2], r[3], r[4], r[6])
        self.flags = r[7]
        self.pose_age = 0.0

    # ---- flying ----------------------------------------------------------------------

    def start(self, g):
        """Into the arena: an empty one, you at your end (host START[0], guest START[1])."""
        self.slot = 1 if self.role == JOIN else 0
        self.flying = True
        self.go = False
        self.ended = None
        self.last_seq = None
        self.pose = None
        self.lost = False
        self.send_t = 0.0
        g.quiet = True
        g.objs[:] = []
        g.speed = START_SPEED
        g.set_anchor(*start_pose(self.slot))
        g.net = self
        g.rules.manual_ecm = True   # the ECM by hand in a duel (Brian, 2026-11-25)
        self.loadout(g)
        self.g = g
        self.ghosts = {}
        self.incoming = {}
        self.flags = 0
        if self.other is not None and not self.deaths and not self.kills:
            g.say("VS " + self.other.name, 2.0)

    def loadout(self, g):
        """Every round starts the same for both (Brian): shields and energy full, an ECM,
        a full missile rack, the lasers cool, nothing armed or locked."""
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

    def over_lines(self):
        """The end screen when we are destroyed: (text, size, rgb) lines."""
        from . import cockpit as ck
        o = self.other
        return (("DESTROYED", 24, ck.RED),
                ("BY " + (o.name if o is not None else "?"), 13,
                 ck.ship_rgb(o.colour) if o is not None else ck.WHITE),
                ("%d - %d" % (self.kills, self.deaths), 14, ck.WHITE),
                ("C: next round", 12, ck.GREY), ("F: leave duel", 12, ck.GREY))

    def stop(self, g):
        """Out of the arena (to the title, or the other left): practice's game again; back
        to the lobby. Leaving, say so (END), so the other knows at once: either leaving
        ends the other's game too (Brian, 2026-11-25)."""
        if self.flying and self.other is not None and self.ended is None:
            for _ in range(END_TIMES):
                self._send(END_PKT, self.role)
        if self.ended is not None:
            self.notice = self.ended
            self.notice_t = NOTICE_FOR
        self.ended = None
        if g is not None:
            g.quiet = False
            g.anchor = None
            g.net = None
            g.rules.manual_ecm = g.rules.hardcore   # practice's own again
            if self.ship is not None and self.ship in g.objs:
                g.objs.remove(self.ship)
        self.g = None
        self.kills = self.deaths = 0
        self.round = 1
        self.ship = None
        self.pose = None
        self.flying = False
        self.start_t = 0.0
        self.leave()

    def flight_step(self, g, dt):
        """Each flight frame, after Game.step (paused too, so the link stays up)."""
        if g.anchor is None:            # the game was reset: C after being destroyed
            if self.dead_here and self.other is not None:   # the next round, for both
                self.round += 1
                struct.pack_into(NEXT_FMT, self.pkt, 0, netplay.MAGIC, NEXT_PKT, 0, self.round)
                for _ in range(AGAIN):
                    self.link.send(memoryview(self.pkt)[:struct.calcsize(NEXT_FMT)])
                self.start(g)
                g.say("ROUND %d" % self.round, 2.0)
            else:
                self.start(g)
            self.ship = None
        self._age(dt)
        self.pose_age += dt
        self._hear()
        if self.start_t > 0:            # host: START again, in case the guest missed it
            self.start_t -= dt
            self.start_gap -= dt
            if self.start_gap <= 0 and self.other is not None:
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
        for n in list(self.incoming):   # their missiles here: hit us, or our ECM got them
            mo = self.incoming[n]
            if mo.dead:
                del self.incoming[n]
                self._gone(n, GONE_ECM if mo.ecmed else GONE_HIT)
        for n in list(self.ghosts):     # our copies that reached them, or ran out
            if self.ghosts[n].dead:
                del self.ghosts[n]
        if g.over and not self.dead_here:
            self.dead_here = True
            self.deaths += 1
        elif not g.over:
            self.dead_here = False
        o = self.other
        if o is not None and o.t >= GONE_END:
            self._end(self._left("LOST"))   # not heard for a long while: gone without a word
        # show theirs
        if self.pose is None or o is None or o.t >= LOST:
            if self.ship is not None:
                if self.ship in g.objs:
                    g.objs.remove(self.ship)
                if self.pose is not None and not self.lost:
                    self.lost = True
                    g.say("LINK LOST", 2.0)
            return
        if self.lost:
            self.lost = False
            g.say("LINK BACK", 1.5)
        if self.flags & netplay.DEAD:   # they are destroyed: an explosion, once
            if self.ship is not None and self.ship in g.objs:
                s = self.ship
                g.objs.remove(s)
                g._boom(s.x, s.y, s.z, 8 + 2 * min(s.bp.explosions, 6))
                g.sfx("explode")
                self.kills += 1
                g.say("%s DESTROYED  %d-%d" % (o.name, self.kills, self.deaths), 3.0)
            return
        if self.ship is None:
            bp = g.types.get(g.ship_name)     # practice flies a Cobra Mk III: so do they
            if bp is None:
                bp = next(b for b in g.types.values() if b.energy and b.name != "MISSILE")
            self.ship = game.Obj(bp, "player", 0.0, 0.0, 0.0)
        s = self.ship
        s.rgb = colour_rgb(o.colour)
        s.label = o.name
        if s not in g.objs:
            g.objs.append(s)
        x, y, z, speed = self.pose
        m = self.pose_m
        # where it is now: its last pose, moved on along its nose at its speed
        v = speed * game.SPEED_K * self.pose_age
        g.place(s, x + m[6] * v, y + m[7] * v, z + m[8] * v, m)
        s.speed = speed
        if self.flags & netplay.FIRING:     # their laser: drawn at you if they are aiming at you
            d = (s.x * s.x + s.y * s.y + s.z * s.z) ** 0.5
            sm = s.m        # their nose as we see it (m is the world's)
            if d > 1 and -(s.x * sm[6] + s.y * sm[7] + s.z * sm[8]) / d > BEAM_CONE:
                s.beam = 0.1
