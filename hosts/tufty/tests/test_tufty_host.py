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

data = tempfile.mkdtemp(prefix="ace_tufty_")
screen = bw.Screen()
badge = bw.Badge()
buttons = dict(bw.BUTTONS)
h = host_tufty.Host(screen, badge, bw.color, bw.shape, bw.font, bw.rect, buttons, None, data)
# the loading screen: a module a frame, the name and a bar drawn meanwhile
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
a = h.app
assert a.platform.__class__ is platform_tufty.Platform, "the Tufty's platform"


def frames(n=1):
    for _ in range(n):
        h.last -= 40            # pretend 40 ms passed
        r = h.update()
        assert r is None, r


def press(name, n=2):
    badge.down.add(buttons[name])
    frames(1)
    badge.down.discard(buttons[name])
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


frames(5)
assert a.mode == "menu" and lit(0, 0, 320, 240) > 200, "the title draws"
shot("tufty_title")
# NEW COMMANDER: C chooses (the Tufty's C is the badge's C), C again on its page
choose = a.choices().index("NEW COMMANDER")
for _ in range(choose):
    press("DOWN")       # the Tufty's DOWN is the badge's E: left, the line before...
a.menu = choose         # (moving lines with E / F wraps; set it to be sure)
press("C")
press("C")
assert a.mode == "docked", a.mode
assert h.ace.SAVE_PATH.startswith(data) and os.path.exists(h.ace.SAVE_PATH), "saved in the data folder"
shot("tufty_docked")
press("A")              # A launches
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
