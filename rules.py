"""Game rules that Hardcore Mode switches from assisted to manual.

No badge imports, so it runs on a PC and on any badge (Tildagon, Tufty).

`GameRules(hardcore=False)`: every flag is False in standard mode (the game as it has been),
and Hardcore Mode turns them all on. Each flag can be set by hand for testing or for a custom mix.

    manual_ecm            the ECM pulses only when you press its key (standard: it fires by
                          itself at an incoming missile)
    missile_lock_required missiles must be armed first (T), then locked by keeping the target in
                          the sights, then fired (M); U disarms (standard: lock builds up by itself
                          and D fires)
    four_way_views        front, rear, left and right views, a laser for each facing     [not built]
    galactic_hyperspace   the galactic hyperdrive from a key rather than a menu            [not built]

Already in the game, so not Hardcore flags: docking by hand (the DOCKING setting: AUTHENTIC /
ASSISTED / AUTOMATIC, build 27), the jump drive's lock-out (it needs the safe zone left behind and
no ship or missile in radar range, build 26), and saving only when docked (build 35).
"""

FLAGS = ("manual_ecm", "missile_lock_required", "four_way_views", "galactic_hyperspace")


class GameRules:
    def __init__(self, hardcore=False):
        self.hardcore = bool(hardcore)
        for name in FLAGS:
            setattr(self, name, self.hardcore)

    def active(self):
        """The names of the rules that are on."""
        return [n for n in FLAGS if getattr(self, n)]
