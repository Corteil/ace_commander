"""The Tufty's buzzers (builds 140, 146): a SparkFun Qwiic Buzzer or an Arduino
Modulino Buzzer on the Qw/ST port (buzzer_tufty.py), on stand-in I2C buses
and a stand-in clock. Needs no Elite files or Badgeware."""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TUFTY = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(TUFTY))
sys.path.insert(0, TUFTY)
sys.path.insert(0, os.path.dirname(REPO))
spec = importlib.util.find_spec("ace_commander")    # the package without its PC __init__
sys.modules["ace_commander"] = importlib.util.module_from_spec(spec)
from ace_commander import sfx           # noqa: E402
import buzzer_tufty as buzzer           # noqa: E402

sfx.SOUNDS, sfx.CHANNELS = sfx.OWN, sfx.OWN_CHANNELS


class FakeI2C:
    def __init__(self, present=True):
        self.present = present
        self.writes = []

    def scan(self):
        return [0x21, buzzer.ADDRESS] if self.present else [0x21]

    def readfrom_mem(self, addr, reg, n):
        assert addr == buzzer.ADDRESS and reg == buzzer.REG_ID
        return bytes([buzzer.ID])

    def writeto_mem(self, addr, reg, data):
        assert addr == buzzer.ADDRESS
        self.writes.append((reg, bytes(data)))


now = [1000]
buzzer.ticks_ms = lambda: now[0]
assert buzzer.find(FakeI2C()) and not buzzer.find(FakeI2C(False))
bus = FakeI2C()
b = buzzer.Buzzer(bus)
sfx.SOUNDS = dict(sfx.OWN, two=(2, [(1200, 40), (1700, 70)]))
b.play("two")               # (1200, 40), (1700, 70)
assert bus.writes[0] == (buzzer.REG_FREQ, bytes([1200 >> 8, 1200 & 255, buzzer.VOLUME, 0, 40]))
assert bus.writes[1] == (buzzer.REG_ACTIVE, b"\x01")
b.step(); assert len(bus.writes) == 2, "not until the tone's time is up"
now[0] += 40; b.step()
assert bus.writes[2][1][4] == 70, "the second tone, its full 70 ms"
assert bus.writes[2][1][:2] == bytes([1700 >> 8, 1700 & 255]), bus.writes[2]
now[0] += 70; b.step()
assert bus.writes[-1] == (buzzer.REG_ACTIVE, b"\x00") and b.steps is None, "done: off"
b.play("incoming")          # priority 4
b.play("laser")             # 1: doesn't cut it short
assert b.steps is sfx.SOUNDS["incoming"][1]
b.play("die")               # 5: does
assert b.steps is sfx.SOUNDS["die"][1]
for _ in range(200):        # the noise burst plays as pitches, then the tones
    now[0] += 20
    b.step()
assert b.steps is None
# steps shorter than a frame are skipped, keeping time (Elite's change every 10 ms)
sfx.SOUNDS = {"fast": (1, [(f, 10, 126) for f in range(500, 1500, 10)])}   # 1 s of 10 ms steps
b.play("fast")
n = 0
while b.steps is not None and n < 100:
    now[0] += 40                # a 40 ms frame
    b.step()
    n += 1
assert 24 <= n <= 26, ("1 s in 40 ms frames", n)
sfx.SOUNDS = {"soft": (1, [(1000, 50, 30), (1000, 50, 126), (1000, 50, 0)])}
bus.writes[:] = []
b.play("soft")
assert bus.writes[0][1][2] == 1, "a quiet step: volume 1"
now[0] += 50; b.step()
assert bus.writes[-2][1][2] == buzzer.VOLUME, "a loud one: the buzzer's volume"
now[0] += 50; b.step()
assert bus.writes[-1] == (buzzer.REG_ACTIVE, b"\x00"), "level 0: a rest"
sfx.SOUNDS = sfx.OWN
print("SparkFun Qwiic Buzzer: tones, rests, noise, priority, levels, keeping time: ok")

# VOLUME 1-11 onto its 1-4
for v, want in ((1, 1), (4, 1), (5, 2), (8, 3), (10, 3), (11, 4), (0, 1), (99, 4)):
    b.set_volume(v)
    assert b.volume == want, (v, b.volume, want)
b.set_volume(sfx.VOLUME_DEFAULT)
assert b.volume == buzzer.VOLUME, "VOLUME 8: the buzzer's old default"


# ---- open_buzzer: whichever is on the bus
class FakeModulino:
    def __init__(self):
        self.writes = []

    def scan(self):
        return [0x21, buzzer.MODULINO]

    def readfrom_mem(self, addr, reg, n):
        raise OSError("no such device")

    def writeto(self, addr, data):
        assert addr == buzzer.MODULINO and len(data) == 8
        self.writes.append(bytes(data))


class Empty(FakeI2C):
    def scan(self):
        return [0x21]


assert type(buzzer.open_buzzer(FakeI2C())) is buzzer.Buzzer
assert buzzer.open_buzzer(Empty()) is None
mb = FakeModulino()
m = buzzer.open_buzzer(mb)
assert type(m) is buzzer.ModulinoBuzzer
assert mb.writes == [bytes(8)], "silent at start"


def tone(data):
    return int.from_bytes(data[:4], "little"), int.from_bytes(data[4:], "little")


sfx.SOUNDS = {"two": (2, [(1200, 40), (1700, 70)]), "low": (2, [(150, 400, 100)]),
              "soft": (1, [(1000, 50, 30), (1000, 50, 0)])}
now[0] = 5000
m.play("two")
assert tone(mb.writes[-1]) == (1200, 40), tone(mb.writes[-1])
now[0] += 40; m.step()
assert tone(mb.writes[-1]) == (1700, 70)
now[0] += 70; m.step()
assert mb.writes[-1] == bytes(8) and m.steps is None, "done: stopped"
m.play("low")
assert tone(mb.writes[-1]) == (buzzer.MODULINO_MIN, 400), "under 180 Hz: raised to 180"
now[0] += 400; m.step()
m.play("soft")
assert tone(mb.writes[-1])[0] == 1000
now[0] += 50; m.step()
assert mb.writes[-1] == bytes(8), "level 0: a rest"
m.stop()
assert mb.writes[-1] == bytes(8) and m.steps is None
print("Arduino Modulino Buzzer: found, tones, low notes, rests, stop: ok")
print("ALL TUFTY BUZZER TESTS PASSED")
