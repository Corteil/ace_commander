"""Whose content the game uses, decided once at start-up: Elite's, from
ship_data.py and game_data.py made from your own copy of the Elite source
(tools/import_ships.py, tools/import_galaxy.py), or the game's own,
original_ships.py and original_data.py. The game's own is used when the
Elite files aren't there, or when Options > CONTENT: OWN is saved in
options.json in the data folder (config.py; it applies from the next start).
"""
import json

from . import config


def _want_own():
    try:
        with open(config.data("options.json")) as f:
            o = json.loads(f.read())
        return bool(o.get("own", o.get("own_ships")))
    except Exception:
        return False


HAVE_ELITE = False      # both Elite files are there: the Options page can switch
_elite_ships = _elite_data = None
try:
    from .ship_data import SHIPS as _elite_ships
except Exception:
    pass
try:
    from . import game_data as _elite_data
except Exception:
    pass
HAVE_ELITE = _elite_ships is not None and _elite_data is not None
OWN = not HAVE_ELITE or _want_own()     # the game's own content

def _have(name):
    """True if module name is in this folder (as .py or .mpy): the game's own
    content can be left off a badge that only plays Elite's (tools/build_mpy.py
    --elite-only)."""
    import os
    d = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
    for ext in (".py", ".mpy"):
        try:
            os.stat(d + "/" + name + ext)
            return True
        except OSError:
            pass
    return False


SHIPS = ()
DATA = None
if OWN:
    try:
        from .original_ships import SHIPS
    except Exception:
        pass
    try:
        from . import original_data as DATA
    except Exception:
        pass
    if (not SHIPS or DATA is None) and HAVE_ELITE:
        OWN = False                 # the game's own content isn't here: Elite's after all
        SHIPS = _elite_ships
        DATA = _elite_data
else:
    SHIPS = _elite_ships
    DATA = _elite_data
# both sets are here, so Options > DATA can switch between them
HAVE_OWN = (bool(SHIPS) and DATA is not None) if OWN else (_have("original_ships") and _have("original_data"))
CAN_SWITCH = HAVE_ELITE and HAVE_OWN
_elite_ships = _elite_data = None   # don't keep the unused set about
