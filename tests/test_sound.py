"""Sound (builds 140, 145): the sound table (sfx.py), the badge's I2S
synthesiser (i2s_sound.py) on a stand-in output and clock, the game asking for
sounds (Game.sfx), ace.py handing them to the device, and Options > SOUND and
SOUND PORT. Needs no Elite files."""
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
from ace_commander import game, i2s_sound, sfx
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
CHANNELS_IN_USE = sfx.CHANNELS
sfx.SOUNDS, sfx.CHANNELS = sfx.OWN, sfx.OWN_CHANNELS    # the synth tests use the game's own


# ---- the I2S synthesiser (build 145), on a stand-in output and clock
class Out:
    def __init__(self):
        self.samples = []
        self.calls = 0

    def write(self, mv):
        self.calls += 1
        self.samples.extend(mv.tolist() if hasattr(mv, "tolist") else list(mv))


now = [1000]
RATE = i2s_sound.RATE
TOP = sfx.VOLUMES[sfx.VOLUME_DEFAULT]       # a square wave's height at level 126
assert sfx.VOLUME_MAX == mod.VOLUME_MAX == 11 and sfx.VOLUME_DEFAULT == mod.VOLUME_DEFAULT
assert len(sfx.VOLUMES) == 12 and list(sfx.VOLUMES) == sorted(sfx.VOLUMES), "it goes to 11"
LEAD = i2s_sound.LEAD_MS * RATE // 1000


def synth():
    o = Out()
    return o, i2s_sound.Synth(o, clock=lambda: now[0])


