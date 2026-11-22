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


def _drop_stale_source():
    """Remove every x.py that has an x.mpy beside it (build 132). A release
    since 0.4.0 is compiled, and the app store's update writes the new files
    over the old folder without deleting anything: 0.3.2's game.py etc. would
    stay, and MicroPython imports x.py before x.mpy, so the old code would run.
    This file and __init__.py stay source and are never compiled."""
    import os
    here = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
    try:
        names = os.listdir(here)
    except OSError:
        return
    for n in names:
        if n.endswith(".mpy") and n[:-4] + ".py" in names:
            try:
                os.remove(here + "/" + n[:-4] + ".py")
                print("removed old " + n[:-4] + ".py (" + n + " replaces it)")
            except OSError:
                pass


if sys.implementation.name == "micropython":
    _drop_stale_source()

# in the order they are imported: each after the ones it needs
STEPS = ("ship_data", "game_data", "config", "layout", "content", "commander", "galaxy", "market", "ships", "equipment", "rules", "game",
         "cockpit", "chart", "find", "screens", "title", "viewer", "describe", "missions", "briefing",
         "docked", "controls", "platform_tildagon", "ace")
OPTIONAL = ("ship_data", "game_data")   # made from your own copy of Elite: may be missing
GREEN = (0.3, 1, 0.4)      # the title screen's menu line
GREY = (0.6, 0.6, 0.6)
DIM = (0.15, 0.3, 0.18)
_letters = None             # letters.py, the name in block letters: loaded first


class AceCommander(app.App):
    def __init__(self):
        super().__init__()
        self.real = None        # the real app, once everything is loaded
        self.done = 0           # modules loaded so far
        self.error = None       # why loading failed, if it did
        self.ship = None        # the ship shown turning (letters.draw_ship), if there
        self.t0 = time.ticks_ms() if hasattr(time, "ticks_ms") else 0

    async def run(self, render_update):
        global _letters
        pkg = __name__.rsplit(".", 1)[0]
        try:        # tiny: the name as the title screen draws it, from the first frame
            _letters = __import__(pkg + ".letters", None, None, ["draw_name"])
        except Exception:
            pass
        try:        # one of the game's own ships to show turning (build 110)
            ships = __import__(pkg + ".original_ships", None, None, ["SHIPS"])
            self.ship = _letters.load_ship(ships.SHIPS)
        except Exception:
            self.ship = None    # a build without them (build_mpy --elite-only)
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
        # the name where the title screen has it, in its colours, so the
        # hand-over to the title screen doesn't jump
        if _letters is not None:
            _letters.draw_name(ctx)
        else:
            _text(ctx, "ACE", 0, -96, 28, (1, 0.85, 0.2))
            _text(ctx, "COMMANDER", 0, -69, 16, (1, 1, 1))
        bar = 4
        if self.ship is not None and _letters is not None:
            t = time.ticks_diff(time.ticks_ms(), self.t0) / 1000.0 if hasattr(time, "ticks_ms") else 0.0
            title = _letters.draw_ship(ctx, self.ship, t)
            _text(ctx, title, 0, _letters.SHIP_Y + _letters.SHIP_SIZE + 8, 10, GREY)
            bar = _letters.BAR_Y
        n = len(STEPS)
        ctx.rgb(*DIM).rectangle(-70, bar, 140, 8).fill()
        ctx.rgb(*GREEN).rectangle(-70, bar, 140 * self.done // n, 8).fill()
        if self.error:
            _text(ctx, "LOAD FAILED", 0, 60, 14, (1, 0.3, 0.2))
            _text(ctx, self.error[:28], 0, 84, 10, GREY)
        else:
            if self.done < n:
                _text(ctx, STEPS[self.done], 0, bar + 24, 10, GREY)
            _text(ctx, "LOADING", 0, 84, 13, GREEN)     # where the menu line will be
        ctx.restore()


def _text(ctx, s, x, y, size, rgb):
    ctx.font_size = size
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


__app_export__ = AceCommander
