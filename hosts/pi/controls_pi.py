"""The Pi's keys and buttons, each with the control names the game reads
(controls.py; platform layer, step 2). Imports nothing, not even pygame.

On the badge platform_tildagon.Input works these names out from the
firmware's buttons; here each key carries them, worked out once by the same
rules (tests/test_pi_controls.py checks they match the badge's, button by
button). keys_pi.py and pad_pi.py pick a Key; Feed tells the game.
"""


class Key:
    """One key or button: its name (for logs and tests) and what it counts as."""

    def __init__(self, name, group, names, ch=None, badge=None):
        self.name = name
        self.group = group
        self.names = tuple(names)
        self.ch = ch            # the letter it types, if any
        self.badge = badge      # the keyboard's A-F: (letter, direction), the badge's button off the flight

    def __repr__(self):
        return "%s.%s" % (self.group, self.name)


# the lettered buttons' system directions, as the 2026 front board sends them
_DIRECTION = {"A": "up", "B": "right", "C": "confirm", "D": "down", "E": "left", "F": "cancel"}
# keys the game reads by their own name ("k_W"), and the number keys' extra names
_NAMED = ("W", "S", "A", "D", "E", "Q", "F", "M", "P", "N", "T", "U", "V", "C", "SPACE", "BACKSPACE",
          "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "H", "J", "SHIFT", "CTRL", "ESCAPE")
_SPEED = {"+": "k_faster", "=": "k_faster", "-": "k_slower", "_": "k_slower"}


def _keyboard(k):
    """The Keyboard Hexpansion's key k (its name in the firmware's table)."""
    names = []
    if k in ("UP", "DOWN", "LEFT", "RIGHT"):
        names.append(k.lower())         # a cursor key is also the system direction...
    elif k == "ENTER":
        names.append("confirm")
    elif k == "ESCAPE":
        names.append("cancel")
    if k in _NAMED:
        names.append("k_" + k)
    if k in ("UP", "DOWN", "LEFT", "RIGHT"):
        names += ["k_" + k, "j_" + k.lower()]   # ...its own key, and the joystick (Brian)
    if k in ("1", "2", "3", "4"):
        names.append("k_view%d" % (int(k) - 1))     # the views: Elite's f0-f3
    if k in _SPEED:
        names.append(_SPEED[k])
    ch = " " if k == "SPACE" else (k if len(k) == 1 and k.isalnum() else None)
    badge = (k, _DIRECTION[k]) if k in _DIRECTION else None
    return Key(k, "Keyboard", names, ch, badge)


KEYBOARD = {c: _keyboard(c) for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"}
for _c in """!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~""":
    KEYBOARD[_c] = _keyboard(_c)
for _n in ("SPACE", "SHIFT", "CTRL", "ALT", "BACKSPACE", "ESCAPE", "ENTER", "UP", "DOWN", "LEFT", "RIGHT"):
    KEYBOARD[_n] = _keyboard(_n)
TAB = Key("TAB", "Keyboard", ["k_TAB"])     # not in the firmware's table: the badge matches it by name

# the 2026 front board's buttons: each a lettered button and a system direction at once
BADGE = {c: Key(c, "TwentyTwentySix", [_DIRECTION[c], c]) for c in "ABCDEF"}
STICK = {n: Key("JOY" + n, "TwentyTwentySix", [n.lower(), "j_" + n.lower()])
         for n in ("UP", "DOWN", "LEFT", "RIGHT")}
STICK["SELECT"] = Key("JOYSELECT", "TwentyTwentySix", ["confirm"])


class Feed:
    """Keys down and up, to the game's controls.Controls. Set as config.input,
    so the game hands over its Controls when it starts (attach)."""

    def __init__(self, log=False):
        self.controls = None
        self.log = log

    def attach(self, controls, owner=None):
        self.controls = controls

    def down(self, key):
        if self.log:
            print("KEY DOWN", repr(key))
        if self.controls is not None:
            self.controls.press(key, key.names, key.ch, key.badge)

    def up(self, key):
        if self.log:
            print("KEY UP", repr(key))
        if self.controls is not None:
            self.controls.release(key)
