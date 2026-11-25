"""A duel (plans/MULTIPLAYER.md): two players in combat practice's arena with
no other ships, each seeing the other's ship. Rules only: the radio is a link
the platform gives (platform.radio(), e.g. net_espnow.Link on the badge):

    link.id          this device's id (bytes), the same on every packet it sends
    link.send(msg)   send bytes to everyone listening
    link.recv()      (sender id, bytes) for the next packet heard, or (None, None)

Before flying (the DUEL page) each side says HELLO four times a second, so each
knows the other is there; the smaller id takes START[0], the other START[1]: 2000
apart, facing each other. In flight each sends its pose (netplay.py) SEND_HZ times
a second and shows the other's ship (kind "player") where its last pose and speed
put it now. Nothing heard for LOST seconds: "LINK LOST", the ship goes until it
comes back. Shots and hits are not built yet.
"""
import struct

from . import game, netplay

HELLO = 2
HELLO_FMT = "<2sBB"         # MAGIC, HELLO, state (LOBBY / FLYING)
LOBBY = 0
FLYING = 1
HELLO_EVERY = 0.25          # seconds between HELLOs on the DUEL page
SEND_HZ = 15                # poses a second in flight (the link test's rate)
LOST = 3.0                  # seconds without a packet: the other player is gone
GONE = 3.0                  # on the page: seconds without a HELLO before "searching" again
# where each side starts in the shared world: (x, y, z, nose x, y, z)
START = ((0.0, 0.0, -1000.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1000.0, 0.0, 0.0, -1.0))
START_SPEED = 14.0          # as a new flight (Game.reset)


def start_pose(slot):
    """(x, y, z, axes) for a starting slot: level, nose along the given way."""
    x, y, z, nx, ny, nz = START[slot]
    m = [0.0] * 9
    game._look(m, nx, ny, nz)
    return x, y, z, m


class Duel:
    def __init__(self, link):
        self.link = link
        self.peer = None        # the other player's id
        self.peer_t = 99.0      # seconds since we last heard them
        self.peer_flying = False
        self.hello_t = 0.0
        self.buf = bytearray(netplay.SIZE)     # made once: no garbage per packet
        self.hello = bytearray(struct.calcsize(HELLO_FMT))
        self.seq = 0
        self.send_t = 0.0
        self.ship = None        # the other player's ship (an Obj, kind "player")
        self.pose_m = [0.0] * 9     # their last axes (filled by read_pose)
        self.pose = None        # (x, y, z, speed) of their last pose
        self.pose_age = 0.0     # seconds since that pose
        self.last_seq = None
        self.lost = False
        self.slot = 0
        self.joined = False     # the other player just started flying: both go back to the start

    # ---- both pages ------------------------------------------------------------------

    @property
    def found(self):
        """True while the other player is heard."""
        return self.peer is not None and self.peer_t < GONE

    def _hear(self):
        """Read every packet waiting. Returns True if a pose came."""
        posed = False
        while True:
            host, msg = self.link.recv()
            if msg is None:
                return posed
            if len(msg) < 4 or bytes(msg[0:2]) != netplay.MAGIC:
                continue
            if host == self.link.id:
                continue        # our own (a UDP broadcast comes back)
            if self.peer is None or not self.found:
                if self.peer != host:
                    self.peer_flying = False    # someone new: not flying until a pose says so
                self.peer = bytes(host)     # the first (or a new) player heard (a copy:
                                            # the radio reuses its buffer)
                self.last_seq = None
            elif host != self.peer:
                continue        # a third player: not yet
            self.peer_t = 0.0
            if msg[2] == HELLO:
                self.peer_flying = msg[3] == FLYING
            elif msg[2] == netplay.POSE:
                r = netplay.read_pose(msg, self.pose_m)
                if r is None:
                    continue
                seq = r[1]
                if self.last_seq is not None and not netplay.newer(seq, self.last_seq):
                    continue    # late: an older pose than the one we have
                self.last_seq = seq
                if not self.peer_flying:    # they have just started flying: both start
                    self.joined = True      # again, facing (flight_step; start clears it)
                self.peer_flying = True
                self.pose = (r[2], r[3], r[4], r[6])
                self.pose_age = 0.0
                posed = True

    def _say_hello(self, state):
        struct.pack_into(HELLO_FMT, self.hello, 0, netplay.MAGIC, HELLO, state)
        self.link.send(self.hello)

    def lobby_step(self, dt):
        """The DUEL page, each frame: say HELLO now and then, hear the other side."""
        self.peer_t += dt
        self.hello_t -= dt
        if self.hello_t <= 0:
            self.hello_t = HELLO_EVERY
            self._say_hello(LOBBY)
        self._hear()

    # ---- flying ----------------------------------------------------------------------

    def start(self, g):
        """Into the arena: an empty one, you at your starting place. Flying alone,
        you take START[0] for now; when someone joins, both start again (flight_step),
        so you can't both be in the same slot (Brian, 2026-11-25: the first one
        flying took slot 0 alone, the second took it too, back to back)."""
        self.slot = 0 if self.peer is None or self.link.id < self.peer else 1
        self.joined = False
        g.quiet = True
        g.objs[:] = []
        g.speed = START_SPEED
        g.set_anchor(*start_pose(self.slot))
        self.send_t = 0.0
        self.lost = False

    def stop(self, g):
        """Out of the arena (to the title): the game is practice's again."""
        if g is not None:
            g.quiet = False
            g.anchor = None
            if self.ship is not None and self.ship in g.objs:
                g.objs.remove(self.ship)
        self.ship = None
        self.pose = None

    def flight_step(self, g, dt):
        """Each flight frame, after Game.step (paused too, so the link stays up)."""
        if g.anchor is None:            # the game was reset (fly again): back to the start
            self.start(g)
            self.ship = None
        self.peer_t += dt
        self.pose_age += dt
        self._hear()
        if self.joined:                 # someone new: both back to the start, facing
            self.start(g)
            self.pose = None            # their pose from before they started again
            g.say("PLAYER JOINED", 2.0)
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
        if self.pose is None or self.peer_t >= LOST:
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
        if self.ship not in g.objs:
            g.objs.append(self.ship)
        x, y, z, speed = self.pose
        m = self.pose_m
        # where it is now: its last pose, moved on along its nose at its speed
        v = speed * game.SPEED_K * self.pose_age
        g.place(self.ship, x + m[6] * v, y + m[7] * v, z + m[8] * v, m)
        self.ship.speed = speed
