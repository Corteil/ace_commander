"""The Pi's radio link through a badge or dongle on USB (run.py --bridge [DEVICE]): a
2024 badge running the ESP-NOW Link app (Corteil/espnow_link), or an ESP32 with MicroPython
running tools/bridge/main.py (Brian's 2022 badge), passes the game's packets between
ESP-NOW and USB serial, so a Pi, a PC or the CardputerZero plays with badges
(plans/MULTIPLAYER.md, "the Pi on ESP-NOW through a bridge").

The same interface as net_udp.Link and the badge's net_espnow.Link: id, send(bytes),
recv() -> (sender, bytes) or (None, None), close(). id is the link's radio address,
what the badges see this player's packets come from: asked for with MAC_ASK, answered
with MAC_IS holding it (a random id if nothing answers). The sender is the player id in
the packet's envelope (envelope.py), not the radio address.

On the wire each packet is a line of text (build 174; it was binary): ">" going to the
link, "<" coming from it, then the 6-byte address (the sender's; going out, broadcast)
and the packet in hex, then a newline. Text because the 2024 badge's firmware prints its
own messages on the same port (they are skipped: not a "<" line of hex), and because no
byte of it is Ctrl-C, so the link's REPL still answers mpremote.
"""
import binascii

import envelope

ADDR = 6
BROADCAST = b"\xff" * ADDR
MAC_ASK = b"MAC?!!"         # to the link: what is your radio address?
MAC_IS = b"MAC=!!"          # from it: the address, as the packet
INFO_ASK = b"INFO?!"        # to the link: its channel and whether it found badges
INFO_IS = b"INFO=!"         # from it: channel, found (0 / 1)
STOP = b"STOP!!"            # to the 2022 dongle: stop (its REPL free afterwards)
MAX = 250 - ADDR            # ESP-NOW carries at most 250 bytes
OUT, IN = b">", b"<"        # a line's mark going to the link, coming from it


def frame(addr, msg, mark=OUT):
    """One line: mark, address and packet in hex, newline."""
    msg = bytes(msg)
    if len(msg) > MAX:
        raise ValueError("packet too long for ESP-NOW: %d bytes" % len(msg))
    return mark + binascii.hexlify(bytes(addr) + msg) + b"\n"


class Frames:
    """Packets out of the lines of a byte stream that comes in pieces: feed(bytes),
    then next(). A line that isn't a mark and whole bytes of hex is skipped."""

    def __init__(self):
        self.buf = bytearray()

    def feed(self, data):
        self.buf += data

    def next(self):
        """(address, packet) for the next whole line, or None."""
        b = self.buf
        while True:
            i = b.find(b"\n")
            if i < 0:
                if len(b) > 4096:           # no newline in all that: junk
                    del b[:]
                return None
            line = bytes(b[:i]).strip()
            del b[:i + 1]
            if len(line) < 1 + 2 * ADDR or line[:1] not in (OUT, IN):
                continue
            try:
                raw = binascii.unhexlify(line[1:])
            except (binascii.Error, ValueError):
                continue
            return raw[:ADDR], raw[ADDR:]


ESPRESSIF = 0x303A          # the USB vendor id of an ESP32-S3's own USB (the 2022 dongle)
TILDAGON = 0x16D0           # the 2024 badge's


def _ports():
    """Serial ports that might be a link: Espressif's first, then badges."""
    try:
        from serial.tools import list_ports
        ps = sorted(list_ports.comports(), key=lambda p: p.device)
        return ([p.device for p in ps if p.vid == ESPRESSIF]
                + [p.device for p in ps if p.vid == TILDAGON])
    except Exception:
        pass
    import os
    d = "/dev/serial/by-id"
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return []
    return ([os.path.join(d, n) for n in names if "espressif" in n.lower()]
            + [os.path.join(d, n) for n in names if "tildagon" in n.lower()])


