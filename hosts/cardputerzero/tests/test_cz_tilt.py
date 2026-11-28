"""Tilt steering and TILT SETUP with a stand-in accelerometer (the CardputerZero's is a
BMI270 read through iio: run_cz.Accel). Tilt is measured across the level pose's
gravity, so the device can be held at any angle; the setup page's settings are saved.

    python3 hosts/cardputerzero/tests/test_cz_tilt.py
"""
import json
import math
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["HOME"] = tempfile.mkdtemp(prefix="ace_cz_tilt_")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pygame       # noqa: E402

import run_cz       # noqa: E402

A = [-1.0, 0.0, 0.0]            # standing on an edge, as the CardputerZero read: gravity along -x
run_cz.find_accel = lambda: (lambda: tuple(A))
data = tempfile.mkdtemp(prefix="ace_cz_tilt_data_")
h = run_cz.Host(save_dir=data, sound=False)
h.pads.pads.clear()
a = h.app
ace = sys.modules["ace_commander.ace"]
for _ in range(3):
    h.step(40)
assert a.tilt_ok and a.platform.tilt_ok, "the accelerometer gives tilt"
assert "TILT SETUP" in a._settings(False), a._settings(False)
print("CardputerZero accelerometer: tilt on, TILT SETUP offered: ok")

# the badge held flat: the directions across gravity are its x and y, as before
e1, e2 = ace._level_axes((0.0, 0.0, 1.0))
assert all(abs(p - q) < 1e-6 for p, q in zip(e1, (1, 0, 0))) and \
    all(abs(p - q) < 1e-6 for p, q in zip(e2, (0, 1, 0))), (e1, e2)
print("flat: across gravity are x and y (the badge as before): ok")

# a first read of all zeros (the badge's IMU right after start) isn't taken as level
keep = list(A)
A[:] = [0.0, 0.0, 0.0]
a.zero = None
a.platform.tilt()
assert a._tilt_xy() == (0.0, 0.0) and a.zero is None, a.zero
A[:] = keep
a.platform.tilt()
a._tilt_xy()
assert a.zero is not None and abs(a.zero[0] + 1.0) < 1e-9, a.zero
print("an all-zero first read isn't level; the next real one is: ok")

# TILT SETUP: level where it is held, then tilt each way and see the dot move one axis
a._change("TILT SETUP", False)
assert a.mode == "tiltset"
h.step(40)
a.zero = None                   # (LEVEL: SET NOW does this)
h.step(40)
t = math.radians(20)
# its y runs across the screen (TILT_AXES): turned about z (y tips) is roll, about y
# (z tips: the top back, as Brian reported "tilt up") pitch, the top back moving the dot up
A[:] = [-math.cos(t), math.sin(t), 0.0]       # turned about z
a.platform.tilt()               # (read once a frame, by the game's update)
dx, dy = a._tilt_xy()
assert abs(dx) > 0.3 and abs(dy) < 1e-6, ("roll", dx, dy)
A[:] = [-math.cos(t), 0.0, -math.sin(t)]      # the top tipped back (z falls, as reported)
a.platform.tilt()
dx, dy = a._tilt_xy()
assert dy < -0.3 and abs(dx) < 1e-6, ("pitch: the top back moves the dot up", dx, dy)
h.step(40)                      # the page draws the dot
print("held upright: each tilt moves one axis (%.2f g at 20 degrees): ok" % abs(dy))

# the settings change with left / right and are saved in options.json
before = (a.t_full, a.t_dead, a.t_swap, a.t_psign, a.t_rsign)
for sel in range(1, 6):
    a.ts_sel = sel
    a.pad.hit = lambda n, _s=sel: n == "j_right"
    a._update_tiltset(0.04, False, False)
    a.held_t.clear()
del a.pad.hit
after = (a.t_full, a.t_dead, a.t_swap, a.t_psign, a.t_rsign)
assert all(x != y for x, y in zip(before, after)), (before, after)
with open(os.path.join(data, "options.json")) as f:
    saved = json.load(f)["tilt_setup"]
assert saved == [a.t_full, a.t_dead, a.t_swap, a.t_psign, a.t_rsign], saved
assert "FULL TILT: %d DEG" % ace._deg(a.t_full) in a._tilt_lines()
# FULL TILT and DEAD ZONE go a degree at a time and stop at their ends
def right(sel, times=1):
    a.ts_sel = sel
    for _ in range(times):
        a.pad.hit = lambda n: n == "j_right"
        a._update_tiltset(0.04, False, False)
        a.held_t.clear()
    del a.pad.hit
d0 = ace._deg(a.t_full)
right(1)
assert ace._deg(a.t_full) == min(d0 + 1, ace.TILT_FULL_DEG[1]), (d0, ace._deg(a.t_full))
right(1, 60)
assert ace._deg(a.t_full) == ace.TILT_FULL_DEG[1], ace._deg(a.t_full)
right(2, 30)
assert ace._deg(a.t_dead) == ace.TILT_DEAD_DEG[1], ace._deg(a.t_dead)
print("FULL TILT / DEAD ZONE a degree at a time, %d and %d at most: ok" % (ace.TILT_FULL_DEG[1], ace.TILT_DEAD_DEG[1]))
a._update_tiltset(0.04, True, False)  # F: back
assert a.mode == "menu", a.mode
print("settings changed and saved %s; F goes back: ok" % saved)

# --no-tilt: none
run_cz.find_accel = lambda: None
print("ALL CARDPUTERZERO TILT TESTS PASSED")
