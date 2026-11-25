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
from START[0], the guest from START[1], 2000 apart and facing. In flight each
sends its pose (netplay.py) SEND_HZ times a second; the other's ship (kind
"player") is drawn where its last pose and speed put it now. Nothing heard for
LOST seconds: "LINK LOST", the ship goes until it comes back. Shots and hits are
not built yet.
"""
import struct

from . import game, netplay

HELLO = 2
START_PKT = 3
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
GONE = 3.0                  # on the page: seconds without a HELLO before they leave the list
NAME_LEN = 16
# where each side starts in the shared world: (x, y, z, nose x, y, z); host 0, guest 1
START = ((0.0, 0.0, -1000.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1000.0, 0.0, 0.0, -1.0))
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
        struct.pack_into(FMT, self.hello, 0, netplay.MAGIC, START_PKT, HOST, self.colour, 0,
                         self.other.id, _name_bytes(self.name))
        self.link.send(self.hello)

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
            if (kind != HELLO and kind != START_PKT) or len(msg) < size:
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
            elif self.role == JOIN and self.other is p and target == me and not self.flying:
                self.go = True              # our host started: fly

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
        self.pose_age = 0.0

    # ---- flying ----------------------------------------------------------------------

    def start(self, g):
        """Into the arena: an empty one, you at your end (host START[0], guest START[1])."""
        self.slot = 1 if self.role == JOIN else 0
        self.flying = True
        self.go = False
        self.last_seq = None
        self.pose = None
        self.lost = False
        self.send_t = 0.0
        g.quiet = True
        g.objs[:] = []
        g.speed = START_SPEED
        g.set_anchor(*start_pose(self.slot))
        if self.other is not None:
            g.say("VS " + self.other.name, 2.0)

    def stop(self, g):
        """Out of the arena (to the title): practice's game again; back to the lobby."""
        if g is not None:
            g.quiet = False
            g.anchor = None
            if self.ship is not None and self.ship in g.objs:
                g.objs.remove(self.ship)
        self.ship = None
        self.pose = None
        self.flying = False
        self.start_t = 0.0
        self.leave()

    def flight_step(self, g, dt):
        """Each flight frame, after Game.step (paused too, so the link stays up)."""
        if g.anchor is None:            # the game was reset (fly again): back to your end
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
            flags = netplay.DEAD if g.over else 0
            netplay.pack_pose(self.buf, self.slot, self.seq, g.world_pose(), g.speed, flags)
            self.link.send(self.buf)
        # show theirs
        o = self.other
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
