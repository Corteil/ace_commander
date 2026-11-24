"""ESP-NOW Echo: tools/espnow_link.py's echo() as a badge app, for range tests on
battery (plans/MULTIPLAYER.md). The badge reboots when its USB is pulled, so an
echo started over USB dies; start this from the badge's menu instead.

Every test packet heard goes straight back to its sender, from the receive
callback (and the background task as a fallback): an app's background task only runs
between frames, ~100 ms on screen, which overflowed ESP-NOW's small receive buffer. The screen shows
the count and when the last one came. F (cancel) leaves; the radio stays on until
the badge restarts. Needs espnow_link.py in this folder.
"""
import time

import app
from asyncio import sleep_ms
from events.input import Buttons, BUTTON_TYPES

from . import espnow_link as link


class EspnowEcho(app.App):
    def __init__(self):
        super().__init__()
        self.buttons = Buttons(self)
        self.peers = set()
        self.n = 0
        self.last = None            # ticks_ms of the last packet
        self.running = True
        self.error = None           # shown on screen instead of crashing
        self.e = None
        self.mac, self.ch = "?", 0
        self.start()

    def start(self):
        """The radio; any error goes on the screen (and to serial)."""
        try:
            self.e, sta, self.ch = link.radio()
            self.mac = link.mac_str(sta.config("mac"))
            self.error = None
            try:
                self.e.config(rxbuf=4096)   # default ~500 bytes: drops packets between frames
            except Exception:
                pass
            # answer from the receive callback (run between Python steps, even
            # mid-frame); the background task stays as a fallback
            self.e.irq(self._irq)
        except Exception as err:
            import sys
            sys.print_exception(err)
            self.error = repr(err)[:60]

    def _irq(self, e):
        self._drain()

    def _drain(self):
        while True:
            host, msg = self.e.irecv(0)
            if msg is None:
                return
            if link.echo_one(self.e, self.peers, host, msg):
                self.n += 1
                self.last = time.ticks_ms()

    async def background_task(self):
        while self.running:
            if self.e is None:
                await sleep_ms(500)
                continue
            self._drain()
            await sleep_ms(5)

    def _retry(self):
        if self.buttons.get(BUTTON_TYPES["CONFIRM"]):
            self.buttons.clear()
            self.start()

    def update(self, delta):
        if self.buttons.get(BUTTON_TYPES["CANCEL"]):
            self.buttons.clear()
            self.running = False
            if self.e is not None:
                self.e.irq(None)
            self.minimise()
        elif self.e is None:
            self._retry()

    def draw(self, ctx):
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.font_size = 24
        ctx.rgb(0.2, 1, 0.4).move_to(0, -60).text("ESP-NOW ECHO")
        ctx.font_size = 16
        if self.error:
            ctx.rgb(1, 0.3, 0.3).move_to(0, -20).text("RADIO FAILED")
            ctx.font_size = 12
            ctx.move_to(0, 5).text(self.error[:30])
            ctx.move_to(0, 22).text(self.error[30:60])
            ctx.font_size = 16
            ctx.rgb(0.8, 0.8, 0.8).move_to(0, 60).text("C: try again  F: leave")
            return
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
