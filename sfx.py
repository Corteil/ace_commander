"""The game's sounds (builds 140-141): each a short run of tones, so a Qwiic
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

NOISE = -3000           # the game's own noise: changing 3000 times a second


def _sweep(f0, f1, n, ms):
    """n steps from f0 to f1 Hz, each ms long."""
    return [(f0 + (f1 - f0) * i // (n - 1), ms) for i in range(n)]


OWN = {
    "laser": (1, [(1800, 20), (1300, 20), (900, 25)]),
    "hit": (2, [(NOISE, 60)]),
    "overheat": (2, [(300, 120), (0, 40), (300, 120)]),
    "hurt": (2, [(220, 50), (170, 70)]),
    "crash": (4, [(NOISE, 300), (150, 100)]),
    "explode": (3, [(NOISE, 220)]),
    "die": (5, [(NOISE, 500), (120, 150), (90, 250)]),
    "lock": (2, [(2000, 40), (0, 30), (2000, 40)]),
    "unarm": (2, [(300, 200)]),
    "missile": (2, _sweep(500, 1600, 6, 25)),
    "incoming": (4, [(1500, 90), (0, 60), (1500, 90), (0, 60), (1500, 90)]),
    "ecm": (3, [(3000, 25), (1500, 25)] * 5),
    "bomb": (5, [(NOISE, 400), (200, 200)]),
    "tick": (1, [(1000, 50)]),
    "jump": (5, _sweep(200, 2400, 12, 40)),
    "scoop": (2, [(1200, 40), (1700, 70)]),
    "upgrade": (3, [(800, 60), (1000, 60), (1300, 60), (1600, 120)]),
    "wave": (2, [(600, 80), (900, 140)]),
    "tractor": (2, [(400, 70), (500, 70), (600, 90)]),
    "launch": (3, _sweep(250, 1200, 10, 50)),
    "dock": (3, _sweep(1200, 250, 10, 50)),
}
SOUNDS = OWN
CHANNELS = {}
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
