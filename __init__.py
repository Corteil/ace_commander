# The badge's launcher imports this folder's app.py and starts its
# __app_export__: that is the loading screen (app.py), which then imports the
# rest, the real app among it (ace.py). On a PC, where the tests run, there is
# nothing to wait for: the package gives the real app.
import sys
if sys.implementation.name != "micropython":
    from .ace import AceCommander
    __all__ = ['AceCommander']
