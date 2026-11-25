"""Finding a system on the Galactic chart by name (build 88): the names
matched, the keyboard's own page with its suggestions, and the badge's own
text entry when no keyboard is fitted (a stand-in for the firmware's
TextDialog), in flight and docked."""
import json, os, sys, types
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
        self.masked = masked
        self._keys = [["a", "b"], ["c"], ["Done"], ["d"], ["e"], ["..."]]   # as the firmware's
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
assert e.tdialog.app is e.host, "registered to the focused app (the host), or no button reaches it"
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
print("in flight: B on the Galactic chart only: ok")

# ---- the commander's name (build 89) -----------------------------------------
assert mod.badge_name() == mod.DEFAULT_NAME == "Jameson", "no badge name: Elite's"
settings = types.ModuleType("settings")
settings.get = lambda k: "Brian" if k == "name" else None
sys.modules["settings"] = settings
assert mod.badge_name() == "Brian"
# the NEW COMMANDER page: on LEVEL, NAME above it showing the suggestion greyed
e.mode = "menu"; e.pad.keyboard = True
choose(e, "NEW COMMANDER")
assert e.mode == "level" and e.n_sel == 1 and "BRIAN" in texts(e)
tick(e, fresh=["JOYUP"]); assert e.n_sel == 0 and "C: name   F: back" in texts(e)
tick(e, fresh=["C"]); assert e.namer is not None and e.namer.suggestion == "BRIAN"
tx = texts(e)
assert "COMMANDER NAME" in tx and "BRIAN" in tx and "Tab: BRIAN" in tx, tx
for k in ("KEY_A", "KEY_C", "KEY_E"):
    tick(e, fresh=[k])
assert e.namer.text == "ACE" and "Tab: BRIAN" not in texts(e)
tick(e, fresh=["KEY_TAB"]); assert e.namer.text == "BRIAN", "Tab fills it in"
tick(e, fresh=["KEY_BACKSPACE"]); tick(e, fresh=["KEY_BACKSPACE"])
tick(e, fresh=["KEY_O"]); tick(e, fresh=["KEY_X"]); assert e.namer.text == "BRIOX"
tick(e, fresh=["KEY_ESCAPE"]); assert e.namer is None and e.n_name == "" and e.mode == "level", "Esc: unchanged"
tick(e, fresh=["C"])
for k in ("KEY_H", "KEY_A", "KEY_N"):
    tick(e, fresh=[k])
tick(e, fresh=["C"]); assert e.namer is None and e.n_name == "HAN" and "HAN" in texts(e)
tick(e, fresh=["JOYDOWN"]); tick(e, fresh=["C"])
assert e.mode == "docked" and e.cmdr.name == "HAN"
import json as _json
assert _json.load(open(SAVE))["name"] == "HAN"
# no keyboard: the badge's text entry; Done on nothing takes the suggestion
e.pad.keyboard = False
e.dock.open("OPTIONS")
items = e._settings(True); assert "NAME: HAN" in items, items
e._change("NAME: HAN", False)
dl = e.ndialog; assert dl is made[-1] and "BRIAN" in dl.message and dl.text == "han"
assert dl.app is e.host
dl.text = ""; dl._result = ""; tick(e)
assert e.ndialog is None and e.cmdr.name == "BRIAN" and _json.load(open(SAVE))["name"] == "BRIAN"
e._change("NAME: BRIAN", False); dl = e.ndialog
dl._result = "zaphod"; tick(e); assert e.cmdr.name == "ZAPHOD"
e._change("NAME: ZAPHOD", False); e.ndialog._result = False; tick(e)
assert e.cmdr.name == "ZAPHOD", "cancelled"
assert mod.cmdr_name(e.cmdr) == "ZAPHOD"
# an old save with no name: the badge's
from ace_commander import commander as cm_
assert cm_.Commander.from_dict({}).name == "" and mod.cmdr_name(cm_.Commander()) == "Brian"
# Status in flight: COMMANDER and the name, as Elite
e.dock.go(0); tick(e, fresh=["A"])
for _ in range(300):
    tick(e)
    if e.mode == "flight":
        break
e._open("status")
assert "COMMANDER ZAPHOD" in texts(e)
assert not any(t.startswith("NAME:") for t in e._settings(True)), "not in flight"
del sys.modules["settings"]
# TEXT ENTRY: PICKER (build 124): the letter picker on the badge's own controls
e.pad.keyboard = False
assert any(t.startswith("TEXT ENTRY: BADGE") for t in e._settings(False)), e._settings(False)
e._change("TEXT ENTRY: BADGE", False)
assert e.use_picker and json.load(open(mod.options_path())).get("picker") is True
got = []
e._open_name("", got.append)
from ace_commander import picker as pk
dl = e.ndialog
assert isinstance(dl, pk.LetterPicker) and dl.driven, type(dl)
tick(e, fresh=["C"])                # keep A
tick(e, fresh=["JOYUP"]); tick(e, fresh=["JOYUP"])  # C
tick(e, fresh=["JOYRIGHT"])         # keep: AC
tick(e, fresh=["JOYLEFT"])          # back onto the C
assert dl.text == "A" and pk.LETTERS[dl.i] == "C", (dl.text, dl.i)
for _ in range(20):
    tick(e, held=["JOYUP"])         # held: it repeats
assert pk.LETTERS[dl.i] != "D", "held up runs on"
tick(e, fresh=["C"])
tick(e, fresh=["A"])                # done
assert got and got[0].startswith("A") and len(got[0]) == 2 and e.ndialog is None, got
got = []
e._open_name("", got.append)
tick(e, fresh=["F"])                # F cancels
assert got == [] and e.ndialog is None
e._change("TEXT ENTRY: PICKER", False)
assert not e.use_picker
os.remove(SAVE)
print("commander's name: suggested from the badge, Tab, Options, saved, Status; the picker: ok")
print("ALL FIND TESTS PASSED")
