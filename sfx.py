"""The game's sounds (builds 140-142): each a short run of tones, so a Qwiic
buzzer (the badge, the Tufty: buzzer.py) and the Pi (hosts/pi/sound_pi.py)
play the same tunes.

SOUNDS[name] = (priority, part, part...): parts play together (the buzzer
plays only the first). A part is a list of steps (Hz, ms) or (Hz, ms, level
0-126): Hz 0 is a rest, a negative Hz noise changing that many times a
second. A sound playing on the buzzer is cut short only by one of the same or
higher priority. CHANNELS[name]: sounds sharing a channel cut each other off
on the Pi (Elite's flush); a name not there has a channel of its own.

With Elite's data (content.OWN False) and elite_sfx.py made from your own
copy of the source (tools/import_sfx.py, gitignored), Elite's sounds are used,
on the events where Elite makes them; otherwise the game's own, below.

The game asks for them by name: game.Game.sfx() in flight, ace.py for
launching and docking; the device plays them (Platform.sound) or not.
"""

NOISE = -3000           # noise changing 3000 times a second


def _zap(n):
    """A laser zap, n times over: a low note, then a jump up falling away."""
    one = [(150, 40, 60)] + [(f, 10, 110) for f in (700, 600, 500, 420, 350, 290, 240, 200)]
    return one * n


def _fade(f, ms, n, top=126):
    """n steps of f Hz, each ms long, fading from top."""
    return [(f, ms, top - top * i // n) for i in range(n)]


# The game's own sounds (builds 140-142): for the same events as Elite's and in
# its style, written by ear, not taken from it; silent where Elite is silent.
OWN = {
    "laser": (1, _zap(4)),
    "hit": (2, _fade(-4000, 250, 5)),
    "explode": (3, _fade(-4000, 250, 5)),
    "hurt": (2, [(300, 30, 50), (380, 30, 80), (300, 30, 110), (380, 30, 80)] * 3),
    "crash": (4, [(-8000, 200, 126), (-6000, 200, 126), (-4000, 300, 110),
                  (-2500, 300, 80), (-1500, 300, 40)]),
    "die": (5, [(-8000, 200, 126), (-6000, 200, 126), (-4000, 300, 110),
                (-2500, 300, 80), (-1500, 300, 40)]),
    "lock": (2, [(1900, 50)]),
    "unarm": (2, [(150, 400, 100)]),
    "beep": (2, [(1900, 50)]),
    "boop": (2, [(150, 400, 100)]),
    "missile": (3, [(-2000, 600, 120)]),
    "incoming": (4, [(-2000, 600, 120)]),
    "launch": (3, [(-2000, 600, 120)]),
    "jump": (5, [(-2000, 200, 40), (-6000, 200, 80), (-3000, 300, 110),
                 (-1500, 400, 80), (-1000, 300, 40)]),
    "ecm": (3, [(2100, 10, 60), (2400, 10, 90)] * 25),
}
# the BBC Micro's layout: tones on 2 and 3, noise on 0 (a sound restarts its channel)
OWN_CHANNELS = {"laser": 2, "hurt": 2, "lock": 3, "unarm": 3, "beep": 3, "boop": 3, "ecm": 3,
                "hit": 0, "explode": 0, "crash": 0, "die": 0, "missile": 0, "incoming": 0,
                "launch": 0, "jump": 0}
SOUNDS = OWN
CHANNELS = OWN_CHANNELS
ELITE = False           # Elite's sounds in use

try:
    from . import content as _content
    if not _content.OWN:
        from . import elite_sfx as _elite
        SOUNDS = _elite.SOUNDS
        CHANNELS = getattr(_elite, "CHANNELS", {})
        ELITE = True
except ImportError:     # no elite_sfx.py (or imported on its own): the game's own
    pass


def length(name):
    """How long a sound lasts, in milliseconds (its longest part)."""
    return max(sum(s[1] for s in part) for part in SOUNDS[name][1:])
