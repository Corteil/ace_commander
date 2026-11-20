"""Which controls are down, by name (platform layer, step 2).

The game asks this, never the firmware: held("j_up"), hit("confirm"),
typed letters. A platform feeds it: on the badge platform_tildagon.Input
matches the firmware's button events to names; another device (hosts/)
sends the names itself. Imports nothing, so it runs anywhere.

Controls are named: "up" / "confirm" / ... for any button of that kind,
"j_up" ... for the joystick only, "A" to "F" for the lettered buttons and
"k_W" ... for keyboard keys ("k_view0" to "k_view3" the number keys 1-4,
"k_faster" / "k_slower" + and -).
"""


class Controls:
    """Kept up to date by press() and release(); answers from a dictionary
    and a set, so asking about twenty things a frame costs little."""

    def __init__(self):
        # off the flight the keyboard's A-F are the badge's buttons (Brian,
        # 2026-11-19: "the letter keys act the same as the badge keys, apart
        # when entering text", "the same everywhere"): a key pressed with
        # badge=(letter, direction) counts as that lettered button and its
        # system direction, as the badge's own do (A up, B right, C confirm,
        # D down, E left, F cancel), instead of as a keyboard key.
        # AceCommander sets as_buttons each frame.
        self.as_buttons = False
        self.down_names = {}    # key -> the names it went down as (for its release)
        self.typed = ""         # letters typed since the last end_frame()
        self.keyboard = False   # a keyboard key has been pressed (see AceCommander._keyboard)
        self.count = {}         # control name -> how many keys hold it down
        self.hits = set()       # control names pressed since the last end_frame()

    def press(self, key, names, ch=None, badge=None):
        """key went down: any hashable that stands for one physical key or
        button (its release must give the same), counting as the control
        names in names. ch: the letter it types, if any. badge: (letter,
        direction) if it is one of the keyboard's A-F."""
        if key in self.down_names:
            return      # already down (key repeat)
        count = self.count
        # Shift or Ctrl held at the moment this went down: the Keyboard
        # Hexpansion sends Shift down, H down, Shift up, H up within one frame,
        # so asking held("k_SHIFT") on the next update is too late (Brian's
        # badge log, build 64). hit("mod+k_H") is a shifted H.
        mod = (count.get("k_SHIFT", 0) > 0 or count.get("k_CTRL", 0) > 0
               or count.get("k_LSHIFT", 0) > 0 or count.get("k_RSHIFT", 0) > 0)
        if self.as_buttons and badge is not None:
            names = badge       # the badge's button, not the key
            self.keyboard = True
        self.down_names[key] = names
        for n in names:
            count[n] = count.get(n, 0) + 1
            self.hits.add(n)
            if mod:
                self.hits.add("mod+" + n)
            if n[:2] == "k_":
                self.keyboard = True
        if ch is not None:
            self.typed += ch
            self.keyboard = True

    def release(self, key):
        names = self.down_names.pop(key, None)
        if names is None:
            return
        count = self.count
        for n in names:
            if count.get(n, 0) > 0:
                count[n] -= 1

    def held(self, name):
        return self.count.get(name, 0) > 0

    def hit(self, name):
        """True if the control was pressed since the last frame."""
        return name in self.hits

    def end_frame(self):
        if self.hits:
            self.hits = set()
        if self.typed:
            self.typed = ""

    def clear(self):
        self.count = {}
        self.hits = set()
        self.down_names = {}
