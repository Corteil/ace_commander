"""The Tildagon badge's side of the platform layer: what only the badge's
firmware can do, so the rest of the game doesn't import it.

Step 2 (build 101): input. Input listens for the firmware's button events and
tells controls.Controls which control names each one counts as. The rest
(LEDs, tilt, dialogs, the frame loop) moves here in step 3.
"""
from events.input import BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from events.joystick import JOYSTICK_BUTTON_TYPES as JOY
from frontboards.common import FRONTBOARD_BUTTON_TYPES as FB
from system.eventbus import eventbus

try:
    from events.keyboard import KEYBOARD_BUTTONS
except ImportError:
    KEYBOARD_BUTTONS = {}

from . import config

# keyboard keys not in the firmware's KEYBOARD_BUTTONS, by the name a driver
# would give them, and the control name they count as
BY_NAME = {"TAB": "k_TAB", "LSHIFT": "k_LSHIFT", "RSHIFT": "k_RSHIFT"}


class Input:
    """The firmware's button events in, control names out (to controls).

    The firmware's own Buttons.get() searches every known button each time it
    is asked, which is slow when a game asks about twenty things a frame. This
    does the matching once per button (a firmware button counts as each of
    its parents: the badge's A is also UP and Frontboard A) and remembers it.
    """

    def __init__(self, owner, controls):
        self.controls = controls
        table = [(name.lower(), BUTTON_TYPES[name])
                 for name in ("UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "CANCEL")]
        for name in ("UP", "DOWN", "LEFT", "RIGHT"):
            table.append(("j_" + name.lower(), JOY[name]))
        for name in "ABCDEF":
            table.append((name, FB[name]))
        for name in ("W", "S", "A", "D", "E", "Q", "F", "M", "P", "N", "T", "U", "V", "C", "SPACE",
                     "BACKSPACE",
                     "UP", "DOWN", "LEFT", "RIGHT"):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append(("k_" + name, key))
                if name in ("UP", "DOWN", "LEFT", "RIGHT"):
                    # the cursor keys count as the joystick too, so every menu,
                    # tab and chart that reads "j_up" ... takes them (Brian)
                    table.append(("j_" + name.lower(), key))
        # the views are Elite's f0 (front), f1 (rear), f2 (left), f3 (right), on the number
        # keys 1 to 4 as the keyboard plan has it (top row 1-0 are f0-f9)
        for n in range(4):
            key = KEYBOARD_BUTTONS.get(str(n + 1))
            if key is not None:
                table.append(("k_view%d" % n, key))
        # the rest of Elite's keys (Brian chose Elite's scheme, 2026-11-16): the
        # number row is f0-f9 ("k_1" ... "k_0"), H hyperspace (Ctrl+H the galactic
        # hyperdrive, as Elite), J the jump drive, + / - speed ("=" and "_" too,
        # the same keys without shift)
        for name in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "H", "J", "SHIFT", "CTRL",
                     "ESCAPE"):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append(("k_" + name, key))
        for name, control in (("+", "k_faster"), ("=", "k_faster"),
                              ("-", "k_slower"), ("_", "k_slower")):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append((control, key))
        self.table = table
        # the letters a keyboard types, for finding a system by name (build 88)
        self.letters = {}
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            key = KEYBOARD_BUTTONS.get(ch)
            if key is not None:
                self.letters[key] = ch
        key = KEYBOARD_BUTTONS.get("SPACE")
        if key is not None:
            self.letters[key] = " "
        # the keyboard's A-F, which off the flight are the badge's buttons
        # (controls.Controls.as_buttons)
        self.badge_keys = {}
        for ch, sysname in (("A", "up"), ("B", "right"), ("C", "confirm"),
                            ("D", "down"), ("E", "left"), ("F", "cancel")):
            key = KEYBOARD_BUTTONS.get(ch)
            if key is not None:
                self.badge_keys[key] = (ch, sysname)
        # and Enter and Esc are C and F there (Brian, build 102)
        for name, as_badge in (("ENTER", ("C", "confirm")), ("ESCAPE", ("F", "cancel"))):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                self.badge_keys[key] = as_badge
        self.names = {}      # button -> the control names it counts as
        eventbus.on(ButtonDownEvent, self._down, owner)
        eventbus.on(ButtonUpEvent, self._up, owner)

    def _names(self, button):
        names = self.names.get(button)
        if names is None:
            names = tuple(n for n, kind in self.table if kind in button)
            # keys the firmware's KEYBOARD_BUTTONS lacks, matched by name in case
            # a keyboard driver sends them anyway: Tab (Elite's energy bomb)
            if getattr(button, "name", None) in BY_NAME:
                names += (BY_NAME[button.name],)
            self.names[button] = names
        return names

    def _down(self, event):
        button = event.button
        if config.log_keys:
            print("KEY DOWN", repr(button))
        self.controls.press(button, self._names(button), self.letters.get(button),
                            self.badge_keys.get(button))

    def _up(self, event):
        button = event.button
        if config.log_keys:
            print("KEY UP", repr(button))
        self.controls.release(button)
