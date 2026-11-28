"""The 8BitDo Micro's own maps (pad_pi.MICRO_*): its D-pad (sent as the left
stick) is the badge's joystick everywhere, flying included; buttons go by what is
printed on it (its X arrives as SDL's "y", its Y as "x"). Headless.

    python3 hosts/pi/tests/test_pi_micro.py
"""
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ["HOME"] = tempfile.mkdtemp(prefix="ace_pi_home_")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pygame       # noqa: E402

import pad_pi       # noqa: E402
import run          # noqa: E402
from controls_pi import BADGE, KEYBOARD, STICK   # noqa: E402

PAD = 77
SDL = {"A": pygame.CONTROLLER_BUTTON_A, "B": pygame.CONTROLLER_BUTTON_B,
       "X": pygame.CONTROLLER_BUTTON_Y, "Y": pygame.CONTROLLER_BUTTON_X,     # as the Micro sends them
       "L": pygame.CONTROLLER_BUTTON_LEFTSHOULDER, "R": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
       "-": pygame.CONTROLLER_BUTTON_BACK, "+": pygame.CONTROLLER_BUTTON_START,
       "HOME": pygame.CONTROLLER_BUTTON_GUIDE}
DPAD = {"up": (pygame.CONTROLLER_AXIS_LEFTY, -1), "down": (pygame.CONTROLLER_AXIS_LEFTY, 1),
        "left": (pygame.CONTROLLER_AXIS_LEFTX, -1), "right": (pygame.CONTROLLER_AXIS_LEFTX, 1)}


def press(h, name, down):
    if name in DPAD:
        ax, sign = DPAD[name]
        h.handle(pygame.event.Event(pygame.CONTROLLERAXISMOTION, instance_id=PAD, axis=ax,
                                    value=int(sign * 32767) if down else 0))
    else:
        t = pygame.CONTROLLERBUTTONDOWN if down else pygame.CONTROLLERBUTTONUP
        h.handle(pygame.event.Event(t, instance_id=PAD, button=SDL[name]))


def tap(h, name, frames=2):
    press(h, name, True)
    h.step(40)
    press(h, name, False)
    for _ in range(frames):
        h.step(40)


h = run.Host(scale=2, save_dir=tempfile.mkdtemp(prefix="ace_pi_micro_"))
pads = h.pads
pads.pads.clear()
pads.micro.clear()
pads.pads[PAD] = object()           # a made-up Micro
pads.micro.add(PAD)
a = h.app
for _ in range(3):
    h.step(40)

# the title: the D-pad moves, A chooses
start = a.menu
tap(h, "right")
assert a.menu != start, "D-pad right: the next line"
while a.choices()[a.menu] != "NEW COMMANDER":
    tap(h, "right")
tap(h, "A")
tap(h, "A")
assert a.mode == "docked", a.mode
assert pads.labels() is pad_pi.MICRO_LABELS
print("title and docked: D-pad the joystick, A chooses, hints in the Micro's names: ok")

# docked: R the next tab, L back; - Options
tab = a.dock.name()
tap(h, "R")
assert a.dock.name() != tab
tap(h, "L")
assert a.dock.name() == tab
print("docked: L / R the tabs: ok")

# + launches; flying, the D-pad holds the joystick (not analogue), A fires, X held the jump drive
tap(h, "+")
for _ in range(300):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight" and pads.state() == "flight"
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
press(h, "up", True)
h.step(40)
assert pads.count.get(STICK["UP"]) == 1, "the D-pad holds the joystick in flight"
an = a.analog
assert an is not None and an.pitch == 0 and an.yaw == 0 and an.speed is None, "no analogue from the Micro"
press(h, "up", False)
h.step(40)
assert pads.count.get(STICK["UP"]) == 0
for name, key in (("A", KEYBOARD["SPACE"]), ("X", KEYBOARD["J"]), ("B", BADGE["D"]),
                  ("L", KEYBOARD["-"]), ("R", KEYBOARD["+"])):
    press(h, name, True)
    assert pads.count.get(key) == 1, name
    press(h, name, False)
    assert pads.count.get(key) == 0, name
print("flight: D-pad pitch / roll, A fire, B missile, X jump drive, L / R speed: ok")

# on a screen (opened from the pause menu, or here the keyboard's 6: the local
# chart) L / R step through the screens; B back to space
for k in (pygame.KEYDOWN, pygame.KEYUP):
    h.handle(pygame.event.Event(k, key=pygame.K_6, unicode="6", mod=0))
    h.step(40)
h.step(40)
assert pads.state() == "screen", a.fsub
tap(h, "R")
assert pads.state() == "screen" and type(a.chart).__name__ == "GalChart", "R: the next screen"
tap(h, "L")
assert pads.state() == "screen" and type(a.chart).__name__ == "Chart", "L: the one before"
tap(h, "B")
assert pads.state() == "flight", a.fsub
# + the pause menu, B back out of it
tap(h, "+")
assert a.paused
tap(h, "B")
assert not a.paused
print("flight screens on L / R, + pause: ok")

# Home held a second: the escape pod
# (a new commander has none fitted, so this checks Esc, the pod's key, is sent)
sent = []
real = pads._tap
pads._tap = lambda *keys: (sent.extend(keys), real(*keys))
press(h, "HOME", True)
for _ in range(10):
    h.step(40)
assert KEYBOARD["ESCAPE"] not in sent, "not before a second"
for _ in range(20):
    h.step(40)
press(h, "HOME", False)
pads._tap = real
assert sent == [KEYBOARD["ESCAPE"]], sent
print("Home held 1 s: escape pod: ok")
# --pad: auto picks the Micro by its name; micro gives every pad its maps (its other
# modes report other names); standard none
for kind, name, want in (("auto", "8BitDo Micro gamepad", True), ("auto", "Xbox 360 Controller", False),
                         ("micro", "Xbox 360 Controller", True), ("standard", "8BitDo Micro gamepad", False)):
    pads.kind = kind
    assert pads.is_micro(name) is want, (kind, name)
pads.kind = "auto"
print("--pad auto / micro / standard: ok")
print("ALL PI MICRO TESTS PASSED")
