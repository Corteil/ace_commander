"""The Pi's keys carry the same control names as the badge works out for the
same keys (platform layer, step 2): every key and button in
hosts/pi/controls_pi.py against platform_tildagon.Input, run on stand-ins
for the firmware's buttons. Needs no pygame."""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
sys.path.insert(0, os.path.join(REPO, "hosts", "pi"))
import badge_stubs as bs                # noqa: E402
from badge_stubs import Button, TYPES   # noqa: E402

bs.install()
import controls_pi as cp                # noqa: E402

# the firmware's keyboard table, every key the Pi has (the Keyboard Hexpansion's
# names: Enter and Escape are CONFIRM and CANCEL too, the arrows the directions)
parent = {"ENTER": TYPES["CONFIRM"], "ESCAPE": TYPES["CANCEL"],
          "UP": TYPES["UP"], "DOWN": TYPES["DOWN"], "LEFT": TYPES["LEFT"], "RIGHT": TYPES["RIGHT"]}
firm = {k: Button(k, "Keyboard", parent.get(k)) for k in cp.KEYBOARD}
kb = types.ModuleType("events.keyboard")
kb.KEYBOARD_BUTTONS = firm
sys.modules["events.keyboard"] = kb
sys.modules.pop("ace_commander.platform_tildagon", None)
from ace_commander import controls, platform_tildagon     # noqa: E402

c = controls.Controls()
owner = sys.modules["app"].App()
inp = platform_tildagon.Input(owner, c)

pairs = [(cp.KEYBOARD[k], firm[k]) for k in cp.KEYBOARD]
pairs.append((cp.TAB, Button("TAB", "Keyboard")))       # matched by name on the badge
for ch in "ABCDEF":
    pairs.append((cp.BADGE[ch], bs.PHYSICAL[ch]))
for d in ("UP", "DOWN", "LEFT", "RIGHT"):
    pairs.append((cp.STICK[d], bs.PHYSICAL["JOY" + d]))
pairs.append((cp.STICK["SELECT"], bs.PHYSICAL["JOYFIRE"]))
for pi_key, button in pairs:
    want = inp._names(button)
    assert sorted(pi_key.names) == sorted(want), (pi_key, pi_key.names, want)
    assert len(set(pi_key.names)) == len(pi_key.names), (pi_key, "a name twice")
    assert pi_key.ch == inp.letters.get(button), (pi_key, pi_key.ch)
    assert pi_key.badge == inp.badge_keys.get(button), (pi_key, pi_key.badge)
print("%d Pi keys and buttons: the same control names, letters and badge buttons as the badge's: ok"
      % len(pairs))

# the Pi's Feed drives Controls as the badge's events do
feed = cp.Feed()
c = controls.Controls()
feed.attach(c)
feed.down(cp.KEYBOARD["SHIFT"]); feed.down(cp.KEYBOARD["H"]); feed.up(cp.KEYBOARD["SHIFT"])
assert c.hit("k_H") and c.hit("mod+k_H") and c.typed == "H" and c.keyboard
feed.up(cp.KEYBOARD["H"]); c.end_frame()
assert not c.held("k_H") and not c.hits
c.as_buttons = True
feed.down(cp.KEYBOARD["C"])
assert c.held("confirm") and c.held("C") and not c.held("k_C"), "off the flight: the badge's C"
feed.down(cp.KEYBOARD["C"]); feed.up(cp.KEYBOARD["C"])
assert not c.held("confirm"), "a repeat doesn't count twice"
print("the Pi's Feed: Shift+H, typing, the keyboard's A-F as the badge's buttons: ok")
print("ALL PI CONTROLS TESTS PASSED")
