"""Ace Commander on the M5 CardputerZero (CM0, 320 x 170 LCD, built-in keyboard).

    python3 hosts/cardputerzero/run_cz.py            on the LCD (KMSDRM, /dev/dri/card1)
    python3 hosts/cardputerzero/run_cz.py --perf     and a FPS / RSS / CPU line a second

The Pi host (hosts/pi/run.py) unchanged underneath, set up for this device
(Phase 1, notes/cardputerzero_phase0.md):

- The screen: KMSDRM on card1 when there is no desktop to draw on (labwc's only
  output is headless), the Elite layout full screen, text TEXT_K times bigger
  (the 240 canvas is drawn at 170 / 240 = 0.71). Whole-frame screens (off the
  flight, and the in-flight screens) are fitted to the LCD (hosts/pi/fit_pygame.py, the Pi's --wide): their
  hints in one row along the bottom, the rest spread over the width and height.
- List menus (pause, Settings, Options, DEBUG, the lobby) show fewer lines,
  MENU_K times further apart, and scroll (config.menu_k).
- Fonts by fixed path (DejaVu Sans Condensed Bold): pygame's font lookup runs
  fc-list, which times out here and holds up the first frame by seconds.
- Keys: Fn + ; . , / are the arrows. On menus and screens (not flying, not
  typing) W / A / S / D are the arrows too; the badge buttons they hide move to
  Q (A: launch, done), Z (C, as C and Enter are) and X (D: sell, data). The hints
  name those keys.
- Stopping from a shell: `touch ~/.cache/ace_commander/stop`, or SIGTERM; both
  end it cleanly. As a launcher app (install.sh), holding Esc ends it too.

Saves are the Pi's: ~/.local/share/ace_commander/.
"""
import os
import resource
import signal
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PI = os.path.join(os.path.dirname(HERE), "pi")
if PI not in sys.path:
    sys.path.insert(0, PI)

SIZE = (320, 170)
TEXT_K = 1.6            # text 1.6 times the Pi's size for the canvas's scale (Brian: "C")
BADGE_TEXT_K = 1.0      # in the badge layout (F10): the round screen is only ~150 px across, so
                        # the badge's own proportions (Brian: messages didn't fit at 1.6)
MENU_K = 1.6            # list menus' lines that much further apart, fewer shown (config.menu_k)
CARD = "1"              # /dev/dri/card1: the LCD (card0 is HDMI)
STOP = os.path.join(os.path.expanduser("~"), ".cache", "ace_commander", "stop")
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
# the game's text in DejaVu Sans Condensed Bold: sharper at these sizes, and narrower
FONTS = {"dejavusans": "DejaVuSansCondensed-Bold.ttf", "dejavusansbold": "DejaVuSansCondensed-Bold.ttf"}


def _video_env():
    """KMSDRM on the LCD unless a driver is chosen or there is a desktop to draw on."""
    if os.environ.get("SDL_VIDEODRIVER"):
        return
    if os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"):
        return
    os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
    os.environ.setdefault("SDL_KMSDRM_DEVICE_INDEX", CARD)


_video_env()
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame               # noqa: E402


def match_font(name, bold=False, italic=False):
    """pygame.font.match_font without fc-list: DejaVu by path, else pygame's own font."""
    key = str(name).replace(" ", "").replace(",", "").lower()
    if bold and not key.endswith("bold"):
        key += "bold"
    f = FONTS.get(key) or FONTS.get(key[:-4] if key.endswith("bold") else key)
    if f:
        path = os.path.join(FONT_DIR, f)
        if os.path.exists(path):
            return path
    return None             # pygame.font.Font(None, ...) is its built-in font


pygame.font.match_font = match_font

import run as pi_run        # noqa: E402  (the Pi's host)
import platform_pi          # noqa: E402

IIO = "/sys/bus/iio/devices"
G = 9.80665


class Accel:
    """The CardputerZero's accelerometer (a BMI270, which the kernel's iio driver
    shows in /sys/bus/iio/devices), read as (x, y, z) in g: the game's tilt steering
    and TILT SETUP. Its files stay open; each read goes back to their start."""

    def __init__(self, folder):
        with open(os.path.join(folder, "in_accel_scale")) as f:
            self.k = float(f.read().strip()) / G       # raw counts to g
        self.files = [open(os.path.join(folder, "in_accel_%s_raw" % a), "rb", buffering=0)
                      for a in "xyz"]

    def __call__(self):
        out = []
        for f in self.files:
            f.seek(0)
            out.append(int(f.read().strip()) * self.k)
        return tuple(out)


def find_accel():
    """The first iio device with an accelerometer, as an Accel, or None."""
    try:
        names = sorted(os.listdir(IIO))
    except OSError:
        return None
    for n in names:
        d = os.path.join(IIO, n)
        if os.path.exists(os.path.join(d, "in_accel_x_raw")):
            try:
                a = Accel(d)
                a()
                return a
            except (OSError, ValueError):
                continue
    return None

pi_run.CONFIG["menu_k"] = MENU_K
pi_run.CONFIG["device_file"] = os.path.join(HERE, "device.json")    # its own defaults

# W/A/S/D as the arrows on menus and screens; the badge buttons they hide (A, D)
# and C on the keys beside them
SCREEN_KEYS = {pygame.K_w: pygame.K_UP, pygame.K_a: pygame.K_LEFT,
               pygame.K_s: pygame.K_DOWN, pygame.K_d: pygame.K_RIGHT,
               pygame.K_q: pygame.K_F1, pygame.K_z: pygame.K_F3, pygame.K_x: pygame.K_F4}
