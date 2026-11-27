"""The CardputerZero host (Phase 1): a 320 x 170 screen, bigger text stretched
across off the flight, fonts without fc-list, W/A/S/D as the arrows on screens
(Q / Z / X as the badge's A / C / D), the stop file. Headless (SDL's dummy driver).

    python3 hosts/cardputerzero/tests/test_cz_host.py
"""
import os
import sys
import tempfile

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
HOME = tempfile.mkdtemp(prefix="ace_cz_home_")
os.environ["HOME"] = HOME           # the stop file and screenshots land here
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import pygame       # noqa: E402

import run_cz       # noqa: E402


def key(h, k, ch="", frames=2):
    h.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0))
    h.step(40)
    h.handle(pygame.event.Event(pygame.KEYUP, key=k, unicode=ch, mod=0))
    for _ in range(frames):
        h.step(40)


# fonts by path, never fc-list
assert pygame.font.match_font is run_cz.match_font
p = run_cz.match_font("DejaVuSans")
assert p is None or p.endswith("DejaVuSansCondensed-Bold.ttf"), p
assert run_cz.match_font("nosuchfont") is None
print("fonts: DejaVu by path, no fc-list: ok")

h = run_cz.Host(save_dir=tempfile.mkdtemp(prefix="ace_cz_"), sound=False)
h.pads.pads.clear()
a = h.app
assert h.window.get_size() == run_cz.SIZE, h.window.get_size()
assert h.layout == "elite" and h.ctx.text_k == run_cz.TEXT_K
for _ in range(3):
    h.step(40)
assert abs(h.ctx.sx - h.scale * run_cz.TEXT_K) < 1e-9, "the title is stretched across"
print("320 x 170, Elite layout, text x%.1f, menus stretched across: ok" % run_cz.TEXT_K)

# list menus: fewer lines, further apart (config.menu_k, 1 on the badge)
ck = h.ck
assert ck.MENU_K == run_cz.MENU_K
assert ck.menu_rows(8, 16) == (int(8 / run_cz.MENU_K), 16 * run_cz.MENU_K)
print("menus: %d of 8 lines shown, %.1f apart: ok" % ck.menu_rows(8, 16))

# the title: D is right (the next line), A left; Z picks (the badge's C)
first = a.choices()[a.menu]
key(h, pygame.K_d, "d")
assert a.choices()[a.menu] != first, "D moves right on the title"
key(h, pygame.K_a, "a")
assert a.choices()[a.menu] == first, "A moves back"
while a.choices()[a.menu] != "NEW COMMANDER":
    key(h, pygame.K_d, "d")
key(h, pygame.K_RETURN)
key(h, pygame.K_z, "z")
assert a.mode == "docked", a.mode
print("title: A / D left and right, Z picks: ok")

# docked: D the next tab; the market's hint names X for selling, and X sells
tab = a.dock.name()
key(h, pygame.K_d, "d")
assert a.dock.name() != tab, "D: the next tab"
while a.dock.name() != "MARKET":
    key(h, pygame.K_d, "d")
h.step(40)
import ctx_pygame   # noqa: E402
assert ctx_pygame.relabel("C: buy   D: sell", h.ctx.labels) == "C: buy   X: sell", h.ctx.labels
cr = a.cmdr.cash
key(h, pygame.K_z, "z")             # buy one
assert a.cmdr.cash < cr, "Z buys"
cr = a.cmdr.cash
key(h, pygame.K_x, "x")             # sell it
assert a.cmdr.cash > cr, "X sells"
print("docked: D next tab, Z buys, X sells, hints say X: ok")

# Q launches (the badge's A); in flight W / A / S / D are flight keys again, unstretched
key(h, pygame.K_q, "q")
for _ in range(300):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight", a.mode
assert h.ctx.sx == h.scale, "flight isn't stretched"
assert not h.on_screen()
h.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_s, unicode="s", mod=0))
assert pygame.K_s not in h._held, "S flies in flight"
h.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_s, unicode="s", mod=0))
print("Q launches; in flight W/A/S/D fly, not stretched: ok")

# the stop file ends it
open(run_cz.STOP, "w").close()
h.step(40)
h.show(40)
assert not h.running
os.remove(run_cz.STOP)
print("stop file: ok")
print("ALL CARDPUTERZERO HOST TESTS PASSED")
