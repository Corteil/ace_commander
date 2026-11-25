"""Ace Commander for the EMF Tildagon / Spaceagon badge: a flight combat game and a
ship viewer, drawn as hidden-line wireframes with the original ship data.

Title screen
    Joystick left / right changes the choice, C (or press the joystick)
    selects it, F leaves the app. CONTINUE and NEW COMMANDER put a saved
    commander, whose kills earn a rank, in dock. COMBAT PRACTICE is the same
    fight with nothing kept.

Docked
    Joystick left / right changes screen (on the charts the joystick moves
    the cursor and E / B change screen). C on Status opens Options, on
    Inventory sells the whole hold, and on a chart makes the selected system
    the hyperspace target. A launches from any screen. F goes back to
    Status, then to the title screen.

Flight (2026 Spaceagon)
    Joystick      pitch and roll
    C, or press the joystick    fire lasers (hold)
    D             fire a missile at the boxed target
    B             energy bomb, once fitted (it is used up)
    F / E         speed up / slow down
    A             in-flight menu, which pauses the game
With tilt steering (chosen in the in-flight menu) tilting the badge steers and
the joystick still works; then a tap on D re-zeroes the tilt and holding D
fires the missile. The badge's LEDs flash red when you are hit.

In-flight menu
    Joystick up / down moves, C selects, F goes back, A resumes

Keyboard
    W / S or up / down pitch, A / D or left / right roll, E / Q speed up /
    down, F or SPACE lasers, M missile, P in-flight menu

Ship viewer
    Joystick or buttons turn the ship, CONFIRM (or N) next ship, P previous
    ship, CANCEL back to the title screen.

Ships come from ship_data.py, next to this file, if you have made it with
tools/import_ships.py from your own copy of the Elite source; otherwise the
game's own ships, original_ships.py.

If something moves the wrong way, or you want other buttons, change the
constants below.
"""
import json
import gc
import math
import random
import time

from . import briefing, cockpit, commander, controls, docked, game, missions, rules, ships, title, viewer

from . import config      # where the files are, and a host's switches (config.py)
# what only the device can do (LEDs, tilt, text entry, the frame loop; platform
# layer, step 3): the badge's firmware, or a host's own (config.platform)
if config.platform is None:
    from . import platform_tildagon as PLATFORM
else:
    PLATFORM = config.platform
from . import content     # Elite's ships and galaxy, or the game's own (content.py)
SHIPS = content.SHIPS
game_data = content.DATA
ORIGINAL_SHIPS = content.OWN        # the game's own content, not Elite's
HAVE_ELITE_SHIPS = content.CAN_SWITCH   # both Elite's files and the game's own are here: Options can switch
missions.use(game_data)
GOODS = getattr(game_data, "GOODS", None)   # the market's goods, if game_data.py has them
EQUIP = getattr(game_data, "EQUIPMENT", None)   # and the equipment
SAFE_GREEN = 60         # the LEDs are this green (0-255) in the safe zone round a station
# Where the 12 ring LEDs are round the screen, for effects that light the LED
# nearest a point on the edge (the jump: white as streaks leave the screen):
# LED 1's angle in degrees, anticlockwise from straight right (3 o'clock), and
# whether the numbers go round clockwise (they do), checked on the badge.
LED_ANGLE1 = 70.0      # LED 1 about 20 degrees past 12 o'clock (Brian saw 1, 2, 3 at 0:10, 2:00, 2:50)
LED_CLOCKWISE = True
JUMP_FADE = 900.0       # how fast a jump flash fades, 0-255 a second
HYPER_RGB = (130, 180, 255)     # arriving from hyperspace: blue-white, like the streaks
DUST_RGB = (255, 255, 255)      # the jump drive's stardust: white
EDGE_IN = 100           # a streak or speck this far from the middle (pixels) is leaving the screen
EDGE_OUT = 140
REPEAT_WAIT = 0.45      # seconds a market button is held before it starts repeating
REPEAT_EVERY = 0.09     # then once every this many seconds

# Flight buttons (letters as printed on the badge)
BTN_SPEED_UP = "F"
BTN_SPEED_DOWN = "E"
BTN_MISSILE = "D"      # with tilt steering: tap to re-zero the tilt, hold to fire
BTN_BOMB = "B"
BTN_MENU = "A"
HOLD_MISSILE = 0.45    # seconds D must be held to fire a missile when steering by tilt

# Tilt control. Values are in g (1 g = 9.81 m/s^2). The axis directions are a
# first guess, so flip the signs if things tilt the wrong way.
TILT_DEFAULT = False    # True to start with tilt steering instead of the joystick
TILT_DEADZONE = 0.10    # ignore small wobbles around the neutral pose
TILT_FULL = 0.50        # tilt that gives full rate (about 30 degrees)
TILT_PITCH_SIGN = 1.0
TILT_ROLL_SIGN = 1.0
TILT_SWAP_AXES = False  # True if the badge's x axis should pitch, y roll
# the CONTROLS setting (Options and Settings, saved; builds 85-87): flips the
# flight controls up / down (pitch), left / right (roll), or both, whichever
# way you steer: tilt, joystick or keyboard (not the charts' cursor)
TILT_FLIPS = ("NORMAL", "UP/DOWN FLIPPED", "L/R FLIPPED", "BOTH FLIPPED")

INVERT_PITCH = False    # False: joystick up raises the nose. True: up dives.
SHOW_FRAME_TIME = True  # small frame time (ms) at the top of the flight screen, to start with
DEBUG_ROWS = 7          # DEBUG page lines shown at once, the chosen one in the middle
VOLUME_MAX = 11         # Options > VOLUME 1-11 (build 145): as sfx.VOLUME_MAX and
VOLUME_DEFAULT = 8      # VOLUME_DEFAULT (not imported here: sfx costs heap without sound)
USE_LEDS = True         # flash the badge's LEDs red when hit (else a ring on screen)
FAST_FRAMES = True      # on the title screen, in flight and in the viewer, don't wait
                        # 50 ms between frames
PERF_LOG = config.perf_log  # print a PERF line to the console every this many flight
                        # frames (0 = never)
LAUNCH_TIME = 2.5       # seconds of launch tunnel (C skips it)
DOCK_TIME = 3.0         # seconds of flying in through the station's tunnel on docking (C skips it)
DOCK_HOLD = (1.0, 2.0)  # then the view of the bay stays this long, chosen at random
EJECT_TIME = 3.0        # seconds of the ESCAPE POD screen before the docking scene (C skips it)
DOCK_NAMES = {"A": "MANUAL", "B": "ASSISTED", "C": "AUTOMATIC"}

# the in-flight screens (Elite's f4-f9 and the charts): shown instead of the
# space view while the game runs on, not pages of the pause menu
SCREENS = ("status", "inventory", "market", "chart", "data")

# docked, the number row is Elite's f0-f9 (Brian chose Elite's scheme,
# 2026-11-16): f0 launch, f1 / f2 buy / sell (the market here; sell starts on
# the first good in the hold), f3 equip ship, f4 galactic chart, f5 local
# chart, f6 system data, f7 market prices, f8 status, f9 inventory (the same
# screen as in flight, as a tab). A missing tab does nothing. The joystick goes
# round the tabs in its own order (docked.TABS); = opens Options over Status.
DOCK_KEYS = (("k_1", "LAUNCH"), ("k_2", "MARKET"), ("k_3", "SELL"),
             ("k_4", "EQUIP SHIP"), ("k_5", "GALACTIC CHART"), ("k_6", "LOCAL CHART"),
             ("k_7", "SYSTEM DATA"), ("k_8", "MARKET"), ("k_9", "STATUS"),
             ("k_0", "INVENTORY"),
             # the two screens Elite didn't have, on the keys after 0 (Brian):
             # - (or _) the Shipyard (build 80: it holds the Repair Shop), = (or +) Options
             ("k_slower", "SHIPYARD"), ("k_faster", "OPTIONS"))
# DEBUG, a page of cheats for testing (the in-flight menu, Settings and
# Options): True or False, or None to show it only if a file called debug.txt
# is in the app's folder (always on a PC, where the tests run), or once it has
# been found: the Easter egg, docking at systems that spell EGG_WORD in the
# first galaxy (see AceCommander._egg)
DEBUG_MENU = config.debug_menu
TITLE_QUIT = config.title_quit  # a QUIT line on the title screen (a host sets it: the Pi; the badge has F)
LASER_LEDS = config.laser_leds  # your laser lights the LEDs (off on the Tufty and the Pi: build 113)
TITLE_CANCEL = config.title_cancel  # cancel on the title leaves (the Pi turns it off: QUIT does)
EGG_WORD = "DRAKE"      # a male duck: no system name starts with C or U for DUCKS
EGG_STOPS = 1           # dockings elsewhere forgiven between letters (to refuel)
PERF_SLOW = 25          # ms over the average that makes a frame count as slow

# the app's folder (metadata.json); the commander is saved in the data folder
# (config.py: the app's folder on the badge)
try:
    APP_DIR = __file__.rsplit("/", 1)[0]
    if not APP_DIR.startswith("/") and ":" not in APP_DIR:
        APP_DIR = "/" + APP_DIR         # the badge gives a path relative to /
except Exception:
    APP_DIR = "/apps/ace_commander"
# each data set keeps its own commander: their galaxy, systems and market
# only make sense in it (content.py, Options > DATA)
DATA_TAG = "own" if ORIGINAL_SHIPS else "elite"
SAVE_PATH = config.data("commander.json" if ORIGINAL_SHIPS else "commander_elite.json")


def _debug_wanted():
    import sys
    if sys.implementation.name != "micropython":
        return True
    try:
        open(config.data("debug.txt")).close()
        return True
    except OSError:
        pass
    try:                # found with the Easter egg
        with open(options_path()) as f:
            return bool(json.loads(f.read()).get("debug"))
    except Exception:
        return False


def options_path():
    """options.json, next to the save: the Options page's choices."""
    return SAVE_PATH.rsplit("/", 1)[0] + "/options.json"


if DEBUG_MENU is None:
    DEBUG_MENU = _debug_wanted()


# The DEBUG cheats in groups (Settings and Options > DEBUG). The names are the
# start of each line; some lines add the current value ("LEVEL: EASY").
DEBUG_GROUPS = (
    # SHIP is also the ship's equipment (SHIP CONFIG), below these
    ("SHIP", ("INVINCIBLE", "REFILL MISSILES", "REFILL FUEL", "FUEL TO 1/4")),
    ("SPAWN", ("ADD AN ENEMY", "ADD A TRADER", "ADD POLICE", "ADD A HUNTER", "ADD A THARGOID",
               "ADD THE CONSTRICTOR", "RELEASE CANISTER", "RELEASE ESCAPE POD", "BAIL OUT",
               "KILL ALL ENEMIES", "NEXT WAVE")),
    ("TRAVEL", ("TO THE STATION", "TO THE SUN", "DOCK NOW", "MIS-JUMP NEXT",
                "TO MISSION SYSTEM")),
    ("COMMANDER", ("+10 KILLS", "+1000 CR", "LEVEL", "HARDCORE", "LEGAL", "ANGER STATION", "MISSION")),
    ("DISPLAY", ("FRAME TIME", "SPEED TEST", "GAMEPAD")),
)
CAREER_ONLY = ("+1000 CR", "HARDCORE", "ADD A TRADER", "ADD POLICE", "ADD A HUNTER", "ANGER STATION",
               "MIS-JUMP NEXT", "LEGAL", "FUEL TO 1/4", "TO MISSION SYSTEM", "MISSION")
# the cheats that work away from a flight (title screen Options, docked Options);
# all but the last two need a commander, as does SHIP (the equipment) there
OFF_FLIGHT = ("+10 KILLS", "+1000 CR", "LEVEL", "HARDCORE", "LEGAL", "MISSION",
              "FRAME TIME", "SPEED TEST", "GAMEPAD")
NO_COMMANDER = ("FRAME TIME", "SPEED TEST", "GAMEPAD")
MSG_TIME = 1.5          # seconds a DEBUG message stays on the Options' DEBUG page


def cheat_group(line):
    """The DEBUG group a cheat's line is in (for the tests), or None."""
    for name, keys in DEBUG_GROUPS:
        for k in keys:
            if line.startswith(k) or k.startswith(line):
                return name
    return None


DEFAULT_NAME = "Jameson"    # Elite's commander: the name when the badge has none set


def cmdr_name(c=None):
    """The commander's name: commander c's own (build 89), else the badge
    owner's from the badge's settings, else Elite's JAMESON."""
    if c is not None and getattr(c, "name", ""):
        return c.name
    return badge_name()


def badge_name():
    """The badge owner's name from the badge's settings, or DEFAULT_NAME."""
    n = PLATFORM.owner_name()
    return n[:16] if n else DEFAULT_NAME
_build = None


def build():
    """The build number from metadata.json next to this file (deploy.bat copies
    it with the code), read once, or "?" if it can't be read."""
    global _build
    if _build is None:
        try:
            import json
            with open(APP_DIR + "/metadata.json") as f:
                _build = str(json.load(f)["version"])
        except Exception:
            _build = "?"
    return _build

LEVEL_NOTE = ("fewer, weaker enemies", "the standard fight", "more, deadlier enemies")
ANY = ("up", "down", "left", "right")           # joystick, buttons or arrow keys
STICK = ("j_up", "j_down", "j_left", "j_right")  # the joystick only
ARROWS = ("k_UP", "k_DOWN", "k_LEFT", "k_RIGHT")

try:
    _us = time.ticks_us
    _ms = time.ticks_ms
    _diff = time.ticks_diff
except AttributeError:   # off the badge (tests)
    def _us():
        return int(time.perf_counter() * 1000000)

    def _ms():
        return int(time.perf_counter() * 1000)

    def _diff(a, b):
        return a - b


def _tilt(v):
    """Turn a tilt in g into -1..1, with a dead zone."""
    a = abs(v) - TILT_DEADZONE
    if a <= 0:
        return 0.0
    a = min(1.0, a / (TILT_FULL - TILT_DEADZONE))
    return a if v > 0 else -a


