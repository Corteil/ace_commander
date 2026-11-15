# On the badge (MicroPython) the app starts with a loading screen (loader.py)
# that imports the rest, which takes a while the first time. On a PC, where
# the tests run, there is nothing to wait for: the app itself.
import sys
if sys.implementation.name == "micropython":
    from .loader import AceCommander
else:
    from .app import AceCommander
__all__ = ['AceCommander']
