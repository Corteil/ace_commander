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
assert all("LOADING" in f[1] for f in frames[:len(loader.STEPS)]), "LOADING, steady"
# the name in block letters, where and as the title screen draws it (build 51)
from ace_commander import letters, title
assert loader._letters is letters
c = CountCtx(); loader.AceCommander().draw(c)
n_name = len(letters.ACE) + len(letters.COMMANDER)
assert c.calls.get("rectangle", 0) >= n_name + 1     # the name, the background, the bar
assert title._ACE is letters.ACE and title._COMMANDER is letters.COMMANDER
assert [f[0] for f in frames[:len(loader.STEPS)]] == list(range(len(loader.STEPS))), \
    "a frame drawn before each module"
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
# the badge's own text entry must be registered to the host, the app the
# firmware focuses, or no button reaches it (build 89: it froze the badge)
import types as _types
_made = []
class _Dialog:
    def __init__(self, message, app, *a, **k):
        self.app = app; self.text = ""; self._result = None; self.message = message
        _made.append(self)
_comp = _types.ModuleType("app_components"); _dlg = _types.ModuleType("app_components.dialog")
_dlg.TextDialog = _Dialog
sys.modules.update({"app_components": _comp, "app_components.dialog": _dlg})
class _Chart:
    number = 1
    def goto(self, i):
        return True
real.galaxy = ace_commander.galaxy.Galaxy(ace_commander.galaxy.seeds_for(ace_commander.ace.game_data.SEEDS, 0),
                                          ace_commander.ace.game_data.PAIRS)
real.pad.keyboard = False
real._open_find(_Chart())
assert _made and _made[-1].app is ld, "the find dialog is the host's"
real.tdialog = None
real._open_name("", lambda n: None)
assert _made[-1].app is ld, "and so is the name's"
real.ndialog = None
del sys.modules["app_components"], sys.modules["app_components.dialog"]
# a module that won't load: the screen says so
ld2 = loader.AceCommander()
ld2.error = "game: MemoryError"
c = CountCtx(); ld2.draw(c)
assert "LOAD FAILED" in [t[0] for t in c.texts]
print("loader: a loading screen with progress, then the app, hosted: ok")
print("ALL LOADER TESTS PASSED")
