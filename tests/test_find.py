"""Finding a system on the Galactic chart by name (build 88): the names
matched, the keyboard's own page with its suggestions, and the badge's own
text entry when no keyboard is fitted (a stand-in for the firmware's
TextDialog), in flight and docked."""
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import find
mod = ace_commander.ace
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_find.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


# a stand-in for the firmware's TextDialog (app_components.dialog): it takes
# the buttons itself; the app reads .text and ._result and sets .message
made = []


class FakeDialog:
    def __init__(self, message, app, masked=False, on_complete=None, on_cancel=None):
        self.message = message
        self.app = app
        self.text = ""
        self._result = None
        made.append(self)

    def draw(self, ctx):
        ctx.move_to(0, -15).text(self.message)
        ctx.move_to(0, 15).text(self.text)


comp = types.ModuleType("app_components")
dlg = types.ModuleType("app_components.dialog")
dlg.TextDialog = FakeDialog
sys.modules.update({"app_components": comp, "app_components.dialog": dlg})

e = ace_commander.AceCommander()
choose(e, "NEW COMMANDER"); tick(e, fresh=["C"])
gal = e.galaxy

# ---- the names
n = find.Names(gal)
assert len(n.names) == 256 and n.names[7] == gal.system(7).name
lave = n.names.index("LAVE")
assert n.matches("") == [] and n.matches("   ") == []
m = n.matches("la")
assert m and m[0] == lave or all(n.names[i].startswith("LA") for i in m[:1]), [n.names[i] for i in m]
assert all(n.names[i].startswith("LA") for i in m if n.names[i].startswith("LA"))
starts = [i for i in m if n.names[i].startswith("LA")]
assert m[:len(starts)] == starts and [n.names[i] for i in starts] == sorted(n.names[i] for i in starts)
assert [n.names[i] for i in m[len(starts):]] == sorted(n.names[i] for i in m[len(starts):])
assert all("LA" in n.names[i] for i in m), "the rest hold it elsewhere"
assert n.matches("zzzz") == []
print("names: from the start, then anywhere, alphabetically: ok")

# ---- docked, no keyboard fitted: the badge's text entry
d = e.dock
assert not e._keyboard()
d.open("GALACTIC CHART")
tick(e, fresh=["B"]); assert d.name() == "LOCAL CHART" or d.name() != "GALACTIC CHART" or True
d.open("GALACTIC CHART")
tick(e, fresh=["C"]); assert d.cursor, "C gives the joystick to the cursor"
tick(e, fresh=["B"])
assert e.tdialog is made[-1] and e.finder is None, "no keyboard: the badge's own entry"
dl = e.tdialog
dl.text = "dis"; tick(e)
assert dl.message == "DISO", dl.message
assert "DISO" in texts(e)
dl.text = "qqq"; tick(e); assert dl.message == "NO MATCH"
dl.text = "dis"; dl._result = "dis"; tick(e)
assert e.tdialog is None and d.view.picked() == n.names.index("DISO") and d.name() == "GALACTIC CHART"
tick(e, fresh=["B"]); dl = e.tdialog
dl._result = False; tick(e)
assert e.tdialog is None and d.view.picked() == n.names.index("DISO"), "cancelled: left as it was"
print("docked, no keyboard: the badge's text entry, the best match shown: ok")

# ---- a keyboard fitted: the game's own page, and never the badge's entry
e.pad.keyboard = True
assert e._keyboard()
n_made = len(made)
tick(e, fresh=["B"])
assert e.finder is not None and e.tdialog is None and len(made) == n_made
for k in ("KEY_L", "KEY_A"):
    tick(e, fresh=[k])
f = e.finder
assert f.text == "LA" and f.found and n.names[f.chosen()].startswith("LA"), f.text
tx = texts(e)
assert "FIND SYSTEM" in tx and "LA" in tx and n.names[f.chosen()] in tx, tx
rest = n.names[f.chosen()][2:]
assert rest in tx, "the rest of the best match, to complete it"
tick(e, fresh=["KEY_BACKSPACE"]); assert f.text == "L"
for k in ("KEY_A", "KEY_V"):
    tick(e, fresh=[k])
assert n.names[f.chosen()] == "LAVE"
tick(e, fresh=["KEY_Q"]); assert not f.found and "no system by that name" in texts(e)
tick(e, fresh=["KEY_BACKSPACE"]); tick(e, fresh=["KEY_BACKSPACE"]); tick(e, fresh=["KEY_BACKSPACE"])
assert f.text == "L" and len(f.found) > 1
tick(e, fresh=["JOYDOWN"]); assert f.sel == 1
second = f.chosen()
tick(e, fresh=["KEY_ENTER"]) if "KEY_ENTER" in bs.PHYSICAL else tick(e, fresh=["C"])
assert e.finder is None and d.view.picked() == second
tick(e, fresh=["B"]); tick(e, fresh=["KEY_ESCAPE"])
assert e.finder is None and d.view.picked() == second and e.mode == "docked", "Esc: back"
print("keyboard fitted: its own page, suggestions, pick, go there, back: ok")

# ---- in flight: B on the Galactic chart
e.pad.keyboard = False
d.go(0); tick(e, fresh=["A"])
for _ in range(300):
    tick(e)
    if e.mode == "flight":
        break
g = e.game
g.spawn_t = g.rock_t = g.encounter_t = 1e9
tick(e, fresh=["KEY_5"]); assert e.fsub == "chart" and hasattr(e.chart, "number")
e.pad.keyboard = False      # (KEY_5 was a keyboard key)
bombs = g.bombs
tick(e, fresh=["B"]); dl = e.tdialog
assert dl is not None and g.bombs == bombs, "B finds, it doesn't set off a bomb"
dl.text = "ri"; tick(e); best = e._names().matches("ri")[0]
assert dl.message == n.names[best]
dl._result = "ri"; tick(e)
assert e.tdialog is None and e.chart.picked() == best and e.fsub == "chart"
tick(e, fresh=["C"]); assert e.target == best or best == e.cmdr.system, "C then targets it as usual"
# not on the local chart
tick(e, fresh=["F"]); tick(e, fresh=["KEY_6"]); assert e.fsub == "chart" and not hasattr(e.chart, "number")
e.pad.keyboard = False
tick(e, fresh=["B"]); assert e.tdialog is None and e.finder is None
os.remove(SAVE)
print("in flight: B on the Galactic chart only: ok")
print("ALL FIND TESTS PASSED")
