"""Ace Commander on a Raspberry Pi (or any computer with Python 3 and pygame).

    python3 hosts/pi/run.py             a window, the badge's round screen at 2x
    python3 hosts/pi/run.py --scale 3   bigger
    python3 hosts/pi/run.py --full      full screen, as big as fits

Keys: arrows are the joystick, Enter confirms (the joystick pressed in), Esc
goes back, F1-F6 are the badge's buttons A-F, and the rest of the keyboard is
the Keyboard Hexpansion (Elite's keys). Close the window or leave from the
title screen to quit. Saves go in ~/.local/share/ace_commander/.

The game itself is the badge app in the folder above, run unchanged on
stand-ins for the badge's firmware (pi_firmware.py); see hosts/README.md.
"""
import argparse
import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
PKG = os.path.basename(REPO)            # the game's package: the repo folder, ace_commander
for p in (HERE, os.path.dirname(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame                       # noqa: E402

import pi_firmware                  # noqa: E402
from ctx_pygame import Ctx          # noqa: E402
from keys_pi import Keys            # noqa: E402

BACKGROUND = (24, 24, 30)           # round the screen, like the badge's case
LED_SIZE = 4                        # an LED's radius, in game pixels
FPS = 60


def data_dir():
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(os.path.expanduser("~"), ".local", "share")
    d = os.path.join(base, "ace_commander")
    os.makedirs(d, exist_ok=True)
    return d


class Host:
    """The game in a pygame window: events in, update, draw, show."""

    def __init__(self, scale=2, full=False, save_dir=None):
        pygame.init()
        pygame.display.set_caption("Ace Commander")
        self.bus, self.leds = pi_firmware.install()
        self.ace = importlib.import_module(PKG + ".ace")
        # saves (and options.json beside them) under the user's data folder
        d = save_dir or data_dir()
        self.ace.SAVE_PATH = os.path.join(d, os.path.basename(self.ace.SAVE_PATH))
        if full:
            self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            w, h = self.window.get_size()
            scale = max(1, min(w, h) * 9 // 10 // 240)
        else:
            margin = 16 * scale
            self.window = pygame.display.set_mode((240 * scale + 2 * margin,) * 2)
        self.scale = scale
        w, h = self.window.get_size()
        size = 240 * scale
        self.screen_rect = pygame.Rect((w - size) // 2, (h - size) // 2, size, size)
        self.screen = pygame.Surface((size, size))
        self.ctx = Ctx(self.screen, scale)
        self.mask = self._round_mask(size)
        self.keys = Keys(self.bus)
        self.app = self.ace.AceCommander()
        self.clock = pygame.time.Clock()
        self.running = True
        self.frames = 0

    @staticmethod
    def _round_mask(size):
        """The case's colour outside the round screen, see-through inside."""
        m = pygame.Surface((size, size), pygame.SRCALPHA)
        m.fill(BACKGROUND + (255,))
        pygame.draw.circle(m, (0, 0, 0, 0), (size // 2, size // 2), size // 2)
        return m

    def handle(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type in (pygame.WINDOWFOCUSLOST, pygame.WINDOWMINIMIZED):
            self.keys.release_all()
        else:
            self.keys.handle(event)

    def step(self, ms):
        """One frame: the game's update, then its drawing, onto the window."""
        self.app.update(ms)
        if getattr(self.app, "quit", False):
            self.running = False
            return
        self.screen.fill((0, 0, 0))
        self.app.draw(self.ctx)
        self.screen.blit(self.mask, (0, 0))
        self.window.fill(BACKGROUND)
        self.window.blit(self.screen, self.screen_rect)
        self._draw_leds()
        self.frames += 1

    def _draw_leds(self):
        """The badge's ring of 12 LEDs round the screen, where the game puts
        them (its LED_ANGLE1 and LED_CLOCKWISE: jump flashes light the side
        the streaks leave by)."""
        cx, cy = self.screen_rect.center
        r = self.screen_rect.width / 2 + (LED_SIZE + 3) * self.scale
        step = -30.0 if self.ace.LED_CLOCKWISE else 30.0
        for i in range(1, 13):
            a = math.radians(self.ace.LED_ANGLE1 + (i - 1) * step)    # anticlockwise from 3 o'clock
            rgb = self.leds.values[i]
            col = rgb if any(rgb) else (40, 40, 48)
            pygame.draw.circle(self.window, col, (cx + r * math.cos(a), cy - r * math.sin(a)),
                               LED_SIZE * self.scale)

    def run(self, frames=None):
        last = pygame.time.get_ticks()
        while self.running:
            for event in pygame.event.get():
                self.handle(event)
            now = pygame.time.get_ticks()
            ms = min(100, max(1, now - last))
            last = now
            self.step(ms)
            pygame.display.flip()
            self.clock.tick(FPS)
            if frames is not None and self.frames >= frames:
                break
        pygame.quit()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Ace Commander on a Raspberry Pi")
    ap.add_argument("--scale", type=int, default=2, help="the badge's 240 x 240 screen times this")
    ap.add_argument("--full", action="store_true", help="full screen")
    ap.add_argument("--frames", type=int, default=None, help="stop after this many frames")
    args = ap.parse_args(argv)
    Host(args.scale, args.full).run(args.frames)


if __name__ == "__main__":
    main()