SCREEN_LABELS = {"A": "Q", "D": "X"}
FLIGHT_SCREEN_LABELS = dict(SCREEN_LABELS, **pi_run.KEY_LABELS_FLIGHT)
TYPING = ("namer", "finder", "tdialog", "ndialog")


class Host(pi_run.Host):
    def __init__(self, perf=False, tilt=True, **kw):
        kw.setdefault("full", True)
        kw.setdefault("layout", "elite")
        kw.setdefault("wide", True)     # screens fitted to the LCD (the Pi's --wide, fit_pygame)
        self.perf = perf
        self._held = {}         # physical key -> the key sent at its key-down
        self._perf = None
        # its accelerometer: STEER: TILT and TILT SETUP in Options (set before the game starts)
        platform_pi.TILT = find_accel() if tilt else None   # its axes: device.json
        super().__init__(**kw)
        self.stop_file = STOP
        try:
            os.makedirs(os.path.dirname(STOP), exist_ok=True)
            os.remove(STOP)
        except OSError:
            pass
        signal.signal(signal.SIGTERM, self._stop)

    def _stop(self, *a):
        self.running = False

    # ---- the screen: always the LCD's size; bigger text ------------------------------
    def _open_window(self):
        flags = pygame.FULLSCREEN if self.full and pygame.display.get_driver() == "kmsdrm" else 0
        self.window = pygame.display.set_mode(SIZE, flags)
        pygame.mouse.set_visible(False)
        self._fit()

    def _fit(self):
        super()._fit()
        self.ctx.text_k = TEXT_K if self.layout == "elite" else BADGE_TEXT_K

    def toggle_full(self):
        pass                    # always the whole LCD

    # ---- keys --------------------------------------------------------------------
    def on_screen(self):
        """A menu or screen is showing: not flying, not in a tunnel, not typing."""
        app = self.app
        if any(getattr(app, n, None) is not None for n in TYPING):
            return False
        mode = getattr(app, "mode", "")
        if mode == "flight":
            return bool(getattr(app, "paused", False) or getattr(app, "chart", None) is not None
                        or getattr(app, "fsub", None) is not None)
        return mode not in ("launch", "docking", "mlaunch", "bench")

    def handle(self, event):
        if event.type in (pygame.KEYDOWN, pygame.KEYUP):
            if event.type == pygame.KEYDOWN and event.key in SCREEN_KEYS and self.on_screen():
                self._held[event.key] = SCREEN_KEYS[event.key]
            new = self._held.get(event.key)
            if new is not None:
                if event.type == pygame.KEYUP:
                    del self._held[event.key]
                event = pygame.event.Event(event.type, key=new, mod=event.mod, unicode="",
                                           scancode=getattr(event, "scancode", 0))
        return super().handle(event)

    def _paint(self, draw):
        # step() has set the labels for the pad or the flight keys; on a screen the
        # hints also name Q and X (the paused flight keeps P for A)
        if not self.pad_last and self.on_screen():
            self.ctx.labels = FLIGHT_SCREEN_LABELS if self.app.mode == "flight" else SCREEN_LABELS
        super()._paint(draw)

    # ---- a frame on the screen, the stop file and --perf -----------------------------
    def show(self, ms=0):
        super().show(ms)
        if os.path.exists(STOP):
            self.running = False
        if self.perf:
            self._perf_line()

    def _perf_line(self):
        now = time.monotonic()
        if self._perf is None:
            self._perf = [now, 0, time.process_time()]
            sys.stderr.write("CZ driver=%s window=%s\n" % (pygame.display.get_driver(), self.window.get_size()))
        p = self._perf
        p[1] += 1
        dt = now - p[0]
        if dt >= 1.0:
            cpu = time.process_time() - p[2]
            sys.stderr.write("FPS %.1f rss_mb %.1f cpu_pct %.0f mode %s t %s\n" % (
                p[1] / dt, _rss_kb() / 1024.0, 100 * cpu / dt, getattr(self.app, "mode", "?"),
                time.strftime("%H:%M:%S")))
            sys.stderr.flush()
            self._perf = [now, 0, time.process_time()]


def _rss_kb():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS"):
                    return int(line.split()[1])
    except OSError:
        pass
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Ace Commander on the M5 CardputerZero")
    ap.add_argument("--window", dest="full", action="store_false", default=True,
                    help="not full screen (on a desktop)")
    ap.add_argument("--debug", action="store_true", help="the DEBUG menu of cheats")
    ap.add_argument("--sound", dest="sound", action="store_true", default=True,
                    help="the game's sounds (the default; accepted as the Pi's run.py takes it)")
    ap.add_argument("--no-sound", dest="sound", action="store_false")
    ap.add_argument("--log-keys", action="store_true", help="print every key and the button it becomes")
    ap.add_argument("--pad", choices=("auto", "micro", "standard"), default="auto",
                    help="the game pad layout (as the Pi's run.py): auto, micro or standard")
    ap.add_argument("--no-tilt", dest="tilt", action="store_false", default=True,
                    help="don't use its accelerometer for tilt steering")
    ap.add_argument("--perf", action="store_true", help="a FPS / RSS / CPU line a second on stderr")
    ap.add_argument("--frames", type=int, default=None, help="stop after this many frames")
    ap.add_argument("--duel", type=int, nargs="?", const=47001, default=None, metavar="PORT",
                    help="MULTIPLAYER on the title screen, over UDP; PORT default 47001")
    args = ap.parse_args(argv)
    try:
        Host(perf=args.perf, tilt=args.tilt, full=args.full, debug=args.debug, log_keys=args.log_keys,
             sound=args.sound, duel=args.duel, pad=args.pad).run(args.frames)
    finally:
        if args.perf:
            sys.stderr.write("CZ exit maxrss_mb %.1f\n" % (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0))


if __name__ == "__main__":
    main()
