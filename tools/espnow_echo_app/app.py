"""ESP-NOW Echo: tools/espnow_link.py's echo() as a badge app, for range tests on
battery (plans/MULTIPLAYER.md). The badge reboots when its USB is pulled, so an
echo started over USB dies; start this from the badge's menu instead.

Every test packet heard goes straight back to its sender, from the background
task (polled every couple of ms, so the round trip stays short). The screen shows
the count and when the last one came. F (cancel) leaves; the radio stays on until
the badge restarts. Needs espnow_link.py in this folder.
"""
import time

import app
from async_helpers import sleep_ms
from events.input import Buttons, BUTTON_TYPES

from . import espnow_link as link


class EspnowEcho(app.App):
    def __init__(self):
        super().__init__()
        self.buttons = Buttons(self)
        self.e, sta, self.ch = link.radio()
        self.mac = link.mac_str(sta.config("mac"))
        self.peers = set()
        self.n = 0
        self.last = None            # ticks_ms of the last packet
        self.running = True

    async def background_task(self):
        while self.running:
            got = False
            for _ in range(8):
                host, msg = self.e.irecv(0)
                if msg is None:
                    break
                got = True
                if link.echo_one(self.e, self.peers, host, msg):
                    self.n += 1
                    self.last = time.ticks_ms()
            await sleep_ms(0 if got else 2)

    def update(self, delta):
        if self.buttons.get(BUTTON_TYPES["CANCEL"]):
            self.buttons.clear()
            self.running = False
            self.minimise()

    def draw(self, ctx):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.font_size = 24
        ctx.rgb(0.2, 1, 0.4).move_to(0, -60).text("ESP-NOW ECHO")
        ctx.font_size = 16
        ctx.rgb(0.8, 0.8, 0.8).move_to(0, -30).text(self.mac)
        ctx.move_to(0, -10).text("channel %d" % self.ch)
        ctx.font_size = 36
        ctx.rgb(1, 1, 1).move_to(0, 30).text(str(self.n))
        ctx.font_size = 16
        if self.last is None:
            s = "waiting for ping"
        else:
            s = "last %d s ago" % (time.ticks_diff(time.ticks_ms(), self.last) // 1000)
        ctx.rgb(0.8, 0.8, 0.8).move_to(0, 62).text(s)
        ctx.move_to(0, 90).text("F: leave")


__app_export__ = EspnowEcho
