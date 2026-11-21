"""The Tufty's flight layout (layout.py's interface; build 109): a 3D view
320 x 180 over an Elite-style dashboard 320 x 60 (dash_tufty.py), the badge's
LED ring painted as a border round the view, the tunnels on the whole screen
and the pause menu over the view. host_tufty sets config.layout to it.
It moves the one Ctx's origin and the screen's clip; the rest of the game draws
on the 240 canvas in the middle of the screen.
"""
import dash_tufty as dash
import platform_tufty


class TuftyLayout:
    view_hw = dash.VIEW_W // 2
    view_hh = dash.VIEW_H // 2
    tunnel_hw = dash.SCREEN_W // 2
    tunnel_hh = dash.SCREEN_H // 2
    dust_x = 500 * dash.VIEW_W // 240       # across the wider view
    leds = True             # the border round the view shows them

    def __init__(self, screen, rect, ck):
        self.screen = screen
        self.rect = rect        # Badgeware's rect(x, y, w, h), for the clip
        self.ck = ck
        dash.use(ck)
        self.full = rect(0, 0, dash.SCREEN_W, dash.SCREEN_H)
        self.view_rect = rect(0, 0, dash.VIEW_W, dash.VIEW_H)
        self.dash_rect = rect(0, dash.VIEW_H, dash.SCREEN_W, dash.DASH_H)

    def view(self, ctx):
        self.screen.clip = self.view_rect
        ctx.ox = dash.SCREEN_W // 2
        ctx.oy = dash.VIEW_H // 2

    def tunnel(self, ctx):
        self.screen.clip = self.full
        ctx.ox = dash.SCREEN_W // 2
        ctx.oy = dash.SCREEN_H // 2

    def hud(self, ctx, g, ms, ring):
        self.screen.clip = self.view_rect
        ctx.ox = dash.SCREEN_W // 2
        ctx.oy = dash.VIEW_H // 2
        dash.draw_view_overlay(ctx, g, ms)
        dash.draw_led_border(ctx, platform_tufty.LEDS[1:])
        self.screen.clip = self.dash_rect
        ctx.oy = dash.VIEW_H + dash.DASH_H // 2
        dash.draw_dashboard(ctx, g)
        return True

    def done(self, ctx):
        self.screen.clip = self.full
        ctx.ox = dash.SCREEN_W // 2
        ctx.oy = dash.VIEW_H // 2       # the pause menu: over the view
