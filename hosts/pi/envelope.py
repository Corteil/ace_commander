"""The multiplayer envelope (build 175; Brian: "should the packets not have an uid for
each player so the sender id does not matter", "and flag update required"): every
packet on every link, the badge's ESP-NOW (net_espnow.py, the same rules inline),
the network (net_udp) and the badge link (net_bridge), is

    VERSION (1 byte), the sender's player id (6 bytes), the game's packet

so who sent it no longer depends on the radio address or the socket, and a relay
(net_relay) passes packets on unchanged. Every game packet starts with
netplay.MAGIC ("AM"), which is how the rest is told apart:

- "AM" first (a badge's), or 6 bytes then "AM" (a Pi's on the network): a game from
  before the envelope (older) -> UPDATE REQUIRED;
- another VERSION byte (0xA0-0xAF) then an id then "AM": older or newer -> flagged;
- anything else: not the game's, skipped.
"""
import time

VERSION = 0xA1
ID_LEN = 6
HEAD = 1 + ID_LEN
MAGIC = b"AM"               # netplay.MAGIC
FRESH = 10.0                # a mismatch counts for this long after the last one heard


def wrap(ident, msg):
    return bytes((VERSION,)) + bytes(ident) + bytes(msg)


def is_game(data):
    """A current game packet in an envelope?"""
    return (len(data) >= HEAD + 2 and data[0] == VERSION
            and data[HEAD] == MAGIC[0] and data[HEAD + 1] == MAGIC[1])


class Mismatch:
    """Players heard on another version of the game: older ones need updating, or,
    with newer ones about, this device does."""

    def __init__(self):
        self.seen = {}              # address -> (when, newer)

    def check(self, addr, data):
        """data isn't a current packet: if it is the game's, remember who and which way."""
        n = len(data)
        if n >= 2 and data[0] == MAGIC[0] and data[1] == MAGIC[1]:
            self.seen[bytes(addr)] = (time.time(), False)       # a badge from before the envelope
        elif (n >= ID_LEN + 2 and data[ID_LEN] == MAGIC[0] and data[ID_LEN + 1] == MAGIC[1]
              and not 0xA0 <= data[0] <= 0xAF):
            self.seen[bytes(data[:ID_LEN])] = (time.time(), False)   # a Pi's, from before (id first)
        elif (n >= HEAD + 2 and 0xA0 <= data[0] <= 0xAF and data[HEAD] == MAGIC[0]
              and data[HEAD + 1] == MAGIC[1]):
            self.seen[bytes(addr)] = (time.time(), data[0] > VERSION)

    def issues(self):
        """(older, newer): how many players on another version were heard lately."""
        now = time.time()
        live = [newer for t, newer in self.seen.values() if now - t < FRESH]
        return sum(1 for x in live if not x), sum(1 for x in live if x)


def open_(addr, data, mismatch):
    """(sender id, packet) from one envelope, or (None, None), noting a mismatch."""
    if is_game(data):
        m = memoryview(bytes(data))
        return bytes(m[1:HEAD]), m[HEAD:]
    mismatch.check(addr, data)
    return None, None
