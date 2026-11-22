"""The game's sounds (build 140): each a short run of tones, so a Qwiic buzzer
(the badge, the Tufty: buzzer.py) and the Pi (hosts/pi/sound_pi.py) play the
same tunes. Imports nothing.

SOUNDS[name] = (priority, steps). A step is (frequency Hz, milliseconds):
0 is a rest, NOISE a burst of noise (random pitches on a buzzer). A sound
playing is cut short only by one of the same or higher priority.

The game asks for them by name: game.Game.sfx() in flight, ace.py for
launching and docking; the device plays them (Platform.sound) or not.
"""

NOISE = -1


def _sweep(f0, f1, n, ms):
    """n steps from f0 to f1 Hz, each ms long."""
    return [(f0 + (f1 - f0) * i // (n - 1), ms) for i in range(n)]


SOUNDS = {
    "laser": (1, [(1800, 20), (1300, 20), (900, 25)]),
    "overheat": (2, [(300, 120), (0, 40), (300, 120)]),
    "hurt": (2, [(220, 50), (170, 70)]),
    "explode": (3, [(NOISE, 220)]),
    "die": (5, [(NOISE, 500), (120, 150), (90, 250)]),
    "lock": (2, [(2000, 40), (0, 30), (2000, 40)]),
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


def length(name):
    """How long a sound lasts, in milliseconds."""
    return sum(ms for f, ms in SOUNDS[name][1])
