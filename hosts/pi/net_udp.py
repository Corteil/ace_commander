"""The Pi's radio link for a duel (duel.py): UDP broadcast on the local network,
with run.py --duel. Two windows on one Pi play each other too (both listen on
PORT with SO_REUSEPORT; a broadcast reaches every socket on it).

Each packet goes out as this run's id (ID_LEN random bytes) and then the
game's bytes; our own broadcasts come back and are dropped here. Not a badge
link: badges speak ESP-NOW (net_espnow.py); a Pi joins them through a bridge,
later (plans/MULTIPLAYER.md).
"""
import os
import socket

PORT = 47001
ID_LEN = 6


class Link:
    def __init__(self, port=PORT, to="255.255.255.255"):
        self.id = os.urandom(ID_LEN)
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

    def send(self, msg):
        try:
            self.sock.sendto(self.id + bytes(msg), self.to)
        except OSError as e:
            if not self.warned:     # no network: say so once, keep playing alone
                self.warned = True
                print("duel: can't send:", e)

    def recv(self):
        while True:
            try:
                data, _ = self.sock.recvfrom(512)
            except (BlockingIOError, InterruptedError):
                return None, None
            except OSError:
                return None, None
            if len(data) <= ID_LEN:
                continue
            host = data[:ID_LEN]
            if host == self.id:
                continue            # our own broadcast
            return host, memoryview(data)[ID_LEN:]

    def close(self):
        self.sock.close()
