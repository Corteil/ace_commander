"""How flight is laid out on the screen (platform layer, step 4, build 105).
Imports nothing.

The game draws everything off the flight (menus, docked screens, charts) on a
240 x 240 canvas, centred: that works on any screen. Flight is different: the
3D view, the HUD and the tunnels follow the screen's shape. cockpit.py asks
the layout in config.layout (this module's BADGE when None) each time it
draws them, so a host never replaces the game's drawing functions:

    view_hw, view_hh        the 3D view's half width and height (canvas units)
    tunnel_hw, tunnel_hh    the launch and docking tunnels' (often the whole screen)
    view(ctx)               before the 3D view: put ctx's origin at its middle
                            (and clip to it, if the screen has more than the view)
    tunnel(ctx)             the same before a tunnel
    hud(ctx, g, ms, ring)   draw this layout's own HUD (a dashboard) and return
                            True; False: the game's round HUD is drawn instead
    done(ctx)               after flight: back to the 240 canvas in the middle
                            (the pause menu is drawn over it)

A host may change its layout's numbers between frames (the Pi's window can be
resized, and F10 switches layouts).
"""


class Layout:
    """The badge's: its round 240 x 240 screen is all 3D view, with the round
    HUD over it, and nothing to move."""
    view_hw = 120
    view_hh = 120
    tunnel_hw = 120
    tunnel_hh = 120

    def view(self, ctx):
        pass

    def tunnel(self, ctx):
        pass

    def hud(self, ctx, g, ms, ring):
        return False

    def done(self, ctx):
        pass


BADGE = Layout()
