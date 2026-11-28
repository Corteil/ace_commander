"""The Pi's radio link for a duel (duel.py): UDP broadcast on the local network,
with run.py --duel. Two windows on one Pi play each other too (both listen on
PORT with SO_REUSEPORT; a broadcast reaches every socket on it).

Each packet goes out in the envelope (envelope.py: version, this run's id, the
game's bytes); our own broadcasts come back and are dropped here, and players on
another version are noted (version_issues) for UPDATE REQUIRED. send_raw /
recv_raw pass whole envelopes, for net_relay. Badges speak ESP-NOW (net_espnow.py);
a Pi joins them through a link badge (net_bridge, net_relay).
"""
import os
import socket

import envelope

PORT = 47001
ID_LEN = envelope.ID_LEN


class Link:
    def __init__(self, port=PORT, to="255.255.255.255", ident=None):
        self.id = bytes(ident) if ident else os.urandom(ID_LEN)   # (net_relay: the link badge's)
        self.to = (to, port)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.bind(("", port))
        s.setblocking(False)
        self.sock = s
        self.warned = False
        self.mismatch = envelope.Mismatch()

    def send(self, msg):
        self.send_raw(envelope.wrap(self.id, msg))

    def send_raw(self, data):
        """A whole envelope, as it is (net_relay passes other players' on)."""
        try:
            self.sock.sendto(bytes(data), self.to)
        except OSError as e:
            if not self.warned:     # no network: say so once, keep playing alone
                self.warned = True
                print("duel: can't send:", e)

    def recv_raw(self):
        """The next datagram as it came, or None."""
        try:
            data, _ = self.sock.recvfrom(512)
        except (BlockingIOError, InterruptedError):
            return None
        except OSError:
            return None
        return data

    def recv(self):
        while True:
            data = self.recv_raw()
            if data is None:
                return None, None
            who, msg = envelope.open_(data[1:1 + ID_LEN], data, self.mismatch)
            if who is None or who == self.id:
                continue            # not a current game packet, or our own broadcast
            return who, msg

    def version_issues(self):
        """(older, newer) players heard on another version (envelope.Mismatch)."""
        return self.mismatch.issues()

    def net_info(self):
        """The NETWORK INFO page's lines: (text, kind), kind "ok", "warn" or ""."""
        ip = local_ip()
        wifi = wifi_name()
        return [("LINK: UDP ON THE NETWORK", "ok"),
                ("PORT: %d" % self.to[1], ""),
                (("WI-FI: " + wifi[:16]) if wifi else "WI-FI: NONE (WIRED?)", ""),
                ("IP: " + ip, "") if ip else ("IP: NO NETWORK", "warn"),
                ("PIS AND PCS ONLY: NO BADGES", "warn"),
                ("YOU: " + hexid(self.id[3:]), "")]

    def close(self):
        self.sock.close()


def local_ip():
    """This computer's address on its network, or None (a UDP socket's connect sends
    nothing: it only picks the route)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def wifi_name():
    """The Wi-Fi network this computer is on, or None (Linux: iwgetid)."""
    import subprocess
    try:
        r = subprocess.run(["iwgetid", "-r"], capture_output=True, text=True, timeout=1)
        return r.stdout.strip() or None
    except Exception:
        return None


def hexid(b):
    return ":".join("%02x" % x for x in bytes(b))
