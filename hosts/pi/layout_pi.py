"""The Pi's flight layouts (platform layer, step 4, build 105), as the game asks
for them (layout.py): run.py sets config.layout to a PiLayout, which follows
the window's layout ("badge" or "elite", F10) and size.

"badge": the badge's round screen, drawn as the game draws it (only the frame
time is left out in full screen, Brian). "elite": a 3D view the window's width
over the Elite-style dashboard (dash_pi.py), the tunnels the whole window, and
the pause menu over the middle. These were hooks round cockpit.draw_world,
draw_hud and draw_tunnel until build 105.
"""
import dash_pi


class PiLayout:
    view_hw = 120
    view_hh = 120
    tunnel_hw = 120
    tunnel_hh = 120

    def __init__(self, host, ck):
        self.host = host        # run.Host: the window, its scale and its layout
        self.ck = ck            # the game's cockpit module (its round HUD)

    def fit(self):
        """The sizes for the window's layout and width (after a resize or F10)."""
        h = self.host
        if h.layout == "elite":
            self.view_hw = self.tunnel_hw = h.lw / 2.0
            self.view_hh = dash_pi.VIEW_H / 2.0
            self.tunnel_hh = 120
        else:
            self.view_hw = self.view_hh = self.tunnel_hw = self.tunnel_hh = 120

    def view(self, ctx):
        h = self.host
        if h.layout == "elite":
            h._clip(0, dash_pi.VIEW_H)
            h._at(ctx, dash_pi.VIEW_H / 2.0)

    def tunnel(self, ctx):
        h = self.host
        if h.layout == "elite":
            h.window.set_clip(None)
            h._at(ctx, 120)

    def hud(self, ctx, g, ms, ring):
        h = self.host
        if h.full:
            ms = None           # no frame time counter in full screen (Brian)
        if h.layout != "elite":
            if ms is None and h.full:
                self.ck._hud(ctx, g, None, ring)
                return True
            return False
        h._clip(0, dash_pi.VIEW_H)
        h._at(ctx, dash_pi.VIEW_H / 2.0)
        dash_pi.draw_view_overlay(ctx, self.ck, g, h.dash_layout, ms)
        h._clip(dash_pi.VIEW_H, dash_pi.DASH_H)
        h._at(ctx, dash_pi.VIEW_H + dash_pi.DASH_H / 2.0)
        if getattr(g, "autodock", False):
            stick = g.auto_stick
        else:
            stick = (g.stick_pitch, g.stick_roll)
        dash_pi.draw_dashboard(ctx, self.ck, g, h.dash_layout, stick)
        return True

    def done(self, ctx):
        h = self.host
        if h.layout == "elite":
            h.window.set_clip(None)
            h._at(ctx, 120)             # the pause menu: over the middle of the window
