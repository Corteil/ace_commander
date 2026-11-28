"""Badges and computers in one game (net_relay.py, run.py --bridge --duel): this Pi's
packets go both ways; a badge's goes on to the network as that badge; another
computer's goes on the radio wrapped (RELAY, its id), and the badge's net_espnow
unwraps it to that computer's id; the network's echoes are dropped; one id, the
link badge's. A pretend radio and network.

    python3 hosts/pi/tests/test_pi_relay.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

import importlib.util                              # noqa: E402
import net_relay                                   # noqa: E402

_spec = importlib.util.spec_from_file_location("net_espnow", os.path.join(ROOT, "net_espnow.py"))
net_espnow = importlib.util.module_from_spec(_spec)     # the badge's (unwrap only: no radio)
_spec.loader.exec_module(net_espnow)


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + ("  " + str(extra) if extra and not cond else ""))
    if not cond:
        raise SystemExit(1)


LINK_ID = bytes.fromhex("64e833721138")
BADGE = bytes.fromhex("7c4fad337ac0")
PC = bytes.fromhex("aabbccddeeff")


class Radio:
    def __init__(self):
        self.id = LINK_ID
        self.inbox = []
        self.sent = []

    def send(self, msg):
        self.sent.append(bytes(msg))

    def recv(self):
        return self.inbox.pop(0) if self.inbox else (None, None)

    def net_info(self):
        return [("LINK: BADGE LINK (USB)", "ok"), ("CHANNEL: 1 (BADGES FOUND)", "ok"), ("YOU: x", "")]

    def close(self):
        pass


class Lan:
    def __init__(self):
        self.id = os.urandom(6)
        self.inbox = []
        self.sent = []          # (as id, packet)

    def send(self, msg):
        self.sent.append((self.id, bytes(msg)))

    def send_as(self, ident, msg):
        self.sent.append((bytes(ident), bytes(msg)))

    def recv(self):
        return self.inbox.pop(0) if self.inbox else (None, None)

    def net_info(self):
        return [("LINK: UDP", "ok"), ("WI-FI: Skynet3", ""), ("IP: 192.168.68.89", "")]

    def close(self):
        pass


radio, lan = Radio(), Lan()
r = net_relay.Link(radio, lan)
check("one id: the link badge's, on the network too", r.id == LINK_ID and lan.id == LINK_ID)

r.send(b"AM\x01mine")
check("our packet goes on the radio and the network",
      radio.sent == [b"AM\x01mine"] and lan.sent == [(LINK_ID, b"AM\x01mine")])
radio.sent.clear()
lan.sent.clear()

radio.inbox.append((BADGE, memoryview(b"AM\x02badge")))
who, msg = r.recv()
check("a badge's packet: played here", who == BADGE and bytes(msg) == b"AM\x02badge")
check("... and on to the network as that badge", lan.sent == [(BADGE, b"AM\x02badge")], lan.sent)

lan.inbox += [(LINK_ID, memoryview(b"AM\x01mine")), (BADGE, memoryview(b"AM\x02badge")),
              (PC, memoryview(b"AM\x02pc"))]
who, msg = r.recv()
check("echoes dropped (ours, the badge's we passed on); a computer's played",
      who == PC and bytes(msg) == b"AM\x02pc")
check("... and on the radio wrapped with its id", radio.sent == [b"AR" + PC + b"AM\x02pc"], radio.sent)
check("nothing more", r.recv() == (None, None))

# the badge's side: net_espnow unwraps it to the computer's id
w, m = net_espnow.unwrap((LINK_ID, radio.sent[0]))
check("badge: a relayed packet comes from the computer itself", bytes(w) == PC and bytes(m) == b"AM\x02pc")
w, m = net_espnow.unwrap((BADGE, b"AM\x02plain"))
check("badge: other packets as they are", w == BADGE and m == b"AM\x02plain")

# another relay's wrapped packet on the radio isn't used (one relay a game)
radio.inbox.append((bytes(6), memoryview(b"AR" + PC + b"AM\x02x")))
check("another relay's packet ignored", r.recv() == (None, None))

# too big to wrap: played, not passed on
radio.sent.clear()
lan.inbox.append((PC, memoryview(b"AM" + bytes(net_relay.MAX))))
who, msg = r.recv()
check("a packet too big to wrap: played, not sent on", who == PC and radio.sent == [])
check("the biggest game packet (224 bytes) fits wrapped", 224 <= net_relay.MAX)

lines = [t for t, k in r.net_info()]
check("NETWORK INFO: relay, channel, Wi-Fi, IP, counts, id",
      lines[0].startswith("LINK: BADGES + NETWORK") and "CHANNEL: 1 (BADGES FOUND)" in lines
      and "WI-FI: Skynet3" in lines and any(t.startswith("RELAYING: 1 BADGES, 1 PCS") for t in lines)
      and lines[-1] == "YOU: 72:11:38", lines)
print("ALL PI RELAY TESTS PASSED")
