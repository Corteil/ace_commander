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


def make(pad):
    """A Tufty host, loaded (through its loading screen) and its game started."""
    global h
    data = DATA
    h = host_tufty.Host(screen, badge, bw.color, bw.shape, bw.font, bw.rect, buttons, pad, data)
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
assert h.ctx.labels == {"C": "B", "F": "A+C"}, "off the flight: B, and A+C for back"
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
frames(5)
badge.down.discard(buttons["UP"])
assert g.stick_pitch != 0.0, "UP steers (the joystick)"
badge.down.add(buttons["A"])
frames(3)
assert g.stick_roll != 0.0, "A rolls"
badge.down.discard(buttons["A"])
g.heat = 0.0
badge.down.add(buttons["B"])
frames(3)                   # (in flight B alone waits PAIR_WAIT ms for a partner)
assert g.beam > 0, "B fires"
badge.down.discard(buttons["B"])
frames(2)
assert h.ctx.labels == {"C": "B", "F": "B+C", "E": "A+B"}, "in flight the hints name the pairs"
s0 = g.speed
badge.down.add(buttons["B"]); badge.down.add(buttons["C"])
frames(10)
badge.down.discard(buttons["B"]); badge.down.discard(buttons["C"])
assert g.speed > s0 + 1, ("B + C together: faster", s0, g.speed)
s1 = g.speed
badge.down.add(buttons["A"]); badge.down.add(buttons["B"])
frames(10)
badge.down.discard(buttons["A"]); badge.down.discard(buttons["B"])
assert g.speed < s1 - 1, ("A + B together: slower", s1, g.speed)
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
assert h.pad is None and cfg.practice_only and cfg.auto_missiles and a.choices() == ["COMBAT PRACTICE"]
assert any(l.startswith("GAMEPAD: OFF") for l in a._cheats("DISPLAY", False))
a._odebug("GAMEPAD: OFF")
assert h.pad is pad and not cfg.practice_only and not cfg.auto_missiles and "NEW COMMANDER" in a.choices()
# NEW COMMANDER: the Tufty's B selects (the badge's C), as without the Pad
a.menu = a.choices().index("NEW COMMANDER")
press("B")
press("B")
assert a.mode == "docked", a.mode
assert h.ace.SAVE_PATH.startswith(data) and os.path.exists(h.ace.SAVE_PATH), "saved in the data folder"
shot("tufty_docked")
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
print("ALL TUFTY HOST TESTS PASSED")
