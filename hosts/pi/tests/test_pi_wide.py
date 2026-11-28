"""The Pi's --wide: in the Elite layout the badge's whole-frame screens are fitted
to the window (fit_pygame): its width used, the hints in one row along the bottom,
the game's wide pages on (config.wide); the badge layout (F10) as before.
Headless (SDL's dummy driver).

    python3 hosts/pi/tests/test_pi_wide.py
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

import fit_pygame   # noqa: E402
import run          # noqa: E402


def key(h, k, ch="", frames=2):
    h.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0))
    h.step(40)
    h.handle(pygame.event.Event(pygame.KEYUP, key=k, unicode=ch, mod=0))
    for _ in range(frames):
        h.step(40)


h = run.Host(scale=2, full=False, save_dir=tempfile.mkdtemp(prefix="ace_pi_wide_"), layout="elite",
             wide=True)
h.pads.pads.clear()
a = h.app
cfg = sys.modules[run.PKG + ".config"]
assert isinstance(h.ctx, fit_pygame.FitCtx) and cfg.wide == fit_pygame.MAX_ASPECT
while a.choices()[a.menu] != "NEW COMMANDER":
    key(h, pygame.K_RIGHT)
key(h, pygame.K_RETURN)
key(h, pygame.K_F3)
assert a.mode == "docked"
key(h, pygame.K_2, "2")             # the market
assert a.dock.name() == "MARKET"
place = [v for (k, row), v in h.fitter.places.items() if k == ("docked", "MARKET")][0]
sx, sy, y0, tk = place
assert sx > h.scale * 1.3 and tk == run.WIDE_TEXT_K, place
W, H = h.window.get_size()
grey = [y for y in range(H - 40, H) if any(h.window.get_at((x, y))[:3] == fit_pygame.GREY
                                          for x in range(0, W, 3))]
assert grey and min(grey) > H - 40, "the hints along the bottom"
print("--wide, Elite layout: the market %.2f x %.2f the plain scale, hints along the bottom: ok"
      % (sx / h.scale, sy / h.scale))
# flight's own frames aren't fitted
key(h, pygame.K_1, "1")
for _ in range(300):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight" and fit_pygame.screen_key(a) is None and h.ctx.sx == h.scale
key(h, pygame.K_9, "9")             # Status: a whole-frame screen in flight
assert fit_pygame.screen_key(a) == ("flight", "status")
key(h, pygame.K_9, "9")
print("flight's frames as before, its screens fitted: ok")
# F10: the badge layout, the game's wide pages off
key(h, pygame.K_F10)
assert h.layout == "badge" and cfg.wide == 0
key(h, pygame.K_F10)
assert h.layout == "elite" and cfg.wide == fit_pygame.MAX_ASPECT
print("F10: badge layout without, Elite with: ok")
# without --wide nothing changes
cfg.wide = 0
h2 = run.Host(scale=2, full=False, save_dir=tempfile.mkdtemp(prefix="ace_pi_wide_"), layout="elite")
assert not h2.wide and h2.fitter is None and not isinstance(h2.ctx, fit_pygame.FitCtx) and cfg.wide == 0
print("without --wide: as before: ok")
print("ALL PI WIDE TESTS PASSED")
