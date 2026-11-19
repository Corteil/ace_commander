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
B = {"back": pygame.CONTROLLER_BUTTON_BACK, "guide": pygame.CONTROLLER_BUTTON_GUIDE, "l3": pygame.CONTROLLER_BUTTON_LEFTSTICK,
     "r3": pygame.CONTROLLER_BUTTON_RIGHTSTICK, "a": pygame.CONTROLLER_BUTTON_A, "b": pygame.CONTROLLER_BUTTON_B,
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
h.pads.pads.clear()                 # a real pad plugged in plays no part here
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

# docked: the bumpers go round the tabs, Back opens Options, the triggers do nothing
tab = d.name()
tap(h, "rb"); assert d.name() != tab, "right bumper: the next tab"
tap(h, "lb"); assert d.name() == tab, "left bumper: the tab before"
for t in (pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT):
    axis(h, t, 1.0); h.step(40); axis(h, t, 0.0); h.step(40)
assert d.name() == tab, "triggers: nothing docked"
tap(h, "back"); assert d.name() == "OPTIONS", ("Back: Options", d.name())
tap(h, "b"); assert d.name() == "STATUS"
# the hints name the pad's buttons once the pad was used, the badge's after a key
texts = []
real_text = h.ctx.text
h.ctx.text = lambda t: (texts.append(h.ctx.labels and __import__("ctx_pygame").relabel(str(t), h.ctx.labels) or str(t)), real_text(t))[1]
h.step(40)
assert "START: LAUNCH" in texts and "B: title screen" in texts, texts
h.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LSHIFT, unicode="", mod=0))
h.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_LSHIFT, unicode="", mod=0))
texts.clear(); h.step(40)
assert "A: LAUNCH" in texts and "F: title screen" in texts, texts
h.ctx.text = real_text
print("docked: bumpers, Back for Options, hints in the pad's names: ok")

# ---- flying: Brian's flight map ---------------------------------------------------
LX, LY = pygame.CONTROLLER_AXIS_LEFTX, pygame.CONTROLLER_AXIS_LEFTY
RX, RY = pygame.CONTROLLER_AXIS_RIGHTX, pygame.CONTROLLER_AXIS_RIGHTY
LT, RT = pygame.CONTROLLER_AXIS_TRIGGERLEFT, pygame.CONTROLLER_AXIS_TRIGGERRIGHT
h.pads.pads[PAD] = None         # the made-up pad counts as plugged in (for the sticks)
tap(h, "start"); assert a.mode == "launch", "Start (the badge's A) launches"
for _ in range(300):
    h.step(40)
    if a.mode == "flight":
        break
assert a.mode == "flight", a.mode
g = a.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
g.objs[:] = []
assert h.pads.flying()


def rock(z=2000.0):
    import importlib
    gm = importlib.import_module(run.PKG + ".game")
    o = gm.Obj(g.types[[n for n in g.types if n != "CORIOLIS"][0]], "rock", 0.0, 0.0, z)
    g.objs[:] = [o]
    return o


# the sticks: right x roll, right y pitch, left x yaw, left y power
o = rock()
axis(h, LX, 1.0)
for _ in range(5):
    h.step(40)
axis(h, LX, 0.0); h.step(40)
assert o.x < -10, ("left stick right: yaw right", o.x)
o = rock()
axis(h, RY, -1.0)
for _ in range(5):
    h.step(40)
axis(h, RY, 0.0); h.step(40)
assert abs(o.y) > 10 and abs(o.x) < 1, ("right stick up / down: pitch", o.x, o.y)
o = rock()
o.x = 300.0
axis(h, RX, 1.0)
for _ in range(5):
    h.step(40)
axis(h, RX, 0.0); h.step(40)
assert abs(o.y) > 10, ("right stick left / right: roll", o.y)
axis(h, LY, -1.0)                   # up: full power
for _ in range(80):
    h.step(40)
assert g.speed >= g.max_speed - 0.01, ("power full", g.speed)
axis(h, LY, 0.0)                    # let go: half
for _ in range(80):
    h.step(40)
assert abs(g.speed - g.max_speed / 2) < 1.0, ("power centre: half", g.speed)
assert not a.pad.held("j_left"), "flying, the left stick isn't the joystick"
print("sticks: yaw, pitch, roll, power: ok")

# triggers and bumpers: right trigger fires, right bumper the bomb, left trigger the missile
axis(h, RT, 1.0)
for _ in range(5):
    h.step(40)
assert g.beam > 0 or g.heat > 0, "right trigger: fire"
axis(h, RT, 0.0); h.step(40)
axis(h, LT, 1.0); h.step(40); axis(h, LT, 0.0); h.step(40)
assert g.msg in ("NO TARGET", "MISSILE NOT ARMED", "NO LOCK"), ("left trigger: the missile", g.msg)
print("triggers: fire, missile: ok")

# D-pad: the views; right stick click: the next view
for name, view in (("down", 1), ("left", 2), ("right", 3), ("up", 0)):
    tap(h, name)
    assert g.view == view, (name, g.view)
tap(h, "r3"); assert g.view == 1, "right stick click: the next view"
tap(h, "up")
print("D-pad views: ok")

# B: the docking computer on / off
tap(h, "b"); assert not g.autodock and g.msg == "NO DOCKING COMPUTER", g.msg
a.cmdr.extras.append("docking"); g.computer = True
g.to_station(4000.0, slot=False)
tap(h, "b"); assert g.autodock, "B: on"
tap(h, "b"); assert not g.autodock, "B again: off"
print("B: docking computer: ok")

# Y: the in-flight screens in turn, then back to space
seen = []
for _ in range(6):
    tap(h, "y")
    seen.append(a.fsub if a.fsub != "chart" else type(a.chart).__name__)