class AceCommander(PLATFORM.App):
    def __init__(self, host=None):
        """host: the app object the badge's scheduler knows, when this one is
        started by the loading screen (app.py); button events, foreground checks and minimise
        go through it. None: this is that object (a PC: the tests)."""
        super().__init__()
        self.host = host if host is not None else self
        # which controls are down, by name (controls.py), fed by the platform:
        # on the badge platform_tildagon.Input matches the firmware's button
        # events; another device sets config.input to feed it itself
        self.pad = controls.Controls()
        if config.input is not None:
            config.input(self.pad, self.host)
        else:
            PLATFORM.Input(self.host, self.pad)
        self.platform = PLATFORM.Platform(self)     # LEDs, tilt, text entry, the frame loop
        # menu (the title screen) | level | docked | launch | flight | viewer | bench
        self.mode = "menu"
        self.bench = None
        self.menu = 0           # which title screen choice is showing
        self.title = title.Title(SHIPS) if SHIPS else None
        self.cmdr = commander.load(SAVE_PATH, DATA_TAG)   # the saved commander, or None
        # the commander as last saved, as JSON: being destroyed goes back to it
        self.saved = json.dumps(self.cmdr.to_dict()) if self.cmdr is not None else None
        self.just_saved = False     # Hardcore: SAVE COMMANDER pressed since Options opened
        self.dock_msg = 0           # the docked screens' message count (a beep for each new one)
        self.level = 1          # the level showing on the new-commander screen
        self.p_level = 1        # combat practice's level (options.json)
        self.p_hardcore = False # combat practice's own HARDCORE, apart from the commander's
        self.p_sel = 0          # the combat practice page's line: 0 LEVEL, 1 HARDCORE
        self.duel = None        # a duel (duel.py), made the first time DUEL is chosen
        self.dueling = False    # the flight is a duel's
        self.duel_err = None    # the radio wouldn't open: why
        self.d_sel = 0          # the duel lobby's line: 0 HOST A GAME, then a JOIN for each host
        self.n_hardcore = False # the new-commander page's HARDCORE
        self.n_sel = 0          # and its line: 0 NAME (build 89), 1 LEVEL, 2 HARDCORE
        self.game = None
        self.career = False     # the current game counts towards the commander
        self.docked = True      # the commander is at a station, not out in a flight
        self.banked = 0         # this game's kills already given to the commander
        self.banked_cash = 0    # and its bounties (tenths of a credit)
        self.saved_over = False
        self.fmenu = 0          # which in-flight menu line is highlighted
        self.fsub = None        # a menu page ("settings", "debug", ...) or a screen (SCREENS)
        self.top = 0            # the first row shown on Market Prices or Inventory
        self.fmarket = None     # Market Prices' market, while it is up
        self.galaxy = None      # made the first time a commander flies
        self.galaxy_n = 0       # which of the 8 galaxies self.galaxy is
        self.eject_t = 0.0      # time since the escape pod was launched
        self.witch = None       # in witchspace: (x, y) on the chart, between systems
        self.misjump = False    # DEBUG: the next jump goes wrong
        self.brief = None       # a mission message being shown (mode "brief")
        self.data_of = None     # the system whose data D shows from the in-flight chart
        self.fire_lock = False  # the lasers wait until C is let go (held on from a menu)
        self._bps = {}              # blueprints made for the docked screens with no game yet (_bp)
        # finding a system on the Galactic chart (build 88): the keyboard's own
        # page (find.Find), or the badge's text entry (the firmware's TextDialog)
        self.finder = None
        self.tdialog = None
        # entering the commander's name (build 89): the keyboard's page
        # (find.NameEntry) or the badge's text entry; what to do with it
        self.namer = None
        self.ndialog = None
        self.name_done = None
        self.n_name = ""        # the NEW COMMANDER page's name ("": the suggestion)
        self.find_chart = None      # the chart the system found goes on
        self.find_names = None      # find.Names for this galaxy, kept
        self.chart = None       # the local chart, while it is open
        self.jump_to = None     # (system, distance) the hyperspace countdown is for
        self.dt = 0.0           # seconds since the last update
        self.dock = None        # the docked screens (docked.Docked), while docked
        self.target = None      # the system picked for the next hyperspace jump
        self.launch_t = 0.0     # how far into the launch tunnel
        self.dock_t = 0.0       # how far into the docking tunnel
        self.dock_hold = 0.0    # how long the view of the bay stays at the end of it
        self.held_t = {}        # how long each market button has been held (see _repeat)
        self.show_ms = SHOW_FRAME_TIME  # the frame time counter (a DEBUG switch)
        self.tunnel = None      # this station's tunnel (cockpit.Tunnel), for launching and docking
        self.d_t = None         # how long D has been down, when steering by tilt
        self.viewer = None
        self.paused = False
        self.tilt_ok = self.platform.tilt_ok    # the accelerometer is there and working
        # steer by tilt as well as the joystick (TILT_DEFAULT, or the menu)
        self.use_tilt = self.tilt_ok and TILT_DEFAULT
        self.tilt_flip = 0      # CONTROLS (TILT_FLIPS): 1 pitch flipped, 2 roll, 3 both
        # a host's analogue controls (the Pi's game pad), or None: anything with
        # roll, pitch, yaw (-1..1, pitch as the joystick: negative is up) and
        # speed (0..1, where the power stick sits; None: leave the speed alone).
        # The badge never sets it.
        self.analog = None
        self.zero = None                 # accelerometer reading taken as "level"
        self.ms = 0.0                    # smoothed frame time
        self.jump_leds = [0.0] * 13      # each ring LED's white jump flash, 0-255 (1 to 12)
        self.jump_lit = False            # the last write was a jump flash
        self.jump_rgb = DUST_RGB         # their colour at full brightness
        self.use_leds = USE_LEDS         # the Options page's LEDS: ON / OFF
        self.use_sound = True            # SOUND: ON / MUTED (builds 140, 145), where there is sound
        self.volume = VOLUME_DEFAULT     # VOLUME: 1-11 (build 145), where the device has it
        self.use_picker = False          # TEXT ENTRY: the letter picker (picker.py) rather than
                                         # the badge's own dialog (build 124, an option)
        self.old_hardcore = False        # options.json's HARDCORE from before build 74
        self.own_ships = ORIGINAL_SHIPS  # DATA: OWN / ELITE, from the next start
        self.omenu = 0                   # the chosen line on the Options page
        self.egg = 0                     # letters of EGG_WORD docked at so far
        self.egg_miss = 0                # and dockings elsewhere since the last
        self.dgroup = None               # the DEBUG group open in flight (fsub "dgroup")
        self.debug_from = None           # where DEBUG was opened from in flight: None (the menu) or "settings"
        self.od_from = None              # Options' DEBUG away from a flight (mode "odebug"):
        self.od_page = None              # the mode to go back to, the group open,
        self.od_sel = 0                  # the chosen line,
        self.od_msg = None               # and what the last cheat did
        self.od_msg_t = 0.0
        self._load_options()
        if self.use_sound and hasattr(self.platform, "sound_warm"):
            self.platform.sound_warm()      # the badge's I2S open now, settled by the first sound
        c = self.cmdr
        if c is not None and c.hardcore is None:    # a save from before build 74:
            c.hardcore = self.old_hardcore          # HARDCORE was an option then
            self.saved = json.dumps(c.to_dict())
        self.glow = 0.0                  # the station's colour fading on the LEDs after launch
        # smoothed time, in ms, spent in the game rules and in drawing calls
        self.t_step = 0.0
        self.t_world = 0.0
        self.t_hud = 0.0
        self.fast = FAST_FRAMES and self.platform.fast
        # totals for the PERF line
        self.p_n = 0
        self.p_frame = 0.0
        self.p_max = 0.0
        self.p_update = 0.0
        self.p_rules = 0.0
        self.p_draw = 0.0
        self.p_world = 0.0      # of which the 3D view, and the HUD
        self.p_hud = 0.0
        self.p_avg = 60.0   # last window's average frame, ms
        self.p_nslow = 0
        self.p_slow = []
        self.p_skip = True  # the first flight frame follows a menu frame

    # ---- frame loop -------------------------------------------------------

    async def run(self, render_update):
        """The frame loop: the platform's (on the badge, it skips the firmware's
        50 ms wait between frames where it can; self.fast)."""
        await self.platform.run(render_update)

    def minimise(self):
        self.platform.minimise()

    # ---- LEDs -------------------------------------------------------------

    def _leds(self, level):
        """Set the ring of 12 LEDs to red at level 0-255."""
        self._leds_rgb(level, 0, 0)

    def _leds_rgb(self, r, g, b):
        """Set the ring of 12 LEDs to (r, g, b), 0-255 each (the platform takes
        them over first, and writes only when the colour changes)."""
        if self.use_leds:
            self.platform.leds_rgb(r, g, b)

    def _led_at(self, x, y):
        """The ring LED (1 to 12) nearest the edge in screen direction (x, y),
        x right and y down."""
        a = math.atan2(-y, x) * 57.29578
        step = (LED_ANGLE1 - a) if LED_CLOCKWISE else (a - LED_ANGLE1)
        return int(math.floor(step / 30.0 + 0.5)) % 12 + 1

    def _jump_flashes(self):
        """Light the ring LEDs white where the jump's streaks leave the screen:
        the hyperspace streaks as you arrive, the stardust with the jump drive
        on. True if any is lit."""
        g = self.game
        lit = self.jump_leds
        fade = JUMP_FADE * self.dt
        any_lit = False
        for i in range(1, 13):
            if lit[i] > 0:
                lit[i] = max(0.0, lit[i] - fade)
        if g.warp > 0:          # the hyperspace streaks (cockpit._STREAKS)
            self.jump_rgb = HYPER_RGB
            k = 256 - int(g.warp * 256 / cockpit._WARP_T)
            for dx, dy, r0 in cockpit._STREAKS:
                b = r0 + (k * 40 >> 8) + 12 + (k * 110 >> 8)     # the streak's outer end
                if EDGE_IN <= b <= EDGE_OUT:
                    lit[self._led_at(dx, dy)] = 255.0
        elif g.jumping:         # stardust streaking past and off the edge
            self.jump_rgb = DUST_RGB
            f = cockpit.IFOCAL
            for p in g.view_dust():     # as the view being looked through sees it
                z = int(p[2])
                if z > cockpit.INEAR:
                    sx = int(p[0]) * f // z
                    sy = -(int(p[1]) * f // z)
                    r2 = sx * sx + sy * sy
                    if EDGE_IN * EDGE_IN <= r2 <= EDGE_OUT * EDGE_OUT:
                        lit[self._led_at(sx, sy)] = 255.0
        for i in range(1, 13):
            if lit[i] > 0:
                any_lit = True
                break
        return any_lit

    def _leds_each(self, values, rgb=DUST_RGB):
        """Each ring LED in colour rgb at its own level (values[1] to [12],
        0-255)."""
        if self.use_leds:
            self.platform.leds_each(values, rgb)

    def _leds_release(self):
        """Hand the LEDs back to the badge's own pattern."""
        self.platform.leds_release()

    def _leds_flight(self):
        g = self.game
        if self.paused:
            self._leds(0)
        elif g.over:
            self._leds(48)
        elif g.bomb_t > 0:      # the energy bomb: a white flash
            self._leds_rgb(255, 255, 255)
        elif g.ecm_t > 0:       # the ECM: a violet flash
            self._leds_rgb(160, 0, 255)
        elif g.flash > 0.18:    # full, then fading over the 0.3 s after a hit
            self._leds(255)
        elif g.flash > 0.09:
            self._leds(160)
        elif g.flash > 0:
            self._leds(80)
        elif g.beam > 0 and LASER_LEDS:     # your laser firing: its own colour (config.laser_leds)
            r, gr, b = cockpit.LASER_COLOURS.get(g.laser, cockpit.RED)
            self._leds_rgb(int(r * 255), int(gr * 255), int(b * 255))
        elif self._jump_flashes() or self.jump_lit:     # the jump: white where streaks leave
            self._leds_each(self.jump_leds, self.jump_rgb)
            self.jump_lit = any(v > 0 for v in self.jump_leds[1:])
        elif self.glow > 0:     # just launched: the station's colour fades away
            self._leds_station(self.glow)
            self.glow -= self.dt * 2.0
        elif g.space is not None and g.scooping:    # skimming fuel: yellow pulses
            k = 255 if int(g.time * 4) % 2 else 90
            self._leds_rgb(k, k * 3 // 4, 0)
        elif g.space is not None and g.cabin > game.COOL_CABIN:   # near the sun: orange to red
            l = ((g.cabin - game.COOL_CABIN) * 15 // (255 - game.COOL_CABIN)) / 15.0   # 16 steps
            r = int(255 * l)
            self._leds_rgb(r, int(r * 0.45 * (1.0 - l)), 0)
        elif g.space is not None and g.space.safe:  # near the station: no ships come here
            self._leds_rgb(0, SAFE_GREEN, 0)
        else:
            self._leds(0)

    def _government(self):
        """The government of the commander's system (0 to 7), or None."""
        c = self.cmdr
        if c is None or c.system is None or self.galaxy is None:
            return None
        return self.galaxy.system(c.system).government

    def _leds_station(self, k):
        """The LEDs in this station's colour, k (0 to 1) of full brightness,
        in 16 steps so they are written only when the step changes."""
        k = int(k * 15 + 0.5)
        rgb = cockpit.station_colour(self._government())
        self._leds_rgb(int(rgb[0] * 255) * k // 15, int(rgb[1] * 255) * k // 15,
                       int(rgb[2] * 255) * k // 15)

    # ---- steering ---------------------------------------------------------

    def _steer(self, tilt, dirs, arrows, wasd=True):
        """(roll, pitch) as -1..1 each, from tilt, the four direction controls
        named in dirs, and the keyboard. Pitch is negative for up."""
        held = self.pad.held
        jx = jy = 0.0
        if tilt and self.tilt_ok:
            pl = self.platform
            if not pl.tilt():   # the sensor failed
                self.tilt_ok = False
                self.use_tilt = False
            else:
                ax = pl.tx
                ay = pl.ty
                if self.zero is None:
                    self.zero = (ax, ay)
                dx = ax - self.zero[0]
                dy = ay - self.zero[1]
                if TILT_SWAP_AXES:
                    dx, dy = dy, dx
                jx = TILT_ROLL_SIGN * _tilt(dx)
                jy = TILT_PITCH_SIGN * _tilt(dy)
        if dirs is not None:
            if held(dirs[0]):
                jy -= 1.0
            if held(dirs[1]):
                jy += 1.0
            if held(dirs[2]):
                jx -= 1.0
            if held(dirs[3]):
                jx += 1.0
        if arrows:      # not already counted in dirs
            if held("k_UP"):
                jy -= 1.0
            if held("k_DOWN"):
                jy += 1.0
            if held("k_LEFT"):
                jx -= 1.0
            if held("k_RIGHT"):
                jx += 1.0
        if wasd:
            if held("k_W"):
                jy -= 1.0
            if held("k_S"):
                jy += 1.0
            if held("k_A"):
                jx -= 1.0
            if held("k_D"):
                jx += 1.0
        return max(-1.0, min(1.0, jx)), max(-1.0, min(1.0, jy))

    # ---- update -----------------------------------------------------------

    def update(self, delta):
        t0 = _us()
        if not self.paused:     # the pause menu shows it, so keep it still there
            self.ms += (delta - self.ms) * 0.1
        pad = self.pad
        hit = pad.hit
        cancel = hit("cancel")
        confirm = hit("confirm")
        self.dt = dt = delta / 1000.0

        if self._update_name(cancel, confirm):
            pass                # the name being entered takes the input
        elif self.mode == "menu":
            if cancel and TITLE_CANCEL:
                pad.clear()
                self.minimise()
            elif SHIPS:     # nothing to choose without ship_data.py
                if self.title is None:
                    self.title = title.Title(SHIPS)
                items = self.choices()
                if self.menu >= len(items):
                    self.menu = 0
                if hit("left") or hit("up"):
                    self.menu = (self.menu - 1) % len(items)
                elif hit("right") or hit("down"):
                    self.menu = (self.menu + 1) % len(items)
                elif confirm:
                    self._choose(items[self.menu])
                self.title.step(dt)
        elif self.mode == "practice":
            self._update_practice(cancel, confirm)
        elif self.mode == "duel":
            self._update_duel(dt, cancel, confirm)
        elif self.mode == "level":
            if cancel:
                self.mode = "menu"
            elif hit("up"):
                self.n_sel = (self.n_sel - 1) % 3
            elif hit("down"):
                self.n_sel = (self.n_sel + 1) % 3
            elif self.n_sel == 0 and (confirm or hit("right")):
                self._open_name(self.n_name, self._new_name)    # NAME: C or right enters it
            elif hit("left") or hit("right"):
                if self.n_sel == 1:
                    n = len(commander.LEVELS)
                    self.level = (self.level + (-1 if hit("left") else 1)) % n
                elif self.n_sel == 2:
                    self.n_hardcore = not self.n_hardcore
            elif confirm:
                self._forget_flight()   # nothing carries over from before (build 138)
                self.cmdr = commander.Commander(self.level)
                self.cmdr.name = self.n_name or badge_name().upper()[:12]
                self.cmdr.hardcore = self.n_hardcore    # fixed from now on (DEBUG can change it)
                self.career = False     # an old commander's flight banks nothing into it
                self._write()
                self.menu = 0       # CONTINUE is now the first choice
                self._dock()
        elif self.mode == "docked":
            self._update_docked(dt, cancel, confirm)
        elif self.mode == "options":
            self._update_options(cancel, confirm)
        elif self.mode == "odebug":
            self._update_odebug(dt, cancel, confirm)
        elif self.mode == "brief":
            b = self.brief
            held = pad.held
            up = held("j_up") or held("k_UP")
            down = held("j_down") or held("k_DOWN")
            b.tick(dt, (1 if down else 0) - (1 if up else 0))
            if cancel:
                b.skip()
            elif confirm:
                b.next()
            if b.done:
                self.brief = None
                self.mode = "docked"
        elif self.mode == "launch":
            self.launch_t += dt
            self._leds_station(cockpit.tunnel_glow(min(1.0, self.launch_t / LAUNCH_TIME),
                                                   self.tunnel))
            if confirm or self.launch_t >= LAUNCH_TIME:
                self.glow = 1.0
                if self.game is not None:
                    self.game.over = True   # every launch is a new flight
                self.docked = False
                self._start_flight(True)
        elif self.mode == "docking":
            self.dock_t += dt
            self._leds_station(cockpit.dock_glow(min(1.0, self.dock_t / DOCK_TIME), self.tunnel))
            if confirm or self.dock_t >= DOCK_TIME + self.dock_hold:
                self._leds_release()
                self._dock()
        elif self.mode == "viewer":
            self._update_viewer(dt, cancel, confirm)
        elif self.mode == "bench":
            if cancel:
                self.mode = "odebug"    # back to DEBUG > DISPLAY, where it was started
                self.bench = None
            else:
                self.bench.step(delta)
        else:
            flying = self._update_flight(dt, cancel, confirm)
            if self.mode == "flight":
                self._leds_flight()
            else:
                self._leds_release()
            if flying and PERF_LOG:
                self._perf(delta, _diff(_us(), t0) / 1000.0)
        if self.dueling:            # paused too: the other player keeps hearing us
            if self.mode == "flight" and self.game is not None:
                self.duel.flight_step(self.game, dt)
            else:                   # left the flight: the game is practice's again
                self.duel.stop(self.game)
                self.dueling = False
        self._sounds()
        pad.end_frame()
        # the keyboard's A-F are the badge's buttons for the next frame's keys:
        # off the flight (docked, the title, its pages), not while typing; in
        # flight, pause menu too, they stay Elite's keys
        pad.as_buttons = (self.mode != "flight" and self.namer is None
                          and self.finder is None and self.tdialog is None)

    def choices(self):
        """The title screen's choices, in order."""
        if config.practice_only:        # too few buttons for the rest (config.py)
            items = ["COMBAT PRACTICE"]
            if TITLE_QUIT:
                items.append("QUIT")
            return items
        items = ["NEW COMMANDER", "COMBAT PRACTICE", "SHIP VIEWER", "OPTIONS"]
        if getattr(self.platform, "radio", None) is not None:
            items.insert(2, "DUEL")     # two players (duel.py): only with a radio
        if self.cmdr is not None:
            items.insert(0, "CONTINUE")
        if TITLE_QUIT:
            items.append("QUIT")
        return items

    def _choose(self, item):
        if item == "CONTINUE":
            g = self.game
            if self.docked or g is None or g.over or not self.career:
                self._dock()
            else:               # a flight that was left part-way carries on
                self._start_flight(True)
        elif item == "NEW COMMANDER":
            self.level = 1
            self.n_hardcore = False
            self.n_name = ""        # the badge's name, or JAMESON, until one is entered
            self.n_sel = 1          # on LEVEL: C starts at once; up to NAME to change it
            self.mode = "level"
        elif item == "COMBAT PRACTICE":
            self.p_sel = 0
            self.mode = "practice"      # its level and HARDCORE first
        elif item == "DUEL":
            if self.duel is None and self.duel_err is None:
                try:
                    from . import duel
                    self.duel = duel.Duel(self.platform.radio())
                except Exception as e:      # no radio after all: the page says why
                    self.duel_err = str(e)[:60] or e.__class__.__name__
            if self.duel is not None:       # the commander's name and paint go to the others
                c = self.cmdr
                self.duel.set_me(cmdr_name(c), c.colour if c is not None else 0)
                self.duel.leave()           # into the lobby
            self.d_sel = 0
            self.mode = "duel"
        elif item == "OPTIONS":
            self.omenu = 0
            self.mode = "options"
        elif item == "QUIT":           # a host's (the Pi's): leave, as F does on the badge
            self.pad.clear()
            self.minimise()
        elif item == "SHIP VIEWER":
            self.zero = None
            if self.viewer is None:
                self.viewer = viewer.Viewer(SHIPS)
            self.mode = "viewer"

    def _update_practice(self, cancel, confirm):
        """Combat practice's page: up / down picks LEVEL or HARDCORE, left /
        right changes it, C flies, F goes back to the title screen. Its
        HARDCORE is its own, apart from the commander's."""
        hit = self.pad.hit
        if cancel:
            self.mode = "menu"
        elif hit("up") or hit("down"):
            self.p_sel = 1 - self.p_sel
        elif hit("left") or hit("right"):
            if self.p_sel == 0:
                n = len(commander.LEVELS)
                self.p_level = (self.p_level + (-1 if hit("left") else 1)) % n
            else:
                self.p_hardcore = not self.p_hardcore
            self._save_options()
        elif confirm:
            self._start_flight(False)

    def _update_duel(self, dt, cancel, confirm):
        """The DUEL pages (Brian, 2026-11-25: a lobby, one player hosts). In the
        lobby up / down picks HOST A GAME or a host to join and C chooses; hosting,
        C starts once someone has joined; joining, the host starts it. F goes back:
        to the lobby, then the title screen."""
        from . import duel as dm
        d = self.duel
        if d is None:
            if cancel:
                self.mode = "menu"
            return
        d.lobby_step(dt)
        if d.go:                    # START: said by us (host) or to us (guest): fly
            self.game = None        # a fresh flight: a practice one left part-way is dropped
            self._start_flight(False)
            d.start(self.game)
            self.dueling = True
            return
        hit = self.pad.hit
        if d.role == dm.LOBBY:
            hosts = d.hosts()
            n = 1 + len(hosts)
            if self.d_sel >= n:
                self.d_sel = n - 1
            if cancel:
                self.mode = "menu"
            elif hit("up"):
                self.d_sel = (self.d_sel - 1) % n
            elif hit("down"):
                self.d_sel = (self.d_sel + 1) % n
            elif confirm:
                if self.d_sel == 0:
                    d.host()
                else:
                    d.join(hosts[self.d_sel - 1])
        elif cancel:
            d.leave()
        elif confirm and d.role == dm.HOST:
            d.start_game()          # (nothing until someone has joined)

    def _draw_duel(self, ctx):
        from . import duel as dm
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text = cockpit.text
        d = self.duel
        if d is None:
            text(ctx, "DUEL", 0, -70, 18, cockpit.WHITE)
            text(ctx, "NO RADIO", 0, -20, 17, cockpit.RED)
            text(ctx, (self.duel_err or "")[:28], 0, 5, 11, cockpit.GREY)
            text(ctx, "F: back", 0, 80, 12, cockpit.GREY)
            return
        me = cockpit.ship_rgb(d.colour)
        if d.role == dm.LOBBY:
            text(ctx, "DUEL LOBBY", 0, -78, 17, cockpit.WHITE)
            text(ctx, d.name, 0, -58, 12, me)
            hosts = d.hosts()
            rows = ["HOST A GAME"] + ["JOIN " + p.name for p in hosts]
            top = max(0, min(self.d_sel - 2, len(rows) - 4))
            for i in range(top, min(len(rows), top + 4)):
                y = -30 + (i - top) * 22
                on = i == self.d_sel
                rgb = cockpit.ship_rgb(hosts[i - 1].colour) if i and not on else (
                    cockpit.GREEN if on else cockpit.GREY)
                text(ctx, ("< %s >" if on else "%s") % rows[i][:18], 0, y, 14 if on else 12, rgb)
            others = d.lobby()
            if others:
                names = ", ".join(p.name for p in others[:3]) + ("..." if len(others) > 3 else "")
                text(ctx, "HERE: " + names[:26], 0, 62, 10, cockpit.GREY)
            else:
                dots = "." * (1 + (_ms() // 500) % 3)
                text(ctx, "nobody else yet" + dots, 0, 62, 10, cockpit.YELLOW)
            text(ctx, "C: choose   F: back", 0, 82, 12, cockpit.GREY)
        elif d.role == dm.HOST:
            text(ctx, "HOSTING", 0, -70, 18, cockpit.WHITE)
            text(ctx, d.name, 0, -48, 12, me)
            o = d.other
            if o is not None:
                text(ctx, o.name, 0, -10, 17, cockpit.ship_rgb(o.colour))
                text(ctx, "has joined", 0, 12, 12, cockpit.GREY)
                text(ctx, "C: start   F: stop", 0, 80, 12, cockpit.GREY)
            else:
                dots = "." * (1 + (_ms() // 500) % 3)
                text(ctx, "waiting for a player" + dots, 0, 0, 12, cockpit.YELLOW)
                text(ctx, "F: stop", 0, 80, 12, cockpit.GREY)
        else:
            text(ctx, "JOINING", 0, -70, 18, cockpit.WHITE)
            o = d.other
            text(ctx, o.name if o is not None else "?", 0, -40, 17,
                 cockpit.ship_rgb(o.colour) if o is not None else cockpit.GREY)
            if o is None or o.t >= dm.GONE:
                text(ctx, "HOST GONE", 0, 0, 14, cockpit.RED)
            elif d.accepted():
                text(ctx, "waiting for the host", 0, -5, 12, cockpit.GREEN)
                text(ctx, "to start", 0, 12, 12, cockpit.GREEN)
            else:
                text(ctx, "asking to join...", 0, 0, 12, cockpit.YELLOW)
            text(ctx, "F: leave", 0, 80, 12, cockpit.GREY)

    def _draw_practice(self, ctx):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        cockpit.text(ctx, "COMBAT PRACTICE", 0, -70, 18, cockpit.WHITE)
        self._draw_rows(ctx, self.p_level, self.p_hardcore, self.p_sel, -42, 56)
        cockpit.text(ctx, "C: fly   F: back", 0, 80, 12, cockpit.GREY)

    def _draw_rows(self, ctx, level, hardcore, sel, top, step, saves=False):
        """The LEVEL and HARDCORE lines of the practice and new-commander pages
        (saves: a commander's, where Hardcore also means saving by hand)."""
        text = cockpit.text
        rows = ("LEVEL", "< %s >" % commander.LEVELS[level], LEVEL_NOTE[level]), \
               ("HARDCORE", "< %s >" % ("ON" if hardcore else "OFF"),
                ("ECM, missiles, saving by hand" if saves else "ECM by hand, armed missiles")
                if hardcore else "the game's usual help")
        for i, (name, value, note) in enumerate(rows):
            y = top + i * step
            on = i == sel
            text(ctx, name, 0, y, 12, cockpit.GREY)
            text(ctx, value, 0, y + 18, 17, cockpit.GREEN if on else cockpit.GREY)
            if on:
                text(ctx, note, 0, y + 38, 11, cockpit.YELLOW)

    def _start_flight(self, career):
        """Go into flight: as the commander, or for practice. A game that was
        left part-way carries on if it is the same kind."""
        level = self.cmdr.level if career else self.p_level
        if not career:
            self.glow = 0.0
        g = self.game
        fresh = True
        if g is None:
            self.game = g = game.Game(SHIPS, level)
            self.banked = 0
            self.banked_cash = 0
        g.auto_missile = config.auto_missiles and not career    # no missile button: practice
        g.practice_upgrades = config.practice_upgrades and not career
        if config.practice_missile is not None:
            g.pickup_missile = config.practice_missile
        elif g.over or career != self.career or g.level != level \
                or g.rules.hardcore != (self._hardcore() if career else self.p_hardcore):
            # HARDCORE changed since the last flight: practice's, or the commander's (build 137:
            # a new Hardcore commander kept a standard one's rules, tractor beam and all)
            g.set_level(level)
            g.reset()
            self.banked = 0
            self.banked_cash = 0
        else:
            fresh = False
        if fresh:
            g.rules = rules.GameRules(self._hardcore() if career else self.p_hardcore)
            if not career:
                g.ecm = True    # practice flies with an ECM (by hand in Hardcore)
                g.set_ship(ships.COBRA)     # practice is always in a Cobra Mk III
                g.missiles = g.max_missiles if g.missile_bp else 0
            g.set_docking(g.docking)        # Hardcore: by hand, whatever the setting
        self.career = career
        g.again = "C: back to last save" if career else "C: fly again"
        g.scoop = self._scoop if career and self.cmdr is not None else None
        g.refuel = self._refuel if career and self.cmdr is not None else None
        if career:
            self._place()
            if fresh or g.space is None:
                self._enter_space("launch")
                self._fit(g)
                if self.cmdr is not None:
                    g.illegal_cargo(self.cmdr.cargo)    # slaves, narcotics, firearms
        self.jump_to = None
        g.jump_t = 0.0
        self.saved_over = False
        self.zero = None
        self.d_t = None
        self.paused = False
        self.fsub = None
        self.fire_lock = True   # the C that launched you (or chose this) isn't a shot
        self.jump_leds = [0.0] * 13     # no jump flash left over from before
        self.jump_lit = False
        self.mode = "flight"

    def _place(self):
        """Make the galaxy, and put a commander who is nowhere yet at the
        starting system. Without game_data.py there is no galaxy."""
        if game_data is None:
            return
        c = self.cmdr
        if self.galaxy is None or self.galaxy_n != c.galaxy:
            from . import galaxy
            self.galaxy = None      # free the old one first
            self.galaxy = galaxy.Galaxy(galaxy.seeds_for(game_data.SEEDS, c.galaxy),
                                        game_data.PAIRS)
            self.galaxy_n = c.galaxy
        if c.system is None:
            c.system = self.galaxy.find(*game_data.START_XY) or 0
            c.fuel = min(c.max_fuel(), game_data.START_FUEL)

    def _enter_space(self, how):
        """Put the game in the commander's star system: "launch" (from the
        station) or "arrive" (from hyperspace). Without a galaxy there is no
        system, and the flight is open space with waves of ships."""
        c = self.cmdr
        if self.galaxy is None or c is None or c.system is None:
            return
        self.game.set_docking(c.docking)
        self._mission_flags()
        s = self.galaxy.system(c.system)
        self.game.enter(s.radius, "DODO" if s.tech >= game.DODO_TECH else "CORIOLIS", how,
                        s.government, (c.system * 37 + 11) % 5,     # the sun's colour
                        (c.system * 53 + 29) % 7)                   # and the planet's

    def _make_dock(self):
        self.dock_msg = 0       # its messages are counted afresh (a beep for each)
        self.dock = docked.Docked(self.cmdr, self.galaxy, self.target, GOODS, EQUIP,
                                  self._ship_bp(),
                                  (lambda: self._settings(True), self._change),
                                  self._bp if SHIPS else None)

    def _mission_flags(self):
        """Tell the game what the missions need of this system (see missions.py)."""
        g = self.game
        c = self.cmdr
        gal = self.galaxy
        g.orarra = missions.constrictor_here(c.galaxy, gal.xs[c.system], gal.ys[c.system])
        g.hunt = g.orarra and missions.hunting(c.mission)
        g.con_wait = missions.QUICK_WAIT if c.quick_con else None
        g.plans = missions.carrying_plans(c.mission)

    def _dock(self):
        """Show the commander docked at their star system, remember it as where
        they start again if destroyed, and save. Fuel is bought on Equip ship
        (it is free only if game_data.py has no equipment)."""
        self._bank()            # before career is set: practice kills don't count
        self._place()
        self.career = True
        c = self.cmdr
        c.docked_at = c.system  # the last station docked at
        self.witch = None
        if not EQUIP:           # nowhere to buy fuel: it's free, as before the equipment
            c.fuel = c.max_fuel()
        if GOODS and self.galaxy is not None and (c.market is None
                                                  or c.market["system"] != c.system):
            from . import market
            c.market = market.new(GOODS, c.system, self.galaxy.system(c.system).economy,
                                  random.randint(0, 255))
        self._auto_write()
        self.just_saved = False
        if self.game is not None:
            self.game.docked = False
            self.game.autodock = False      # the docking computer starts afresh next time
            self.game.auto_phase = 0
            self.game.auto_level = False
        if self.target == c.system:
            self.target = None
        self._make_dock()
        self.docked = True
        self.jump_to = None
        self.paused = False
        self.fsub = None
        self.chart = None
        self.mode = "docked"
        self._mission_news()
        self._egg()

    def _egg(self):
        """The Easter egg: dock at systems whose names start with the letters
        of EGG_WORD, in order, in the first galaxy, and the DEBUG menu is
        yours. One docking elsewhere between letters is forgiven (to refuel:
        no route has every step on one tank); more starts again. Kept in
        options.json."""
        global DEBUG_MENU
        c = self.cmdr
        if DEBUG_MENU or c is None or c.galaxy != 0 or self.galaxy is None:
            return
        ch = self.galaxy.system(c.system).name[:1]
        if ch == EGG_WORD[self.egg]:
            self.egg += 1
            self.egg_miss = 0
        elif ch == EGG_WORD[0]:
            self.egg = 1                # a fresh start
            self.egg_miss = 0
        else:
            self.egg_miss += 1
            if self.egg_miss > EGG_STOPS:
                self.egg = self.egg_miss = 0
        if self.egg >= len(EGG_WORD):
            DEBUG_MENU = True
            self.egg = self.egg_miss = 0
            if self.mode == "docked":   # not over a mission's message
                self.brief = briefing.Briefing(game_data, 0, "", 0, None, pages=(
                    ("QUACK!\nYou have found the hidden DEBUG menu: cheats, at the end of "
                     "Settings and Options and on the in-flight menu.\nMESSAGE ENDS", False),))
                self.mode = "brief"
        self._save_options()

    def _mission_news(self):
        """Docking may start or end a mission (missions.on_docking): if so,
        save, and show the message before the docked screens."""
        c = self.cmdr
        gal = self.galaxy
        if gal is None or not (getattr(game_data, "DESC_TOKENS", None)
                               or getattr(game_data, "MISSION_TEXTS", None)):
            return
        n = missions.on_docking(c, gal.xs[c.system], gal.ys[c.system])
        if n is None:
            return
        self._auto_write()
        ship = None
        if n in missions.SHOWS_SHIP:
            for e in SHIPS:
                if e[0] == game.CONSTRICTOR:
                    ship = game.Blueprint(e)
        self.brief = briefing.Briefing(game_data, n, cmdr_name(c), c.galaxy, ship)
        if not self.brief.done:
            self.mode = "brief"

    def _update_docked(self, dt, cancel, confirm):
        """The docked tabs. The joystick changes tab, and E / B do too. On a
        chart C hands the joystick to the cursor, then C picks a target and F
        hands it back. C on Status opens Options. A launches from any tab. F
        goes back to Status, and from Status to the title screen."""
        d = self.dock
        hit = self.pad.hit
        d.tick(dt)
        if d.msg_n != self.dock_msg:
            self._play("beep")          # a trade done or refused: Elite's short high beep
        self.dock_msg = d.msg_n
        if not d.in_options:
            self.just_saved = False     # "SAVED" shows until Options is left
        if self._update_find(cancel, confirm):
            return
        if (d.view is not None and d.cursor and hasattr(d.view, "number")
                and hit(BTN_BOMB)):
            self._open_find(d.view)     # B on the Galactic chart (cursor on): find a system
            return
        if cancel and d.view is not None and d.cursor:
            d.use_cursor(False)     # F: the joystick goes back to changing tabs
            return
        if cancel:
            if not d.back():        # a sub-screen to its tab, a tab to Status
                self._save_docked()
                self.mode = "menu"
            return
        if hit(BTN_MENU):
            self._launch()
            return
        for key, tab in DOCK_KEYS:      # Elite's f0-f9 on the number row
            if hit(key):
                if tab == "LAUNCH":
                    self._launch()
                elif tab == "SELL" and "MARKET" in d.tabs:
                    d.go(d.tabs.index("MARKET"))
                    have = [i for i, n in enumerate(self.cmdr.cargo) if n]
                    if have:            # Elite's Sell Cargo: start on what you carry
                        d.pick_good(have[0] - d.sel)
                elif tab in d.tabs or tab == "OPTIONS":
                    d.open(tab)
                return
        if hit(BTN_SPEED_DOWN):
            d.go(d.tab - 1)
            return
        if hit(BTN_BOMB):
            d.go(d.tab + 1)
            return
        if d.view is not None and d.cursor:
            if confirm:
                d.pick()
                self.target = d.target
            elif (hit(BTN_MISSILE)) or hit("k_D"):
                d.show(d.view.picked())     # its data; the target stays as it was
            else:
                jx, jy = self._steer(False, STICK, True)
                d.view.move(jx, jy, dt)
            return
        if d.view is not None:              # the joystick changes tab (below) until C
            if confirm:
                d.use_cursor(True)
                return
            if (hit(BTN_MISSILE)) or hit("k_D"):
                d.show(d.view.picked())
                return
        if hit("j_left"):
            d.go(d.tab - 1)
        elif hit("j_right"):
            d.go(d.tab + 1)
        elif d.name() == "EQUIP SHIP":
            if self._repeat("j_up", dt):
                d.pick_item(-1)
            elif self._repeat("j_down", dt):
                d.pick_item(1)
            elif hit("C"):
                d.buy_item()
            elif (hit(BTN_MISSILE)) or hit("k_D"):
                d.next_mount()      # which view a laser is fitted to
        elif d.name() == "REPAIR SHOP":
            if hit("j_up"):
                d.pick_paint(-1)
            elif hit("j_down"):
                d.pick_paint(1)
            elif hit("C"):
                d.buy_paint()
            elif hit(BTN_MISSILE) or hit("k_D"):
                d.buy_transponder()      # a stolen ship, on a pirate world (build 84)
        elif d.name() == "SHIPYARD":
            if hit("j_up"):
                d.pick_ship(-1)
            elif hit("j_down"):
                d.pick_ship(1)
            elif hit("C"):
                d.open_stats()      # any page: that ship's stats (and buying, for one for sale)
            elif (hit(BTN_MISSILE) or hit("k_D")) and d.ysel == 0:
                d.open("REPAIR SHOP")       # your own ship: the Repair Shop (build 82: on D)
        elif d.name() == "SHIP STATS":
            if d.ysel and hit("C"):
                d.buy_ship(False)       # the one you fly goes into the hangar
            elif d.ysel and (hit(BTN_MISSILE) or hit("k_D")):
                d.buy_ship(True)        # trade it in
        elif d.name() == "HANGAR":
            if hit("j_up"):
                d.pick_owned(-1)
            elif hit("j_down"):
                d.pick_owned(1)
            elif hit("C"):
                d.fly_owned()
            elif hit(BTN_MISSILE) or hit("k_D"):
                d.sell_owned()
        elif d.name() == "OPTIONS":
            if hit("j_up"):
                d.pick_option(-1)
            elif hit("j_down"):
                d.pick_option(1)
            elif hit("C"):
                d.change_option()
        elif d.name() == "SYSTEM DATA" and ((hit(BTN_MISSILE)) or hit("k_D")):
            d.back_to_chart()       # D: back to the chart you came from
        elif d.name() == "INVENTORY":
            if self._repeat("j_up", dt):
                d.scroll_inventory(-1)
            elif self._repeat("j_down", dt):
                d.scroll_inventory(1)
            elif hit("C"):
                d.sell_all()        # the whole hold at this station's prices
                d.scroll_inventory(0)
        elif d.name() == "MARKET":
            # the joystick picks a good; C buys and D sells; all repeat when held
            if self._repeat("j_up", dt):
                d.pick_good(-1)
            elif self._repeat("j_down", dt):
                d.pick_good(1)
            elif self._repeat("C", dt):
                d.trade(True)
            elif self._repeat(BTN_MISSILE, dt):
                d.trade(False)
        elif confirm and d.name() == "STATUS":
            if d.options:
                d.open("OPTIONS")   # A launches (Brian), so C is Options
            else:
                self._launch()

    def _repeat(self, name, dt):
        """True when button name is pressed, and again and again while it is
        held: after REPEAT_WAIT, every REPEAT_EVERY seconds."""
        pad = self.pad
        if pad.hit(name):
            self.held_t[name] = 0.0
            return True
        if name not in self.held_t:
            return False
        if not pad.held(name):
            del self.held_t[name]
            return False
        t = self.held_t[name] + dt
        if t >= REPEAT_WAIT:
            self.held_t[name] = t - REPEAT_EVERY
            return True
        self.held_t[name] = t
        return False

    def _sound_ok(self):
        """The device can play sounds (Platform.sound: the Pi, the badge's I2S)."""
        return getattr(self.platform, "sound_ok", False)

    def _play(self, name):
        """One of sfx.py's sounds, if the device has sound and SOUND is ON."""
        if self.use_sound and self._sound_ok():
            self.platform.sound(name)

    def _apply_volume(self):
        """Options > VOLUME to the device, if it has one (build 145)."""
        if hasattr(self.platform, "set_volume"):
            self.platform.set_volume(self.volume)

    def _sounds(self):
        """Each frame: the flight's sounds (Game.sfx) to the device, and its
        player moved on (the badge's I2S writes what plays next)."""
        g = self.game
        if g is not None and g.sounds:
            if self.mode == "flight" and not self.paused:
                for name in g.sounds:
                    self._play(name)
            del g.sounds[:]
        if self._sound_ok():
            self.platform.sound_step()

    def _forget_flight(self):
        """A new commander starts with nothing left from before (Brian, build 138):
        no flight carried on (its rules, docking style, ship, kills), no target,
        jump, witchspace, open screen or chart, and nothing banked. Kept: the
        settings (options.json) and the tilt sensor's level. The galaxy goes
        too (Brian): the new commander's, the first, is made afresh."""
        self.game = None
        self.galaxy = None
        self.galaxy_n = 0
        self.find_names = None
        self.career = False     # an old commander's flight banks nothing into it
        self.docked = True
        self.banked = 0
        self.banked_cash = 0
        self.saved = None
        self.saved_over = False
        self.just_saved = False
        self.paused = False
        self.fmenu = 0
        self.fsub = None
        self.top = 0
        self.fmarket = None
        self.chart = None
        self.data_of = None
        self.finder = None
        self.tdialog = None
        self.find_chart = None
        self.target = None
        self.jump_to = None
        self.witch = None
        self.misjump = False
        self.brief = None
        self.eject_t = 0.0
        self.fire_lock = False
        self.dgroup = None
        self.debug_from = None
        self.dock = None
        self.tunnel = None
        self.glow = 0.0
        self.jump_leds = [0.0] * 13
        self.jump_lit = False
        self._bps = {}

    def _hardcore(self):
        """The commander's HARDCORE (picked with them, fixed but for DEBUG)."""
        return self.cmdr is not None and bool(self.cmdr.hardcore)

    def _manual_docking(self):
        """Hardcore: docking is by hand only. In a flight, the rules it started with;
        elsewhere the commander's HARDCORE (which a flight takes up when it starts)."""
        if self.game is not None and self.mode == "flight":
            return self.game.rules.manual_docking
        return self._hardcore()

    def _fit(self, g):
        """A fresh career flight: the commander's ship as equipped."""
        c = self.cmdr
        if c is None:
            return
        g.set_ship(self._ship_name(), ships.pylons(self._ship_name()))
        g.missiles = min(c.missiles, g.max_missiles) if g.missile_bp else 0
        mounts = ships.mounts(self._ship_name())
        for view in range(4):
            g.set_laser((c.lasers[view] or None) if view < mounts or view == 0 else None, view)
        g.energy_unit = "energy" in c.extras or "navy" in c.extras
        g.navy = "navy" in c.extras
        g.fuel_scoops = "scoops" in c.extras
        g.ecm = "ecm" in c.extras
        g.pod = "pod" in c.extras
        g.bombs = 1 if "bomb" in c.extras else 0
        g.computer = "docking" in c.extras
        g.ship_rgb = cockpit.ship_rgb(c.colour)     # for the view from behind your ship
        g.fuel_max = c.max_fuel()   # the fuel gauge's full tank (0: no hyperdrive)
        g.legal = c.legal
        g.stolen = c.stolen         # lawful police may spot a stolen ship (build 84)
        self._hot()

    def _hot(self):
        """A stolen ship keeps you an offender while you fly it (Brian, build
        84): jumps and the escape pod clear your record no further than
        ships.STOLEN_LEGAL. The galactic hyperdrive clears the ship too (85)."""
        c = self.cmdr
        if c is None or not c.stolen:
            return
        c.legal = max(c.legal, ships.STOLEN_LEGAL)
        g = self.game
        if g is not None and self.career:
            g.legal = max(g.legal, ships.STOLEN_LEGAL)

    def _refuel(self, n):
        """Fuel skimmed from the sun: n tenths of a light year into the tank.
        Returns how many fitted (see Game.refuel)."""
        c = self.cmdr
        n = min(n, c.max_fuel() - c.fuel)
        c.fuel += n
        self.game.fuel = c.fuel
        return n

    def _scoop(self, i):
        """A canister scooped in flight: good i into the hold (see Game.scoop)."""
        from . import market
        return market.scoop(self.cmdr, GOODS, i)

    def _save_docked(self):
        """Save what was bought and sold while docked (not in Hardcore: only
        SAVE COMMANDER saves there, build 133)."""
        self._auto_write()

    def _auto_write(self):
        """A save the game makes by itself: none in Hardcore (rules.manual_save)."""
        if not self._hardcore():
            self._write()

    def _save_now(self):
        """Options > SAVE COMMANDER (Hardcore, docked): it then reads COMMANDER SAVED."""
        self._write()
        self.just_saved = True

    def _write(self):
        """Save the commander, and keep a copy of what was saved: being
        destroyed goes back to it (see _restore). Only done at a station, as
        in the original, where you could save only while docked."""
        c = self.cmdr
        if c is None:
            return
        c.data = DATA_TAG
        self.saved = json.dumps(c.to_dict())
        c.save(SAVE_PATH)

    def _write_setting(self, key, value):
        """Change one setting in the last save, without saving the flight so far."""
        if self.saved is None:
            return
        d = json.loads(self.saved)
        d[key] = value
        self.saved = json.dumps(d)
        commander.Commander.from_dict(d).save(SAVE_PATH)

    def _restore(self):
        """Destroyed: as in the original, everything since the last save is
        lost. The commander goes back to how they were when last saved (docked
        at a station), and this flight's kills, bounties and used missiles are
        written off so that nothing more is banked from it. (With an escape
        pod only the cargo is lost: see _update_flight.)"""
        if self.saved is not None:
            self.cmdr = commander.Commander.from_dict(json.loads(self.saved))
        else:                   # never saved: lose the cargo at least
            self.cmdr.cargo = [0] * commander.GOODS
        c = self.cmdr
        g = self.game
        self.banked = g.kills
        self.banked_cash = g.bounty
        g.missiles = c.missiles
        g.fuel = c.fuel
        g.legal = c.legal       # nothing more from the dead flight
        self.witch = None       # back where you last saved
        self.target = None
        self.jump_to = None

    def _pick_tunnel(self, pod=False):
        """This station's tunnel: its slot's shape and its own ring spacing, from its
        system, with ships parked in the bay that suit the system. Flying through
        it: the ship you fly, or with pod the escape pod (Brian: after the pod
        is used, the docking scene shows the pod coming in)."""
        c = self.cmdr
        seed = 0
        station = "CORIOLIS"
        if c is not None and c.system is not None:
            seed = c.system
            if self.galaxy is not None and self.galaxy.system(seed).tech >= game.DODO_TECH:
                station = "DODO"
        self.tunnel = cockpit.Tunnel(seed, station)
        # ships parked in the bay, the kinds this system would have
        gov = tech = None
        if c is not None and c.system is not None and self.galaxy is not None:
            s = self.galaxy.system(seed)
            gov, tech = s.government, s.tech
        if self.game is not None:
            types = self.game.types
        else:
            types = {e[0]: game.Blueprint(e) for e in SHIPS} if SHIPS else {}
        if types:
            if pod:
                self.tunnel.fly(types.get("ESCAPE POD"), cockpit.ME_RGB)
            else:
                self.tunnel.fly(types.get(self._ship_name()),      # your ship, seen from behind
                                cockpit.ship_rgb(c.colour if c is not None else 0))
            self.tunnel.park([types[n] for n in game.parked_ships(gov, tech) if n in types],
                             random)

    def _launch(self):
        self._play("launch")
        self._save_docked()
        self._pick_tunnel()
        self.launch_t = 0.0
        self.dock = None
        self.mode = "launch"

    def _jump_ok(self):
        """The hyperspace target, if the fuel will reach it: (system, distance)."""
        if self.target is None or self.galaxy is None or not self.career:
            return None
        if self.witch is not None:      # from where you are, between systems
            d = self.galaxy.distance_xy(self.witch[0], self.witch[1], self.target)
        else:
            d = self.galaxy.distance(self.cmdr.system, self.target)
        if 0 < d <= self.cmdr.fuel:
            return self.target, d
        return None

    def _arrive(self):
        """The game has just jumped: move the commander and use the fuel.
        Not saved: as in the original, only docking saves."""
        g = self.game
        g.jumped = False
        if self.fsub in SCREENS:    # out of hyperspace looking at space, as Elite
            self._resume()
        to = self.jump_to
        self.jump_to = None
        c = self.cmdr
        if to is None or not self.career or c is None or self.galaxy is None:
            return
        if to[0] == "galaxy":   # the galactic hyperdrive: the next galaxy, no fuel used
            from . import galaxy
            c.galaxy = (c.galaxy + 1) % 8
            self._extra(c, "hyperdrive", False)     # used up
            g.legal = 0         # a new galaxy: a clean record, as in the original
            c.stolen = g.stolen = False     # and a clean ship: nobody knows it there (build 85)
            self._place()
            c.system = self.galaxy.nearest(*galaxy.GAL_ARRIVE)
            c.docked_at = None  # nowhere docked in this galaxy yet
            to = (c.system, 0)
        elif self.witch is None and (self.misjump or random.random() < game.MISJUMP_ODDS):
            # a mis-jump (MJP): the fuel is used, but you end up in witchspace,
            # short of the target and above or below it on the chart
            self.misjump = False
            c.fuel = max(0, c.fuel - to[1])
            self.witch = (self.galaxy.xs[to[0]], self.galaxy.ys[to[0]] ^ 31)
            g.witchspace()
            return
        self.witch = None
        c.system = to[0]
        c.fuel = max(0, c.fuel - to[1])
        g.legal //= 2           # a jump halves your legal status
        self._hot()             # but not below an offender's in a stolen ship
        c.market = None         # a new system: its market is worked out on docking
        self.target = None
        self._enter_space("arrive")
        g.say(self.galaxy.system(c.system).name, 3.0)

    def _bank(self):
        """Give the commander the kills and bounties made since the last call.
        A bounty shows the new cash, as in the original; a new rank shows instead."""
        g = self.game
        if g is None or not self.career or self.cmdr is None:
            return
        c = self.cmdr
        c.missiles = g.missiles             # the ones fired are gone
        if g.got_constrictor:               # mission 1: tell the Navy when you next dock
            g.got_constrictor = False
            c.mission = missions.killed(c.mission)
        c.legal = g.legal
        g.bad = game.bad(c.cargo)           # contraband: the police look for it
        g.fuel = c.fuel                     # for the HUD
        paid = g.bounty - self.banked_cash
        if paid > 0:
            c.cash += paid
            self.banked_cash = g.bounty
            if not g.over and g.jump_t <= 0:    # the hyperspace countdown matters more
                g.say(c.cash_text(), 1.5)
        if g.kills > self.banked:
            rank = c.add_kills(g.kills - self.banked)
            self.banked = g.kills
            if rank and not g.over:
                g.say("RANK: " + rank, 3.0)

    def _to_title(self):
        """To the title screen. Nothing is saved: a flight left part-way
        carries on with CONTINUE until the app is closed."""
        self.paused = False
        self.fsub = None
        self.mode = "menu"

    def _perf(self, delta, update_ms):
        """Every PERF_LOG flight frames, print where the time went.

        A frame counts as slow if it took PERF_SLOW ms longer than the last
        window's average; the line lists how long each slow one took (up to
        8). Nothing here forces a garbage collection, so a slow frame is the
        badge's own doing. Printing and reading the heap size take a while,
        so the frame after each line is left out."""
        if self.p_skip:
            self.p_skip = False
            return
        self.p_n += 1
        self.p_frame += delta
        if delta > self.p_max:
            self.p_max = delta
        if delta > self.p_avg + PERF_SLOW:
            self.p_nslow += 1
            if len(self.p_slow) < 8:
                self.p_slow.append(int(delta))
        self.p_update += update_ms
        if self.p_n >= PERF_LOG:
            n = self.p_n
            self.p_avg = self.p_frame / n
            t0 = _us()
            used = getattr(gc, "mem_alloc", lambda: 0)()
            free = getattr(gc, "mem_free", lambda: 0)()
            mem_ms = _diff(_us(), t0) / 1000.0
            ts = cockpit.T_SPACE
            space = ts[0] / 1000.0 / n if ts is not None else 0.0
            if ts is not None:
                ts[0] = 0
            print("PERF frame %.0f max %.0f update %.1f rules %.1f draw %.1f (world %.1f space %.1f"
                  " hud %.1f) objs %d fast %d slow %d %s used %d free %d memcall %.1f" % (
                      self.p_avg, self.p_max, self.p_update / n, self.p_rules / n,
                      self.p_draw / n, self.p_world / n, space, self.p_hud / n,
                      len(self.game.objs), 1 if self.fast else 0,
                      self.p_nslow, self.p_slow, used, free, mem_ms))
            self.p_n = 0
            self.p_nslow = 0
            self.p_slow = []
            self.p_skip = True
            self.p_frame = self.p_max = self.p_update = self.p_rules = self.p_draw = 0.0
            self.p_world = self.p_hud = 0.0

    def _update_viewer(self, dt, cancel, confirm):
        v = self.viewer
        pad = self.pad
        if cancel:
            self.mode = "menu"
            return
        if confirm or pad.hit("k_N"):
            v.switch(1)
            self.zero = None
        elif pad.hit("k_P"):
            v.switch(-1)
            self.zero = None
        jx, jy = self._steer(self.use_tilt, ANY, False)
        v.step(dt, jx, jy)

    def _update_flight(self, dt, cancel, confirm):
        """Returns True if the game moved on a step."""
        pad = self.pad
        hit = pad.hit
        held = pad.held
        g = self.game
        menu = hit(BTN_MENU)
        # Elite's docking computer keys (Brian): C on, P off. P is the pause menu
        # otherwise. Read in any view, as Elite's main loop reads them.
        if hit("k_P"):
            if g.autodock and not self.paused:
                g.stop_autodock()
            else:
                menu = True
        if hit("k_C") and not g.over and not g.autodock and not self.paused:
            why = g.start_autodock()
            if why:
                g.say(why, 1.0)

        if g.over and g.ejected:
            # the escape pod: the ship and its cargo are lost, the pod is used
            # up, and you wake up docked at this system's station with a full
            # tank, as in the original
            if not self.saved_over:
                self.saved_over = True
                self.eject_t = 0.0
                c = self.cmdr
                if self.career and c is not None:
                    c.cargo = [0] * commander.GOODS
                    self._extra(c, "pod", False)
                    c.fuel = c.max_fuel()
                    c.legal = g.legal = 0       # the original's pod clears your record too
                    self._hot()                 # (not the ship's: it is insured, still stolen)
                    self.jump_to = None
                # nothing else since the last save is lost; docking saves it
            self.eject_t += dt
            if self.career and (confirm or self.eject_t >= EJECT_TIME):
                g.ejected = False
                self._fly_in(True)  # the pod is taken in: the docking tunnel, then docked
            elif not self.career and confirm:   # practice has no station: fly again
                g.reset()
                self.banked = 0
                self.banked_cash = 0
                self.saved_over = False
                self.zero = None
            elif cancel:
                self._to_title()
            else:
                g.step(dt, 0.0, 0.0, 0.0, False, False)
            return False
        if g.over:
            if not self.saved_over:
                self.saved_over = True
                if self.career and self.cmdr is not None:
                    self._restore()     # back to the last save, as in the original
            if confirm and self.career:
                self._dock()
            elif confirm:
                g.reset()
                self.jump_to = None
                self.banked = 0
                self.banked_cash = 0
                self.saved_over = False
                self.zero = None
            elif cancel:
                self._to_title()
            else:
                g.step(dt, 0.0, 0.0, 0.0, False, False)   # let the wreckage drift
            return False
        if self.paused:
            if not self._screen_keys():
                self._update_fmenu(menu, cancel, confirm)
            return False
        if menu:
            self.paused = True
            self.fmenu = 0
            self.fsub = None
            self.chart = None
            self.d_t = None
            g.looking = True
            return False
        self._screen_keys()
        # a screen up (status, market, a chart...): the game runs on, as Elite's
        # does, but the joystick and buttons work the screen and only Elite's
        # primary flight controls (steer, speed, fire) still fly, from the
        # keyboard or by tilting; lasers fire but can't hit (Game.looking)
        busy = self.fsub in SCREENS
        if busy:
            self._update_screen(cancel, confirm)
        g.looking = self.fsub not in SCREENS

        tilt = self.use_tilt and self.tilt_ok
        throttle = 0.0
        missile = False
        if busy:                # the keyboard's W / A / S / D, or tilt
            roll, jy = self._steer(tilt, None, False)
        else:                   # joystick steers; lettered buttons do the rest
            if held(BTN_SPEED_UP):
                throttle += 1.0
            if held(BTN_SPEED_DOWN):
                throttle -= 1.0
            if not tilt:
                self.d_t = None
                if hit(BTN_MISSILE):
                    if g.rules.missile_lock_required and not g.armed:
                        g.arm_missile()         # Hardcore: D arms first, then fires
                    else:
                        missile = True
            else:               # a tap on D re-zeroes the tilt, holding it fires
                if hit(BTN_MISSILE):
                    self.d_t = 0.0
                if self.d_t is not None:
                    if held(BTN_MISSILE):
                        self.d_t += dt
                        if self.d_t >= HOLD_MISSILE:
                            missile = True
                            self.d_t = None
                    else:
                        self.zero = None
                        self.d_t = None
            if hit(BTN_BOMB) and g.energy_bomb() and self.career and self.cmdr is not None:
                self._extra(self.cmdr, "bomb", False)     # used up
            roll, jy = self._steer(tilt, STICK, True)
        yaw = 0.0
        an = self.analog
        if an is not None:      # a host's analogue pad: added to the rest
            roll = max(-1.0, min(1.0, roll + an.roll))
            jy = max(-1.0, min(1.0, jy + an.pitch))
            yaw = an.yaw
            if an.speed is not None and not g.autodock:
                # the stick's place is the speed; right at the top it holds
                # speed up, so at full speed it is the jump drive (as J)
                if an.speed >= 0.98:
                    throttle += 1.0
                else:
                    want = an.speed * g.max_speed
                    throttle += max(-1.0, min(1.0, (want - g.speed) / (game.THROTTLE_RATE * max(dt, 0.001))))
            if g.autodock and not busy and max(abs(an.roll), abs(an.pitch), abs(an.yaw)) > 0.5:
                g.stop_autodock()   # taking the controls, as _took_controls
        if self.tilt_flip & 1:      # the CONTROLS setting (build 87: every way of steering)
            jy = -jy
        if self.tilt_flip & 2 and self.tilt_ok:     # (without tilt only PITCH is offered)
            roll = -roll
            yaw = -yaw
        if g.rules.manual_ecm:      # Hardcore: E is the ECM (or both speed buttons together)
            if not busy and (hit("k_E") or (hit(BTN_SPEED_UP) and held(BTN_SPEED_DOWN))
                             or (hit(BTN_SPEED_DOWN) and held(BTN_SPEED_UP))):
                g.fire_ecm()
        elif held("k_E"):
            throttle += 1.0
        if held("k_Q"):
            throttle -= 1.0
        # + / - in every mode (in Hardcore E is the ECM); J holds speed up, which
        # at full speed with no ships about is the jump drive (Elite's J)
        if held("k_faster") or (held("k_J") and not busy):
            throttle += 1.0
        if held("k_slower"):
            throttle -= 1.0
        if not busy:            # Elite's secondary keys: only looking at space
            if g.rules.missile_lock_required:       # Hardcore: T arms and locks, U disarms
                if hit("k_T"):
                    g.arm_missile()
                if hit("k_U"):
                    g.unarm_missile()
            if hit("k_M"):
                missile = True
            # Elite's TAB; Backspace too, which an unpatched Keyboard Hexpansion
            # sends where it drops Tab (Brian)
            if ((hit("k_TAB") or hit("k_BACKSPACE")) and g.energy_bomb() and self.career
                    and self.cmdr is not None):
                self._extra(self.cmdr, "bomb", False)     # used up
            if hit("k_ESCAPE"):
                g.eject()           # Elite's ESCAPE: the escape pod (Esc is still back on menus)
            for n in range(4):      # the views, on a keyboard (both modes)
                if hit("k_view%d" % n):
                    g.set_view(n)
            if hit("k_V"):
                g.next_view()
        fire = held("confirm") and not busy
        if self.fire_lock:      # the C held on from a menu or the launch: fire once it is let go
            if fire:
                fire = False
            else:
                self.fire_lock = False
        # Space and F fire too (not locked: they never choose anything, so
        # one held through closing a screen keeps firing)
        fire = fire or held("k_F") or held("k_SPACE")
        if g.autodock and not busy and self._took_controls():
            g.stop_autodock()       # taking the controls switches the docking computer off
        pitch = jy if INVERT_PITCH else -jy
        t0 = _us()
        g.step(dt, pitch, roll, max(-1.0, min(1.0, throttle)), fire, missile, yaw)
        rules = _diff(_us(), t0) / 1000.0
        self.t_step += (rules - self.t_step) * 0.1
        self.p_rules += rules
        if g.jumped:
            self._arrive()
        if self.career:
            self._bank()
            if g.docked:        # flown in: the tunnel, then the docked screens
                g.docked = False
                self._fly_in()
        return True

    def _took_controls(self):
        """A fresh press of a flight control (not one still held from choosing
        DOCKING COMPUTER in the menu, and not tilting the badge): the
        docking computer hands back control."""
        hit = self.pad.hit
        for name in (STICK):
            if hit(name):
                return True
        if (hit(BTN_SPEED_UP) or hit(BTN_SPEED_DOWN) or hit(BTN_MISSILE)):
            return True
        for name in ("confirm", "k_E", "k_Q", "k_F", "k_SPACE", "k_M"):
            if hit(name):
                return True
        return False

    def _ship_name(self):
        """The ship you fly, by Elite's name (the game's own design for that role
        with DATA: OWN): the commander's (ships.py, build 78), the Cobra Mk III
        without one. The scenes and the Repair Shop all ask here."""
        c = self.cmdr
        if c is not None and ships.known(c.ship):
            return c.ship
        return ships.COBRA

    def _ship_bp(self):
        """Your ship's blueprint, or None without ship data."""
        return self._bp(self._ship_name())

    def _bp(self, name):
        """A ship type's blueprint, or None without ship data."""
        if self.game is not None:
            return self.game.types.get(name)
        bp = self._bps.get(name)
        if bp is None:
            for e in SHIPS or ():
                if e[0] == name:
                    bp = self._bps[name] = game.Blueprint(e)
                    break
        return bp

    def _fly_in(self, pod=False):
        """The docking scene: in through the station's tunnel, a while in the
        bay, then the docked screens (see update, mode "docking"). pod: it is
        the escape pod coming in."""
        self._bank()
        self.dock_t = 0.0
        self.dock_hold = random.uniform(*DOCK_HOLD)
        self._pick_tunnel(pod)
        self.mode = "docking"
        self._play("dock")

    # ---- in-flight menu ---------------------------------------------------

    def _settings(self, cmdr):
        """The settings, shared by the in-flight Settings page and the title
        screen's Options page. cmdr: include the commander's own (docking
        style and the Constrictor)."""
        if self.tilt_ok:
            items = ["STEER: " + ("TILT" if self.use_tilt else "JOYSTICK"),
                     "CONTROLS: " + TILT_FLIPS[self.tilt_flip]]
        else:   # no tilt sensor (the Pi, the Tufty): nothing to choose but the pitch (build 136)
            items = ["PITCH: " + ("SWAPPED" if self.tilt_flip & 1 else "NORMAL")]
        if cmdr and self.mode == "docked" and self._hardcore():   # no saving by itself (build 133)
            # once saved it says so (Brian, build 135), until Options is left
            items.insert(0, "COMMANDER SAVED" if self.just_saved else "SAVE COMMANDER")
        if cmdr and self.cmdr is not None and self.mode != "flight":
            items.append("NAME: " + cmdr_name(self.cmdr).upper())     # build 89
        if cmdr and self.cmdr is not None:
            items.append("DOCKING: " + DOCK_NAMES["A" if self._manual_docking() else self.cmdr.docking])
            items.append("CONSTRICTOR: " + ("2 MIN" if self.cmdr.quick_con else "ORIGINAL"))
        if self.platform.leds:
            items.append("LEDS: " + ("ON" if self.use_leds else "OFF"))
        if self._sound_ok():        # the Pi, or the badge's I2S (builds 140, 145)
            items.append("SOUND: " + ("ON" if self.use_sound else "MUTED"))
            if self.use_sound and hasattr(self.platform, "set_volume"):    # (build 145)
                items.append("VOLUME: %d" % self.volume)
            port = getattr(self.platform, "sound_port", None)
            if port is not None and self.use_sound:     # where the I2S amp is (build 145)
                items.append("SOUND PORT: %d" % port)
        if getattr(self.platform, "picker_choice", False):    # the badge: its own or the picker
            items.append("TEXT ENTRY: " + ("PICKER" if self.use_picker else "BADGE"))
        if HAVE_ELITE_SHIPS and self.mode != "flight":     # whose data, from the next start
            items.append("DATA: " + ("OWN" if self.own_ships else "ELITE")
                         + ("" if self.own_ships == ORIGINAL_SHIPS else " (RESTART)"))
        if DEBUG_MENU:
            items.append("DEBUG")
        return items

    def _change(self, item, left):
        """Change one setting: left goes back a choice, anything else on.
        DEBUG opens the cheats: in flight its page of the in-flight menu,
        elsewhere a page of its own that comes back here."""
        if item == "DEBUG":
            if left:
                return
            if self.mode == "flight":
                self.fsub = "debug"
                self.debug_from = "settings"
                self.fmenu = 0
            else:
                self.od_from = self.mode
                self.od_page = None
                self.od_sel = 0
                self.od_msg = None
                self.mode = "odebug"
        elif item in ("SAVE COMMANDER", "COMMANDER SAVED"):
            if not left:
                self._save_now()
        elif item.startswith("NAME"):
            if not left:
                self._open_name(self.cmdr.name, self._set_name)
        elif item.startswith("PITCH"):     # no tilt sensor: up / down swapped or not
            self.tilt_flip = (self.tilt_flip & 1) ^ 1
            self._save_options()
        elif item.startswith("CONTROLS"):  # left goes back a choice
            self.tilt_flip = (self.tilt_flip + (-1 if left else 1)) % len(TILT_FLIPS)
            self._save_options()
        elif item.startswith("STEER"):
            if self.tilt_ok:
                self.use_tilt = not self.use_tilt
                self.zero = None
                self._save_options()
        elif item.startswith("CONSTRICTOR"):
            c = self.cmdr       # how soon mission 1's Constrictor turns up at Orarra
            c.quick_con = not c.quick_con
            if self.game is not None and self.galaxy is not None and c.system is not None:
                self._mission_flags()
            self._write_setting("quick_con", c.quick_con)
        elif item.startswith("DOCKING"):
            if self._manual_docking():
                return          # Hardcore: only by hand (or a docking computer)
            c = self.cmdr       # A, B, C, A going on; left goes back
            i = commander.DOCKING.index(c.docking) + (-1 if left else 1)
            c.docking = commander.DOCKING[i % len(commander.DOCKING)]
            if self.game is not None:
                self.game.set_docking(c.docking)
            self._write_setting("docking", c.docking)
        elif item.startswith("DATA"):
            self.own_ships = not self.own_ships
            self._save_options()
        elif item.startswith("LEDS"):
            self.use_leds = not self.use_leds
            if not self.use_leds:
                self._leds_release()
            self._save_options()
        elif item.startswith("SOUND PORT"):    # 1-6, left back (build 145)
            p = self.platform
            p.set_sound_port((p.sound_port - 1 + (-1 if left else 1)) % 6 + 1)
            self._save_options()
            self._play("beep")      # heard if the amp is on this port
        elif item.startswith("VOLUME"):        # 1-11, left quieter; stops at the ends
            v = max(1, min(VOLUME_MAX, self.volume + (-1 if left else 1)))
            if v != self.volume:
                self.volume = v
                self._apply_volume()
                self._save_options()
            self._play("beep")      # at the new volume
        elif item.startswith("SOUND"):
            self.use_sound = not self.use_sound     # ON / MUTED
            self._save_options()
            if self.use_sound:
                self._play("beep")
            elif hasattr(self.platform, "sound_stop"):
                self.platform.sound_stop()          # muted: at once
        elif item.startswith("TEXT ENTRY"):
            self.use_picker = not self.use_picker
            self._save_options()

    def _load_options(self):
        try:
            with open(options_path()) as f:
                d = json.loads(f.read())
        except Exception:
            return
        if isinstance(d, dict):
            if isinstance(d.get("tilt"), bool):
                self.use_tilt = d["tilt"] and self.tilt_ok
            if isinstance(d.get("leds"), bool):
                self.use_leds = d["leds"]
            if isinstance(d.get("picker"), bool):
                self.use_picker = d["picker"]
            if isinstance(d.get("sound"), bool):
                self.use_sound = d["sound"]
            v = d.get("volume")
            if isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= VOLUME_MAX:
                self.volume = v
                self._apply_volume()
            sp = d.get("sound_port")
            if (isinstance(sp, int) and not isinstance(sp, bool) and 1 <= sp <= 6
                    and getattr(self.platform, "sound_port", None) is not None):
                self.platform.set_sound_port(sp)
            k = d.get("tilt_flip")
            if isinstance(k, int) and not isinstance(k, bool) and 0 <= k < len(TILT_FLIPS):
                self.tilt_flip = k
            if isinstance(d.get("hardcore"), bool):
                self.old_hardcore = d["hardcore"]
            if isinstance(d.get("practice_hardcore"), bool):
                self.p_hardcore = d["practice_hardcore"]
            p = d.get("practice_level")
            if isinstance(p, int) and not isinstance(p, bool) and 0 <= p < len(commander.LEVELS):
                self.p_level = p
            if isinstance(d.get("egg"), int) and isinstance(d.get("egg_miss"), int):
                self.egg, self.egg_miss = d["egg"], d["egg_miss"]
            own = d.get("own", d.get("own_ships"))
            if isinstance(own, bool):
                self.own_ships = own

    def _save_options(self):
        try:
            with open(options_path(), "w") as f:
                f.write(json.dumps({"tilt": self.use_tilt, "tilt_flip": self.tilt_flip,
                                    "leds": self.use_leds, "picker": self.use_picker,
                                    "sound": self.use_sound,
                                    "volume": self.volume,
                                    "sound_port": getattr(self.platform, "sound_port", None),
                                    "practice_level": self.p_level,
                                    "practice_hardcore": self.p_hardcore,
                                    "own": self.own_ships, "egg": self.egg,
                                    "egg_miss": self.egg_miss, "debug": DEBUG_MENU}))
        except Exception:
            pass

    def _update_options(self, cancel, confirm):
        """The title screen's Options page: joystick up / down picks, left /
        right or C changes, F goes back to the title screen."""
        hit = self.pad.hit
        items = self._settings(True)
        self.omenu %= len(items)
        if cancel:
            self.mode = "menu"
        elif hit("j_up"):
            self.omenu = (self.omenu - 1) % len(items)
        elif hit("j_down"):
            self.omenu = (self.omenu + 1) % len(items)
        else:
            left = hit("j_left")
            if confirm or left or hit("j_right"):
                self._change(items[self.omenu], left)

    def _draw_options(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "OPTIONS", 0, -80, 20, cockpit.WHITE)
        items = self._settings(True)
        # eight lines fit above the hints; more scroll (build 131)
        y = cockpit.menu_lines(ctx, items, self.omenu % len(items), -50, 16, 8)
        if self.cmdr is None:
            text(ctx, "more with a commander", 0, y + 4, 11, cockpit.GREY)
        text(ctx, "< > or C: change", 0, 82, 11, cockpit.GREY)     # below six lines
        text(ctx, "F: back", 0, 96, 11, cockpit.GREY)

    def _fitems(self):
        """The lines on the current page of the in-flight menu."""
        if self.fsub == "settings":
            return self._settings(self.career)
        if self.fsub == "debug":
            return self._cheat_groups(True)
        if self.fsub == "dgroup":
            if self.dgroup == "SHIP":   # the ship cheats, then its equipment
                return self._cheats("SHIP", True) + self._ship_items()
            return self._cheats(self.dgroup, True)
        return self._fitems_top()

    # ---- DEBUG, in groups ---------------------------------------------------

    def _cheat_ok(self, key, flying):
        if flying:
            if self.career:
                return key != "NEXT WAVE"       # waves are for combat practice
            return key not in CAREER_ONLY       # no commander: no cash, traffic or legal status
        if key == "GAMEPAD":        # a device whose platform can switch its gamepad (the Tufty's)
            return getattr(self.platform, "gamepad", None) is not None
        if key == "TO MISSION SYSTEM":      # docked: moved there and docked again
            return self.cmdr is not None and (self.mode == "docked" or self.od_from == "docked")
        if key not in OFF_FLIGHT:
            return False
        return self.cmdr is not None or key in NO_COMMANDER

    def _cheat_label(self, key, flying):
        """A cheat's line, with its current value where it has one."""
        g = self.game
        c = self.cmdr
        onoff = lambda b: "ON" if b else "OFF"
        if key == "INVINCIBLE":
            return "INVINCIBLE: " + onoff(g.god)
        if key == "LEVEL":
            return "LEVEL: " + commander.LEVELS[g.level if flying else c.level]
        if key == "HARDCORE":
            return "HARDCORE: " + onoff(self._hardcore())
        if key == "FRAME TIME":
            return "FRAME TIME: " + onoff(self.show_ms)
        if key == "GAMEPAD":
            return "GAMEPAD: " + onoff(getattr(self.platform, "gamepad", None))
        if key == "MIS-JUMP NEXT":
            return "MIS-JUMP NEXT: " + onoff(self.misjump)
        if key == "LEGAL":
            return "LEGAL: " + game.legal_name(g.legal if flying else c.legal)
        if key == "MISSION":
            return "MISSION: " + missions.stage_name(c.mission if c else 0)
        return key

    def _cheats(self, group, flying):
        for name, keys in DEBUG_GROUPS:
            if name == group:
                return [self._cheat_label(k, flying) for k in keys if self._cheat_ok(k, flying)]
        return []

    def _cheat_groups(self, flying):
        return [name for name, keys in DEBUG_GROUPS
                if any(self._cheat_ok(k, flying) for k in keys)
                or (name == "SHIP" and (flying or self.cmdr is not None))]

    @staticmethod
    def _is_cheat(item, group):
        for name, keys in DEBUG_GROUPS:
            if name == group:
                return any(item.startswith(k) for k in keys)
        return False

    @staticmethod
    def _debug_title(page, group):
        if page in (None, "debug"):
            return "DEBUG - BUILD " + build()
        if group == "SHIP":
            return "SHIP CONFIG"
        return "DEBUG: " + group

    def _draw_list(self, ctx, title, items, sel, help_line):
        """A DEBUG page: the chosen line in the middle, the list going round
        above and below it."""
        text = cockpit.text
        text(ctx, title, 0, -66, 16, cockpit.RED)
        n = len(items)
        if not n:
            return
        if n <= DEBUG_ROWS:     # all of it fits: in order, top to bottom
            for i in range(n):
                y = (i - (n - 1) / 2) * 16
                text(ctx, items[i], 0, y, 14, cockpit.GREEN if i == sel else cockpit.GREY)
            if help_line:
                text(ctx, help_line + "   F: back", 0, 70, 11, cockpit.GREY)
            return
        rows = min(DEBUG_ROWS, n)
        for k in range(rows):
            off = k - rows // 2
            i = (sel + off) % n
            y = off * 16
            text(ctx, items[i], 0, y, 14, cockpit.GREEN if off == 0 else cockpit.GREY)
        if help_line:
            text(ctx, help_line + "   F: back", 0, 70, 11, cockpit.GREY)

    def _mission_cheat(self):
        """DEBUG MISSION: the next stage; docking then starts the next mission."""
        c = self.cmdr
        c.mission = missions.next_stage(c.mission)
        c.kills = max(c.kills, missions.stage_kills(c.mission, c))
        self._write_setting("mission", c.mission)   # kept even if a flight ends in death
        self._write_setting("kills", c.kills)
        if self.mode == "flight":
            self._mission_flags()
        return "MISSION: " + missions.stage_name(c.mission)

    # away from a flight: Options > DEBUG (mode "odebug")

    def _od_items(self):
        if self.od_page is None:
            return self._cheat_groups(False)
        if self.od_page == "SHIP":
            return self._ship_items_c()
        return self._cheats(self.od_page, False)

    def _update_odebug(self, dt, cancel, confirm):
        hit = self.pad.hit
        if self.od_msg_t > 0:
            self.od_msg_t -= dt
            if self.od_msg_t <= 0:
                self.od_msg = None
        items = self._od_items()
        n = max(1, len(items))
        if cancel:
            if self.od_page is not None:
                groups = self._cheat_groups(False)
                self.od_sel = groups.index(self.od_page) if self.od_page in groups else 0
                self.od_page = None
            else:
                self.mode = self.od_from or "menu"
        elif hit("j_up"):
            self.od_sel = (self.od_sel - 1) % n
        elif hit("j_down"):
            self.od_sel = (self.od_sel + 1) % n
        elif confirm and items:
            item = items[self.od_sel % n]
            if self.od_page is None:
                self.od_page = item
                self.od_sel = 0
            elif self.od_page == "SHIP":
                self._ship_config_c(item)
            else:
                self.od_msg = self._odebug(item)
                self.od_msg_t = MSG_TIME

    def _draw_odebug(self, ctx):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        items = self._od_items()
        self._draw_list(ctx, self._debug_title(self.od_page, self.od_page), items,
                        self.od_sel % max(1, len(items)),
                        "C: open" if self.od_page is None else "C: do it")
        if self.od_msg:
            cockpit.text(ctx, self.od_msg, 0, 86, 12, cockpit.YELLOW)

    def _odebug(self, item):
        """Do a cheat away from a flight; returns what happened. Changes to the
        commander are written into the save straight away."""
        c = self.cmdr
        if item.startswith("FRAME TIME"):
            self.show_ms = not self.show_ms
            return "FRAME TIME " + ("ON" if self.show_ms else "OFF")
        if item.startswith("GAMEPAD"):
            self.platform.set_gamepad(not self.platform.gamepad)
            return "GAMEPAD " + ("ON" if self.platform.gamepad else "OFF")
        if item == "SPEED TEST":
            from . import bench     # only when asked for: a DEBUG page (DISPLAY > SPEED TEST)
            self.bench = bench.Bench()      # F comes back to this page
            self.mode = "bench"
            return None
        if c is None:
            return None
        if item == "+10 KILLS":
            rank = c.add_kills(10)
            self._write_setting("kills", c.kills)
            return ("RANK: " + rank) if rank else "%d KILLS" % c.kills
        if item == "+1000 CR":
            c.cash += 10000
            self._write_setting("credits", c.credits)
            return c.cash_text()
        if item.startswith("LEVEL"):
            c.level = (c.level + 1) % len(commander.LEVELS)
            c._needs = commander.thresholds(c.level)
            self._write_setting("level", c.level)
            return "LEVEL: " + commander.LEVELS[c.level]
        if item.startswith("HARDCORE"):
            c.hardcore = not c.hardcore
            self._write_setting("hardcore", c.hardcore)
            return "HARDCORE " + ("ON" if c.hardcore else "OFF")
        if item.startswith("LEGAL"):
            c.legal = 20 if c.legal == 0 else (game.FUGITIVE if c.legal < game.FUGITIVE else 0)
            self._write_setting("legal", c.legal)
            return game.legal_name(c.legal)
        if item.startswith("MISSION"):
            return self._mission_cheat()
        if item == "TO MISSION SYSTEM":
            why = self._mission_move()
            if why:
                return why
            self.game = None        # any flight left part-way is from somewhere else
            self._dock()            # docked there: its mission message, if any
            return None
        return None

    def _ship_items_c(self):
        """SHIP CONFIG away from a flight: the commander's equipment."""
        c = self.cmdr
        onoff = lambda b: "ON" if b else "OFF"
        e = c.extras
        return ["SHIP: " + self._ship_title(c.ship),
                "LASER: " + c.lasers[0].upper(),
                "REAR LASER: " + (c.lasers[1] or "none").upper(),
                "LEFT LASER: " + (c.lasers[2] or "none").upper(),
                "RIGHT LASER: " + (c.lasers[3] or "none").upper(),
                "MISSILES: %d" % c.missiles,
                "ENERGY UNIT: " + onoff("energy" in e), "NAVY ENERGY UNIT: " + onoff("navy" in e),
                "CARGO BAY: %dT" % c.hold, "FUEL SCOOPS: " + onoff("scoops" in e),
                "ECM: " + onoff("ecm" in e), "ESCAPE POD: " + onoff("pod" in e),
                "ENERGY BOMB: " + onoff("bomb" in e), "DOCK COMPUTER: " + onoff("docking" in e),
                "GAL. HYPERDRIVE: " + onoff("hyperdrive" in e),
                "STOLEN: " + onoff(c.stolen)]

    def _ship_config_c(self, item):
        c = self.cmdr
        extras = {"ENERGY UNIT": "energy", "NAVY ENERGY UNIT": "navy", "FUEL SCOOPS": "scoops",
                  "ECM": "ecm", "ESCAPE POD": "pod", "ENERGY BOMB": "bomb",
                  "DOCK COMPUTER": "docking", "GAL. HYPERDRIVE": "hyperdrive"}
        key = item.split(":")[0]
        if key == "SHIP":
            self._debug_ship()
            return
        if key == "STOLEN":
            self._debug_stolen()
            return
        mount = self.MOUNTS.get(key)
        if mount is not None:
            kinds = list(commander.LASERS) + ([] if mount == 0 else [""])
            now = c.lasers[mount]
            c.lasers[mount] = kinds[(kinds.index(now) + 1) % len(kinds)] if now in kinds else kinds[0]
            self._write_setting("lasers", list(c.lasers))
            return
        if key == "MISSILES":
            c.missiles = (c.missiles + 1) % (ships.pylons(c.ship) + 1)
            self._write_setting("missiles", c.missiles)
            return
        if key == "CARGO BAY":
            from . import equipment
            c.hold = ships.base_hold(c.ship) if c.hold > ships.base_hold(c.ship) else ships.big_hold(c.ship)
            self._write_setting("hold", c.hold)
            return
        name = extras.get(key)
        if name is None:
            return
        on = name not in c.extras
        self._extra(c, name, on)
        if on and name in ("energy", "navy"):      # one energy unit or the other
            self._extra(c, "navy" if name == "energy" else "energy", False)
        self._write_setting("extras", list(c.extras))

    MOUNTS = {"LASER": 0, "REAR LASER": 1, "LEFT LASER": 2, "RIGHT LASER": 3}

    def _ship_title(self, name):
        """A ship type's name as shown (the game's own name with DATA: OWN)."""
        bp = self.game.types.get(name) if self.game is not None else None
        if bp is None:
            for e in SHIPS or ():
                if e[0] == name:
                    return e[5] if len(e) > 5 else e[0]
        return bp.title if bp is not None else name

    def _debug_stolen(self):
        """DEBUG > SHIP CONFIG > STOLEN (Brian, build 84): the ship you fly is
        stolen or not, saved; in a flight the police see it at once."""
        c = self.cmdr
        c.stolen = not c.stolen
        self._write_setting("stolen", c.stolen)
        g = self.game
        if g is not None and self.mode == "flight" and self.career:
            g.stolen = c.stolen
        self._hot()
        self._write_setting("legal", c.legal)

    def _debug_ship(self):
        """DEBUG > SHIP CONFIG > SHIP (Brian, build 78): fly the next ship
        type, cheapest first, keeping the equipment it can take (the hold,
        missiles and laser mounts cut down to its own). In a career flight or
        docked it is the commander's ship from now on, saved; in practice only
        this flight's."""
        order = sorted(ships.TYPES, key=lambda n: ships.TYPES[n][ships.PRICE])
        flying = self.mode == "flight" and self.game is not None
        c = self.cmdr if (self.career or not flying) else None
        now = c.ship if c is not None else self.game.ship_name
        name = order[(order.index(now) + 1) % len(order)] if now in order else order[0]
        if c is not None:
            c.ship = name
            c.hold = max(ships.base_hold(name), min(ships.big_hold(name), c.hold))
            c.missiles = min(c.missiles, ships.pylons(name))
            c.fuel = min(c.fuel, c.max_fuel())
            for v in range(1, 4):
                if v >= ships.mounts(name):
                    c.lasers[v] = ""
            for key, value in (("ship", name), ("hold", c.hold), ("missiles", c.missiles),
                               ("lasers", list(c.lasers)), ("fuel", c.fuel)):
                self._write_setting(key, value)
            if not flying and self.dock is not None:
                self.dock.ship = self._ship_bp()    # the Repair Shop shows the new one
        if flying:
            g = self.game
            if c is not None:
                self._fit(g)
            else:
                g.set_ship(name, ships.pylons(name))
                for v in range(1, 4):
                    if v >= ships.mounts(name):
                        g.set_laser(None, v)

    def _ship_items(self):
        """The SHIP CONFIG page (a DEBUG page): the ship's equipment, changed
        straight away in this flight and, with a commander, for good."""
        g = self.game
        onoff = lambda b: "ON" if b else "OFF"
        items = ["SHIP: " + self._ship_title(g.ship_name),
                 "LASER: " + g.lasers[0].upper(),
                 "REAR LASER: " + (g.lasers[1] or "none").upper(),
                 "LEFT LASER: " + (g.lasers[2] or "none").upper(),
                 "RIGHT LASER: " + (g.lasers[3] or "none").upper(),
                 "MISSILES: %d" % g.missiles,
                 "ENERGY UNIT: " + onoff(g.energy_unit and not g.navy),
                 "NAVY ENERGY UNIT: " + onoff(g.navy)]
        if self.career and self.cmdr is not None:
            c = self.cmdr
            items += ["CARGO BAY: %dT" % c.hold, "FUEL SCOOPS: " + onoff(g.fuel_scoops)]
        items += ["ECM: " + onoff(g.ecm), "ESCAPE POD: " + onoff(g.pod),
                  "ENERGY BOMB: " + onoff(g.bombs), "DOCK COMPUTER: " + onoff(g.computer)]
        if self.career and self.cmdr is not None:
            items.append("GAL. HYPERDRIVE: " + onoff("hyperdrive" in self.cmdr.extras))
            items.append("STOLEN: " + onoff(self.cmdr.stolen))
        return items

    def _ship_config(self, item):
        """Change one thing on the SHIP CONFIG page (C goes to the next setting)."""
        g = self.game
        c = self.cmdr if self.career else None
        if item.startswith("SHIP:"):
            self._debug_ship()
            return
        if item.startswith("STOLEN:"):
            self._debug_stolen()
            return
        mount = self.MOUNTS.get(item.split(":")[0])
        if mount is not None:      # C goes round: the lasers, then none (the front always has one)
            kinds = list(game.LASERS) + ([] if mount == 0 else [None])
            now = g.lasers[mount]
            nxt = kinds[(kinds.index(now) + 1) % len(kinds)] if now in kinds else kinds[0]
            g.set_laser(nxt, mount)
            if c is not None:
                c.lasers[mount] = nxt or ""
        elif item.startswith("MISSILES"):
            if g.missile_bp:
                g.missiles = (g.missiles + 1) % (g.max_missiles + 1)
                if c is not None:
                    c.missiles = g.missiles
        elif item.startswith("ENERGY UNIT"):
            g.energy_unit = not (g.energy_unit and not g.navy)
            g.navy = False
            if c is not None:
                self._extra(c, "navy", False)
                self._extra(c, "energy", g.energy_unit)
        elif item.startswith("NAVY ENERGY UNIT"):
            # mission 2's reward, at once: it takes the place of the usual unit
            g.navy = not g.navy
            g.energy_unit = g.navy
            if c is not None:
                self._extra(c, "energy", False)
                self._extra(c, "navy", g.navy)
        elif item.startswith("CARGO BAY") and c is not None:
            from . import equipment
            c.hold = ships.base_hold(c.ship) if c.hold > ships.base_hold(c.ship) else ships.big_hold(c.ship)
        elif item.startswith("FUEL SCOOPS") and c is not None:
            g.fuel_scoops = not g.fuel_scoops
            self._extra(c, "scoops", g.fuel_scoops)
        elif item.startswith("ECM"):
            g.ecm = not g.ecm
            if c is not None:
                self._extra(c, "ecm", g.ecm)
        elif item.startswith("ESCAPE POD"):
            g.pod = not g.pod
            if c is not None:
                self._extra(c, "pod", g.pod)
        elif item.startswith("ENERGY BOMB"):
            g.bombs = 0 if g.bombs else 1
            if c is not None:
                self._extra(c, "bomb", bool(g.bombs))
        elif item.startswith("DOCK COMPUTER"):
            g.computer = not g.computer
            if not g.computer:
                g.stop_autodock()
            if c is not None:
                self._extra(c, "docking", g.computer)
        elif item.startswith("GAL. HYPERDRIVE") and c is not None:
            self._extra(c, "hyperdrive", "hyperdrive" not in c.extras)

    @staticmethod
    def _extra(c, name, on):
        if on and name not in c.extras:
            c.extras.append(name)
        elif not on and name in c.extras:
            c.extras.remove(name)

    def _debug(self, item):
        """Do one of the DEBUG page's cheats. Kills made this way count like
        any others, so with a commander they raise the rank."""
        g = self.game
        if item.startswith("HARDCORE"):
            # the commander's Hardcore, at once: this flight's rules too
            c = self.cmdr
            c.hardcore = not c.hardcore
            g.rules = rules.GameRules(c.hardcore)
            g.armed = False
            g.set_docking(c.docking)
            self._write_setting("hardcore", c.hardcore)     # kept even if this flight ends in death
            g.say("HARDCORE " + ("ON" if c.hardcore else "OFF"))
            return
        if item.startswith("LEVEL"):
            # the next level, at once: the enemies, and with a commander the ranks too
            level = (g.level + 1) % len(commander.LEVELS)
            g.set_level(level)
            c = self.cmdr
            if self.career and c is not None:
                c.level = level
                c._needs = commander.thresholds(level)
                self._write_setting("level", level)     # kept even if this flight ends in death
            g.say("LEVEL: " + commander.LEVELS[level])
            return
        if item.startswith("FRAME TIME"):
            self.show_ms = not self.show_ms
        elif item.startswith("GAMEPAD"):
            self.platform.set_gamepad(not self.platform.gamepad)
            g.auto_missile = config.auto_missiles and not self.career  # at once, this flight too
            if config.practice_missile is not None:
                g.pickup_missile = config.practice_missile
            else:
                g.pickup_missile = game.PICKUP_MISSILE
            g.say("GAMEPAD " + ("ON" if self.platform.gamepad else "OFF"))
        elif item.startswith("INVINCIBLE"):
            g.god = not g.god
            if g.god:
                g.shield = g.hull = 100.0
        elif item == "KILL ALL ENEMIES":
            for o in list(g.objs):
                if o.kind == "ship" or o.kind == "missile":
                    g._kill(o)
        elif item == "NEXT WAVE":
            g.wave += 1
            g.wave_kills = 0
            g.say("WAVE %d" % g.wave, 2.5)
        elif item in ("ADD A TRADER", "ADD POLICE", "ADD A HUNTER"):
            if g.space is None:
                g.say("ONLY IN A STAR SYSTEM")
            elif len(g.objs) + len(g.new) < game.MAX_OBJECTS:
                if item == "ADD A TRADER":
                    g.add_trader()
                elif item == "ADD A HUNTER":
                    g.add_hunter()
                else:
                    g.add_police(False)
        elif item == "ADD THE CONSTRICTOR":
            if g.add_constrictor() is None:
                g.say("TOO MANY OBJECTS")
        elif item.startswith("MISSION") and self.career and self.cmdr is not None:
            g.say(self._mission_cheat())
            return
        elif item == "TO MISSION SYSTEM" and self.career and self.cmdr is not None:
            self._to_mission()
            return
        elif item == "ADD A THARGOID":
            if g.add_thargoid() is None:
                g.say("TOO MANY OBJECTS")
        elif item.startswith("MIS-JUMP NEXT"):
            self.misjump = not self.misjump     # like the original's CTRL during a jump
            g.say("MIS-JUMP NEXT " + ("ON" if self.misjump else "OFF"))
        elif item == "ANGER STATION":
            if g.space is None:
                g.say("ONLY IN A STAR SYSTEM")
            else:
                g.anger_station()
        elif item.startswith("LEGAL"):
            # CLEAN, OFFENDER, FUGITIVE and round again
            g.legal = 20 if g.legal == 0 else (game.FUGITIVE if g.legal < game.FUGITIVE else 0)
            g.say(g.legal_name())
        elif item == "ADD AN ENEMY":
            if len(g.objs) + len(g.new) < game.MAX_OBJECTS:
                g._spawn_ship()
        elif item == "REFILL MISSILES":
            if g.missile_bp:
                g.missiles = g.max_missiles
        elif item == "REFILL FUEL":
            if self.career and self.cmdr is not None:
                self.cmdr.fuel = self.cmdr.max_fuel()
        elif item == "+10 KILLS":
            g.kills += 10
        elif item == "FUEL TO 1/4":
            if self.career and self.cmdr is not None:
                self.cmdr.fuel = self.cmdr.max_fuel() // 4
                c = self.cmdr
                g.say("FUEL %d.%d LY" % (c.fuel // 10, c.fuel % 10))
        elif item == "+1000 CR":
            if self.career and self.cmdr is not None:
                self.cmdr.cash += 10000
                g.say(self.cmdr.cash_text())
        elif item == "RELEASE CANISTER":
            if g.release_canister() is None:
                g.say("TOO MANY OBJECTS")
        elif item == "RELEASE ESCAPE POD":      # build 86
            if g.release_pod() is None:
                g.say("TOO MANY OBJECTS")
        elif item == "BAIL OUT":           # the nearest ship with a pod abandons ship
            if g.bail_nearest() is None:
                g.say("NO SHIP WITH A POD")
            else:
                g.say("ESCAPE POD AWAY")
        elif item == "TO THE SUN":
            # flying on takes you down through the scooping band: half SCOOP_ALT up at the
            # closest (build 143: the band is a fixed height, whatever the sun's size)
            sp = g.space
            k = 1.0 + 0.5 * game.SCOOP_ALT / sp.sr if sp is not None else 1.15
            g.to_sun(k, 1.6)
        elif item == "TO THE STATION":
            g.to_station()
        elif item == "DOCK NOW":
            if self.career and self.cmdr is not None:
                self._dock()
                return
        if self.career:
            self._bank()

    def _to_mission(self):
        """A cheat: to where the current mission stage happens (galaxy and
        system), arriving as from hyperspace; then TO THE STATION and dock."""
        g = self.game
        why = self._mission_move()
        if why:
            g.say(why)
            return
        self._enter_space("arrive")
        g.say(self.galaxy.system(self.cmdr.system).name, 3.0)
        self._resume()

    def _mission_move(self):
        """Put the commander where the current mission stage happens (galaxy
        and system). Returns why not, or None."""
        c = self.cmdr
        w = missions.where(c.mission)
        if w is None:
            gal = 1 if c.mission & 15 == 0 else 2     # where the next one can start
            if c.mission & 15 not in (0, 2):
                return "DOCK ANYWHERE" if c.mission & 3 == 3 else "NO MISSION TO GO TO"
            w = (gal, None, None)
        c.galaxy = w[0]
        self._place()
        if w[1] is None:
            c.system = self.galaxy.nearest(96, 96)
        else:
            c.system = self.galaxy.find(w[1], w[2])
        c.market = None
        self.witch = None
        self.target = None
        self.jump_to = None
        return None

    def _resume(self):
        self.paused = False
        self.fsub = None
        self.zero = None
        self.fire_lock = True   # the C that chose a menu line isn't a shot

    def _update_fmenu(self, menu, cancel, confirm):
        hit = self.pad.hit
        if menu:        # A closes the menu from any page
            self._resume()
            return
        items = self._fitems()
        if hit("j_up"):
            self.fmenu = (self.fmenu - 1) % len(items)
        elif hit("j_down"):
            self.fmenu = (self.fmenu + 1) % len(items)
        elif cancel:
            if self.fsub is None:
                self._resume()
            elif self.fsub == "dgroup":     # back to the groups
                self.fsub = "debug"
                self.fmenu = max(0, self._fitems().index(self.dgroup)
                                 if self.dgroup in self._fitems() else 0)
            elif self.fsub == "debug" and self.debug_from == "settings":   # back to Settings
                self.fsub = "settings"
                self.fmenu = self._fitems().index("DEBUG")
            elif self.fsub == "debug":      # back to the menu
                self.fsub = None
                self.fmenu = self._fitems_top().index("DEBUG")
            else:
                self.fmenu = self._fitems_top().index("SETTINGS")
                self.fsub = None
        elif self.fsub == "settings":
            left = hit("j_left")
            side = left or hit("j_right")
            if confirm or side:
                self._change(items[self.fmenu], left)
        elif self.fsub is None and items[self.fmenu].startswith("VIEW: ") and (
                confirm or hit("j_left") or hit("j_right")):
            # the camera changes and the menu stays open (Brian): C or right
            # goes to the next view, left back
            step = -1 if hit("j_left") else 1
            self.game.set_view((self.game.view + step) % 4)
        elif self.fsub == "debug":
            if confirm:
                self.dgroup = items[self.fmenu]
                self.fsub = "dgroup"
                self.fmenu = 0
        elif self.fsub == "dgroup":
            if confirm:
                item = items[self.fmenu]
                if self.dgroup == "SHIP" and not self._is_cheat(item, "SHIP"):
                    self._ship_config(item)     # the ship's equipment
                else:
                    self._debug(item)
        elif confirm:
            self._fpick(items[self.fmenu])

    def _screen_keys(self):
        """Elite's keys for the screens (Brian chose Elite's scheme, 2026-11-16),
        flying, on a screen or in the menu: 5 galactic chart (f4), 6 local chart
        (f5), 7 the target's system data (f6), 8 market prices (f7), 9 status
        (f8), 0 inventory (f9); H hyperspace, Ctrl+H the galactic hyperdrive.
        On a screen or in the menu 1-4 fly on looking that way, and the open
        screen's own key closes it. None of it pauses the game. Each is there
        only when the in-flight menu has its line (so not in combat practice,
        not during a countdown, Ctrl+H only with the hyperdrive). True if a
        key did something."""
        hit = self.pad.hit
        g = self.game
        on = self.fsub in SCREENS
        if self.paused or on:
            for n in range(4):
                if hit("k_view%d" % n):
                    self._resume()
                    g.set_view(n)
                    return True
        if on:
            own = {"status": "k_9", "inventory": "k_0", "market": "k_8", "data": "k_7"}.get(self.fsub)
            if self.fsub == "chart":
                own = "k_5" if type(self.chart).__name__ == "GalChart" else "k_6"
            if own is not None and hit(own):
                self._resume()
                return True
        items = self._fitems_top()

        def line(start):
            for item in items:
                if item.startswith(start):
                    return item
            return None

        if hit("k_H"):
            # Shift+H the galactic hyperdrive (Brian: the Keyboard Hexpansion never
            # sends Ctrl, so Elite's Ctrl+H can't work there; Ctrl+H still does on
            # a keyboard that sends it)
            pick = line("GALACTIC JUMP") if hit("mod+k_H") else line("HYPERSPACE")
            if pick is None:
                c = self.cmdr
                if self.career and c is not None and not c.max_fuel() and self.game is not None:
                    self.game.say("NO HYPERDRIVE", 1.5)     # an in-system ship (ships.TANKS)
                return False        # Ctrl+H is never plain hyperspace
            self._fpick(pick)
            return True
        charts = line("LOCAL CHART") is not None
        if hit("k_6") and charts:
            self._fpick("LOCAL CHART")
        elif hit("k_5") and charts:
            self._fpick("LOCAL CHART")
            if self.witch is None:
                from . import chart
                c = self.cmdr
                self.chart = chart.GalChart(self.galaxy, c.system, c.fuel, self.target,
                                            "JUMP", c.galaxy + 1)
                self.chart.marked = self.target
        elif hit("k_7") and charts:     # the target's data, or here's; D or F back to the chart
            self._fpick("LOCAL CHART")
            self.data_of = self.target if self.target is not None else self.cmdr.system
            self.fsub = "data"
        elif hit("k_8") and line("STATUS") is not None and GOODS and self.witch is None:
            self._open_market()
        elif hit("k_9") and line("STATUS") is not None:
            self._open("status")
        elif hit("k_0") and line("STATUS") is not None:
            self._open("inventory")
        else:
            return False
        return True

    def _open(self, screen):
        """Show one of the in-flight screens (SCREENS); the game runs on."""
        self.paused = False
        self.fsub = screen
        self.top = 0
        self.d_t = None

    def _open_market(self):
        """Market Prices in flight. A system's market is worked out the first
        time it is needed here, as docking would, and kept with the commander,
        so the station has the same prices when you dock."""
        from . import market
        c = self.cmdr
        if c.market is None or c.market["system"] != c.system:
            c.market = market.new(GOODS, c.system, self.galaxy.system(c.system).economy,
                                  random.randint(0, 255))
        self.fmarket = market.Market(GOODS, self.galaxy.system(c.system).economy, c)
        self._open("market")

    def _update_screen(self, cancel, confirm):
        """A screen's own controls: the joystick and buttons (and the cursor
        keys, Enter and Esc). C or F goes back to the flight."""
        s = self.fsub
        hit = self.pad.hit
        if s == "chart":
            self._update_chart(cancel, confirm)
            return
        if s == "data":         # back to the chart
            if confirm or cancel or (hit(BTN_MISSILE)) or hit("k_D"):
                self.fsub = "chart"
            return
        if confirm or cancel:
            self._resume()
            return
        if s == "market" or s == "inventory":
            from . import screens
            if s == "market":
                n, shown = len(GOODS), screens.ROWS
            else:
                n, shown = len(screens.cargo_rows(self.cmdr)), screens.ROWS - 1
            if self._repeat("j_up", self.dt):
                self.top = max(0, self.top - 1)
            elif self._repeat("j_down", self.dt):
                self.top = max(0, min(n - shown, self.top + 1))

    def _fpick(self, item):
        """Do what choosing line item of the in-flight menu does (C on it, or
        its key: see _screen_keys)."""
        if item == "RESUME":
            self._resume()
        elif item == "STATUS":
            self._open("status")
        elif item == "LOCAL CHART" or item == "HYPERSPACE":   # no target: pick one
            from . import chart
            self.chart = chart.Chart(self.galaxy, self.cmdr.system, self.cmdr.fuel,
                                     self.target, at=self.witch)
            self.chart.marked = self.target
            self._open("chart")
        elif item.startswith("HYPERSPACE: "):
            to = self._jump_ok()
            if to is not None:
                self.jump_to = to
                self.game.start_jump()
            self._resume()
        elif item == "DOCKING COMPUTER":
            why = self.game.start_autodock()
            if why:
                self.game.say(why)
            self._resume()
        elif item == "DOCK COMPUTER OFF":
            self.game.stop_autodock()
            self._resume()
        elif item == "GALACTIC JUMP":
            self.jump_to = ("galaxy", 0)
            self.game.stop_autodock()
            self.game.start_jump()
            self.game.say("GALACTIC HYPERSPACE", 1.5)
            self._resume()
        elif item == "QUIT TO TITLE":
            self._to_title()
        elif item == "DEBUG":
            self.fsub = "debug"
            self.debug_from = None
            self.fmenu = 0
        else:
            self.fsub = "settings"
            self.fmenu = 0

    # ---- finding a system by name (build 88) -----------------------------

    def _keyboard(self):
        """True if a keyboard is fitted: its hexpansion's driver (KeyboardApp)
        is running, or its header names a keyboard; else if a keyboard key
        has been pressed."""
        if getattr(self.platform, "pad_in_use", False):    # the Pi: its game pad used last
            return False
        return self.platform.keyboard_fitted() or self.pad.keyboard

    def _names(self):
        from . import find
        if self.find_names is None or self.find_names[0] != self.galaxy_n:
            self.find_names = (self.galaxy_n, find.Names(self.galaxy))
        return self.find_names[1]

    def _open_find(self, chart):
        """Find a system for this chart: with a keyboard fitted, the game's
        own page (type, suggestions, pick); without, the badge's text entry
        (Brian: only one or the other)."""
        from . import find
        self.find_chart = chart
        names = self._names()
        if not self._keyboard():
            # the badge's own text entry (platform_tildagon.text_dialog), or
            # None (no firmware dialog, a PC): the keyboard page
            self.tdialog = self.platform.text_dialog("FIND SYSTEM")
            if self.tdialog is not None:
                return
        self.finder = find.Find(self.galaxy, names)

    def _found(self, i):
        """Put the chart's cursor on system i (None: not found)."""
        self.finder = None
        self.tdialog = None
        ch = self.find_chart
        self.find_chart = None
        if i is not None and ch is not None:
            ch.goto(i)

    def _update_find(self, cancel, confirm):
        """While a search is open: True (it takes all the input)."""
        if self.tdialog is not None:
            dl = self.tdialog
            driven = self._drive_picker(dl)
            found = self._names().matches(dl.text)
            dl.message = self._names().names[found[0]] if found else (
                "NO MATCH" if dl.text else "FIND SYSTEM")
            r = getattr(dl, "_result", None)
            if r is False:
                self._found(None)
            elif r is not None:
                if not found:
                    self._play("boop")      # a search that finds nothing: Elite's long low beep
                self._found(found[0] if found else None)
            if r is not None or not driven:
                self.pad.clear()    # the dialog has the buttons (or the one that closed it)
            return True
        if self.finder is None:
            return False
        f = self.finder
        hit = self.pad.hit
        for ch in self.pad.typed:
            f.type(ch)
        if hit("k_BACKSPACE"):
            f.back()
        elif hit("j_up"):
            f.pick(-1)
        elif hit("j_down"):
            f.pick(1)
        elif confirm:
            if f.chosen() is None:
                self._play("boop")      # nothing found (Elite's HME6)
            self._found(f.chosen())
        elif cancel:
            self._found(None)
        return True

    def _drive_picker(self, dl):
        """The letter picker (picker.py) on the game's own controls, where the
        game drives it (the badge's TEXT ENTRY: PICKER, the Pi's pad): the
        joystick's up / down the letter (held, it repeats), C or right keeps
        it, left goes back, A is done, F cancels. False for any other dialog."""
        if not getattr(dl, "driven", False):
            return False
        hit = self.pad.hit
        held = self.pad.held
        if hit("j_up"):
            dl.press("UP")
        elif hit("j_down"):
            dl.press("DOWN")
        elif hit("confirm") or hit("j_right"):
            dl.press("B")
        elif hit("j_left") or hit("k_BACKSPACE"):
            dl.press("C")
        elif hit("A"):
            dl.press("A")
        elif hit("cancel"):
            dl.cancel()
        ms = int(self.dt * 1000)
        if held("j_up"):
            dl.hold("UP", ms)
        elif held("j_down"):
            dl.hold("DOWN", ms)
        else:
            dl.let_go()
        return True

    def _open_name(self, current, done):
        """Enter a commander's name, starting from current; done(name) gets
        it. The suggestion is the badge's name (Elite's JAMESON without one):
        greyed on the keyboard's page, Tab fills it; the badge's text entry
        takes it when Done is pressed on nothing."""
        from . import find
        self.name_done = done
        sug = badge_name().upper()[:find.NAME_MAX]
        if not self._keyboard():
            self.ndialog = self.platform.text_dialog("NAME? (none: %s)" % sug)     # see _open_find
            if self.ndialog is not None:
                self.ndialog.text = current.lower()
                return
        self.namer = find.NameEntry(sug, current)

    def _name_entered(self, name):
        done = self.name_done
        self.namer = self.ndialog = self.name_done = None
        if name is not None and done is not None:
            done(name)

    def _update_name(self, cancel, confirm):
        """While the name is being entered: True (it takes all the input)."""
        from . import find
        if self.ndialog is not None:
            driven = self._drive_picker(self.ndialog)
            r = getattr(self.ndialog, "_result", None)
            if r is False:
                self._name_entered(None)
            elif r is not None:
                n = r.strip().upper()[:find.NAME_MAX]
                self._name_entered(n or badge_name().upper()[:find.NAME_MAX])
            if r is not None or not driven:
                self.pad.clear()    # the dialog has the buttons (or the one that closed it)
            return True
        if self.namer is None:
            return False
        e = self.namer
        hit = self.pad.hit
        for ch in self.pad.typed:
            e.type(ch)
        if hit("k_TAB"):
            e.fill()
        elif hit("k_BACKSPACE"):
            e.back()
        elif confirm:
            self._name_entered(e.result())
        elif cancel:
            self._name_entered(None)
        return True

    def _draw_name(self, ctx):
        if self.namer is not None:
            self.namer.draw(ctx)
        elif self.ndialog is not None:
            self.ndialog.draw(ctx)

    def _new_name(self, name):
        self.n_name = name

    def _set_name(self, name):
        """The commander's new name, saved at once."""
        self.cmdr.name = name
        self._write_setting("name", name)

    def _draw_find(self, ctx):
        if self.finder is not None:
            self.finder.draw(ctx)
        elif self.tdialog is not None:
            self.tdialog.draw(ctx)

    def _update_chart(self, cancel, confirm):
        """The in-flight charts: the joystick moves the cursor, C makes the
        selected system the target (Brian: only that; H or the menu's
        HYPERSPACE line jumps, as Elite), C on where you are clears it, D
        shows its data, F goes back."""
        if self._update_find(cancel, confirm):
            return
        if cancel:
            self._resume()
            self.chart = None
            return
        ch = self.chart
        if self.pad.hit(BTN_BOMB) and hasattr(ch, "number"):
            self._open_find(ch)     # B on the Galactic chart: find a system by name
            return
        if (self.pad.hit(BTN_MISSILE)) or self.pad.hit("k_D"):
            if ch.picked() is not None:
                self.data_of = ch.picked()      # D: the selected system's data
                self.fsub = "data"
            return
        if confirm:
            i = ch.picked()
            if i is not None:
                self.target = None if i == ch.here else i
                ch.marked = self.target
            return
        jx, jy = self._steer(False, STICK, True, False)   # W A S D fly the ship
        ch.move(jx, jy, self.dt)

    def _draw_screen(self, ctx):
        """The in-flight screen that is up (SCREENS)."""
        s = self.fsub
        if s == "chart":
            self.chart.draw(ctx)
            self._draw_find(ctx)
            return
        if s == "data":
            self._draw_data(ctx)
            return
        from . import screens
        c = self.cmdr
        gal = self.galaxy
        if s == "market":
            screens.draw_market(ctx, self.fmarket, c, gal.system(c.system).name, self.top)
        elif s == "inventory":
            screens.draw_inventory(ctx, c, GOODS, self.top)
        else:
            here = ("WITCHSPACE" if self.witch is not None
                    else gal.system(c.system).name if gal is not None and c.system is not None
                    else None)
            target = dist = None
            if gal is not None and self.target is not None and c.system is not None:
                target = gal.system(self.target).name
                dist = gal.distance(c.system, self.target)
            screens.draw_status(ctx, c, here, target, dist, self.game.condition(),
                                game.legal_name(c.legal), cmdr_name(c).upper())

    def _draw_data(self, ctx):
        """D on the in-flight chart: the selected system's data."""
        c = self.cmdr
        i = self.data_of
        if self.witch is not None:
            dist = self.galaxy.distance_xy(self.witch[0], self.witch[1], i)
        else:
            dist = None if i == c.system else self.galaxy.distance(c.system, i)
        docked.system_page(ctx, self.galaxy, self.galaxy.system(i), dist, c.fuel,
                           "C, D or F: back to chart")

    def _fitems_top(self):
        items = ["RESUME"]
        if self.game is not None:
            items.append("VIEW: " + game.VIEW_NAMES[self.game.view])
        if self.career:
            # always there, unless a countdown is on: with a target in range it
            # jumps, without one it opens the local chart to pick one
            if (self.galaxy is not None and self.game is not None and self.game.jump_t <= 0
                    and self.cmdr is not None and self.cmdr.max_fuel()):    # no hyperdrive: no line
                to = self._jump_ok()
                items.append("HYPERSPACE: " + self.galaxy.system(to[0]).name if to is not None
                             else "HYPERSPACE")
            if self.galaxy is not None:
                items.append("LOCAL CHART")
            g = self.game
            c = self.cmdr
            if g is not None and g.computer:
                if g.autodock:
                    items.append("DOCK COMPUTER OFF")
                elif g.space is not None and g.space.safe:
                    items.append("DOCKING COMPUTER")
            if (c is not None and "hyperdrive" in c.extras and g is not None and c.max_fuel()
                    and g.jump_t <= 0 and self.galaxy is not None):
                items.append("GALACTIC JUMP")
            items.append("STATUS")
        items.append("SETTINGS")
        items.append("QUIT TO TITLE")
        if DEBUG_MENU:
            items.append("DEBUG")
        return items

    # ---- draw -------------------------------------------------------------

    def draw(self, ctx):
        ctx.save()
        if self.mode == "viewer":
            self.viewer.draw(ctx)
        elif self.mode == "bench":
            self.bench.draw(ctx)
        elif self.mode == "flight":
            if self.fsub in SCREENS and not self.paused:   # instead of the space view
                self._draw_screen(ctx)
                ctx.restore()
                return
            t0 = _us()
            cockpit.draw_world(ctx, self.game)
            t1 = _us()
            cockpit.draw_hud(ctx, self.game, self.ms if self.show_ms else None,
                             not self.platform.leds_on)
            if self.paused:
                self._draw_fmenu(ctx)
            else:
                world = _diff(t1, t0) / 1000.0
                hud = _diff(_us(), t1) / 1000.0
                self.t_world += (world - self.t_world) * 0.1
                self.t_hud += (hud - self.t_hud) * 0.1
                self.p_draw += world + hud
                self.p_world += world
                self.p_hud += hud
        elif self.mode == "level":
            self._draw_level(ctx)
        elif self.mode == "practice":
            self._draw_practice(ctx)
        elif self.mode == "duel":
            self._draw_duel(ctx)
        elif self.mode == "docked":
            self.dock.draw(ctx)
            self._draw_find(ctx)
        elif self.mode == "brief":
            self.brief.draw(ctx)
        elif self.mode == "options":
            self._draw_options(ctx)
        elif self.mode == "odebug":
            self._draw_odebug(ctx)
        elif self.mode == "launch":
            cockpit.draw_tunnel(ctx, min(1.0, self.launch_t / LAUNCH_TIME), self.launch_t,
                                cockpit.station_colour(self._government()), False, self.tunnel)
        elif self.mode == "docking":
            cockpit.draw_tunnel(ctx, min(1.0, self.dock_t / DOCK_TIME), self.dock_t,
                                cockpit.station_colour(self._government()), True, self.tunnel)
        else:
            self._draw_menu(ctx)
        self._draw_name(ctx)
        ctx.restore()

    def _draw_menu(self, ctx):
        if not SHIPS or self.title is None:
            text = cockpit.text
            ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
            text(ctx, "ACE", 0, -74, 34, cockpit.WHITE)
            text(ctx, "COMMANDER", 0, -46, 18, cockpit.WHITE)
            if not SHIPS:
                text(ctx, "ship_data.py", 0, -10, 16, cockpit.YELLOW)
                text(ctx, "not found", 0, 10, 16, cockpit.YELLOW)
                text(ctx, "copy it next to ace.py", 0, 36, 12, cockpit.GREY)
            return
        items = self.choices()
        self.title.draw(ctx, items[self.menu % len(items)])

    def _draw_level(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "NEW COMMANDER", 0, -94, 15, cockpit.WHITE)
        # NAME (build 89): the one entered, or the badge's (JAMESON) greyed
        on = self.n_sel == 0
        text(ctx, "NAME", 0, -76, 12, cockpit.GREY)
        name = self.n_name or badge_name().upper()[:12]
        text(ctx, name, 0, -58, 16, (cockpit.GREEN if on else cockpit.WHITE) if self.n_name
             else cockpit.GREY)
        self._draw_rows(ctx, self.level, self.n_hardcore, self.n_sel - 1, -36, 54, True)
        if self.n_sel == 1:
            top = commander.thresholds(self.level)[-1]
            text(ctx, "top rank at %d kills" % top, 0, 58, 11, cockpit.GREY)
        if self.cmdr is not None:
            text(ctx, "replaces your saved commander", 0, 72, 11, cockpit.RED)
        # on LEVEL / HARDCORE left / right changes it, C starts from any line (build 134:
        # C on HARDCORE: OFF started a standard commander)
        text(ctx, "C: name   F: back" if on else "< > change   C: start", 0, 86, 12, cockpit.GREY)

    def _draw_fmenu(self, ctx):
        text = cockpit.text
        ctx.rgba(0, 0, 0, 0.85).rectangle(-100, -80, 200, 142).fill()
        if self.fsub in ("debug", "dgroup"):
            self._draw_list(ctx, self._debug_title(self.fsub, self.dgroup), self._fitems(),
                            self.fmenu, None)
            return
        pause = self.fsub == "settings"
        text(ctx, "SETTINGS" if pause else "PAUSED", 0, -60, 18, cockpit.WHITE)
        items = self._fitems()
        many = len(items) > 6       # equipment adds lines: closer together
        step = 13 if many else 16
        top = -44 if many else -40
        for i, label in enumerate(items):
            y = top + i * step
            text(ctx, label, 0, y, 12 if many else 13,
                 cockpit.GREEN if i == self.fmenu else cockpit.GREY)


# the badge starts app.py (the loading screen), which makes this
