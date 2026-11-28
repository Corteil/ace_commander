"""Badges and computers in one game (run.py --bridge --duel; Brian, 2026-11-28: "pi
version not connecting to local network at same time"): this Pi has the badge link
(net_bridge, ESP-NOW through a link badge) and the network (net_udp) and passes
packets between them, so every badge hears every computer and the other way round.

- A badge's packet heard on the radio is played here and sent on to the network as
  that badge (net_udp.Link.send_as), so the other computers see the badge itself.
- A packet from another computer is played here and sent on the radio wrapped as
  RELAY, its sender's id, the packet; the badges unwrap it (net_espnow.unwrap), since
  over the radio everything this Pi sends comes from the link badge's address.
- This Pi's own packets go to both. Its id on the network is the link badge's
  address, the id the badges know it by.
- The network echoes our broadcasts back: our own id, and badges' packets we sent on
  (their ids are remembered as radio ones), are dropped.

Only one Pi in a game may relay: two would each pass the other's packets on again.
"""
import time

RELAY = b"AR"               # net_espnow.RELAY
ADDR = 6
MAX = 250 - 6 - 2 - ADDR    # the most a computer's packet can be to fit wrapped (net_bridge.MAX)


class Link:
    def __init__(self, radio, lan):
        self.radio = radio
        self.lan = lan
        self.id = radio.id
        lan.id = radio.id           # one id, the one the badges see
        self.on_radio = {}          # badge id -> when last heard (for the page)
        self.on_lan = {}            # computer id -> when last heard
        self.to_lan = 0             # packets passed on each way
        self.to_radio = 0

    def send(self, msg):
        self.radio.send(msg)
        self.lan.send(msg)

    def recv(self):
        who, msg = self.radio.recv()
        if msg is not None:
            who = bytes(who)
            if bytes(msg[:2]) == RELAY:
                return self.recv()      # another relay's: not ours to use (one relay only)
            self.on_radio[who] = time.time()
            self.lan.send_as(who, msg)
            self.to_lan += 1
            return who, msg
        while True:
            who, msg = self.lan.recv()
            if msg is None:
                return None, None
            who = bytes(who)
            if who == self.id or who in self.on_radio:
                continue                # our own, or a badge's we passed on, come back
            self.on_lan[who] = time.time()
            if len(msg) <= MAX:
                self.radio.send(RELAY + who + bytes(msg))
                self.to_radio += 1
            return who, msg

    def net_info(self):
        """NETWORK INFO: the badge link's lines, the network's, and what is relayed."""
        now = time.time()
        badges = sum(1 for t in self.on_radio.values() if now - t < 10)
        pcs = sum(1 for t in self.on_lan.values() if now - t < 10)
        lines = [("LINK: BADGES + NETWORK (RELAY)", "ok")]
        lines += [l for l in self.radio.net_info() if not l[0].startswith(("LINK:", "YOU:"))]
        lines += [l for l in self.lan.net_info()
                  if l[0].startswith(("WI-FI:", "IP:"))]
        lines.append(("RELAYING: %d BADGES, %d PCS" % (badges, pcs), "ok" if badges or pcs else ""))
        lines.append(("YOU: " + ":".join("%02x" % x for x in self.id[3:]), ""))
        return lines

    def close(self):
        self.radio.close()
        self.lan.close()
