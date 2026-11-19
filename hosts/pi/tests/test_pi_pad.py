"""The Raspberry Pi host (P2): a game controller as the badge, headless (SDL's
dummy video driver), driven by controller events as a pad would send them.

    python3 hosts/pi/tests/test_pi_pad.py

No pad needs to be plugged in: the events are made here.
"""
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.dirname(HERE)
sys.path.insert(0, PI)

import pygame       # noqa: E402

import run          # noqa: E402

PAD = 99            # the made-up pad's instance id
B = {"a": pygame.CONTROLLER_BUTTON_A, "b": pygame.CONTROLLER_BUTTON_B,
     "x": pygame.CONTROLLER_BUTTON_X, "y": pygame.CONTROLLER_BUTTON_Y,
     "start": pygame.CONTROLLER_BUTTON_START,
     "up": pygame.CONTROLLER_BUTTON_DPAD_UP, "down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
     "left": pygame.CONTROLLER_BUTTON_DPAD_LEFT, "right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
     "lb": pygame.CONTROLLER_BUTTON_LEFTSHOULDER, "rb": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER}


def button(h, name, down):
    t = pygame.CONTROLLERBUTTONDOWN if down else pygame.CONTROLLERBUTTONUP
    h.handle(pygame.event.Event(t, instance_id=PAD, button=B[name]))


def axis(h, which, value):
    h.handle(pygame.event.Event(pygame.CONTROLLERAXISMOTION, instance_id=PAD,
                                axis=which, value=int(value * 32767)))


def tap(h, name, frames=2):
    button(h, name, True)
    h.step(40)
    button(h, name, False)
    for _ in range(frames):
        h.step(40)


h = run.Host(scale=2, save_dir=tempfile.mkdtemp(prefix="ace_pi_pad_"))
a = h.app
for _ in range(5):
    h.step(40)

# the title: the D-pad moves the menu, south (C) chooses
start = a.menu
tap(h, "right")
assert a.menu != start, "D-pad right: the next line"
while a.choices()[a.menu] != "NEW COMMANDER":
    tap(h, "right")
tap(h, "a"); assert a.mode == "level", a.mode
tap(h, "a"); assert a.mode == "docked", a.mode
d = a.dock
print("title and NEW COMMANDER by pad: ok")

# docked: the stick and the shoulders go round the tabs, east (F) back
axis(h, pygame.CONTROLLER_AXIS_LEFTX, 0.9); h.step(40)
axis(h, pygame.CONTROLLER_AXIS_LEFTX, 0.6); h.step(40)     # still pushed: no second step
axis(h, pygame.CONTROLLER_AXIS_LEFTX, 0.0); h.step(40)
assert d.name() == "INVENTORY", ("the stick: one tab right", d.name())
tap(h, "lb"); assert d.name() == "STATUS", ("left shoulder (E): the tab before", d.name())
tap(h, "y"); assert d.name() == "INVENTORY", ("north (B): the next tab", d.name())
tap(h, "b"); assert d.name() == "STATUS", "east (F): back to Status"
# the market: south (C) buys, west (D) sells
while d.name() != "MARKET":
    tap(h, "right")
c = a.cmdr
cash = c.cash
tap(h, "a"); assert sum(c.cargo) == 1 and c.cash < cash, "south: buy"
tap(h, "x"); assert sum(c.cargo) == 0 and c.cash == cash, "west: sell"
print("docked by pad: tabs, back, buy, sell: ok")

# Start (A) launches; the stick steers, south fires, the triggers change speed
tap(h, "start"); assert a.mode == "launch", a.mode
for _ in range(300):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight", a.mode
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
assert a.pad.held("j_left") is False
axis(h, pygame.CONTROLLER_AXIS_LEFTX, -1.0); h.step(40)
assert a.pad.held("j_left"), "the stick left: the joystick left"
button(h, "left", True); h.step(40)
axis(h, pygame.CONTROLLER_AXIS_LEFTX, 0.0); h.step(40)
assert a.pad.held("j_left"), "the D-pad still holds it"
button(h, "left", False); h.step(40)
assert not a.pad.held("j_left"), "let go of both: let go"
button(h, "a", True)
for _ in range(5):
    h.step(40)
assert g.beam > 0 or g.heat > 0, "south held: firing"
button(h, "a", False); h.step(40)
speed = g.speed
axis(h, pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 1.0)
for _ in range(10):
    h.step(40)
axis(h, pygame.CONTROLLER_AXIS_TRIGGERRIGHT, 0.0); h.step(40)
assert g.speed > speed, ("right trigger (F): faster", speed, g.speed)
print("flight by pad: Start launches, stick and D-pad steer, south fires, trigger speeds up: ok")

# Start: the menu; unplugging lets go of whatever the pad held
tap(h, "start"); assert a.paused
tap(h, "start"); assert not a.paused
axis(h, pygame.CONTROLLER_AXIS_LEFTX, -1.0); h.step(40)
assert a.pad.held("j_left")
h.handle(pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=PAD)); h.step(40)
assert not a.pad.held("j_left"), "unplugged: let go"
print("the pause menu by Start; unplugging lets go: ok")
pygame.quit()
print("ALL PI PAD TESTS PASSED")
