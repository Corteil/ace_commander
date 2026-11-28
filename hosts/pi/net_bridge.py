"""The Pi's radio link through a USB dongle (run.py --bridge DEVICE): an ESP32 (Brian's
2022 EMF badge, or any ESP32 with MicroPython) running tools/bridge/main.py passes the
game's packets between ESP-NOW and USB serial, so a Pi, a PC or the CardputerZero plays
with badges (plans/MULTIPLAYER.md, "the Pi on ESP-NOW through a bridge").

The same interface as net_udp.Link and the badge's net_espnow.Link: id, send(bytes),
recv() -> (sender, bytes) or (None, None), close(). id is the dongle's radio address,
what the badges see this player's packets come from: asked for with a MAC_ASK frame,
answered with a MAC_IS frame holding it (a random id if an old dongle doesn't answer). The sender is the 6-byte radio
address of the badge (or dongle) that sent it, as on the badge.

On the wire, both ways, each packet is a frame: SYNC, a length byte n, then n bytes:
the 6-byte address (the sender's; going out, broadcast) and the packet. A byte that
isn't SYNC where a frame should start is skipped, so a frame cut short is resynced.
"""
SYNC = 0xA5
ADDR = 6
BROADCAST = b"\xff" * ADDR
MAC_ASK = b"MAC?!!"         # to the dongle: what is your radio address?
MAC_IS = b"MAC=!!"          # from it: the address, as the packet
INFO_ASK = b"INFO?!"        # to the dongle: its channel and whether it found badges
INFO_IS = b"INFO=!"         # from it: channel, found (0 / 1)
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


ESPRESSIF = 0x303A          # the USB vendor id of an ESP32-S3's own USB (the dongle)


def find_dongle():
    """The dongle's serial port, or None: the first port with Espressif's USB vendor id
    (pyserial's list, so Linux, Windows and macOS alike), else a by-id name saying
    Espressif. The badges (Tildagon, 16d0) and the Tufty (Pimoroni) aren't picked."""
    try:
        from serial.tools import list_ports
        for p in sorted(list_ports.comports(), key=lambda p: p.device):
            if p.vid == ESPRESSIF:
                return p.device
    except Exception:
        pass
    import os
    d = "/dev/serial/by-id"
    try:
        for n in sorted(os.listdir(d)):
            if "espressif" in n.lower():
                return os.path.join(d, n)
    except OSError:
        pass
    return None


class Link:
    def __init__(self, device="auto", baud=115200):
        import serial           # pyserial (python3-serial)
        if device in (None, "auto"):
            device = find_dongle()
            if device is None:
                raise OSError("no bridge dongle found (an ESP32 running tools/bridge/main.py)")
        self.ser = serial.Serial(device, baud, timeout=0, write_timeout=0.05)
        self.ser.reset_input_buffer()
        self.frames = Frames()
        self.warned = False
        self.held = []              # packets read while waiting for the address
        self.channel = None         # the dongle's channel, from INFO_IS (info())
        self.found = False
        self.device = device
        self.id = self._ask_mac()

    def _ask_mac(self, wait=6.0, every=0.5):
        """Ask again every `every` s: a dongle just plugged in is still starting
        (3 s for Ctrl-C, then its screen) and misses what comes before."""
        import os
        import time
        end = time.time() + wait
        asked = 0
        while time.time() < end:
            if time.time() >= asked + every:
                self.ser.write(frame(MAC_ASK, b""))
                asked = time.time()
            f = self._next()
            if f is None:
                time.sleep(0.01)
                continue
            addr, msg = f
            if addr == MAC_IS and len(msg) == ADDR:
                return bytes(msg)
            self.held.append(f)
        print("bridge: the dongle didn't give its address (an old tools/bridge/main.py?)")
        return os.urandom(ADDR)

    def _next(self):
        f = self.frames.next()
        if f is None:
            try:
                n = self.ser.in_waiting
                if n:
                    self.frames.feed(self.ser.read(n))
            except Exception:
                return None
            f = self.frames.next()
        return f

    def info(self):
        """Ask the dongle for its channel (the answer lands in .channel / .found)."""
        try:
            self.ser.write(frame(INFO_ASK, b""))
        except Exception:
            pass

    def send(self, msg):
        try:
            self.ser.write(frame(BROADCAST, msg))
        except Exception as e:      # unplugged, or the dongle stopped reading
            if not self.warned:
                self.warned = True
                print("bridge: can't send:", e)

    def recv(self):
        while True:
            f = self.held.pop(0) if self.held else self._next()
            if f is None:
                return None, None
            addr, msg = f
            if addr == INFO_IS:
                if len(msg) >= 2:
                    self.channel, self.found = msg[0], bool(msg[1])
                continue
            if addr == MAC_IS:
                continue
            return addr, memoryview(msg)

    def net_info(self):
        """The NETWORK INFO page's lines: (text, kind), kind "ok", "warn" or "". Asks
        the dongle its channel again, for the next time (the answer comes in recv)."""
        import os
        self.info()
        if self.channel is None:
            ch = ("CHANNEL: ASKING THE DONGLE", "warn")
        elif self.found:
            ch = ("CHANNEL: %d (BADGES FOUND)" % self.channel, "ok")
        else:
            ch = ("CHANNEL: %d HUNTING" % self.channel, "warn")
        return [("LINK: BRIDGE (USB DONGLE)", "ok"),
                ("PORT: " + os.path.basename(os.path.realpath(self.device))[:20], ""),
                ch,
                ("YOU: " + ":".join("%02x" % x for x in self.id[3:]), "")]

    def stop_dongle(self):
        """Tell the dongle program to stop (its REPL is free afterwards): a frame from
        tools/bridge/main.py's STOP_ADDR."""
        self.ser.write(frame(b"STOP!!", b""))

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass
