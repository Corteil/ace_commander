"""The Raspberry Pi host (P1): a whole trip by keyboard, through the real game
in a pygame window, headless (SDL's dummy video driver).

    python3 hosts/pi/tests/test_pi_trip.py

Buy on the market, launch, fight, pick a system on the local chart, jump,
dock with the docking computer, sell, and buy a ship in the Shipyard; on the
way, every docked tab and in-flight screen is drawn and must show something.
Keys do the playing; only the waits a player would fly through (finding a
fight, flying to the station) are skipped by placing things. Also checks the
Pi's own files: save and options.json in the data folder, DEBUG off unless
asked for. Saves screenshots to hosts/pi/tests/shots/ (git-ignored).
"""
import json
import os
import random
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
random.seed(7)


def press(h, k, ch=""):
    h.handle(pygame.event.Event(pygame.KEYDOWN, key=k, unicode=ch, mod=0))


def let_go(h, k, ch=""):
    h.handle(pygame.event.Event(pygame.KEYUP, key=k, unicode=ch, mod=0))


def key(h, k, ch="", frames=2):
    """Press and let go of a key, with a frame in between and after."""
    press(h, k, ch)
    h.step(40)
    let_go(h, k, ch)
    for _ in range(frames):
        h.step(40)


def ch_key(h, ch):
    """A character key: a letter, a digit or a symbol, as typed."""
    k = pygame.key.key_code(ch) if ch not in "-=" else (pygame.K_MINUS if ch == "-" else pygame.K_EQUALS)
    key(h, k, ch)


def lit(h):
    """How many pixels of the round screen aren't black (one in 16)."""
    s = h.screen
    w, ht = s.get_size()
    return sum(1 for y in range(0, ht, 4) for x in range(0, w, 4) if s.get_at((x, y))[:3] != (0, 0, 0))


def shot(h, name, least=300):
    n = lit(h)
    assert n >= least, (name, n)
    pygame.image.save(h.window, os.path.join(SHOTS, "trip_" + name + ".png"))


def until(h, cond, frames, ms=40):
    for _ in range(frames):
        if cond():
            return True
        h.step(ms)
    return cond()


save_dir = tempfile.mkdtemp(prefix="ace_pi_trip_")
h = run.Host(scale=2, save_dir=save_dir)
a = h.app
ace = h.ace
assert not ace.DEBUG_MENU, "no DEBUG menu on the Pi unless asked for"
assert ace.options_path().startswith(save_dir) and ace.SAVE_PATH.startswith(save_dir)
assert sys.modules[run.PKG + ".content"].__file__.startswith(save_dir), \
    "content.py reads options.json from the data folder"

# ---- a new commander, docked ---------------------------------------------------
until(h, lambda: False, 5)
while a.choices()[a.menu] != "NEW COMMANDER":
    key(h, pygame.K_RIGHT)
key(h, pygame.K_RETURN)
key(h, pygame.K_F3)                 # C: start
assert a.mode == "docked", a.mode
c = a.cmdr
d = a.dock
print("new commander, docked at", a.galaxy.system(c.system).name)

# every docked tab draws: the joystick (arrow keys) goes round them
seen = []
for _ in range(len(d.tabs)):
    seen.append(d.name())
    shot(h, "dock_" + d.name().lower().replace(" ", "_"))
    key(h, pygame.K_RIGHT)
assert d.name() == seen[0] and len(set(seen)) == len(d.tabs), seen
print("every docked tab draws:", ", ".join(seen))

# Options (= on the keyboard) opens over Status, F (the badge's F: F6) back
ch_key(h, "=")
assert d.name() == "OPTIONS", d.name()
shot(h, "dock_options")
key(h, pygame.K_F6)
assert d.name() != "OPTIONS"

