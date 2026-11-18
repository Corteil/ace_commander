"""Finding a system on the Galactic chart by name (Brian, build 88), as
Elite's "Planet Name?" on the chart. Typed on a keyboard here, with the
best match offered to complete and a short list of the others; with no
keyboard the badge's own text entry (the firmware's TextDialog) is used
instead, by ace.py, with the best match shown above what is typed.

Names match from their start, ignoring case; past those, names that hold
the text elsewhere. Imported the first time a search is opened.
"""
from . import cockpit

SHOWN = 4       # matches listed under the one picked


class Names:
    """The galaxy's system names, worked out once."""

    def __init__(self, gal):
        self.names = [gal.system(i).name for i in range(len(gal.xs))]

    def matches(self, text):
        """System numbers whose names fit text: those starting with it,
        alphabetically, then those holding it elsewhere. None for no text."""
        t = text.strip().upper()
        if not t:
            return []
        start = []
        inside = []
        for i, n in enumerate(self.names):
            if n.startswith(t):
                start.append(i)
            elif t in n:
                inside.append(i)
        key = lambda i: self.names[i]
        start.sort(key=key)
        inside.sort(key=key)
        return start + inside


class Find:
    """The keyboard's find page: what is typed, its matches, the one picked."""

    def __init__(self, gal, names=None):
        self.names = names or Names(gal)
        self.text = ""
        self.found = []     # system numbers matching text
        self.sel = 0        # the one picked among them

    def type(self, ch):
        if len(self.text) < 12:
            self.text += ch
            self._match()

    def back(self):
        """Backspace."""
        self.text = self.text[:-1]
        self._match()

    def _match(self):
        self.found = self.names.matches(self.text)
        self.sel = 0

    def pick(self, step):
        if self.found:
            self.sel = (self.sel + step) % len(self.found)

    def chosen(self):
        """The system picked, or None."""
        return self.found[self.sel] if self.found else None

    def draw(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "FIND SYSTEM", 0, -92, 12, cockpit.GREY)
        # what is typed, then the rest of the picked name (the suggestion) dimmer
        best = self.names.names[self.chosen()] if self.found else ""
        typed = self.text.upper()
        rest = best[len(typed):] if best.startswith(typed) else ""
        w = 9 * (len(typed) + len(rest))        # about 9 px a letter at size 16
        x = -w // 2
        ctx.rgb(*cockpit.DIM).rectangle(-90, -71, 180, 22).fill()
        text(ctx, typed, x, -60, 16, cockpit.WHITE, -1)
        if rest:
            text(ctx, rest, x + 9 * len(typed), -60, 16, cockpit.GREY, -1)
        else:
            ctx.rgb(*cockpit.GREEN).rectangle(x + 9 * len(typed) + 1, -68, 2, 15).fill()
        if self.text and not self.found:
            text(ctx, "no system by that name", 0, -20, 11, cockpit.RED)
        top = max(0, min(self.sel - 1, len(self.found) - SHOWN))
        for row in range(min(SHOWN, len(self.found))):
            k = top + row
            y = -30 + row * 18
            if k == self.sel:
                ctx.rgb(*cockpit.DIM).rectangle(-80, y - 8, 160, 16).fill()
            text(ctx, self.names.names[self.found[k]], 0, y, 13,
                 cockpit.GREEN if k == self.sel else cockpit.GREY)
        if len(self.found) > SHOWN:
            text(ctx, "%d of %d" % (self.sel + 1, len(self.found)), 0, 46, 10, cockpit.GREY)
        text(ctx, "type a name   up / down: pick", 0, 64, 11, cockpit.GREY)
        text(ctx, "Enter: go there   Esc: back", 0, 80, 11, cockpit.GREY)


NAME_MAX = 12       # "COMMANDER " and the name fit Status's title


class NameEntry:
    """The keyboard's page for the commander's name (Brian, build 89): what
    is typed, with the suggestion (the badge's name, or Elite's JAMESON)
    greyed after it; Tab fills it in, Enter takes it (an empty name: the
    suggestion), Esc goes back."""

    def __init__(self, suggestion, text=""):
        self.suggestion = suggestion.upper()[:NAME_MAX]
        self.text = text.upper()[:NAME_MAX]

    def type(self, ch):
        if len(self.text) < NAME_MAX and (ch != " " or self.text):
            self.text += ch

    def back(self):
        self.text = self.text[:-1]

    def fill(self):
        """Tab: the suggestion."""
        self.text = self.suggestion

    def result(self):
        return self.text.strip() or self.suggestion

    def draw(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "COMMANDER NAME", 0, -70, 14, cockpit.WHITE)
        typed = self.text
        rest = self.suggestion[len(typed):] if self.suggestion.startswith(typed) else ""
        w = 10 * (len(typed) + len(rest))       # about 10 px a letter at size 18
        x = -w // 2
        ctx.rgb(*cockpit.DIM).rectangle(-100, -42, 200, 26).fill()
        text(ctx, typed, x, -29, 18, cockpit.WHITE, -1)
        cx = x + 10 * len(typed)
        if rest:
            text(ctx, rest, cx, -29, 18, cockpit.GREY, -1)
        ctx.rgb(*cockpit.GREEN).rectangle(cx + 1, -38, 2, 18).fill()
        if rest:
            text(ctx, "Tab: " + self.suggestion, 0, 6, 12, cockpit.GREY)
        text(ctx, "type a name   Backspace: delete", 0, 40, 11, cockpit.GREY)
        text(ctx, "Enter: done   Esc: back", 0, 56, 11, cockpit.GREY)
