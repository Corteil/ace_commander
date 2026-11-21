# Ace Commander for the Tufty 2350: the file Badgeware runs when the app starts.
# The app folder holds hosts/tufty's files and the game as the package
# ace_commander (made by hosts/tufty/build_tufty.py).
import sys

_here = "/system/apps/ace_commander"
try:
    _here = __file__.rsplit("/", 1)[0] or _here
except NameError:
    pass
if _here not in sys.path:
    sys.path.insert(0, _here)

import host_tufty

_host = host_tufty.start(globals())


def update():
    return _host.update()


def on_exit():
    _host.on_exit()


run(update)
