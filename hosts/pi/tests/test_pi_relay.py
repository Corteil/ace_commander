"""Badges and computers in one game (net_relay.py, run.py --bridge --duel), with the
envelope (envelope.py): this Pi's packets go to both, in its envelope with the link
badge's id; a badge's goes on to the network as it is, and another computer's goes on
the radio as it is (the id inside says who sent it); the network's echoes are dropped;
packets of another version aren't passed on but are flagged. A pretend radio and
network; and the envelope's rules the same on the badge (net_espnow) and here.

    python3 hosts/pi/tests/test_pi_relay.py
"""
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

import envelope     # noqa: E402
import net_relay    # noqa: E402

if not hasattr(time, "ticks_ms"):       # MicroPython's, for net_espnow
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
    time.ticks_diff = lambda a, b: a - b
_spec = importlib.util.spec_from_file_location("net_espnow", os.path.join(ROOT, "net_espnow.py"))
net_espnow = importlib.util.module_from_spec(_spec)     # the badge's (its envelope rules only)
_spec.loader.exec_module(net_espnow)


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + ("  " + str(extra) if extra and not cond else ""))
    if not cond:
        raise SystemExit(1)


LINK_ID = bytes.fromhex("64e833721138")
BADGE = bytes.fromhex("7c4fad337ac0")
PC = bytes.fromhex("aabbccddeeff")


def E(ident, msg):
    return envelope.wrap(ident, b"AM" + msg)


class Radio:
    def __init__(self):
        self.id = LINK_ID
        self.inbox = []         # (radio address, data)
        self.sent = []

    def send_raw(self, data):
        self.sent.append(bytes(data))

    def recv_raw(self):
        return self.inbox.pop(0) if self.inbox else None

    def net_info(self):
        return [("LINK: BADGE LINK (USB)", "ok"), ("CHANNEL: 1 (BADGES FOUND)", "ok"), ("YOU: x", "")]

    def close(self):
        pass


class Lan:
    def __init__(self):
        self.id = os.urandom(6)
        self.inbox = []
        self.sent = []

    def send_raw(self, data):
        self.sent.append(bytes(data))

    def recv_raw(self):
        return self.inbox.pop(0) if self.inbox else None

    def net_info(self):
        return [("LINK: UDP", "ok"), ("WI-FI: Skynet3", ""), ("IP: 192.168.68.89", "")]

    def close(self):
        pass


check("the envelope's rules agree: badge and Pi", net_espnow.VERSION == envelope.VERSION
      and net_espnow.HEAD == envelope.HEAD)

radio, lan = Radio(), Lan()
r = net_relay.Link(radio, lan)
check("one id: the link badge's, on the network too", r.id == LINK_ID and lan.id == LINK_ID)

r.send(b"AM\x01mine")
check("our packet goes to both, in our envelope",
      radio.sent == [envelope.wrap(LINK_ID, b"AM\x01mine")] == lan.sent)
radio.sent.clear()
lan.sent.clear()

radio.inbox.append((BADGE, E(BADGE, b"\x02badge")))
who, msg = r.recv()
check("a badge's packet: played here, from its id", who == BADGE and bytes(msg) == b"AM\x02badge")
check("... and on to the network as it is", lan.sent == [E(BADGE, b"\x02badge")], lan.sent)

lan.inbox += [envelope.wrap(LINK_ID, b"AM\x01mine"), E(BADGE, b"\x02badge"), E(PC, b"\x02pc")]
who, msg = r.recv()
check("echoes dropped (ours, the badge's we passed on); a computer's played",
      who == PC and bytes(msg) == b"AM\x02pc")
check("... and on the radio as it is", radio.sent == [E(PC, b"\x02pc")], radio.sent)
check("nothing more", r.recv() == (None, None))

# the badge's side reads the computer's packet as from the computer, though the radio
# address is the link badge's
got = net_espnow.open_env((LINK_ID, radio.sent[0]), {}, {})
check("badge: the computer's packet comes from the computer", got[0] == PC and bytes(got[1]) == b"AM\x02pc")

# another version: not passed on, flagged
radio.sent.clear()
lan.sent.clear()
radio.inbox.append((BADGE, b"AM\x02from before the envelope"))
lan.inbox.append(bytes((0xA2,)) + PC + b"AM\x02newer")
check("other versions: not played", r.recv() == (None, None))
check("... not passed on", radio.sent == [] and lan.sent == [])
check("... flagged: one older, one newer", r.version_issues() == (1, 1), r.version_issues())

lines = [t for t, k in r.net_info()]
check("NETWORK INFO: relay, channel, Wi-Fi, IP, counts, id",
      lines[0].startswith("LINK: BADGES + NETWORK") and "CHANNEL: 1 (BADGES FOUND)" in lines
      and "WI-FI: Skynet3" in lines and any(t.startswith("RELAYING: 1 BADGES, 1 PCS") for t in lines)
      and lines[-1] == "YOU: 72:11:38", lines)
print("ALL PI RELAY TESTS PASSED")
