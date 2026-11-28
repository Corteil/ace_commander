"""The 2022 EMF badge's (TiDAL's) screen under stock MicroPython, for the bridge's
status page (main.py): an ST7789, 135 x 240, on SPI; pins from the TiDAL firmware
(emfcamp/TiDAL-Firmware, modules/tidal.py): clock GPIO12, data GPIO11, chip select
GPIO10, data / command GPIO13, reset GPIO14; power GPIO39 and backlight GPIO0, both
on when low. Drawn landscape (240 x 135) through a framebuf with its 8 x 8 font.
"""
import time
import framebuf
from machine import Pin, SPI

W, H = 240, 135
X0, Y0 = 40, 53         # where a 135 x 240 panel's picture starts in the ST7789's 240 x 320

BLACK = 0x0000
WHITE = 0xFFFF
GREEN = 0x07E0
YELLOW = 0xFFE0
CYAN = 0x07FF
RED = 0xF800
GREY = 0x8410
PINK = 0xF81F


def rgb(c):
    """framebuf's RGB565 is little-endian; the ST7789 wants big-endian: swap the bytes."""
    return ((c & 0xFF) << 8) | (c >> 8)


class Screen:
    def __init__(self):
        Pin(39, Pin.OUT, value=0)                           # the screen's power: on
        Pin(0, Pin.OUT, drive=Pin.DRIVE_0, value=0)         # backlight: on
        self.cs = Pin(10, Pin.OUT, value=1)
        self.dc = Pin(13, Pin.OUT, value=0)
        self.rst = Pin(14, Pin.OUT, value=1)
        self.spi = SPI(2, baudrate=40000000, polarity=0, sck=Pin(12), mosi=Pin(11))
        self.buf = bytearray(W * H * 2)
        self.fb = framebuf.FrameBuffer(self.buf, W, H, framebuf.RGB565)
        self._reset()

    def _cmd(self, c, data=None):
        self.cs(0)
        self.dc(0)
        self.spi.write(bytes((c,)))
        if data:
            self.dc(1)
            self.spi.write(data)
        self.cs(1)

    def _reset(self):
        self.rst(0)
        time.sleep_ms(20)
        self.rst(1)
        time.sleep_ms(120)
        self._cmd(0x01)                 # software reset
        time.sleep_ms(150)
        self._cmd(0x11)                 # out of sleep
        time.sleep_ms(120)
        self._cmd(0x3A, b"\x55")        # 16-bit colour
        self._cmd(0x36, b"\x60")        # landscape (row / column exchange, mirror x)
        self._cmd(0x21)                 # inverted colours: this panel's normal
        self._cmd(0x13)                 # normal display
        self._cmd(0x29)                 # on
        time.sleep_ms(20)

    def show(self):
        """Send the whole picture."""
        x1, y1 = X0 + W - 1, Y0 + H - 1
        self._cmd(0x2A, bytes((X0 >> 8, X0 & 0xFF, x1 >> 8, x1 & 0xFF)))
        self._cmd(0x2B, bytes((Y0 >> 8, Y0 & 0xFF, y1 >> 8, y1 & 0xFF)))
        self._cmd(0x2C, self.buf)

    def clear(self, c=BLACK):
        self.fb.fill(rgb(c))

    def text(self, s, x, y, c=WHITE, scale=1):
        """Text in framebuf's 8 x 8 font, scale times as big (1 or 2)."""
        if scale == 1:
            self.fb.text(s, x, y, rgb(c))
            return
        tmp = framebuf.FrameBuffer(bytearray(8 * 8 * 2), 8, 8, framebuf.RGB565)
        for i, ch in enumerate(s):
            tmp.fill(0)
            tmp.text(ch, 0, 0, 1)
            for py in range(8):
                for px in range(8):
                    if tmp.pixel(px, py):
                        self.fb.fill_rect(x + (i * 8 + px) * scale, y + py * scale, scale, scale, rgb(c))

    def rect(self, x, y, w, h, c):
        self.fb.fill_rect(x, y, w, h, rgb(c))
