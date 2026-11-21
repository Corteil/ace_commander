"""The Pi's side of the platform layer (step 3, build 103): what the game asks
of the device it runs on, as platform_tildagon.py gives it on the badge. run.py
sets config.platform to this module before the game is imported, so the game
imports none of the badge's firmware and needs no stand-ins for it.

The Pi has an LED ring drawn round the badge's screen (run.py reads LEDS), no
tilt sensor, no firmware text entry (with a keyboard the game uses its own
typing pages) and its own frame loop (run.py's Host.run).
"""

# the ring the game writes, LED 1 to 12 (0 unused), which run.py draws
LEDS = [(0, 0, 0)] * 13


def owner_name():
    """No badge settings here: the game uses Elite's JAMESON."""
    return None


class App:
    """The game's base class: nothing to do on the Pi (the badge's is the
    firmware's app.App)."""

    def __init__(self):
        pass


class Platform:
    def __init__(self, app):
        self.app = app
        self.leds = True        # drawn round the screen in the badge layout
        self.leds_on = False    # the game has written to them since it last let go
        self.tilt_ok = False
        self.fast = False       # run.py runs the frames itself
        self.quit = False       # the game asked to leave: run.py ends

    def leds_rgb(self, r, g, b):
        self.leds_on = True
        rgb = (r, g, b)
        for i in range(1, 13):
            LEDS[i] = rgb

    def leds_each(self, values, rgb):
        self.leds_on = True
        r, g, b = rgb
        for i in range(1, 13):
            v = int(values[i])
            LEDS[i] = (r * v // 255, g * v // 255, b * v // 255)

    def leds_release(self):
        """The badge shows its own pattern again; here the ring goes dark."""
        if self.leds_on:
            self.leds_on = False
            for i in range(1, 13):
                LEDS[i] = (0, 0, 0)

    def tilt(self):
        return False

    def keyboard_fitted(self):
        return False

    def text_dialog(self, title):
        return None

    async def run(self, render_update):
        raise RuntimeError("on the Pi, run.py runs the frames (Host.run)")

    def minimise(self):
        self.quit = True        # leaving the game ends the Pi program