def _answers(device, wait=1.5):
    """Does something on device answer MAC_ASK? (A badge in the game ignores it.)"""
    import time
    import serial
    try:
        s = serial.Serial(device, 115200, timeout=0, write_timeout=0.2)
    except Exception:
        return False
    try:
        s.reset_input_buffer()
        f = Frames()
        end = time.time() + wait
        asked = 0
        while time.time() < end:
            if time.time() >= asked + 0.5:
                s.write(frame(MAC_ASK, b""))
                asked = time.time()
            n = s.in_waiting
            if n:
                f.feed(s.read(n))
            while True:
                got = f.next()
                if got is None:
                    break
                if got[0] == MAC_IS:
                    return True
            time.sleep(0.02)
        return False
    except Exception:
        return False
    finally:
        s.close()


def find_dongle():
    """The link's serial port, or None: the first port (Espressif's, then the badges')
    whose program answers MAC_ASK: ESP-NOW Link or tools/bridge/main.py. Linux,
    Windows and macOS alike (pyserial's list)."""
    for d in _ports():
        if _answers(d):
            return d
    return None


class Link:
    def __init__(self, device="auto", baud=115200):
        import serial           # pyserial (python3-serial)
        if device in (None, "auto"):
            device = find_dongle()
            if device is None:
                raise OSError("no link found: start ESP-NOW Link on a badge (or a bridge dongle)")
        self.ser = serial.Serial(device, baud, timeout=0, write_timeout=0.05)
        self.ser.reset_input_buffer()
        self.frames = Frames()
        self.warned = False
        self.held = []              # packets read while waiting for the address
        self.mismatch = envelope.Mismatch()
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
        print("bridge: the link didn't give its address (an old ESP-NOW Link or bridge?)")
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
        self.send_raw(envelope.wrap(self.id, msg))

    def send_raw(self, data):
        """A whole envelope onto the radio, as it is (net_relay passes others' on)."""
        try:
            self.ser.write(frame(BROADCAST, data))
        except Exception as e:      # unplugged, or the dongle stopped reading
            if not self.warned:
                self.warned = True
                print("bridge: can't send:", e)

    def recv_raw(self):
        """(radio address, data) for the next packet heard, or None."""
        while True:
            f = self.held.pop(0) if self.held else self._next()
            if f is None:
                return None
            addr, msg = f
            if addr == INFO_IS:
                if len(msg) >= 2:
                    self.channel, self.found = msg[0], bool(msg[1])
                continue
            if addr == MAC_IS:
                continue
            return addr, msg

    def recv(self):
        """(sender's player id, packet) from the envelope; another version is noted."""
        while True:
            f = self.recv_raw()
            if f is None:
                return None, None
            who, msg = envelope.open_(f[0], f[1], self.mismatch)
            if who is None or who == self.id:
                continue
            return who, msg

    def version_issues(self):
        return self.mismatch.issues()

    def net_info(self):
        """The NETWORK INFO page's lines: (text, kind), kind "ok", "warn" or "". Asks
        the dongle its channel again, for the next time (the answer comes in recv)."""
        import os
        self.info()
        if self.channel is None:
            ch = ("CHANNEL: ASKING THE LINK", "warn")
        elif self.channel == 0:         # the link's radio won't start
            ch = ("NO ESP-NOW ON THE LINK", "warn")
        elif self.found:
            ch = ("CHANNEL: %d (BADGES FOUND)" % self.channel, "ok")
        else:
            ch = ("CHANNEL: %d HUNTING" % self.channel, "warn")
        return [("LINK: BADGE LINK (USB)", "ok"),
                ("PORT: " + os.path.basename(os.path.realpath(self.device))[:20], ""),
                ch,
                ("YOU: " + ":".join("%02x" % x for x in self.id[3:]), "")]

    def stop_dongle(self):
        """Tell the dongle program to stop (its REPL is free afterwards): a frame from
        tools/bridge/main.py's STOP_ADDR."""
        self.ser.write(frame(STOP, b""))

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass
