"""The Tufty host on a PC: the real game through host_tufty on the Badgeware v3
stand-ins (sim_badgeware.py). Title -> new commander -> docked -> launch ->
flight, the dashboard and the LED border drawn, saved in the data folder,
frames written to hosts/tufty/tests/shots/ to look at."""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TUFTY = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(TUFTY))
sys.path.insert(0, HERE)
sys.path.insert(0, TUFTY)
sys.path.insert(0, os.path.dirname(REPO))
SHOTS = os.path.join(HERE, "shots")
os.makedirs(SHOTS, exist_ok=True)

# the game package without its PC __init__ (which imports ace at once, before
# the host has set config): as on the Tufty, where __init__ does nothing
spec = importlib.util.find_spec("ace_commander")
sys.modules["ace_commander"] = importlib.util.module_from_spec(spec)

import sim_badgeware as bw      # noqa: E402
import host_tufty               # noqa: E402
import controls_tufty           # noqa: E402
from ace_commander import picker as dialog_tufty  # noqa: E402  (the letter picker: picker.py)
import platform_tufty           # noqa: E402

class FakePad:
    """A Qw/ST Pad: read_buttons() as qwstpad's, from the names held."""

    def __init__(self):
        self.down = set()

    def read_buttons(self):
        return {k: (k in self.down) for k in ("U", "D", "L", "R", "A", "B", "X", "Y", "+", "-")}


screen = bw.Screen()
badge = bw.Badge()
buttons = dict(bw.BUTTONS)


DATA = tempfile.mkdtemp(prefix="ace_tufty_")    # one for both hosts: the game fixes its save
                                                # path when its module first loads


def make(pad, buzzer=None):
    """A Tufty host, loaded (through its loading screen) and its game started."""
    global h
    data = DATA
    h = host_tufty.Host(screen, badge, bw.color, bw.shape, bw.font, bw.rect, buttons, pad, data,
                        buzzer=buzzer)
    assert h.app is None
    h.update()
    assert h.app is None and h.done == 1 and h.letters is not None
    h.update()
    screen.img.save(os.path.join(SHOTS, "tufty_loading.png"))
    px = screen.img.load()
    assert any(px[x, y] != (0, 0, 0) for x in range(80, 240, 2) for y in range(10, 60, 2)), "the name"
    for _ in range(len(host_tufty.STEPS)):
        h.update()
    assert h.loaded is not None and h.app is None and h.error is None, h.error
    h.update()
    assert h.app is None, "held for LOAD_HOLD, to see the ship"
    h.t_load -= host_tufty.LOAD_HOLD
    h.update()
    assert h.app is not None, "then the game takes over"
    assert h.app.platform.__class__ is platform_tufty.Platform, "the Tufty's platform"
    return h, h.app, data


def frames(n=1):
    for _ in range(n):
        h.last -= 40            # pretend 40 ms passed
        r = h.update()
        assert r is None, r


def press(name, n=2):
    badge.down.add(buttons[name])
    frames(3)               # (in flight B alone waits PAIR_WAIT ms for a partner)
    badge.down.discard(buttons[name])
    frames(n)


def pad_press(name, n=2):
    h.pad.down.add(name)
    frames(1)
    h.pad.down.discard(name)
    frames(n)


def shot(name):
    screen.img.save(os.path.join(SHOTS, name + ".png"))


def lit(x0, y0, x1, y1):
    n = 0
    px = screen.img.load()
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if px[x, y] != (0, 0, 0):
                n += 1
    return n


# ---- the Tufty's buttons alone (no Pad, build 111): combat practice only; A / C /
# UP / DOWN are cursor keys off the flight and the joystick in flight, B selects
# and fires
h, a, data = make(None)
frames(5)
assert a.choices() == ["COMBAT PRACTICE"], a.choices()
assert not any(l.startswith("GAMEPAD") for l in a._cheats("DISPLAY", False)), "no Pad found: no line"
cfg = sys.modules["ace_commander.config"]
assert cfg.auto_missiles and cfg.practice_missile == 1.0, "missiles by themselves, in every canister"
assert h.ctx.labels == controls_tufty.LABELS_OFF, "off the flight: B, and A+C for back"
press("B")
assert a.mode == "practice", a.mode
badge.down.add(buttons["A"]); badge.down.add(buttons["C"])     # A + C: back (the badge's F)
frames(3)
badge.down.discard(buttons["A"]); badge.down.discard(buttons["C"])
frames(2)
assert a.mode == "menu", ("A + C goes back", a.mode)
press("B")
press("B")
assert a.mode == "flight", a.mode
g = a.game
assert g.auto_missile and g.pickup_missile == 1.0
g.spawn_t = g.rock_t = 1e9
frames(3)
m0 = list(g.space.station.m) if g.space and g.space.station else None
badge.down.add(buttons["UP"])
frames(5)                   # (alone, UP waits PAIR_WAIT ms for DOWN)
assert g.stick_pitch != 0.0, "UP steers (the joystick)"
badge.down.discard(buttons["UP"])
badge.down.add(buttons["A"])
frames(3)
assert g.stick_roll != 0.0, "A rolls"
badge.down.discard(buttons["A"])
g.heat = 0.0
badge.down.add(buttons["B"])
fired = False
for _ in range(3):
    frames(1)
    fired = fired or g.beam > 0
assert fired, "B fires"
badge.down.discard(buttons["B"])
frames(2)
assert h.ctx.labels == controls_tufty.LABELS, "in flight: B named; the game says what A + C does"
s0 = g.speed
badge.down.add(buttons["A"]); badge.down.add(buttons["C"])     # A + C: UP / DOWN to speed
frames(3)
badge.down.discard(buttons["A"]); badge.down.discard(buttons["C"])
frames(1)
assert h.speed_mode and g.msg == "UP/DOWN: SPEED" and g.speed == s0, (h.speed_mode, g.msg)
badge.down.add(buttons["UP"])
frames(10)
badge.down.discard(buttons["UP"])
assert g.speed > s0 + 1 and g.stick_pitch == 0.0, ("UP: faster, no pitch", s0, g.speed)
s1 = g.speed
badge.down.add(buttons["DOWN"])
frames(10)
badge.down.discard(buttons["DOWN"])
assert g.speed < s1 - 1, ("DOWN: slower", s1, g.speed)
badge.down.add(buttons["A"]); badge.down.add(buttons["C"])     # A + C again: pitch
frames(3)
badge.down.discard(buttons["A"]); badge.down.discard(buttons["C"])
frames(1)
assert not h.speed_mode and g.msg == "UP/DOWN: PITCH"
badge.down.add(buttons["UP"])
frames(3)
badge.down.discard(buttons["UP"])
assert g.stick_pitch != 0.0, "UP pitches again"
badge.down.add(buttons["UP"]); badge.down.add(buttons["DOWN"])     # UP + DOWN: the pause menu
frames(3)
badge.down.discard(buttons["UP"]); badge.down.discard(buttons["DOWN"])
frames(2)
assert a.paused, "UP + DOWN opens the pause menu"
badge.down.add(buttons["UP"]); badge.down.add(buttons["DOWN"])
frames(3)
badge.down.discard(buttons["UP"]); badge.down.discard(buttons["DOWN"])
frames(2)
assert not a.paused, "and closes it"
frames(2)
shot("tufty_practice")
print("Tufty buttons alone: combat practice only, cursor keys, joystick, B fires: ok")

# ---- with a Pad: the whole game
pad = FakePad()
h, a, data = make(pad)
frames(5)
assert a.mode == "menu" and lit(0, 0, 320, 240) > 200, "the title draws"
shot("tufty_title")
assert "NEW COMMANDER" in a.choices() and not a.ctx_labels if hasattr(a, "ctx_labels") else True
assert h.ctx.labels is not None, "with the Pad too the hints name the Tufty's buttons"
# DEBUG > DISPLAY > GAMEPAD: the Pad off plays as without it, on again as with it
assert any(l.startswith("GAMEPAD: ON") for l in a._cheats("DISPLAY", False)), a._cheats("DISPLAY", False)
a._odebug("GAMEPAD: ON")
cfg = sys.modules["ace_commander.config"]
assert h.pad_off and cfg.auto_missiles and not cfg.practice_only and "NEW COMMANDER" in a.choices(), \
    "GAMEPAD OFF: practice as without the Pad; the Pad and the whole game still off the flight"
