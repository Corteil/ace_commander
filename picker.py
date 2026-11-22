"""A letter picker for text entry without a keyboard (builds 122-124): the
Galactic chart's search and the commander's name. It has the interface the game
reads from the badge's firmware TextDialog: .text, .message (the game sets it,
e.g. the best match), ._result (None while open, the text when done, False if
cancelled) and draw(ctx). Imports the game's cockpit only to draw.

    letter up / down   the letter at the cursor: through LETTERS (held, it repeats)
    keep               the cursor moves right to the next place (the same letter
                       there to start from)
    back               the cursor moves left onto the last letter, to change it
    done

Drawn as a row of MAX_LEN places (Brian: "select letter, cursor moves right when
selected"): the letters kept, the cursor's place highlighted, the empty places dim.
press(name) takes the Tufty's button names: "UP" / "DOWN" the letter, "B" keep,
"C" back, "A" done. Who gives it them: the Tufty's host (its buttons and Pad,
hosts/tufty/dialog_tufty), or the game itself on the badge (an Options choice)
and on the Pi with its pad (ace._drive_picker: joystick up / down the letter,
C or right keep, left back, A done, F cancel).
"""

LETTERS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
MAX_LEN = 16
SLOT = 12               # pixels a place is wide
REPEAT_WAIT = 400       # ms UP / DOWN are held before they repeat
REPEAT_EVERY = 110      # then a letter every this many ms


class LetterPicker:
    def __init__(self, title, ck=None, driven=False):
        self.message = title
        self.text = ""
        self.masked = False
        self._result = None
        if ck is None:
            from . import cockpit as ck
        self.ck = ck            # the game's cockpit module (its text and colours)
        # driven: the game reads its buttons (ace._drive_picker: the badge, the Pi's pad);
        # otherwise the host gives it them (press / hold / let_go: the Tufty)
        self.driven = driven
        self.hints = None       # (line, line) to show instead of the usual (a host's: the
                                # Tufty's Pad or buttons, whichever was used last)
        self.i = 1              # LETTERS[1]: A
        self.held_ms = 0        # how long UP or DOWN has been held
        self.next_ms = 0        # when it next repeats

    def press(self, name):
        """A button going down: "UP", "DOWN", "A", "B" or "C"."""
        if self._result is not None:
            return
        if name == "UP":
            self.i = (self.i + 1) % len(LETTERS)
        elif name == "DOWN":
            self.i = (self.i - 1) % len(LETTERS)
        elif name == "B":
            if len(self.text) < MAX_LEN:
                self.text = self.text.upper() + LETTERS[self.i]
        elif name == "C":
            t = self.text.upper()
            if t:           # back onto the last letter, to change it
                self.i = LETTERS.find(t[-1]) if LETTERS.find(t[-1]) >= 0 else self.i
                self.text = t[:-1]
        elif name == "A":
            self._result = self.text.upper()

    def hold(self, name, ms):
        """UP or DOWN still held for another ms: repeat after REPEAT_WAIT."""
        self.held_ms += ms
        if self.held_ms >= REPEAT_WAIT and self.held_ms >= self.next_ms:
            self.next_ms = self.held_ms + REPEAT_EVERY
            self.press(name)

    def let_go(self):
        self.held_ms = 0
        self.next_ms = REPEAT_WAIT

    def draw(self, ctx):
        ck = self.ck
        text = ck.text
        ctx.save()
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()     # solid: easier to read
        text(ctx, self.message, 0, -40, 14, ck.GREEN)
        shown = self.text.upper()
        x0 = -SLOT * MAX_LEN // 2
        for k in range(MAX_LEN):       # the places: letters kept, the cursor, the rest
            x = x0 + k * SLOT
            if k < len(shown):
                text(ctx, shown[k], x + SLOT // 2, 0, 16, ck.WHITE)
            elif k == len(shown):
                letter = LETTERS[self.i]
                ctx.rgb(*ck.CYAN).rectangle(x, -10, SLOT - 1, 20).fill()
                text(ctx, "_" if letter == " " else letter, x + SLOT // 2, 0, 16, (0, 0, 0))
            else:
                ctx.rgb(*ck.DIM).rectangle(x + 2, 8, SLOT - 4, 2).fill()
        if self.hints:      # the host's (the Tufty: its Pad or its buttons)
            text(ctx, self.hints[0], 0, 36, 11, ck.GREY)
            text(ctx, self.hints[1], 0, 52, 11, ck.GREY)
        elif self.driven:   # the badge's buttons (ace._drive_picker)
            # (with colons, so a host's labels name its own buttons: the Pi's pad)
            text(ctx, "UP/DOWN letter   C: next", 0, 36, 11, ck.GREY)
            text(ctx, "LEFT back   A: done   F: cancel", 0, 52, 11, ck.GREY)
        else:               # the Tufty's
            text(ctx, "UP/DOWN letter   B next", 0, 36, 11, ck.GREY)
            text(ctx, "C back   A done", 0, 52, 11, ck.GREY)
        ctx.restore()

    def cancel(self):
        if self._result is None:
            self._result = False
