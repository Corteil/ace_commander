"""The Raspberry Pi host (P0): the real game in a pygame window, headless
(SDL's dummy video driver), driven by key events as a player would.

    python3 hosts/pi/tests/test_pi_host.py

Saves screenshots to hosts/pi/tests/shots/ (git-ignored).
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

SHOTS = os.path.join(HERE, "shots")
os.makedirs(SHOTS, exist_ok=True)


def key(host, k, ch="", frames=2):
    """Press and let go of a key, with a frame in between and after."""
    host.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0))
    host.step(40)
    host.handle(pygame.event.Event(pygame.KEYUP, key=k, unicode=ch, mod=0))
    for _ in range(frames):
        host.step(40)


def lit(host, rect=None):
    """How many pixels of the round screen aren't black."""
    surf = host.screen
    w, h = surf.get_size()
    n = 0
    for y in range(0, h, 4):
        for x in range(0, w, 4):
            if surf.get_at((x, y))[:3] != (0, 0, 0):
                n += 1
    return n


save_dir = tempfile.mkdtemp(prefix="ace_pi_")
h = run.Host(scale=2, save_dir=save_dir)
a = h.app
assert h.window.get_size() == (544, 544) and h.screen.get_size() == (480, 480)
assert a.host is a and a.mode == "menu"
assert h.ace.SAVE_PATH.startswith(save_dir), "saves go under the user's data folder"

# the title screen draws: the name in block letters and a tumbling ship
for _ in range(10):
    h.step(40)
assert lit(h) > 500, lit(h)
pygame.image.save(h.window, os.path.join(SHOTS, "pi_title.png"))
print("title screen in a 480 x 480 round screen: ok")

# the keyboard picks: arrows round the title menu, Enter chooses
start = a.choices()[a.menu]
key(h, pygame.K_RIGHT)
assert a.choices()[a.menu] != start, "an arrow key moves the title menu"
while a.choices()[a.menu] != "NEW COMMANDER":
    key(h, pygame.K_RIGHT)
key(h, pygame.K_RETURN)
assert a.mode == "level", a.mode
pygame.image.save(h.window, os.path.join(SHOTS, "pi_new_commander.png"))
# a keyboard is fitted: NAME uses the game's own typing page; Tab fills the suggestion
key(h, pygame.K_UP); assert a.n_sel == 0
key(h, pygame.K_RETURN); assert a.namer is not None, "the keyboard's name page"
for ch in "pi":
    key(h, getattr(pygame, "K_" + ch), ch)
assert a.namer.text == "PI"
pygame.image.save(h.window, os.path.join(SHOTS, "pi_name.png"))
key(h, pygame.K_RETURN); assert a.n_name == "PI"
# F1-F6 are the badge's buttons: F3 is C, which starts from LEVEL
key(h, pygame.K_DOWN); key(h, pygame.K_F3)
assert a.mode == "docked" and a.cmdr.name == "PI", a.mode
assert os.path.exists(h.ace.SAVE_PATH), "saved"
pygame.image.save(h.window, os.path.join(SHOTS, "pi_docked.png"))
print("keyboard: menus, the name page, the badge's buttons on F1-F6: ok")

# the LED ring: a value the game writes shows round the screen
h.leds[1] = (255, 0, 0)
h.step(40)
assert any(h.window.get_at((x, y))[:3] == (255, 0, 0)
           for x in range(0, 544, 2) for y in range(0, 80, 2)), "LED 1 near the top"
h.leds[1] = (0, 0, 0)
print("the LED ring round the screen: ok")

# F1 is the badge's A: launch, through the tunnel into flight, and fly a little
key(h, pygame.K_F1)
assert a.mode == "launch", a.mode
for _ in range(120):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight", a.mode
a.game.spawn_t = a.game.rock_t = a.game.encounter_t = 1e9
h.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT, unicode="", mod=0))
for _ in range(10):
    h.step(40)
h.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_LEFT, unicode="", mod=0))
h.step(40)
assert lit(h) > 200
pygame.image.save(h.window, os.path.join(SHOTS, "pi_flight.png"))
key(h, pygame.K_F1)             # A: the in-flight menu
assert a.paused
for _ in range(20):
    if a._fitems()[a.fmenu] == "QUIT TO TITLE":
        break
    key(h, pygame.K_DOWN)
key(h, pygame.K_RETURN)
assert a.mode == "menu", a.mode
print("launch with F1 (the badge's A), fly, the menu, quit to title: ok")

# leaving from the title screen ends the program
key(h, pygame.K_ESCAPE)
assert not h.running, "Esc on the title screen quits"
pygame.quit()
print("ALL PI HOST TESTS PASSED")
