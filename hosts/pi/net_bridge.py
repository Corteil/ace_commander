"""The Pi's radio link through a USB dongle (run.py --bridge DEVICE): an ESP32 (Brian's
2022 EMF badge, or any ESP32 with MicroPython) running tools/bridge/main.py passes the
game's packets between ESP-NOW and USB serial, so a Pi, a PC or the CardputerZero plays
with badges (plans/MULTIPLAYER.md, "the Pi on ESP-NOW through a bridge").

The same interface as net_udp.Link and the badge's net_espnow.Link: send(bytes),
recv() -> (sender, bytes) or (None, None), close(). The sender is the 6-byte radio
address of the badge (or dongle) that sent it, as on the badge.

On the wire, both ways, each packet is a frame: SYNC, a length byte n, then n bytes:
the 6-byte address (the sender's; going out, broadcast) and the packet. A byte that
isn't SYNC where a frame should start is skipped, so a frame cut short is resynced.
"""
SYNC = 0xA5
ADDR = 6
BROADCAST = b"\xff" * ADDR
MAX = 250 - ADDR            # ESP-NOW carries at most 250 bytes


def frame(addr, msg):
    """One frame: SYNC, length, address, packet."""
    msg = bytes(msg)
    if len(msg) > MAX:
        raise ValueError("packet too long for ESP-NOW: %d bytes" % len(msg))
    return bytes((SYNC, ADDR + len(msg))) + bytes(addr) + msg


class Frames:
    """Frames out of a byte stream that comes in pieces: feed(bytes), then next()."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data

    def next(self):
        """(address, packet) for the next whole frame, or None."""
        b = self.buf
        while b:
            if b[0] != SYNC:
                i = b.find(bytes((SYNC,)))
                del b[:len(b) if i < 0 else i]          # skip to the next SYNC
                continue
            if len(b) < 2:
                return None
            n = b[1]
            if n < ADDR:
                del b[:1]                               # not a frame: look further on
                continue
            if len(b) < 2 + n:
                return None                             # the rest is still coming
            addr, msg = bytes(b[2:2 + ADDR]), bytes(b[2 + ADDR:2 + n])
            del b[:2 + n]
            return addr, msg
        return None


class Link:
    def __init__(self, device, baud=115200):
        import serial           # pyserial (python3-serial)
        self.ser = serial.Serial(device, baud, timeout=0, write_timeout=0.05)
        self.ser.reset_input_buffer()
        self.frames = Frames()
        self.warned = False

    def send(self, msg):
        try:
            self.ser.write(frame(BROADCAST, msg))
        except Exception as e:      # unplugged, or the dongle stopped reading
            if not self.warned:
                self.warned = True
                print("bridge: can't send:", e)

    def recv(self):
        f = self.frames.next()
        if f is None:
            try:
                n = self.ser.in_waiting
                if n:
                    self.frames.feed(self.ser.read(n))
            except Exception:
                return None, None
            f = self.frames.next()
        if f is None:
            return None, None
        addr, msg = f
        return addr, memoryview(msg)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass
