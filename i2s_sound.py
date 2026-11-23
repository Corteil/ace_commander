"""The game's sounds on an I2S amplifier or DAC on a hexpansion port (build
145, plans/I2S_SOUND.md): a MAX98357A speaker amp or the AudioHexpansion's
PCM5102A, wired as BadgeRadio's: the port's HS1 = BCLK, HS2 = LRC, HS3 = DIN.
It replaces the Qwiic buzzer (buzzer.py, builds 140-144).

The sounds (sfx.py) are made as they play, not stored (stored, they would take
about 300 KB of heap): one voice per part, square waves and noise as the Pi
(hosts/pi/sound_pi.py), mixed into one reused buffer. A sound starts on its
channel (sfx.CHANNELS, Elite's flush), cutting off what was playing there.

Never blocks a frame for long: step() (each frame) writes only what the
amplifier will play before about LEAD_MS from now, so the I2S buffer is never
full when it writes. Nothing is written when nothing plays: the badge's I2S
sends silence when it runs out (the firmware's auto_clear).

Synth runs on a PC too (the tests): anything with write(buffer) as the output
and a clock in milliseconds; the inner loops are viper on the badge, plain
Python elsewhere (the same numbers).
"""
import sys
from array import array

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

RATE = 11025            # samples a second, mono 16 bit: the BBC Micro's sounds are low-fi
LEAD_MS = 120           # written ahead of what plays: rides out a garbage collection (~45 ms)
CHUNK = 512             # samples made at a time (the buffer, reused)
IBUF = 8192             # bytes the I2S driver buffers (it keeps 16-bit stereo: ~186 ms)
SETTLE_MS = 250         # after opening, its buffers are all in use for about that long, so a
                        # write waits (measured: 43-67 ms frames): nothing written till then
MAX_VOICES = 4          # parts playing at once (the BBC Micro had 4 channels)
PORT = 2                # the hexpansion port, as BadgeRadio's default
PORTS = (1, 2, 3, 4, 5, 6)
I2S_ID = 0
SEED = 0x2545F491

# a voice's state, a word each (array 'i', so viper reads it as ptr32)
PHASE, INC, AMP, VALUE, RAND = 0, 1, 2, 3, 4

if sys.implementation.name == "micropython":
    import micropython

    @micropython.viper
    def _clear(buf: ptr16, n: int):
        i = 0
        while i < n:
            buf[i] = 0
            i += 1

    @micropython.viper
    def _square(buf: ptr16, pos: int, n: int, st: ptr32):
        """Add n samples of a square wave to buf from pos (16.16 phase)."""
        phase = st[0]
        inc = st[1]
        amp = st[2]
        i = pos
        end = pos + n
        while i < end:
            v = int(buf[i])
            if v > 32767:
                v -= 65536
            if phase & 0x8000:
                v -= amp
            else:
                v += amp
            if v > 32767:
                v = 32767
            elif v < -32767:
                v = -32767
            buf[i] = v & 0xFFFF
            phase = (phase + inc) & 0xFFFF
            i += 1
        st[0] = phase

    @micropython.viper
    def _noise(buf: ptr16, pos: int, n: int, st: ptr32):
        """Add n samples of noise to buf from pos: a new random level each time
        the phase passes a whole cycle (INC: the rate it changes at)."""
        phase = st[0]
        inc = st[1]
        amp = st[2]
        val = st[3]
        s = uint(st[4])
        span = amp * 2 + 1
        i = pos
        end = pos + n
        while i < end:
            phase += inc
            if phase >= 0x10000:
                phase &= 0xFFFF
                s ^= s << 13
                s ^= s >> 17
                s ^= s << 5
                val = ((int(s >> 16) * span) >> 16) - amp
            v = int(buf[i])
            if v > 32767:
                v -= 65536
            v += val
            if v > 32767:
                v = 32767
            elif v < -32767:
                v = -32767
            buf[i] = v & 0xFFFF
            i += 1
        st[0] = phase
        st[3] = val
        st[4] = int(s)
else:
    def _clear(buf, n):
        for i in range(n):
            buf[i] = 0

    def _square(buf, pos, n, st):
        phase, inc, amp = st[0], st[1], st[2]
        for i in range(pos, pos + n):
            v = buf[i] + (-amp if phase & 0x8000 else amp)
            buf[i] = 32767 if v > 32767 else (-32767 if v < -32767 else v)
            phase = (phase + inc) & 0xFFFF
        st[0] = phase

    def _noise(buf, pos, n, st):
        phase, inc, amp, val = st[0], st[1], st[2], st[3]
        s = st[4] & 0xFFFFFFFF
        span = amp * 2 + 1
        for i in range(pos, pos + n):
            phase += inc
            if phase >= 0x10000:
                phase &= 0xFFFF
                s ^= (s << 13) & 0xFFFFFFFF
                s ^= s >> 17
                s ^= (s << 5) & 0xFFFFFFFF
                val = (((s >> 16) * span) >> 16) - amp
            v = buf[i] + val
            buf[i] = 32767 if v > 32767 else (-32767 if v < -32767 else v)
        st[0] = phase
        st[3] = val
        st[4] = s - 0x100000000 if s >= 0x80000000 else s