def run(s, ms, frame=40):
    """Frames of `frame` ms until ms have passed."""
    for _ in range(ms // frame):
        now[0] += frame
        s.step()


def crossings(xs):
    return sum(1 for a, b in zip(xs, xs[1:]) if (a < 0) != (b < 0))


out, s = synth()
s.step()
assert out.calls == 0, "idle: nothing written"
sfx.SOUNDS = dict(sfx.OWN, tone=(1, [(1000, 200)]), soft=(1, [(1000, 200, 63)]),
                  two=(1, [(500, 100)], [(1500, 100)]), hiss=(1, [(-2000, 200)]),
                  rest=(1, [(0, 100), (1000, 100)]), loud=(1, [(500, 100)] , [(500, 100)],
                                                           [(500, 100)], [(500, 100)],
                                                           [(500, 100)], [(500, 100)]))
s.play("tone")
s.step()
assert len(out.samples) == LEAD, ("one frame: only the lead written", len(out.samples), LEAD)
run(s, 400)
n = RATE * 200 // 1000
assert len(out.samples) == n, ("the whole tone, no more", len(out.samples), n)
assert max(out.samples) == TOP and min(out.samples) == -TOP
c = crossings(out.samples)
assert abs(c - 2 * 1000 * 200 // 1000) <= 2, ("1000 Hz", c)
assert s.t0 is None and not s.playing(), "all played: idle again"
calls = out.calls
run(s, 200)
assert out.calls == calls, "nothing written while idle"
# keeping ahead: a long frame (a garbage collection) is silence, then it catches up
out, s = synth()
sfx.SOUNDS["long"] = (1, [(800, 1000)])
s.play("long")
s.step()
now[0] += 300                   # 300 ms without a frame: the lead ran out
s.step()
played = 300 * RATE // 1000
assert s.written == played + LEAD, ("resynced past the gap", s.written, played + LEAD)
for _ in range(10):
    now[0] += 40
    before = s.written
    s.step()
    assert s.written - before <= 40 * RATE // 1000 + 1, "never more than a frame's worth ahead"
# levels, rests, parts mixed, noise
out, s = synth()
s.play("soft"); run(s, 400)
assert max(out.samples) == TOP * 63 // 126, "level 63: half"
out, s = synth()
s.play("rest"); run(s, 400)
half = RATE * 100 // 1000
assert not any(out.samples[:half]) and max(out.samples[half:]) > 0, "a rest, then the tone"
out, s = synth()
s.play("two"); run(s, 400)
assert len(out.samples) == half and max(out.samples) == 2 * TOP, "two parts added"
out, s = synth()
s.play("hiss"); run(s, 400)
xs = out.samples
assert len(set(xs)) > 50 and max(xs) <= TOP and min(xs) >= -TOP, "noise"
runs = sum(1 for a, b in zip(xs, xs[1:]) if a != b)
assert abs(runs - 2000 * 200 // 1000) < 40, ("noise changing 2000 times a second", runs)
out, s = synth()
s.play("loud"); run(s, 400)
assert len(s.voices) == 0 and max(out.samples) == 4 * TOP, "4 voices at most"
# channels: a sound restarts its own channel (Elite's flush), others play on
out, s = synth()
s.play("laser"); s.play("lock")
assert len(s.voices) == 2
s.play("beep")                  # lock's channel
assert len(s.voices) == 2 and s.voices[-1].steps is sfx.OWN["beep"][1]
s.play("laser")
assert len(s.voices) == 2 and s.voices[-1].channel == sfx.OWN_CHANNELS["laser"]
# every sound in both tables plays through and ends
for table in (sfx.OWN, SOUNDS_IN_USE):
    sfx.SOUNDS = table
    for name in table:
        out, s = synth()
        s.play(name)
        run(s, sfx.length(name) + 400)
        assert not s.playing() and s.t0 is None, name
        want = max(sum(RATE * st[1] // 1000 for st in part) for part in table[name][1:])
        assert len(out.samples) == want, (name, len(out.samples), want)
        assert max(abs(v) for v in out.samples) <= 32767, name
# just opened: nothing written while it settles, then the sound from its start
out, s = synth()
s.settle()
sfx.SOUNDS = dict(sfx.OWN, tone=(1, [(1000, 100)]))
s.play("tone")
for _ in range(i2s_sound.SETTLE_MS // 40):
    now[0] += 40; s.step()
assert out.calls == 0, "settling: nothing written"
run(s, 400)
assert len(out.samples) == RATE * 100 // 1000 and s.hold is None, "then all of it"
# render (the Pi's, build 146): the same samples the badge streams
sfx.SOUNDS = sfx.OWN
for name in ("laser", "explode", "jump", "ecm"):
    out, s = synth()
    s.play(name)
    run(s, sfx.length(name) + 400)
    r = i2s_sound.Synth(None).render(name)
    assert list(r) == out.samples, (name, len(r), len(out.samples))
# VOLUME: the height, from the next sound (or step)
for v, want in ((1, sfx.VOLUMES[1]), (11, sfx.VOLUMES[11]), (0, sfx.VOLUMES[1]), (99, sfx.VOLUMES[11])):
    out, s = synth()
    s.set_volume(v)
    sfx.SOUNDS = dict(sfx.OWN, tone=(1, [(1000, 100)]))
    s.play("tone"); run(s, 300)
    assert max(out.samples) == want, (v, max(out.samples), want)
out, s = synth()
s.play("tone"); s.step(); s.stop(); run(s, 300)
assert not s.playing() and s.t0 is None, "stopped (MUTED): idle"
sfx.SOUNDS = sfx.OWN
print("I2S synth: tones, pitch, levels, rests, mixing, noise, voices, channels, keeping ahead: ok")
sfx.SOUNDS, sfx.CHANNELS = SOUNDS_IN_USE, CHANNELS_IN_USE

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
assert "SOUND: ON" in items and not any(i.startswith("SOUND PORT") for i in items), \
    "no port to choose (the Pi): no SOUND PORT line"
ports = []
a.platform.sound_port = 2       # the badge: its I2S port (build 145)
a.platform.set_sound_port = lambda p: (ports.append(p), setattr(a.platform, "sound_port", p))
assert "SOUND PORT: 2" in a._settings(False), a._settings(False)
a._change("SOUND PORT: 2", False)
assert ports == [3] and "SOUND PORT: 3" in a._settings(False) and dev.played == ["beep"]
a._change("SOUND PORT: 3", True); a._change("SOUND PORT: 2", True)
assert ports == [3, 2, 1]
a._change("SOUND PORT: 1", True)
assert ports[-1] == 6, "left from 1: 6"
a._change("SOUND PORT: 6", False)
assert ports[-1] == 1, "on from 6: 1"
a._change("SOUND PORT: 1", False)       # 2
a._change("SOUND PORT: 2", False)       # 3, saved
del dev.played[:]
b1 = ace_commander.AceCommander()
got = []
b1.platform.sound_port = 2
b1.platform.set_sound_port = got.append
b1._load_options()
assert got == [3], ("SOUND PORT kept in options.json", got)
bs.tick(a)
bs.choose(a, "COMBAT PRACTICE")
assert a.mode == "flight"
a.game.sfx("explode")
bs.tick(a)
assert "explode" in dev.played and dev.steps > 0 and not a.game.sounds
vols = []
stops = []
a.platform.set_volume = vols.append
a.platform.sound_stop = lambda: stops.append(1)
items = a._settings(False)
assert "VOLUME: 8" in items and items.index("VOLUME: 8") == items.index("SOUND: ON") + 1, items
del dev.played[:]
a._change("VOLUME: 8", False)
assert a.volume == 9 and vols == [9] and dev.played == ["beep"], "up one, and a beep to hear it"
for _ in range(5):
    a._change("VOLUME", False)
assert a.volume == 11 and vols[-1] == 11 and "VOLUME: 11" in a._settings(False), "it goes to 11"
for _ in range(15):
    a._change("VOLUME", True)
assert a.volume == 1 and vols[-1] == 1, "and down to 1, no further"
a._change("VOLUME", False); a._change("VOLUME", False)      # 3
a._change("SOUND: ON", False)
assert not a.use_sound and "SOUND: MUTED" in a._settings(False)
assert stops == [1], "muting cuts off what plays"
assert not any(i.startswith("VOLUME") or i.startswith("SOUND PORT") for i in a._settings(False)), \
    "muted: no VOLUME or SOUND PORT line"
dev.played[:] = []
a.game.sfx("explode")
bs.tick(a)
assert dev.played == [] and not a.game.sounds, "SOUND: MUTED plays nothing"
# docked: a beep with each trade message or refusal, as Elite's dn2 (build 142)
from ace_commander import commander
a._change("SOUND: MUTED", False)
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
assert not b2.use_sound and b2.volume == 3, "kept in options.json"
a._change("SOUND: MUTED", False)
print("ace: sounds to the device, SOUND: ON / MUTED, VOLUME, SOUND PORT, saved: ok")
print("ALL SOUND TESTS PASSED")
