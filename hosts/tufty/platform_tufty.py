"""The Tufty 2350's side of the platform layer (build 109), as platform_tildagon
is the badge's and hosts/pi/platform_pi the Pi's. host_tufty sets
config.platform to this module before the game is imported.

The game writes the badge's 12-LED ring into LEDS: layout_tufty paints it as
a border round the 3D view and host_tufty lights the Tufty's case lights by
how bright it is. No tilt sensor; text entry is dialog_tufty's letter picker
on the five buttons (build 122). The frame
loop is Badgeware's run(update) (host_tufty); leaving the game ends it.
"""

LEDS = [(0, 0, 0)] * 13     # LED 1 to 12 (0 unused), as the game writes them


def owner_name():
    """No badge settings here: the game uses Elite's JAMESON."""
    return None


class App:
    """The game's base class: nothing to do (the badge's is the firmware's app.App)."""

    def __init__(self):
        pass


class Platform:
    def __init__(self, app):
        self.app = app
        self.leds = True        # shown as the border round the view
        self.leds_on = False
        self.tilt_ok = False
        self.tx = self.ty = 0.0
        self.fast = False       # Badgeware runs the frames (host_tufty)
        self.quit = False       # the game asked to leave: update() ends run()
        self.dialog = None      # the text entry open (text_dialog), if any
        self.ck = None          # the game's cockpit module, for drawing it (host_tufty sets it)
        self.gamepad = None     # True / False with a Pad found (DEBUG > DISPLAY > GAMEPAD),
        self.host = None        # which host_tufty switches (set_gamepad)
        self.buzzer = None      # a Qwiic buzzer on the Qw/ST port (host_tufty, build 140)
        self.sound_ok = False

    def sound(self, name):
        self.buzzer.play(name)

    def sound_step(self):
        self.buzzer.step()

    def set_gamepad(self, on):
        if self.host is not None:
            self.host.set_gamepad(on)

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
        if self.leds_on:
            self.leds_on = False
            for i in range(1, 13):
                LEDS[i] = (0, 0, 0)

    def tilt(self):
        return False

    def keyboard_fitted(self):
        return False

    def text_dialog(self, title):
        """The Tufty's letter picker (dialog_tufty), which host_tufty gives the
        buttons while it is open."""
        from dialog_tufty import LetterDialog
        self.dialog = LetterDialog(title, self.ck)
        return self.dialog

    async def run(self, render_update):
        raise RuntimeError("on the Tufty, Badgeware runs the frames (host_tufty)")

    def minimise(self):
        self.quit = True
