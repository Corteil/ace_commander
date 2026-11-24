"""The badge's radio link for a duel (duel.py): ESP-NOW broadcast, no router.
Measured with tools/espnow_link.py (plans/MULTIPLAYER.md): ~5 ms each way, no
loss side by side, ~1% at 10 m through a door. Both badges must be on one
Wi-Fi channel: one on a network uses that network's; one that isn't is set to
CHANNEL (and disconnected first, so it stops hunting for its network).

recv() is read every frame by the game, so the bigger receive buffer (RXBUF)
holds a few frames' packets; the default ~500 bytes dropped packets.
"""
CHANNEL = 1
RXBUF = 4096
BROADCAST = b"\xff" * 6


class Link:
    def __init__(self, channel=CHANNEL):
        import network
        import espnow
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            try:
                sta.disconnect()
            except Exception:
                pass
            sta.config(channel=channel)
        e = espnow.ESPNow()
        e.active(True)
        try:
            e.config(rxbuf=RXBUF)
        except Exception:
            pass
        try:
            e.add_peer(BROADCAST)
        except OSError:
            pass                # already a peer (opened before)
        self.e = e
        self.id = bytes(sta.config("mac"))
        self.channel = sta.config("channel")

    def send(self, msg):
        try:
            self.e.send(BROADCAST, msg, False)
        except OSError:
            pass                # a full send queue: the next pose will do

    def recv(self):
        """(sender, packet) or (None, None). Both are buffers the radio reuses:
        copy what you keep."""
        return self.e.irecv(0)