assert seen == ["Chart", "GalChart", "status", "inventory", "market", None], seen
assert not a.paused
print("Y: local chart, galactic chart, status, inventory, market, space: ok")

# on an in-flight screen: D-pad cursor, A selects, X data, B back, Back the search;
# the sticks still fly and the right trigger fires; X is no hyperspace there
tap(h, "y"); assert a.fsub == "chart" and type(a.chart).__name__ == "Chart"
assert h.pads.state() == "screen"
cx = a.chart.cx
home = a.chart.sel
for k in ("right", "down", "left", "up"):    # until the cursor is on another system
    button(h, k, True)
    for _ in range(40):
        h.step(40)
        if a.chart.sel != home:
            break
    button(h, k, False); h.step(40)
    if a.chart.sel != home:
        break
assert a.chart.cx != cx or a.chart.sel != home, ("D-pad: the chart cursor", cx, a.chart.cx)
assert a.chart.sel != home, "the cursor on another system"
o = rock()
axis(h, RX, 1.0)
for _ in range(5):
    h.step(40)
axis(h, RX, 0.0); h.step(40)
o.x = o.y = 0.0
axis(h, LX, 1.0)
for _ in range(5):
    h.step(40)
axis(h, LX, 0.0); h.step(40)
assert o.x < -1, ("the sticks still fly on a screen", o.x)
axis(h, RT, 1.0)
for _ in range(3):
    h.step(40)
assert g.beam > 0 or g.heat > 0, "right trigger fires on a screen"
axis(h, RT, 0.0); h.step(40)
tap(h, "a"); assert a.target is not None, "A: select the target"
jt = g.jump_t
tap(h, "x"); assert a.fsub == "data" and g.jump_t == jt, ("X: system data, no jump", a.fsub)
tap(h, "x"); assert a.fsub == "chart", "X again: back to the chart"
tap(h, "y"); assert type(a.chart).__name__ == "GalChart", "Y: the galactic chart"
tap(h, "back"); assert a.finder is not None or a.tdialog is not None or a.fsub == "chart", "Back: search"
if a.finder is not None:
    key = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode="", mod=0)
    h.handle(key); h.step(40)
    h.handle(pygame.event.Event(pygame.KEYUP, key=pygame.K_ESCAPE, unicode="", mod=0)); h.step(40)
tap(h, "b"); assert a.fsub not in ("chart", "data", "status"), ("B: back to space", a.fsub)
assert h.pads.state() == "flight"
print("in-flight screens: cursor, select, data, search, back; still flying: ok")

# the pause menu: the pad as the badge, B resumes
tap(h, "start"); assert a.paused and h.pads.state() == "badge"
tap(h, "down"); assert a.fmenu == 1
tap(h, "b"); assert not a.paused, "B: resume"
print("pause menu: D-pad, B resumes: ok")

# X: hyperspace to the target (a tap); held 1 s: the galactic hyperdrive
reach = a._jump_ok
a.target = None
for s_ in range(256):
    a.target = s_
    if s_ != a.cmdr.system and reach() is not None:
        break
assert reach() is not None
g.to_station(60000.0, slot=False)
tap(h, "x")
assert g.jump_t > 0, "X: the countdown"
g.jump_t = 0.0
sent = []
real_send = h.bus.send
h.bus.send = lambda e: (sent.append((type(e).__name__, e.button.name)), real_send(e))
button(h, "x", True)
for _ in range(30):
    h.step(40)
button(h, "x", False); h.step(40)
h.bus.send = real_send
assert ("ButtonDownEvent", "SHIFT") in sent and ("ButtonDownEvent", "H") in sent, sent
assert sent.count(("ButtonDownEvent", "H")) == 1, "held: only the galactic one, no plain jump after"
print("X: hyperspace, held: galactic: ok")

# A held: the jump drive (J)
button(h, "a", True); h.step(40)
assert a.pad.held("k_J"), "A held: J"
button(h, "a", False); h.step(40)
assert not a.pad.held("k_J")

# Start: the pause menu, where the pad is the badge again
tap(h, "start"); assert a.paused and not h.pads.flying()
tap(h, "down"); assert a.fmenu == 1, "D-pad down in the menu: the next line"
tap(h, "start"); assert not a.paused
print("A: jump drive; Start: the pause menu (the pad as the badge there): ok")

# the Xbox button held 1 s: the escape pod (Esc); a short press does nothing
sent = []
h.bus.send = lambda e: (sent.append((type(e).__name__, e.button.name)), real_send(e))
tap(h, "guide")
assert ("ButtonDownEvent", "ESCAPE") not in sent, "a short press: nothing"
button(h, "guide", True)
for _ in range(15):
    h.step(40)
assert ("ButtonDownEvent", "ESCAPE") not in sent, "not before 1 s"
for _ in range(15):
    h.step(40)
button(h, "guide", False); h.step(40)
h.bus.send = real_send
assert sent.count(("ButtonDownEvent", "ESCAPE")) == 1, sent
print("Xbox button held 1 s: escape pod: ok")

# after the ship is lost (or the pod is out) the pad is the badge: A is C, "continue"
g = a.game
was = g.over
g.over = True
assert h.pads.state() == "badge" and h.pads.labels()["C"] == "A"
g.over = was
print("ship lost: the pad is the badge again: ok")

# unplugging lets go of whatever the pad held
button(h, "a", True); h.step(40)
assert a.pad.held("k_J")
h.handle(pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=PAD)); h.step(40)
assert not a.pad.held("k_J") and PAD not in h.pads.pads, "unplugged: let go"
assert a.analog is None, "no pad: no analogue controls"
print("unplugging lets go: ok")
pygame.quit()
print("ALL PI PAD TESTS PASSED")