# off the flight the letters A C D E F are the badge's buttons too (Brian):
# C on Status opens Options, F goes back, E and the arrow go round the tabs
ch_key(h, "9"); assert d.name() == "STATUS"
ch_key(h, "c"); assert d.name() == "OPTIONS", "C: the badge's C"
ch_key(h, "f"); assert d.name() == "STATUS", "F: the badge's F"
ch_key(h, "2"); cash = c.cash
ch_key(h, "c"); assert sum(c.cargo) == 1 and c.cash < cash, "C buys, as the badge's C"
ch_key(h, "d"); assert sum(c.cargo) == 0 and c.cash == cash, "D sells, as the badge's D"
ch_key(h, "e"); assert d.name() != "MARKET", "E: the tab before"
ch_key(h, "9"); ch_key(h, "b"); assert d.name() == "INVENTORY", ("B: the next tab", d.name())
ch_key(h, "5"); ch_key(h, "c"); assert d.cursor, "C: the chart's cursor"
ch_key(h, "b"); assert a.finder is not None, "B on the Galactic chart: find a system"
for ch in "abcdef":     # typing: the letters are only letters
    ch_key(h, ch)
assert a.finder is not None and d.name() == "GALACTIC CHART"
key(h, pygame.K_ESCAPE)
assert a.finder is None, "Esc leaves the search"
key(h, pygame.K_ESCAPE); ch_key(h, "9")
print("docked, the letters A-F work as the badge's buttons (not while typing)")

# ---- B is the badge's B docked, on the market too: the next tab ----------------
ch_key(h, "2")
cash = c.cash
ch_key(h, "b"); assert d.name() == "EQUIP SHIP" and c.cash == cash, ("B: next tab", d.name())

# ---- buy on the market: 2, then C held (C buys, D sells) ------------------------
ch_key(h, "2")
assert d.name() == "MARKET", d.name()
press(h, pygame.K_c, "c")
until(h, lambda: False, 15)
let_go(h, pygame.K_c, "c")
h.step(40)
bought = sum(c.cargo)
assert bought > 0 and c.cash < cash, (bought, cash, c.cash)
shot(h, "market_bought")
print("market: bought %d t for %.1f Cr" % (bought, (cash - c.cash) / 10.0 if cash > 1000 else cash - c.cash))

# ---- launch: 1 ------------------------------------------------------------------
ch_key(h, "1")
assert a.mode == "launch", a.mode
assert until(h, lambda: a.mode == "flight", 300), a.mode
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9      # no one else turns up
until(h, lambda: False, 10)
shot(h, "flight", 100)
print("launched")

# every in-flight screen draws, and its own key closes it (the game runs on)
for k, sub in (("9", "status"), ("0", "inventory"), ("8", "market"), ("6", "chart"),
               ("5", "chart"), ("7", "data")):
    ch_key(h, k)
    assert a.fsub == sub and not a.paused, (k, a.fsub)
    shot(h, "screen_%s_%s" % (k, sub))
    if sub == "data":
        key(h, pygame.K_F4)         # D: back to the chart
        assert a.fsub == "chart"
        ch_key(h, "6")
    else:
        ch_key(h, k)
    assert a.fsub not in ace.SCREENS, (k, a.fsub)
print("in-flight screens 0 and 5-9 draw and close")

# the four views: 2-4 and back to the front with 1
for n, k in enumerate("1234"):
    ch_key(h, k)
    assert g.view == n, (k, g.view)
ch_key(h, "1")

# ---- a fight: a pirate dead ahead; Space fires ----------------------------------
name = next(n for n in g.types if n in ("SIDEWINDER",)) if "SIDEWINDER" in g.types else \
    [n for n, t in g.types.items() if t.energy and not n.startswith(("CORIOLIS", "DODO"))][0]
o = ace.game.Obj(g.types[name], "ship", 0.0, 0.0, 700.0)
o.has_pod = False
g.objs.append(o)
g.god = True                        # this is about the keys, not about surviving
press(h, pygame.K_SPACE, " ")
fought = False
for _ in range(400):                # held in the sights, as a player would steer
    o.x = o.y = 0.0
    h.step(40)
    if o.dead or o not in g.objs:
        fought = True
        break
let_go(h, pygame.K_SPACE, " ")
assert fought, ("the laser never got it", o.energy)
until(h, lambda: False, 5)
shot(h, "fight", 100)
g.god = False
print("fight: Space fired the laser and the", name, "went down")

# ---- pick a system on the local chart (6, arrows, Enter) and jump (H) -------------
here = c.system
ch_key(h, "6")
assert a.fsub == "chart"
reach = a._jump_ok
for k in (pygame.K_RIGHT, pygame.K_UP, pygame.K_LEFT, pygame.K_DOWN):
    press(h, k)
    until(h, lambda: False, 12)
    let_go(h, k)
    key(h, pygame.K_RETURN)
    if a.target is not None and a.target != here and reach() is not None:
        break
assert a.target is not None and reach() is not None, "a system in range picked on the chart"
to = a.target
shot(h, "chart_target")
ch_key(h, "6")                      # back to the space view
ch_key(h, "h")
assert g.jump_t > 0, "H started the countdown"
assert until(h, lambda: c.system == to, 1500), ("jumped", c.system, to)
until(h, lambda: a.mode == "flight" and a.witch is None, 300)
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
until(h, lambda: False, 10)
shot(h, "arrived", 100)
print("hyperspace by H: arrived at", a.galaxy.system(to).name)

# ---- dock: the docking computer (bought here, the waits flown over), C ---------
g.computer = True
g.to_station(4000.0, slot=False)
for o in list(g.objs):
    if o.kind == "ship":
        g.objs.remove(o)            # nobody in the way
ch_key(h, "c")
assert g.autodock, "C: the docking computer on"
assert until(h, lambda: a.mode != "flight", 4000, ms=50), "docked"
assert until(h, lambda: a.mode == "docked", 800), a.mode
shot(h, "docked_again")
print("docking computer flew in; docked at", a.galaxy.system(c.system).name)

# ---- sell: 3 opens the market on the first good in the hold, D held sells ---------
d = a.dock
ch_key(h, "3")
assert d.name() == "MARKET" and c.cargo[d.sel] > 0, (d.name(), d.sel)
before = sum(c.cargo)
cash = c.cash
press(h, pygame.K_d, "d")
until(h, lambda: False, 20)
let_go(h, pygame.K_d, "d")
h.step(40)
assert sum(c.cargo) < before and c.cash > cash, (sum(c.cargo), c.cash)
print("market: sold %d t" % (before - sum(c.cargo)))

# ---- buy a ship: - (Shipyard), down to one for sale, C (stats), C (buy) ----------
c.cash += 10 ** 7                   # a rich trader
ch_key(h, "-")
assert d.name() == "SHIPYARD", d.name()
key(h, pygame.K_DOWN)
assert d.ysel > 0, "a ship for sale picked"
key(h, pygame.K_F3)
assert d.name() == "SHIP STATS", d.name()
shot(h, "ship_stats")
old = a._ship_name()
ch_key(h, "c")
assert a._ship_name() != old, ("bought", old, a._ship_name())
shot(h, "new_ship")
print("Shipyard: bought a", a._ship_name(), "(the", old, "is in the hangar)")
assert c.hangar, "the old ship is in the hangar"

# ---- saved where the Pi keeps it; quit to the title and leave ---------------------
with open(ace.SAVE_PATH) as f:
    saved = json.load(f)
assert saved, "saved in the data folder"
for _ in range(4):                  # F: back a screen at a time, to the title
    if a.mode == "menu":
        break
    key(h, pygame.K_F6)
assert a.mode == "menu", a.mode
key(h, pygame.K_ESCAPE)
assert not h.running
pygame.quit()

# Options > CONTENT: OWN saved in the Pi's options.json picks the game's own
# content at the next start (content.py reads it from the data folder)
import subprocess   # noqa: E402
own_dir = tempfile.mkdtemp(prefix="ace_pi_own_")
with open(os.path.join(own_dir, "options.json"), "w") as f:
    json.dump({"own": True}, f)
out = subprocess.run([sys.executable, "-c", (
    "import sys; sys.path.insert(0, %r); import run, pi_firmware; pi_firmware.install(); ace = run.load_game(%r); "
    "print(ace.ORIGINAL_SHIPS, ace.SAVE_PATH, ace.DEBUG_MENU)") % (PI, own_dir)],
    capture_output=True, text=True, check=True).stdout.split()
assert out == ["True", os.path.join(own_dir, "commander.json"), "False"], out
print("options.json in the data folder: CONTENT OWN applies at the next start")
print("ALL PI TRIP TESTS PASSED")
