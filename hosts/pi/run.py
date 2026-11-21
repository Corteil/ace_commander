"""Ace Commander on a Raspberry Pi (or any computer with Python 3 and pygame).

    python3 hosts/pi/run.py                   as last time (first time: the badge's round screen)
    python3 hosts/pi/run.py --layout elite    a 3D view over an Elite-style dashboard
    python3 hosts/pi/run.py --full            full screen (--window: in a window)

F10 switches between the badge layout and the Elite one, F11 full screen, F12 saves
a screenshot (in ~/Pictures/Ace Commander); the window can be any size. The choice is kept in pi.json in the data folder.

Keys: arrows are the joystick, Enter confirms (the joystick pressed in), Esc
goes back, F1-F6 are the badge's buttons A-F (docked and on the title, the
letters A-F are too, but not while typing), and the rest of the keyboard is
the Keyboard Hexpansion (Elite's keys). A game controller flies with analogue
sticks and is the badge's buttons elsewhere (pad_pi.py). Docked, C buys and D sells. Close the window or choose QUIT on the
title screen to quit (Esc there does nothing). Saves and options.json go in
~/.local/share/ace_commander/; --debug shows the DEBUG menu of cheats.

The game itself is the badge app in the folder above, run unchanged on
the Pi's own platform (platform_pi.py: LEDs, no tilt, leaving); see hosts/README.md.
"""
import argparse
import importlib.util
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PKG = os.path.basename(REPO)            # the game's package: the repo folder, ace_commander
for p in (HERE, os.path.dirname(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame                       # noqa: E402

import platform_pi                  # noqa: E402
from ctx_pygame import Ctx          # noqa: E402
from controls_pi import Feed        # noqa: E402
from keys_pi import Keys            # noqa: E402
from pad_pi import Pads             # noqa: E402
import dash_pi                      # noqa: E402
from layout_pi import PiLayout      # noqa: E402

BACKGROUND = (24, 24, 30)           # round the screen, like the badge's case
LED_SIZE = 4                        # an LED's radius, in game pixels
FPS = 60
LINE_K = 0.5                        # the Elite layout's lines: half as thick as the scale
LOAD_HOLD = 3000                    # ms the loading screen shows (as the Tufty's hold)
# the hints' badge letters named as the keyboard's keys in flight, where it is Elite's
# keys, not the badge's buttons (Brian, build 126: "hints must use local buttons / keys
# names"): C is Enter, F is Esc, A (the pause menu) is P
KEY_LABELS_FLIGHT = {"A": "P", "C": "ENTER", "F": "ESC"}
WIRE_MIN = 3                        # ships are wireframes down to this size (badge units; the badge: 8)


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, "ace_commander")
    os.makedirs(d, exist_ok=True)
    return d


def load_game(d, debug=False):
    """Import the game (ace.py) with its files in data folder d: the save,
    options.json and debug.txt. The game reads where its files are and the
    host's switches from config.py as it loads (platform layer, step 1), so
    config is set first. The badge's files don't change. The DEBUG menu is on
    only with --debug, debug.txt in d, or the Easter egg (options.json's
    "debug"), as on the badge (on a PC the game would otherwise always show
    it); its PERF timing lines are printed only with the DEBUG menu. Esc on
    the title screen doesn't quit: its QUIT line does. Ships
    stay wireframes further out than on the badge (WIRE_MIN)."""
    want = debug or os.path.exists(os.path.join(d, "debug.txt"))
    try:
        with open(os.path.join(d, "options.json")) as f:
            want = want or bool(json.load(f).get("debug"))
    except (OSError, ValueError):
        pass
    full = PKG + ".ace"
    if full not in sys.modules:
        spec = importlib.util.find_spec(PKG)
        pkg = importlib.util.module_from_spec(spec)
        sys.modules[PKG] = pkg
        config = importlib.import_module(PKG + ".config")
        config.data_dir = d
        config.platform = platform_pi   # LEDs, tilt, text entry, leaving (platform layer, step 3)
        config.title_quit = True    # a computer needs a way out on the title screen (Brian)
        config.title_cancel = False # Esc on the title doesn't quit: QUIT does (Brian, 2026-11-21)
        config.laser_leds = False   # no laser colour on the drawn LED ring (Brian, build 113)
        config.debug_menu = want
        config.perf_log = 60 if want else 0     # the badge's timing lines, a line a second in flight
        config.wire_min = WIRE_MIN
        spec.loader.exec_module(pkg)
        return sys.modules[full]
    # loaded already (a second Host in one process, the tests): point it at d
    ace = sys.modules[full]
    config = sys.modules[PKG + ".config"]
    config.data_dir = d
    ace.SAVE_PATH = config.data(ace.SAVE_PATH.replace("\\", "/").rsplit("/", 1)[-1])
    ace.DEBUG_MENU = want
    ace.PERF_LOG = 60 if want else 0
    return ace


class Host:
    """The game in a pygame window: events in, update, draw, show.

    Two layouts, switched with F10 (and remembered in pi.json in the data folder):
    "badge", the badge's round screen in its case with the LED ring round it, and
    "elite", the whole window: a 3D view over an Elite-style dashboard in flight
    (dash_pi.py), the badge's screens in the middle elsewhere, no LEDs. F11: full
    screen. The window can be any size: everything scales to fit."""

    def __init__(self, scale=2, full=None, save_dir=None, debug=False, log_keys=False, layout=None):
        pygame.init()
        pygame.display.set_caption("Ace Commander")
        self.leds = platform_pi.LEDS    # the ring the game writes, drawn round the screen
        self.data = save_dir or data_dir()
        # the save, options.json and debug.txt under the user's data folder
        self.ace = load_game(self.data, debug)
        self.ck = sys.modules[PKG + ".cockpit"]
        self.gm = sys.modules[PKG + ".game"]
        prefs = self._prefs()
        self.full = prefs.get("full", False) if full is None else full
        self.layout = layout or prefs.get("layout") or ("elite" if self.full else "badge")
        self.win_scale = scale
        # flight laid out for the window (platform layer, step 4): the game asks it
        self.flight = PiLayout(self, self.ck)
        sys.modules[PKG + ".config"].layout = self.flight
        self._open_window()
        # the keyboard and pads send the game control names (platform layer, step 2):
        # the game hands its controls.Controls to the feed when it starts
        self.feed = Feed(log_keys)      # with --log-keys, every key down and up is printed
        sys.modules[PKG + ".config"].input = self.feed.attach
        self.keys = Keys(self.feed)
        self.pads = Pads(self.feed, lambda: self.app, log_keys)
        self.pad_last = False       # the pad was the last thing used
        self.log_keys = log_keys
        self.app = self.ace.AceCommander()
        self.app.platform.host = self       # its text entry asks whether the pad is in use
        self.clock = pygame.time.Clock()
        self.running = True
        self.frames = 0

    # ---- settings: the layout and full screen, kept between runs ------------------------
    def _prefs(self):
        try:
            with open(os.path.join(self.data, "pi.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def _save_prefs(self):
        try:
            with open(os.path.join(self.data, "pi.json"), "w") as f:
                json.dump({"layout": self.layout, "full": self.full}, f)
        except OSError:
            pass

    # ---- the window --------------------------------------------------------------------
    def _open_window(self):
        if self.full:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        elif self.layout == "elite":
            s = self.win_scale
            self.window = pygame.display.set_mode((384 * s, 240 * s), pygame.RESIZABLE)
        else:
            s = self.win_scale
            self.window = pygame.display.set_mode((272 * s,) * 2, pygame.RESIZABLE)
        pygame.mouse.set_visible(False)     # no pointer over the game (Brian)
        self._fit()

    def _fit(self):
        """Work the layout out for the window's size (after opening or resizing)."""
        w, h = self.window.get_size()
        # the Elite layout's screen is square, its corners show: hints on the charts and
        # the title screen (build 129); the badge layout's round screen hasn't room
        cfg = sys.modules.get(PKG + ".config")
        if cfg is not None:
            cfg.more_hints = self.layout == "elite"
        if self.layout == "elite":
            s = h / 240.0
            self.scale = s
            self.lw = w / s                         # the canvas: lw x 240
            self.dash_layout = dash_pi.Layout(self.lw)
            self.ctx = Ctx(self.window, s)
            self.ctx.line_k = max(1.0, s * LINE_K)
            self.screen = self.window
        else:
            s = min(w, h) / 272.0                   # the screen and its case, as the badge
            self.scale = s
            size = int(240 * s)
            self.screen_rect = pygame.Rect((w - size) // 2, (h - size) // 2, size, size)
            self.screen = pygame.Surface((size, size))
            self.ctx = Ctx(self.screen, s)
            self.mask = self._round_mask(size)
        self.flight.fit()

    def toggle_layout(self):
        self.layout = "badge" if self.layout == "elite" else "elite"
        self._save_prefs()
        if not self.full:
            self._open_window()     # each layout's own window shape
        else:
            self._fit()

    def toggle_full(self):
        self.full = not self.full
        self._save_prefs()
        self._open_window()

    @staticmethod
    def _round_mask(size):
        """The case's colour outside the round screen, see-through inside."""
        m = pygame.Surface((size, size), pygame.SRCALPHA)
        m.fill(BACKGROUND + (255,))
        pygame.draw.circle(m, (0, 0, 0, 0), (size // 2, size // 2), size // 2)
        return m

    # ---- the Elite layout's flight screen (layout_pi.PiLayout asks these) ----------------
    def _elite(self):
        return self.layout == "elite"

    def _at(self, ctx, y):
        """Put ctx's origin at the window's middle across, y canvas units down."""
        ctx.ox = self.window.get_width() / 2.0
        ctx.oy = y * self.scale

    def _clip(self, y0, h):
        s = self.scale
        self.window.set_clip(pygame.Rect(0, round(y0 * s), self.window.get_width(), round(h * s)))

    # ---- screenshots (F12) --------------------------------------------------------------
    def shots_dir(self):
        """~/Pictures/Ace Commander (made if need be), or the data folder's shots."""
        pics = os.path.join(os.path.expanduser("~"), "Pictures")
        d = os.path.join(pics, "Ace Commander") if os.path.isdir(pics) else os.path.join(self.data, "shots")
        os.makedirs(d, exist_ok=True)
        return d

    def screenshot(self):
        """Save the window as it was last drawn, as a PNG named by the date and time."""
        import time
        name = time.strftime("ace-commander-%Y%m%d-%H%M%S")
        path = os.path.join(self.shots_dir(), name + ".png")
        n = 1
        while os.path.exists(path):
            path = os.path.join(self.shots_dir(), "%s-%d.png" % (name, n))
            n += 1
        pygame.image.save(self.window, path)
        self.shot_t = 1.5
        self.last_shot = path
        return path

    def _shot_note(self, ms):
        """'SCREENSHOT SAVED' for a moment after F12 (not in the picture itself)."""
        if getattr(self, "shot_t", 0) <= 0:
            return
        self.shot_t -= ms / 1000.0
        f = pygame.font.Font(pygame.font.match_font("dejavusans") or None,
                             max(12, self.window.get_height() // 40))
        img = f.render("SCREENSHOT SAVED", True, (255, 220, 60))
        self.window.blit(img, (self.window.get_width() - img.get_width() - 12, 8))

    # ---- events and frames ----------------------------------------------------------------
    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
            self.keys.release_all()
            self.pads.release_all()
        elif event.type == pygame.VIDEORESIZE:
            self._fit()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F10:
            self.toggle_layout()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
            self.toggle_full()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
            self.screenshot()
        elif self.pads.handle(event):
            if event.type in (pygame.CONTROLLERBUTTONDOWN,) or (
                    event.type == pygame.CONTROLLERAXISMOTION and abs(event.value) > 16000):
                self.pad_last = True        # the hints name the pad's buttons
        else:
            if event.type == pygame.KEYDOWN:
                self.pad_last = False       # and the badge's again
            if self.log_keys and event.type in (pygame.KEYDOWN, pygame.KEYUP):
                print("PYGAME", "DOWN" if event.type == pygame.KEYDOWN else "UP",
                      pygame.key.name(event.key), repr(getattr(event, "unicode", "")),
                      "mod", event.mod, "->", self.keys.button(event),
                      "| mode", self.app.mode, getattr(self.app.dock, "name", lambda: "")()
                      if getattr(self.app, "dock", None) else "", flush=True)
            self.keys.handle(event)

    def step(self, ms):
        """One frame: the game's update, then its drawing, onto the window."""
        self.pads.tick(ms / 1000.0)
        self.app.update(ms)
        if self.app.platform.quit:
            self.running = False
            return
        if self.window.get_size() != getattr(self, "_size", None):
            self._size = self.window.get_size()
            self._fit()
        if self.pad_last:
            self.ctx.labels = self.pads.labels()
        elif self.app.mode == "flight":     # the keyboard in flight: Elite's keys (build 126)
            self.ctx.labels = KEY_LABELS_FLIGHT
        else:
            self.ctx.labels = None          # off the flight its A-F are the badge's buttons
        self._paint(self.app.draw)
        self.frames += 1

    def _paint(self, draw):
        """Draw a frame with draw(ctx) on the 240 canvas, framed for the layout:
        the middle of the window (Elite), or the round screen in its case."""
        if self._elite():
            self.window.set_clip(None)
            self.window.fill((0, 0, 0))
            self._at(self.ctx, 120)         # the badge's screens: in the middle
            draw(self.ctx)
            self.window.set_clip(None)
        else:
            self.screen.fill((0, 0, 0))
            draw(self.ctx)
            self.screen.blit(self.mask, (0, 0))
            self.window.fill(BACKGROUND)
            self.window.blit(self.screen, self.screen_rect)
            self._draw_leds()

    def loading(self, hold=LOAD_HOLD):
        """The loading screen the badge and the Tufty show, for hold ms (the Pi
        loads at once, so the bar fills over that time): the name, one of the
        game's own ships turning (letters.draw_ship) and LOADING (build 110).
        Any key or pad button skips it; closing the window quits."""
        try:
            L = importlib.import_module(PKG + ".letters")
            ship = L.load_ship(importlib.import_module(PKG + ".original_ships").SHIPS)
        except Exception:
            return
        t0 = pygame.time.get_ticks()

        def draw(ctx):
            t = (pygame.time.get_ticks() - t0) / 1000.0
            ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
            L.draw_name(ctx)
            if ship is not None:
                title = L.draw_ship(ctx, ship, t)
                _text(ctx, title, 0, L.SHIP_Y + L.SHIP_SIZE + 8, 10, (0.6, 0.6, 0.6))
            f = min(1.0, t * 1000.0 / hold)
            ctx.rgb(0.15, 0.3, 0.18).rectangle(-70, L.BAR_Y, 140, 8).fill()
            ctx.rgb(0.3, 1, 0.4).rectangle(-70, L.BAR_Y, 140 * f, 8).fill()
            _text(ctx, "LOADING", 0, 84, 13, (0.3, 1, 0.4))
        while self.running and pygame.time.get_ticks() - t0 < hold:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.CONTROLLERBUTTONDOWN):
                    return
            if self.window.get_size() != getattr(self, "_size", None):
                self._size = self.window.get_size()
                self._fit()
            self._paint(draw)
            self.show()
            self.clock.tick(FPS)

    def show(self, ms=0):
        """Put the frame on the screen (the screenshot note on top of it)."""
        self._shot_note(ms)
        pygame.display.flip()

    def _draw_leds(self):
        """The badge's ring of 12 LEDs round the screen, where the game puts
        them (its LED_ANGLE1 and LED_CLOCKWISE: jump flashes light the side
        the streaks leave by)."""
        cx, cy = self.screen_rect.center
        r = self.screen_rect.width / 2 + (LED_SIZE + 3) * self.scale
        step = -30.0 if self.ace.LED_CLOCKWISE else 30.0
        for i in range(1, 13):
            a = math.radians(self.ace.LED_ANGLE1 + (i - 1) * step)    # anticlockwise from 3 o'clock
            rgb = self.leds[i]
            col = rgb if any(rgb) else (40, 40, 48)
            pygame.draw.circle(self.window, col, (cx + r * math.cos(a), cy - r * math.sin(a)),
                               LED_SIZE * self.scale)

    def run(self, frames=None, loading=True):
        if loading and frames is None:
            self.loading()
        last = pygame.time.get_ticks()
        while self.running:
            for event in pygame.event.get():
                self.handle(event)
            now = pygame.time.get_ticks()
            ms = min(100, max(1, now - last))
            last = now
            self.step(ms)
            self.show(ms)
            self.clock.tick(FPS)
            if frames is not None and self.frames >= frames:
                break
        pygame.quit()


def _text(ctx, s, x, y, size, rgb):
    ctx.font_size = size
    ctx.text_align = ctx.CENTER
    ctx.text_baseline = ctx.MIDDLE
    ctx.rgb(*rgb).move_to(x, y).text(s)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ace Commander on a Raspberry Pi")
    ap.add_argument("--scale", type=int, default=2, help="the window's first size: the badge's screen times this")
    ap.add_argument("--full", action="store_true", default=None, help="full screen (F11 switches)")
    ap.add_argument("--window", dest="full", action="store_false", help="in a window")
    ap.add_argument("--layout", choices=("badge", "elite"), default=None,
                    help="badge: the round screen; elite: a 3D view over a dashboard (F10 switches)")
    ap.add_argument("--debug", action="store_true", help="the DEBUG menu of cheats")
    ap.add_argument("--log-keys", action="store_true", help="print every key and the button it becomes")
    ap.add_argument("--frames", type=int, default=None, help="stop after this many frames")
    args = ap.parse_args(argv)
    Host(args.scale, args.full, debug=args.debug, log_keys=args.log_keys,
         layout=args.layout).run(args.frames)


if __name__ == "__main__":
    main()

