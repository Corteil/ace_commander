"""The Raspberry Pi host (P3): the Elite layout (a 3D view over a dashboard), window
sizes, switching layouts (F10), screenshots (F12). Headless (SDL's dummy driver).

    python3 hosts/pi/tests/test_pi_elite.py
"""
import os
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HOME = tempfile.mkdtemp(prefix="ace_pi_home_")
os.makedirs(os.path.join(HOME, "Pictures"))
os.environ["HOME"] = HOME           # screenshots land here, not in the real ~/Pictures
HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.dirname(HERE)
sys.path.insert(0, PI)

import json         # noqa: E402

import pygame       # noqa: E402

import dash_pi      # noqa: E402
import run          # noqa: E402

SHOTS = os.path.join(HERE, "shots")
os.makedirs(SHOTS, exist_ok=True)


def key(h, k, ch="", frames=2):
    h.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0))
    h.step(40)
    h.handle(pygame.event.Event(pygame.KEYUP, key=k, unicode=ch, mod=0))
    for _ in range(frames):
        h.step(40)


def lit(surf, rect):
    n = 0
    for y in range(rect.top, rect.bottom, 6):
        for x in range(rect.left, rect.right, 6):
            if surf.get_at((x, y))[:3] != (0, 0, 0):
                n += 1
    return n


def resize(h, w, ht):
    h.window = pygame.display.set_mode((w, ht), pygame.RESIZABLE)
    h.handle(pygame.event.Event(pygame.VIDEORESIZE, w=w, h=ht, size=(w, ht)))
    h.step(40)


save = tempfile.mkdtemp(prefix="ace_pi_elite_")
h = run.Host(scale=2, full=False, save_dir=save, layout="elite")
h.pads.pads.clear()
a = h.app
assert h.layout == "elite" and h.window.get_size() == (768, 480), h.window.get_size()
resize(h, 1920, 1200)
assert h.scale == 5 and h.lw == 384, (h.scale, h.lw)
for _ in range(5):
    h.step(40)
assert lit(h.window, pygame.Rect(720, 0, 480, 1200)) > 50, "the title in the middle"
print("Elite layout: 1920 x 1200 is a 384 x 240 canvas at 5x; the title in the middle: ok")

# a commander, docked (the badge's screens in the middle), then flight
while a.choices()[a.menu] != "NEW COMMANDER":
    key(h, pygame.K_RIGHT)
key(h, pygame.K_RETURN)
key(h, pygame.K_F3)
assert a.mode == "docked"
key(h, pygame.K_1, "1")
for _ in range(300):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight"
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
for _ in range(3):
    h.step(40)
s = h.scale
dash = pygame.Rect(0, int(dash_pi.VIEW_H * s) + 4, 1920, int(dash_pi.DASH_H * s) - 8)
view = pygame.Rect(0, 0, 1920, int(dash_pi.VIEW_H * s))
assert lit(h.window, dash) > 400, "the dashboard draws"
pygame.image.save(h.window, os.path.join(SHOTS, "elite_flight.png"))
assert h.gm.DUST_X == 800, ("stardust across the wider view", h.gm.DUST_X)
print("flight: view over the dashboard: ok")

# the dashboard follows the game: RL with the stick, the energy banks with the hull
L = h.dash_layout
bx = L.right[1]


def marker_x(row):
    """Where the yellow marker of right-hand row (RL 1, DC 2) is, in pixels."""
    y = int((dash_pi.VIEW_H + dash_pi.DASH_H / 2.0 + dash_pi._row_y(row) + dash_pi.BAR_H / 2.0) * s)
    xs = [x for x in range(0, 1920, 2) if h.window.get_at((x, y))[:3] == (255, 210, 60)
          or (h.window.get_at((x, y))[0] > 200 and h.window.get_at((x, y))[2] < 120
              and h.window.get_at((x, y))[1] > 150)]
    return sum(xs) / len(xs) if xs else None


h.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT, unicode="", mod=0))
for _ in range(3):
    h.step(40)
right = marker_x(1)
h.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_RIGHT, unicode="", mod=0))
h.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT, unicode="", mod=0))
for _ in range(3):
    h.step(40)
left = marker_x(1)
h.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_LEFT, unicode="", mod=0))
h.step(40)
assert right is not None and left is not None and right > left + 50, ("RL follows the roll", left, right)
g.hull = 40.0
h.step(40)
# bank 4 (bottom) full, 3 part-full, 1 and 2 empty
row_y = lambda r: int((dash_pi.VIEW_H + dash_pi.DASH_H / 2.0 + dash_pi._row_y(r) + 2) * s)   # noqa: E731
mid = int((bx + dash_pi.BAR_W * 0.5) * s + 960)
end = int((bx + dash_pi.BAR_W * 0.9) * s + 960)
assert h.window.get_at((end, row_y(6)))[:3] == (64, 255, 96) or h.window.get_at((end, row_y(6)))[1] > 200, \
    "bank 4 full"
assert h.window.get_at((mid, row_y(3)))[1] < 100, "bank 1 empty"
g.hull = 100.0
print("dashboard: RL follows the stick, the energy banks the hull: ok")

# hit: a red frame round the view (no LEDs here)
g.flash = 0.3
h.step(40)
assert h.window.get_at((2, 300))[0] > 200 and h.window.get_at((2, 300))[1] < 80, "red frame when hit"
print("hit: a red frame round the view: ok")

# any window shape: 4:3 and 16:9
for w, ht, lw in ((800, 600, 320), (1280, 720, 1280 * 240 / 720)):
    resize(h, w, ht)
    assert abs(h.lw - lw) < 0.01, (w, ht, h.lw)
    assert lit(h.window, pygame.Rect(0, int(dash_pi.VIEW_H * h.scale) + 2, w,
                                     int(dash_pi.DASH_H * h.scale) - 4)) > 100
    pygame.image.save(h.window, os.path.join(SHOTS, "elite_%dx%d.png" % (w, ht)))
print("4:3 and 16:9 windows: the dashboard fits: ok")

# F12: a screenshot in ~/Pictures/Ace Commander
key(h, pygame.K_F12)
d = os.path.join(HOME, "Pictures", "Ace Commander")
pics = os.listdir(d)
assert len(pics) == 1 and pics[0].endswith(".png"), pics
img = pygame.image.load(os.path.join(d, pics[0]))
assert img.get_size() == h.window.get_size()
print("F12: screenshot saved in ~/Pictures/Ace Commander: ok")

# F10: the badge layout and back, remembered in pi.json
key(h, pygame.K_F10)
assert h.layout == "badge" and h.window.get_size()[0] == h.window.get_size()[1]
assert h.screen is not h.window and h.mask is not None
with open(os.path.join(save, "pi.json")) as f:
    assert json.load(f) == {"layout": "badge", "full": False}
for _ in range(3):
    h.step(40)
assert a.mode == "flight", "switching layout leaves the game where it was"
key(h, pygame.K_F10)
assert h.layout == "elite"
h2_prefs = h._prefs()
assert h2_prefs["layout"] == "elite"
print("F10: badge layout and back, remembered: ok")
pygame.quit()

# the next start comes up as it was left
h = run.Host(scale=2, save_dir=save)
assert h.layout == "elite" and not h.full
pygame.quit()
print("ALL PI ELITE TESTS PASSED")
