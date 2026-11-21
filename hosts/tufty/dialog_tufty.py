"""Text entry on the Tufty's five buttons (Brian, build 122): what the game asks
the platform for (platform_tufty.text_dialog) where the badge uses its
firmware's TextDialog, for the Galactic chart's search and the commander's name.
The same interface the game reads: .text, .message (the game sets it, e.g. the
best match), ._result (None while open, the text when done) and draw(ctx).

    UP / DOWN   the letter after the text: forward / back through LETTERS
                (held, they repeat)
    B           add it          C   delete the last letter      A   done

host_tufty gives it the buttons while it is open (press), and the game draws it.
"""

LETTERS = " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
MAX_LEN = 16
REPEAT_WAIT = 400       # ms UP / DOWN are held before they repeat
REPEAT_EVERY = 110      # then a letter every this many ms


class LetterDialog:
    def __init__(self, title, ck):
        self.message = title
        self.text = ""
        self.masked = False
        self._result = None
        self.ck = ck            # the game's cockpit module (its text and colours)
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
            self.text = self.text[:-1]
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
        letter = LETTERS[self.i]
        ctx.rgb(*ck.DIM).rectangle(-100, -12, 200, 24).fill()
        text(ctx, shown, -4, 0, 18, ck.WHITE, 1)          # the text, ending at the middle
        ctx.rgb(*ck.CYAN).rectangle(0, -10, 14, 20).fill()
        text(ctx, "_" if letter == " " else letter, 7, 0, 18, (0, 0, 0))   # the letter to add
        text(ctx, "UP/DOWN letter   B add", 0, 36, 11, ck.GREY)
        text(ctx, "C delete   A done", 0, 52, 11, ck.GREY)
        ctx.restore()
