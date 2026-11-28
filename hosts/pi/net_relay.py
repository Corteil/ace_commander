"""Badges and computers in one game (run.py --bridge --duel; Brian, 2026-11-28: "pi
version not connecting to local network at same time"): this Pi has the badge link
(net_bridge, ESP-NOW through a link badge) and the network (net_udp) and passes
packets between them, so every badge hears every computer and the other way round.

Every packet carries its sender's player id in its envelope (envelope.py), so they
are passed on as they are: what is heard on the radio goes to the network, what is
heard on the network goes on the radio, and this Pi's own go to both. The network
echoes our broadcasts back: our own (our id) and those we passed on from the radio
(their ids are remembered as radio ones) are dropped. Packets of another version
aren't passed on; they are noted for UPDATE REQUIRED (version_issues).

Only one Pi in a game may relay: two would each pass the other's packets on again.
"""
import time

import envelope


class Link:
    def __init__(self, radio, lan):
        self.radio = radio
        self.lan = lan
        self.id = radio.id
        lan.id = radio.id           # one id on both
        self.on_radio = {}          # player id -> when last heard (badges, for the page)
        self.on_lan = {}            # player id -> when last heard (computers)
        self.mismatch = envelope.Mismatch()

    def send(self, msg):
        data = envelope.wrap(self.id, msg)
        self.radio.send_raw(data)
        self.lan.send_raw(data)

    def recv(self):
        while True:
            f = self.radio.recv_raw()
            if f is None:
                break
            addr, data = f
            who, msg = envelope.open_(addr, data, self.mismatch)
            if who is None or who == self.id:
                continue
            self.on_radio[who] = time.time()
            self.lan.send_raw(data)
            return who, msg
        while True:
            data = self.lan.recv_raw()
            if data is None:
                return None, None
            who, msg = envelope.open_(data[1:1 + envelope.ID_LEN], data, self.mismatch)
            if who is None or who == self.id or who in self.on_radio:
                continue                # not current, ours, or a badge's we passed on
            self.on_lan[who] = time.time()
            self.radio.send_raw(data)
            return who, msg

    def version_issues(self):
        return self.mismatch.issues()

    def net_info(self):
        """NETWORK INFO: the badge link's lines, the network's, and what is relayed."""
        now = time.time()
        badges = sum(1 for t in self.on_radio.values() if now - t < 10)
        pcs = sum(1 for t in self.on_lan.values() if now - t < 10)
        lines = [("LINK: BADGES + NETWORK (RELAY)", "ok")]
        lines += [l for l in self.radio.net_info() if not l[0].startswith(("LINK:", "YOU:"))]
        lines += [l for l in self.lan.net_info() if l[0].startswith(("WI-FI:", "IP:"))]
        lines.append(("RELAYING: %d BADGES, %d PCS" % (badges, pcs), "ok" if badges or pcs else ""))
        lines.append(("YOU: " + ":".join("%02x" % x for x in self.id[3:]), ""))
        return lines

    def close(self):
        self.radio.close()
        self.lan.close()
