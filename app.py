"""The app's entry point on the badge: a loading screen. (The badge's launcher
imports this folder's app.py and starts its __app_export__, so this file must
be called app.py; the real app is in ace.py.)

MicroPython compiles every module from source the first time it is
imported, and this app's are big (game.py alone takes over a second), so
starting it used to show nothing for about ten seconds. This module is tiny
and imports nothing of the game's: the badge shows its screen at once while
run() imports the rest one module at a time, drawing a progress bar between
them, then hands everything over to the real app (ace.AceCommander), which
it hosts: the scheduler only knows this object, so the real app sends its
button handlers, foreground checks and minimise through it.
"""
import gc
import sys
import time

import app

# in the order they are imported: each after the ones it needs
STEPS = ("ship_data", "game_data", "content", "commander", "galaxy", "market", "equipment", "game",
         "cockpit", "chart", "title", "viewer", "bench", "describe", "missions", "briefing",
         "docked", "ace")
OPTIONAL = ("ship_data", "game_data")   # made from your own copy of Elite: may be missing
GREEN = (0.3, 1, 0.4)      # the title screen's menu line
GREY = (0.6, 0.6, 0.6)
DIM = (0.15, 0.3, 0.18)
_letters = None             # letters.py, the name in block letters: loaded first
FLASH_MS = 500              # LOADING is on this long, then off this long, by the clock
WAIT_MS = 200               # after a quick import, wait up to this long to redraw on the change


def _now():
    """Milliseconds, on the badge and on a PC."""
    try:
        return time.ticks_ms()
    except AttributeError:
        return int(time.time() * 1000)


class AceCommander(app.App):
    def __init__(self):
        super().__init__()
        self.real = None        # the real app, once everything is loaded
        self.done = 0           # modules loaded so far
        self.error = None       # why loading failed, if it did
        self.t0 = _now()        # LOADING flashes by the clock from here

    async def run(self, render_update):
        global _letters
        pkg = __name__.rsplit(".", 1)[0]
        try:        # tiny: the name as the title screen draws it, from the first frame
            _letters = __import__(pkg + ".letters", None, None, ["draw_name"])
        except Exception:
            pass
        for name in STEPS:
            await render_update()           # show how far it has got
            try:
                __import__(pkg + "." + name)
            except Exception as e:
                if name not in OPTIONAL:
                    self.error = "%s: %s" % (name, e)
                    await render_update()
                    raise
            self.done += 1
            gc.collect()
            # the screen can only change between imports: after a quick one,
            # wait for a flash change that is nearly due, so it lands on time
            while self._until_change() <= WAIT_MS:
                await render_update()
                if self._until_change() > WAIT_MS:
                    break
        self.real = sys.modules[pkg + ".ace"].AceCommander(self)
        await self.real.run(render_update)

    def _shown(self):
        """LOADING's flash, by the clock: on for FLASH_MS, off for FLASH_MS."""
        return (_elapsed(self.t0) // FLASH_MS) % 2 == 0

    def _until_change(self):
        """Milliseconds until the flash next changes."""
        return FLASH_MS - _elapsed(self.t0) % FLASH_MS

    def draw(self, ctx):
        if self.real is not None:
            self.real.draw(ctx)
            return
        ctx.save()
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        # the name where the title screen has it, in its colours, so the
        # hand-over to the title screen doesn't jump
        if _letters is not None:
            _letters.draw_name(ctx)
        else:
            _text(ctx, "ACE", 0, -96, 28, (1, 0.85, 0.2))
            _text(ctx, "COMMANDER", 0, -69, 16, (1, 1, 1))
        n = len(STEPS)
        ctx.rgb(*DIM).rectangle(-70, 4, 140, 8).fill()
        ctx.rgb(*GREEN).rectangle(-70, 4, 140 * self.done // n, 8).fill()
        if self.error:
            _text(ctx, "LOAD FAILED", 0, 60, 14, (1, 0.3, 0.2))
            _text(ctx, self.error[:28], 0, 84, 10, GREY)
        else:
            if self.done < n:
                _text(ctx, STEPS[self.done], 0, 28, 10, GREY)
            if self._shown():   # flashing, where the menu line will be
                _text(ctx, "LOADING", 0, 84, 13, GREEN)
        ctx.restore()


def _elapsed(t0):
    try:
        return time.ticks_diff(_now(), t0)
    except AttributeError:
        return _now() - t0


def _text(ctx, s, x, y, size, rgb):
    ctx.font_size = size
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


__app_export__ = AceCommander
