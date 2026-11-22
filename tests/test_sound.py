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

# ---- the tables: the game's own, and Elite's when it's in use (build 141)
def check(table):
    for name, s in table.items():
        prio, parts = s[0], s[1:]
        assert isinstance(prio, int) and parts and all(parts), name
        for part in parts:
            for st in part:
                f, ms = st[0], st[1]
                assert isinstance(f, int) and isinstance(ms, int) and 0 < ms <= 1500, (name, st)
                assert f < 0 or f == 0 or 50 <= f <= 8000, (name, f)
                assert len(st) == 2 or 0 <= st[2] <= 126, (name, st)
            assert sum(st[1] for st in part) <= 2000, (name, "short")


check(sfx.OWN)
check(sfx.SOUNDS)
from ace_commander import content
if sfx.ELITE:
    E = sfx.SOUNDS
    assert not content.OWN
    assert E["lock"][1] == [(1838, 50, 126)], "Elite's short high beep"
    assert E["unarm"][1] == [(145, 400, 100)], "and its long low beep"
    assert E["laser"][1][0][0] == 122 and max(st[0] for st in E["laser"][1]) > 500, "the zap"
    assert all(st[0] < 0 for st in E["missile"][1]), "missile launch: noise"
    assert "scoop" not in E and "tick" not in E and "dock" not in E, "silent, as in Elite"
    assert sfx.CHANNELS["laser"] == sfx.CHANNELS["hurt"] == 2 and sfx.CHANNELS["lock"] == 3
    print("Elite's sounds (elite_sfx.py) in use: ok")
else:
    print("the game's own sounds in use (no elite_sfx.py, or DATA: OWN)")
print("sound tables: ok")
SOUNDS_IN_USE = sfx.SOUNDS
sfx.SOUNDS = sfx.OWN            # the buzzer tests below use the game's own


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
print("Qwiic buzzer: tones, rests, noise, priority, levels, keeping time: ok")
sfx.SOUNDS = SOUNDS_IN_USE

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
assert g.sounds == ["hurt"], "lasers on the shields"
del g.sounds[:]
g.flash = 0.0
g.shield = 0.0
g._hurt(5)
assert g.sounds == ["crash"], "no shields left: Elite's crash sound"
g.shield = 100.0
g.hull = 100.0
g.start_jump()
assert "tick" in g.sounds
g.jump_t = 0.0
# ENERGY LOW, as Elite: the message and a short high beep while the banks are low (build 142)
del g.sounds[:]
g.hull = game.ENERGY_LOW - 1
g.step(0.04, 0, 0, 0, False, False)
assert g.msg == "ENERGY LOW" and "beep" in g.sounds, (g.msg, g.sounds)
del g.sounds[:]
g.step(0.04, 0, 0, 0, False, False)
assert "beep" not in g.sounds, "not every frame"
g.hull = 100.0
# a missile exploding: Elite's crash sound
del g.sounds[:]
m = game.Obj(g.types["MISSILE"], "missile", 0.0, 0.0, 100.0)
m.t = 5.0
g.objs.append(m)
g.step(0.04, 0, 0, 0, False, False)
assert "crash" in g.sounds, g.sounds
print("Game.sfx: laser, hurt, countdown, ENERGY LOW, missile exploding: ok")

# the jump drive refused: Elite's long low beep, once a hold, again for a new field (build 144)
mod.SAVE_PATH = os.path.join(tempfile.mkdtemp(), "j.json")
from ace_commander import commander as _cm
ja = ace_commander.AceCommander()
ja.cmdr = _cm.Commander(1); ja._write(); ja._dock(); ja._start_flight(True)
jg = ja.game
jg.speed = jg.max_speed


def hold(frames, throttle=1.0):
    n = 0
    for _ in range(frames):
        del jg.sounds[:]
        jg.step(0.04, 0, 0, throttle, False, False)
        n += jg.sounds.count("boop")
    return n


assert jg.space.safe and hold(60) == 1, "the station's zone: once while held"
sp = jg.space
jg.to_sun(0.0, 1.5)                                 # the sun ahead: its mass, the station far
jg.objs[:] = []
assert not sp.safe and jg._blocker(sp) == "sun", jg._blocker(sp)
jg.speed = jg.max_speed
assert hold(30) == 1, "a new field stops the jump: once more"
jg.speed = jg.max_speed
assert hold(30) == 0, "still the same field"
hold(2, throttle=0.0)                               # let go
jg.speed = jg.max_speed
assert hold(30) == 1, "held again: once"
print("jump refused: once a hold, again for a new field: ok")


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
# docked: a beep with each trade message or refusal, as Elite's dn2 (build 142)
from ace_commander import commander
a._change("SOUND: OFF", False)
a.cmdr = commander.Commander(1)
a._write()
a._dock()
bs.tick(a)
dev.played[:] = []
a.dock.msg = "NOT ENOUGH CASH"
bs.tick(a)
a.dock.msg = "NOT ENOUGH CASH"      # the same refusal again: another beep
bs.tick(a)
assert dev.played.count("beep") == 2, dev.played
bs.tick(a)
assert dev.played.count("beep") == 2, "not again without a new message"
a._change("SOUND: ON", False)
b2 = ace_commander.AceCommander()
assert not b2.use_sound, "kept in options.json"
a._change("SOUND: OFF", False)
print("ace: sounds to the device, SOUND: ON / OFF, saved: ok")
print("ALL SOUND TESTS PASSED")
