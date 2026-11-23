"""A SparkFun Qwiic Buzzer (build 140) playing the game's sounds (sfx.py) on
the Tufty's Qw/ST port: the Tufty's only way to make a sound (it has no buzzer
or free I2S pins). The badge dropped it for I2S in build 145 (i2s_sound.py);
it came back for the Tufty alone, as a host file (build 146). Register map from SparkFun's Qwiic_Buzzer_Py (MIT): address 0x34, ID
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
    from ace_commander import sfx       # on the Tufty, and the tests
except ImportError:
    import sfx

ADDRESS = 0x34
ID = 0x5E
REG_ID = 0x00
REG_FREQ = 0x03
REG_ACTIVE = 0x08
MODULINO = 0x1E             # an Arduino Modulino Buzzer (build 146): 0x3C in Arduino's
MODULINO_MIN = 180          # 8-bit form; 8 bytes a tone, no volume, nothing under 180 Hz
NOISE_STEP = 20             # ms a pitch lasts in a noise burst, changed each frame
NOISE_FAST = 3              # with a timer: a new pitch every 3 ms, heard as static (Brian,
                            # build 147: 3 and 2 ms alike; 250-1333 Hz better than 200-8000)
VOLUME = 3                  # 1 quiet ... 4 loudest


def open_buzzer(i2c):
    """The buzzer on this bus: a SparkFun Qwiic Buzzer, else an Arduino
    Modulino Buzzer, else None (build 146)."""
    if find(i2c):
        return Buzzer(i2c, timer=_timer())
    try:
        if MODULINO in i2c.scan():
            return ModulinoBuzzer(i2c, timer=_timer())
    except Exception:
        pass
    return None


def _timer():
    """A software timer for noise (machine.Timer), or None (a PC)."""
    try:
        from machine import Timer
        return Timer()
    except Exception:
        return None


def find(i2c):
    """True if a SparkFun Qwiic Buzzer answers on this bus."""
    try:
        if ADDRESS not in i2c.scan():
            return False
        return i2c.readfrom_mem(ADDRESS, REG_ID, 1)[0] == ID
    except Exception:
        return False


class Buzzer:
    def __init__(self, i2c, volume=VOLUME, timer=None):
        """timer: a machine.Timer for fast noise (build 147); None: a new
        pitch each frame at most (NOISE_STEP)."""
        self.i2c = i2c
        self.timer = timer
        self.fast = False       # the timer is running (a noise step now)
        self.lo = self.hi = 0   # its pitches
        self.tick = self._tick  # (made once: a bound method is a new object each time)
        self.volume = volume
        self.steps = None       # the sound playing: its steps,
        self.i = 0              # the one now,
        self.prio = -1          # its priority
        self.end = 0            # when the step now ends (ticks_ms)
        self.shown = -1         # the step last written
        self.next_noise = 0     # when a noise step next changes pitch
        self.buf = bytearray(5)
        self.vol = volume       # this step's volume (its level, up to volume)
        self.ok = True          # False once a write has failed: it is left alone

    def set_volume(self, v):
        """Options > VOLUME 1-11 onto the buzzer's 1-4: 1-4 quietest, 5-7, 8-10, 11 loudest."""
        v = max(1, min(sfx.VOLUME_MAX, v))
        self.volume = 1 + (v - 1) * 3 // (sfx.VOLUME_MAX - 1)

    def play(self, name):
        s = sfx.SOUNDS.get(name)
        if s is None or not self.ok:
            return
        prio, steps = s[0], s[1]    # (only the first part: one tone at a time)
        if self.steps is not None and prio < self.prio:
            return              # something more important is playing
        self.steps = steps
        self.prio = prio
        self.i = 0
        self.end = ticks_ms() + steps[0][1]     # when this step ends
        self.shown = -1         # the step last written to the buzzer
        self.next_noise = 0
        self.step()

    def step(self):
        """Write the tone due now. Called once a frame, so steps shorter than a
        frame (Elite's change every 10 ms) are skipped over, keeping time."""
        if self.steps is None or not self.ok:
            return
        now = ticks_ms()
        steps = self.steps
        while ticks_diff(now, self.end) >= 0:
            self.i += 1
            if self.i >= len(steps):
                self.steps = None
                self.prio = -1
                self._slow()
                self._write(REG_ACTIVE, 0)
                return
            self.end += steps[self.i][1]
        st = steps[self.i]
        f = st[0]
        level = st[2] if len(st) > 2 else 126
        vol = 0 if level <= 0 else min(self.volume, 1 + level * self.volume // 127)
        left = ticks_diff(self.end, now)
        if f < 0 and vol:       # noise: random pitches round its rate
            r = -f
            if self.timer is not None:      # every NOISE_FAST ms, by the timer
                if self.i != self.shown:
                    self.vol = vol
                    self.lo = max(80, r // 16)
                    self.hi = max(160, min(4000, r // 3))
                    self.shown = self.i
                    self._tick(None)
                    if not self.fast:
                        self.timer.init(period=NOISE_FAST, mode=self.timer.PERIODIC,
                                        callback=self.tick)
                        self.fast = True
                return
            if self.i != self.shown or ticks_diff(now, self.next_noise) >= 0:
                self.vol = vol
                self._tone(random.randint(max(80, r // 16), max(160, min(4000, r // 3))),
                           min(NOISE_STEP, left))
                self.next_noise = now + NOISE_STEP
                self.shown = self.i
            return
        self._slow()
        if self.i == self.shown:
            return
        self.shown = self.i
        if f <= 0 or not vol:
            self._write(REG_ACTIVE, 0)          # a rest
        else:
            self.vol = vol
            self._tone(f, left)

    def stop(self):
        self.steps = None
        self.prio = -1
        self._slow()
        self._write(REG_ACTIVE, 0)

    def _slow(self):
        """No noise step now: the timer off."""
        if self.fast:
            self.fast = False
            try:
                self.timer.deinit()
            except Exception:
                pass

    def _tick(self, _t):
        """The timer (a soft callback, between bytecodes): the next random
        pitch, while the noise step lasts and nothing else has taken over."""
        if not self.fast and _t is not None:
            return
        if self.steps is None or not self.ok or ticks_diff(ticks_ms(), self.end) >= 0:
            return              # step() moves on (and stops the timer) next frame
        self._tone(random.randint(self.lo, self.hi), NOISE_FAST + 5)

    def _tone(self, f, ms):
        b = self.buf
        b[0] = (f >> 8) & 0xFF
        b[1] = f & 0xFF
        b[2] = self.vol
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


class ModulinoBuzzer(Buzzer):
    """An Arduino Modulino Buzzer (build 146; Arduino's arduino-modulino-mpy):
    one 8-byte write a tone, the frequency then the length in ms, each 4 bytes
    little-endian; all zeros stops it. It has no volume (VOLUME does nothing
    but a level 0 step is still a rest) and plays nothing under 180 Hz, so
    lower notes are raised to that."""

    def __init__(self, i2c, volume=VOLUME, timer=None):
        Buzzer.__init__(self, i2c, volume, timer)
        self.buf = bytearray(8)
        self._write(REG_ACTIVE, 0)

    def _tone(self, f, ms):
        if f < MODULINO_MIN:
            f = MODULINO_MIN
        b = self.buf
        for i in range(4):
            b[i] = (f >> (8 * i)) & 0xFF
            b[4 + i] = (ms >> (8 * i)) & 0xFF
        try:
            self.i2c.writeto(MODULINO, b)
        except Exception:
            self.ok = False

    def _write(self, reg, v):
        if v:
            return              # (it starts with each tone)
        b = self.buf
        for i in range(8):
            b[i] = 0
        try:
            self.i2c.writeto(MODULINO, b)
        except Exception:
            self.ok = False
