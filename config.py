"""Where the game keeps its files, and the switches a host sets before the
game starts (platform layer, step 1).

The badge uses the defaults: everything in the app's own folder. Another
device (hosts/) imports this module first, changes what it needs, then
imports the rest of the game, which reads these once as it loads. Imports
nothing, so it is safe to import before anything else.
"""

# the folder for the save, options.json and debug.txt; None: the app's folder
data_dir = None

# the DEBUG page of cheats: True, False, or None to decide as the badge does
# (on with debug.txt in the data folder or the Easter egg; always on a PC,
# where the tests run)
debug_menu = None
perf_log = 60           # a PERF line on the console every this many flight frames (0: never)
log_keys = False        # print every button / key event (to see what a keyboard sends)
title_quit = False      # a QUIT line on the title screen (the badge has F to leave)
title_cancel = True     # cancel (F, Esc) on the title screen leaves the game
practice_only = False   # the title screen offers only COMBAT PRACTICE (a device with too
                        # few buttons for the rest: the Tufty without its Pad; build 111)
auto_missiles = False   # a missile goes as soon as a ship is locked, one a ship (no missile
                        # button: the Tufty without its Pad; build 112)
practice_missile = None # how often a scooped canister in combat practice holds a missile
                        # too (None: game.PICKUP_MISSILE; build 112)
practice_upgrades = True    # combat practice: each wave cleared drops an upgrade canister
                        # (it can't be destroyed), the next of game.UPGRADES when scooped,
                        # and the next wave comes after a countdown (game.WAVE_WAIT; every
                        # device, Brian; build 113)
more_hints = False      # the screen is square, so its corners show (the Tufty, the Pi's
                        # Elite layout): hint lines where the badge's round screen has no
                        # room, the charts and the title screen (Brian, build 129)
laser_leds = True       # your laser lights the LEDs in its colour (off on the Tufty and the
                        # Pi, whose "LEDs" are drawn on the screen; build 113)
menu_k = 1             # list menus' lines this many times further apart, fewer of them shown
                        # (they scroll): a small screen with bigger text (the CardputerZero)
wire_min = 8.0          # ships that look smaller than this (pixels) are drawn as a marker

# the game's input (platform layer, step 2): None on the badge, where
# platform_tildagon.Input matches the firmware's button events; a host sets
# a function input(controls, owner) that feeds controls.Controls itself
input = None

# what only the device can do (platform layer, step 3): None on the badge, where
# the game uses platform_tildagon; a host sets its own module with App,
# Platform and owner_name (see the top of platform_tildagon.py)
platform = None

# how flight is laid out on the screen (platform layer, step 4): None on the
# badge (layout.BADGE); a host sets an object like layout.Layout
layout = None


def app_dir():
    """The folder this file is in: the app's."""
    try:
        d = __file__.rsplit("/", 1)[0]
        if not d.startswith("/") and ":" not in d:
            d = "/" + d         # the badge gives a path relative to /
        return d
    except Exception:
        return "/apps/ace_commander"


def data(name):
    """The path of one of the game's own files (the save, options.json,
    debug.txt) in the data folder."""
    return (data_dir or app_dir()) + "/" + name