class Voice:
    """One part of a sound: its steps, played in turn."""

    def __init__(self, channel, prio, steps, rate, seed, top):
        self.channel = channel
        self.prio = prio
        self.steps = steps
        self.rate = rate
        self.top = top          # the height at level 126 (the volume)
        self.i = -1
        self.left = 0           # samples left of the step now
        self.kind = 0           # 0 a rest, 1 a square wave, 2 noise
        self.st = array("i", [0, 0, 0, 0, seed])
        self.next()

    def next(self):
        """On to the next step; False when there are none left."""
        self.i += 1
        if self.i >= len(self.steps):
            return False
        s = self.steps[self.i]
        f, ms = s[0], s[1]
        amp = self.top * (s[2] if len(s) > 2 else 126) // 126
        self.left = self.rate * ms // 1000
        st = self.st
        st[AMP] = amp
        st[INC] = ((-f if f < 0 else f) << 16) // self.rate
        self.kind = 0 if f == 0 or amp == 0 else (2 if f < 0 else 1)
        return True


class Synth:
    def __init__(self, out, rate=RATE, clock=None):
        """out: anything with write(buffer) (machine.I2S, or a test's stand-in)."""
        self.out = out
        self.rate = rate
        self.clock = clock or ticks_ms
        self.voices = []
        self.buf = array("h", bytes(CHUNK * 2))
        self.mv = memoryview(self.buf)
        self.t0 = None          # when the first sample written plays (ms), or None: idle
        self.written = 0        # samples written since t0
        self.seed = SEED
        self.level = sfx.VOLUMES[sfx.VOLUME_DEFAULT]    # the height at level 126
        self.hold = None        # nothing written before this time (ms), or None

    def settle(self, ms=SETTLE_MS):
        """Just opened: write nothing for ms (sounds asked for meanwhile start then)."""
        self.hold = self.clock() + ms

    def set_volume(self, v):
        """Options > VOLUME, 1-11 (sfx.VOLUMES): from each sound's next step."""
        self.level = sfx.VOLUMES[max(1, min(sfx.VOLUME_MAX, v))]

    def play(self, name):
        s = sfx.SOUNDS.get(name)
        if s is None:
            return
        ch = sfx.CHANNELS.get(name, name)
        vs = [v for v in self.voices if v.channel != ch]    # its channel restarts
        for part in s[1:]:
            self.seed = (self.seed * 1103515245 + 12345) & 0x7FFFFFFF
            vs.append(Voice(ch, s[0], part, self.rate, self.seed, self.level))
        while len(vs) > MAX_VOICES:     # too many: the least important, oldest first
            low = min(v.prio for v in vs)
            for k, v in enumerate(vs):
                if v.prio == low:
                    del vs[k]
                    break
        self.voices = vs

    def render(self, name):
        """The whole of one sound, as 16-bit samples (array 'h'): the Pi makes
        each of its sounds this way at start (build 146), so both play the
        same. Not for the badge: a sound at once costs heap."""
        out = array("h")
        self.voices = []
        self.play(name)
        while self.voices:
            n = self._make(CHUNK)
            out.extend(self.buf[:n])
        return out

    def playing(self):
        return bool(self.voices)

    def stop(self):
        self.voices = []

    def step(self):
        """Write what plays before LEAD_MS from now (each frame)."""
        if self.hold is not None:
            if ticks_diff(self.hold, self.clock()) > 0:
                return
            self.hold = None
        if self.t0 is None:
            if not self.voices:
                return
            self.t0 = self.clock()
            self.written = 0
        played = ticks_diff(self.clock(), self.t0) * self.rate // 1000
        if self.written < played:       # ran out (a long frame): it played silence
            self.written = played
        if not self.voices:
            if played >= self.written:
                self.t0 = None          # all played: idle
            return
        want = played + LEAD_MS * self.rate // 1000 - self.written
        while want > 0 and self.voices:
            n = self._make(CHUNK if want > CHUNK else want)
            self.out.write(self.mv[:n])
            self.written += n
            want -= n
        if self.written > 0x3FFFFFFF:   # very long: start counting again
            self.t0 = None

    def _make(self, n):
        """The next n samples of every voice, mixed into buf. Returns how many
        to write: n, or fewer if every voice ended before it."""
        buf = self.buf
        _clear(buf, n)
        done = False
        last = 0
        for v in self.voices:
            pos = 0
            while pos < n:
                k = n - pos
                if k > v.left:
                    k = v.left
                if v.kind == 1:
                    _square(buf, pos, k, v.st)
                elif v.kind == 2:
                    _noise(buf, pos, k, v.st)
                v.left -= k
                pos += k
                if v.left <= 0 and not v.next():
                    v.steps = None
                    done = True
                    break
            if pos > last:
                last = pos
        if done:
            self.voices = [v for v in self.voices if v.steps is not None]
        return n if self.voices else last


def open_i2s(port, rate=RATE):
    """machine.I2S on the port's high-speed pins (HS1 BCLK, HS2 LRC, HS3 DIN),
    opened small and closed first, as BadgeRadio does, to clear what a crash
    may have left. Raises if it can't."""
    from machine import I2S
    from system.hexpansion.config import HexpansionConfig
    pins = HexpansionConfig(port).pin
    sck, ws, sd = pins[0], pins[1], pins[2]
    try:
        I2S(I2S_ID, sck=sck, ws=ws, sd=sd, mode=I2S.TX, bits=16, format=I2S.MONO,
            rate=rate, ibuf=2048).deinit()
    except Exception:
        pass
    return I2S(I2S_ID, sck=sck, ws=ws, sd=sd, mode=I2S.TX, bits=16, format=I2S.MONO,
               rate=rate, ibuf=IBUF)