assert any(l.startswith("GAMEPAD: OFF") for l in a._cheats("DISPLAY", False))
pad.down.add("D"); frames(3); pad.down.discard("D"); frames(2)
assert a.menu == 1, ("the Pad still works on the title screen", a.menu)
a.menu = 0
a._odebug("GAMEPAD: OFF")
assert not h.pad_off and not cfg.auto_missiles and "NEW COMMANDER" in a.choices()
# text entry (build 122): the letter picker on the Tufty's buttons, for the name
got = []
a._open_name("", got.append)
d = a.ndialog
assert d is not None and d is a.platform.dialog, "the Tufty's letter picker, not the keyboard page"
press("B")                  # A, the cursor on to the next place (A there too)
assert d.hints == controls_tufty.TYPING_HINTS, "the Tufty's buttons: theirs"
press("UP")                 # B
press("UP")                 # C
press("B")                  # AC
press("C")                  # back onto the C: A, the cursor's letter C
assert d.text == "A" and dialog_tufty.LETTERS[d.i] == "C"
press("UP")                 # D
press("B")                  # AD
shot("tufty_name_entry")
assert d.text == "AD", d.text
press("A")                  # done
assert got == ["AD"] and a.ndialog is None, (got, a.ndialog)
frames(2)
# and on the Pad (PAD_TYPING): up the letter, A keeps it, B back, + done
got = []
a._open_name("", got.append)
d = a.ndialog
pad_press("U")              # B
pad_press("A")              # B
pad_press("R")              # BB
pad_press("B")              # back onto the last B: B
pad_press("U")              # C
pad_press("A")              # BC
assert d.hints == controls_tufty.PAD_TYPING_HINTS, "the Pad used: its names in the picker's hints"
pad_press("+")              # done
assert got == ["BC"], got
frames(2)
# the hints name what was pressed last (build 126): the Pad's buttons, then the Tufty's
pad_press("D"); frames(1)
assert h.pad_last and h.ctx.labels == controls_tufty.PAD_LABELS_OFF, h.ctx.labels
press("UP"); frames(1)
assert not h.pad_last and h.ctx.labels == controls_tufty.LABELS_OFF, h.ctx.labels
a.menu = 0
# "< >" is the Tufty's A / C with its own buttons (build 129)
from ctx_tufty import relabel   # noqa: E402
assert relabel("< > screens   F: status", controls_tufty.LABELS_OFF) == "A/C screens   A+C: status"
assert relabel("C: cursor   < > screens", controls_tufty.PAD_LABELS_OFF) == "A: cursor   < > screens"
# the Pad's Y off the flight is the badge's B (search on the Galactic chart: build 125)
assert controls_tufty.PAD_MAP_OFF["Y"] is controls_tufty.BADGE["B"]
assert controls_tufty.PAD_MAP["Y"] is controls_tufty.BADGE["E"], "in flight Y still slows down"
# NEW COMMANDER: the Tufty's B selects (the badge's C), as without the Pad
a.menu = a.choices().index("NEW COMMANDER")
press("B")
press("B")
assert a.mode == "docked", a.mode
assert h.ace.SAVE_PATH.startswith(data) and os.path.exists(h.ace.SAVE_PATH), "saved in the data folder"
shot("tufty_docked")
d = a.dock
d.open("GALACTIC CHART")
pad_press("A")              # the chart's cursor (the badge's C)
assert d.name() == "GALACTIC CHART" and d.cursor, (d.name(), d.cursor)
shot("tufty_galactic")      # build 129: a hint line (the Pad's names: "A: target ... Y: find")
pad_press("Y")              # the Pad's Y: search (the badge's B on the Galactic chart)
assert a.tdialog is not None, "Y opens the search"
h.pad.down.add("+")         # done (nothing typed: no match), held as a real press is
frames(6)
assert a.tdialog is None
assert a.mode == "docked", "the + that closed the picker doesn't launch (build 128)"
h.pad.down.discard("+")
frames(2)
assert a.mode == "docked", a.mode
# the Tufty's A, held through closing the picker, doesn't go on either
pad_press("Y")
assert a.tdialog is not None
badge.down.add(buttons["A"])
frames(6)
assert a.tdialog is None and a.mode == "docked", a.mode
badge.down.discard(buttons["A"])
frames(2)
d.open("STATUS")
pad_press("+")          # the Pad's + is the badge's A: launch
for _ in range(200):
    frames(1)
    if a.mode == "flight":
        break
assert a.mode == "flight", a.mode
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
frames(5)
dash = lit(0, 182, 320, 240)
view = lit(0, 0, 320, 180)
assert dash > 300 and view > 20, (dash, view)
assert g.dust_x == 666, ("the stardust spreads across the wider view", g.dust_x)
shot("tufty_flight")
g._hurt(10.0)
frames(1)
assert any(platform_tufty.LEDS[i][0] > 100 for i in range(1, 13)), "the hit lights the LED ring"
assert badge.lights and badge.lights[-1] > 0.3, "and the case lights"
shot("tufty_hit")
print("Tufty host: title, new commander, docked, launch, flight, dashboard, LED border: ok")
# a buzzer on the Qw/ST port (builds 140, 146: SparkFun or Modulino): the game's sounds go to it
assert not h.app.platform.sound_ok and not any(i.startswith("SOUND") for i in h.app._settings(False))


class FakeBuzzer:
    def __init__(self):
        self.played = []
        self.steps = 0
        self.volume = None
        self.stopped = 0

    def play(self, name):
        self.played.append(name)

    def step(self):
        self.steps += 1

    def set_volume(self, v):
        self.volume = v

    def stop(self):
        self.stopped += 1


fb = FakeBuzzer()
make(None, fb)
a = h.app
items = a._settings(False)
assert a.platform.sound_ok and "SOUND: ON" in items and "VOLUME: %d" % a.volume in items, items
assert fb.volume == a.volume, "options.json's VOLUME given to the buzzer"
assert not any(i.startswith("SOUND PORT") for i in items), "no port to choose"
frames(2)
assert fb.steps > 0, "moved on each frame"
a._change("VOLUME", True)
assert fb.volume == a.volume
a._change("VOLUME", False)
a.mode = "menu"
a.menu = a.choices().index("COMBAT PRACTICE")
press("B"); press("B")      # practice's page, then fly
assert a.mode == "flight", a.mode
a.game.sfx("explode")
frames(1)
assert "explode" in fb.played, fb.played
a._change("SOUND: ON", False)
assert fb.stopped == 1, "MUTED stops it"
a._change("SOUND: MUTED", False)
print("Tufty: a buzzer plays the game's sounds, VOLUME, MUTED: ok")
print("ALL TUFTY HOST TESTS PASSED")
