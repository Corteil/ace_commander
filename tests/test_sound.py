"""Sound (build 140): the sound table (sfx.py), the Qwiic buzzer player
(buzzer.py) on a stand-in I2C bus, the game asking for sounds (Game.sfx), ace.py
handing them to the device, and Options > SOUND. Needs no Elite files."""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs

bs.install()
import ace_commander
from ace_commander import buzzer, game, sfx
mod = ace_commander.ace

# ---- the table
for name, (prio, steps) in sfx.SOUNDS.items():
    assert isinstance(prio, int) and steps, name
    for f, ms in steps:
        assert isinstance(f, int) and isinstance(ms, int) and 0 < ms <= 1000, (name, f, ms)
        assert f == sfx.NOISE or f == 0 or 50 <= f <= 5000, (name, f)
    assert sfx.length(name) <= 1500, (name, "short")
print("sound table: %d sounds: ok" % len(sfx.SOUNDS))


# ---- the buzzer, on a stand-in bus and clock
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
b.play("scoop")             # (1200, 40), (1700, 70)
assert bus.writes[0] == (buzzer.REG_FREQ, bytes([1200 >> 8, 1200 & 255, buzzer.VOLUME, 0, 40]))
assert bus.writes[1] == (buzzer.REG_ACTIVE, b"\x01")
b.step(); assert len(bus.writes) == 2, "not until the tone's time is up"
now[0] += 40; b.step()
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
print("Qwiic buzzer: tones, rests, noise, priority: ok")

# ---- the game asks for sounds
g = game.Game(mod.SHIPS)
g.rock_t = g.encounter_t = g.spawn_t = 1e9
g.objs[:] = []
g.set_laser("pulse")
for _ in range(3):
    g.step(0.04, 0, 0, 0, True, False)
assert "laser" in g.sounds, g.sounds
del g.sounds[:]
g._hurt(5)
assert g.sounds == ["hurt"]
g.start_jump()
assert "tick" in g.sounds
print("Game.sfx: laser, hurt, countdown: ok")


# ---- ace hands them to the device, Options > SOUND
class Sound:
    def __init__(self):
        self.played = []
        self.steps = 0

    def play(self, name):
        self.played.append(name)

    def step(self):
        self.steps += 1


mod.SAVE_PATH = os.path.join(tempfile.mkdtemp(), "c.json")
a = ace_commander.AceCommander()
assert not any(i.startswith("SOUND") for i in a._settings(False)), "no sound: no line"
dev = Sound()
a.platform.sound_ok = True
a.platform.sound = dev.play
a.platform.sound_step = dev.step
items = a._settings(False)
assert "SOUND: ON" in items, items
bs.tick(a)
bs.choose(a, "COMBAT PRACTICE")
assert a.mode == "flight"
a.game.sfx("explode")
bs.tick(a)
assert "explode" in dev.played and dev.steps > 0 and not a.game.sounds
a._change("SOUND: ON", False)
assert not a.use_sound and "SOUND: OFF" in a._settings(False)
dev.played[:] = []
a.game.sfx("explode")
bs.tick(a)
assert dev.played == [] and not a.game.sounds, "SOUND: OFF plays nothing"
b2 = ace_commander.AceCommander()
assert not b2.use_sound, "kept in options.json"
a._change("SOUND: OFF", False)
print("ace: sounds to the device, SOUND: ON / OFF, saved: ok")
print("ALL SOUND TESTS PASSED")
