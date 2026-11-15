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

import app

# in the order they are imported: each after the ones it needs
STEPS = ("ship_data", "game_data", "commander", "galaxy", "market", "equipment", "game",
         "cockpit", "chart", "title", "viewer", "bench", "docked", "ace")
OPTIONAL = ("ship_data", "game_data")   # made from your own copy of Elite: may be missing
GREEN = (0.3, 1, 0.4)
GREY = (0.6, 0.6, 0.6)
DIM = (0.15, 0.3, 0.18)


class AceCommander(app.App):
    def __init__(self):
        super().__init__()
        self.real = None        # the real app, once everything is loaded
        self.done = 0           # modules loaded so far
        self.error = None       # why loading failed, if it did

    async def run(self, render_update):
        pkg = __name__.rsplit(".", 1)[0]
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
        self.real = sys.modules[pkg + ".ace"].AceCommander(self)
        await self.real.run(render_update)

    def draw(self, ctx):
        if self.real is not None:
            self.real.draw(ctx)
            return
        ctx.save()
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        _text(ctx, "ACE", 0, -38, 30, GREEN)
        _text(ctx, "COMMANDER", 0, -10, 22, GREEN)
        n = len(STEPS)
        ctx.rgb(*DIM).rectangle(-70, 18, 140, 8).fill()
        ctx.rgb(*GREEN).rectangle(-70, 18, 140 * self.done // n, 8).fill()
        if self.error:
            _text(ctx, "LOAD FAILED", 0, 44, 14, (1, 0.3, 0.2))
            _text(ctx, self.error[:28], 0, 62, 10, GREY)
        else:
            _text(ctx, "LOADING", 0, 44, 13, GREY)
            if self.done < n:
                _text(ctx, STEPS[self.done], 0, 62, 10, GREY)
        ctx.restore()


def _text(ctx, s, x, y, size, rgb):
    ctx.font_size = size
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


__app_export__ = AceCommander
