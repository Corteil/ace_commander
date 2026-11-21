"""The Tufty's buttons and a Qw/ST Pad, as the control names the game reads
(controls.py; platform layer, step 2), the way hosts/pi/controls_pi.py does
the Pi's keys. Imports nothing.

Each button stands for one of the badge's: its lettered buttons A-F (each also
a system direction: A up, B right, C confirm, D down, E left, F cancel) or its
joystick. The game's controls (DESIGN.md): joystick = pitch / roll and list
moves; C lasers / select / buy; D missile; E / F slow / speed up (F also back);
A menu / launch; B bomb / sell. Edit the maps freely.
"""

# the badge's lettered buttons: each a button and a system direction at once
_DIRECTION = {"A": "up", "B": "right", "C": "confirm", "D": "down", "E": "left", "F": "cancel"}


class Key:
    """One button: its name (for logs and tests) and the control names it is."""

    def __init__(self, name, names):
        self.name = name
        self.names = tuple(names)

    def __repr__(self):
        return "Tufty." + self.name


BADGE = {c: Key(c, (_DIRECTION[c], c)) for c in "ABCDEF"}
STICK = {n: Key("JOY" + n, (n.lower(), "j_" + n.lower())) for n in ("UP", "DOWN", "LEFT", "RIGHT")}
STICK["SELECT"] = Key("JOYSELECT", ("confirm",))
# the Tufty's five buttons, with or without the Pad (Brian, builds 111-112): A / C /
# UP / DOWN are the joystick, cursor keys off the flight (A left, C right) and the
# steering in flight; B is the badge's C, select off the flight and fire in flight.
# Without the Pad only combat practice is offered (config.practice_only), missiles go
# by themselves (config.auto_missiles) and the hints name these buttons (LABELS)
TUFTY = {"A": STICK["LEFT"], "C": STICK["RIGHT"], "UP": STICK["UP"], "DOWN": STICK["DOWN"],
         "B": BADGE["C"]}
# A + C held together (Brian, builds 114-119), for the badge's buttons the five haven't
# got alone: in flight it toggles UP and DOWN between pitch and speed (SPEED: UP its F,
# faster, and DOWN its E, slower), staying so once let go; off the flight its F (back).
# A or C held alone waits PAIR_WAIT ms for the other before it counts, so starting
# A + C doesn't roll or move the cursor first
SHIFT = ("A", "C")
SHIFTED = {"UP": BADGE["F"], "DOWN": BADGE["E"]}    # in flight, in speed mode
BACK = BADGE["F"]                                   # off the flight, A + C
# UP + DOWN held together in flight (Brian, build 120): the badge's A, the pause menu
# (open, and close again from inside it); UP or DOWN alone waits PAIR_WAIT ms there too
MENU_PAIR = ("UP", "DOWN")
MENU = BADGE["A"]
PAIR_WAIT = 60
# the hints' badge letters named as the Tufty's buttons (ctx_tufty), Pad or not
LABELS = {"C": "B"}         # (in flight A + C switches UP / DOWN: the game says which)
LABELS_OFF = {"C": "B", "F": "A+C"}
# and each Qw/ST Pad button (qwstpad's names): the D-pad is the joystick
PAD_MAP = {"U": STICK["UP"], "D": STICK["DOWN"], "L": STICK["LEFT"], "R": STICK["RIGHT"],
           "A": BADGE["C"], "B": BADGE["D"], "X": BADGE["F"], "Y": BADGE["E"],
           "+": BADGE["A"], "-": BADGE["B"]}


class Feed:
    """Buttons down and up, to the game's controls.Controls. Set as
    config.input: the game hands over its Controls when it starts (attach)."""

    def __init__(self):
        self.controls = None
        self.down = set()

    def attach(self, controls, owner=None):
        self.controls = controls

    def set_held(self, keys):
        """keys: the set of Keys held now. Sends the game what changed."""
        c = self.controls
        if c is None:
            return
        for k in self.down - keys:
            c.release(k)
        for k in keys - self.down:
            c.press(k, k.names)
        self.down = keys
