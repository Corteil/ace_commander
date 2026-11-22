"""A SparkFun Qwiic Buzzer (build 140) playing the game's sounds (sfx.py) on
the badge (a hexpansion port with a Qwiic connector) or the Tufty (its Qw/ST
port). Register map from SparkFun's Qwiic_Buzzer_Py (MIT): address 0x34, ID
register 0x00 reads 0x5E; from register 0x03 frequency (2 bytes), volume
(1-4), duration ms (2 bytes); register 0x08 starts (1) or stops (0) it.

Never blocks: play() starts a sound, step() (each frame) moves it on to its
next tone when that tone's time is up. Each tone is one short I2C write.
"""
import random

try:
    from time import ticks_ms, ticks_diff
except ImportError:         # a PC (the tests)
    import time

    def ticks_ms():
        return int(time.monotonic() * 1000)

    def ticks_diff(a, b):
        return a - b

try:
    from . import sfx
except ImportError:
    import sfx

ADDRESS = 0x34
ID = 0x5E
REG_ID = 0x00
REG_FREQ = 0x03
REG_ACTIVE = 0x08
NOISE_STEP = 20             # ms a pitch lasts in a noise burst
VOLUME = 3                  # 1 quiet ... 4 loudest


def find(i2c):
    """True if a Qwiic Buzzer answers on this bus."""
    try:
        if ADDRESS not in i2c.scan():
            return False
        return i2c.readfrom_mem(ADDRESS, REG_ID, 1)[0] == ID
    except Exception:
        return False


class Buzzer:
    def __init__(self, i2c, volume=VOLUME):
        self.i2c = i2c
        self.volume = volume
        self.steps = None       # the sound playing: its steps,
        self.i = 0              # the one now,
        self.prio = -1          # its priority
        self.due = 0            # and when the next step starts (ticks_ms)
        self.left = 0           # ms of noise left in this step
        self.buf = bytearray(5)
        self.ok = True          # False once a write has failed: it is left alone

    def play(self, name):
        s = sfx.SOUNDS.get(name)
        if s is None or not self.ok:
            return
        prio, steps = s
        if self.steps is not None and prio < self.prio:
            return              # something more important is playing
        self.steps = steps
        self.prio = prio
        self.i = -1
        self.left = 0
        self.due = ticks_ms()
        self.step()

    def step(self):
        """Move on to the next tone if this one's time is up."""
        if self.steps is None or not self.ok:
            return
        now = ticks_ms()
        if ticks_diff(now, self.due) < 0:
            return
        if self.left > 0:                       # more of a noise burst
            ms = min(NOISE_STEP, self.left)
            self.left -= ms
            self._tone(random.randint(120, 700), ms)
            self.due = now + ms
            return
        self.i += 1
        if self.i >= len(self.steps):
            self.steps = None
            self.prio = -1
            self._write(REG_ACTIVE, 0)
            return
        f, ms = self.steps[self.i]
        if f == sfx.NOISE:
            self.left = ms
            self.due = now
            self.step()
            return
        if f <= 0:
            self._write(REG_ACTIVE, 0)          # a rest
        else:
            self._tone(f, ms)
        self.due = now + ms

    def stop(self):
        self.steps = None
        self.prio = -1
        self._write(REG_ACTIVE, 0)

    def _tone(self, f, ms):
        b = self.buf
        b[0] = (f >> 8) & 0xFF
        b[1] = f & 0xFF
        b[2] = self.volume
        b[3] = (ms >> 8) & 0xFF
        b[4] = ms & 0xFF
        try:
            self.i2c.writeto_mem(ADDRESS, REG_FREQ, b)
            self.i2c.writeto_mem(ADDRESS, REG_ACTIVE, b"\x01")
        except Exception:
            self.ok = False

    def _write(self, reg, v):
        try:
            self.i2c.writeto_mem(ADDRESS, reg, b"\x01" if v else b"\x00")
        except Exception:
            self.ok = False
