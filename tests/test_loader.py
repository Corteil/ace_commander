"""app.py, the badge's entry point (the launcher imports <folder>.app): a
loading screen while the other modules are imported (builds 49, 50); the real
app is ace.py."""
import asyncio, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx, App

bs.install()
import ace_commander
from ace_commander import app as loader

assert ace_commander.AceCommander is ace_commander.ace.AceCommander, "on a PC: the app itself"
assert loader.__app_export__ is loader.AceCommander, "what the badge's launcher starts"
for name in loader.STEPS:
    assert os.path.exists(os.path.join(REPO, name + ".py")) or name in loader.OPTIONAL, name

# a pretend clock: each look at it moves it on 37 ms
clock = [0]
def fake_now():
    clock[0] += 37
    return clock[0]
loader._now = fake_now
ld = loader.AceCommander()
assert ld.real is None and ld.done == 0
frames = []


def shot():
    c = CountCtx(); ld.draw(c)
    assert c.depth == 0
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


class Handed(Exception):
    pass


async def render_update():
    frames.append((ld.done, shot()))
    if ld.real is not None:
        raise Handed()      # the real app's loop has started: stop here


try:
    asyncio.run(ld.run(render_update))
except Handed:
    pass
assert frames[0][0] == 0 and "LOADING" in frames[0][1]
shown = ["LOADING" in f[1] for f in frames]
assert True in shown and False in shown, "LOADING flashes on and off"
# by the clock: on for FLASH_MS, off for FLASH_MS, whatever the steps take
t = ld.t0
for ms, on in ((0, True), (loader.FLASH_MS - 1, True), (loader.FLASH_MS, False),
               (2 * loader.FLASH_MS - 1, False), (2 * loader.FLASH_MS, True)):
    clock[0] = t + ms - 37
    assert ld._shown() == on, (ms, on)
clock[0] = t + loader.FLASH_MS - 60 - 37
assert ld._until_change() == 60
# the name in block letters, where and as the title screen draws it (build 51)
from ace_commander import letters, title
assert loader._letters is letters
c = CountCtx(); loader.AceCommander().draw(c)
n_name = len(letters.ACE) + len(letters.COMMANDER)
assert c.calls.get("rectangle", 0) >= n_name + 1     # the name, the background, the bar
assert title._ACE is letters.ACE and title._COMMANDER is letters.COMMANDER
assert sorted(set(f[0] for f in frames)) == list(range(len(loader.STEPS) + 1)) or \
    set(range(len(loader.STEPS))) <= set(f[0] for f in frames), "a frame drawn before each module"
assert ld.done == len(loader.STEPS)
real = ld.real
assert isinstance(real, ace_commander.ace.AceCommander) and real.host is ld
assert real.mode == "menu"
# drawing and minimise go through
c = CountCtx(); ld.draw(c); assert c.depth == 0
App.minimised = 0
real.minimise(); assert App.minimised == 1
alone = ace_commander.ace.AceCommander()
assert alone.host is alone
# a module that won't load: the screen says so
ld2 = loader.AceCommander()
ld2.error = "game: MemoryError"
c = CountCtx(); ld2.draw(c)
assert "LOAD FAILED" in [t[0] for t in c.texts]
print("loader: a loading screen with progress, then the app, hosted: ok")
print("ALL LOADER TESTS PASSED")
