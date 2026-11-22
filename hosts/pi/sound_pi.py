"""The Pi's sounds (build 140): the game's sound table (sfx.py) played as
square waves and noise through pygame's mixer, the same tunes a Qwiic buzzer
plays on the badge and the Tufty. Each sound is made once, at start.

run.py makes a Player with --sound and gives the platform its play() and
step() (platform_pi.Platform.sound / sound_step).
"""
import array
import random

RATE = 22050
LEVEL = 6000            # of 32767: square waves are loud
NOISE_HOLD = 6          # samples each noise value is held: a rougher, lower hiss


class Player:
    def __init__(self, pygame, sfx):
        """Raises if there is no sound device (run.py then carries on silent)."""
        self.pg = pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(RATE, -16, 1, 512)
        self.rate, _, self.channels = pygame.mixer.get_init()
        pygame.mixer.set_num_channels(12)
        self.sounds = {}
        for name, (prio, steps) in sfx.SOUNDS.items():
            self.sounds[name] = pygame.mixer.Sound(buffer=self._make(steps, sfx.NOISE))

    def _make(self, steps, noise):
        rate = self.rate
        out = array.array("h")
        for f, ms in steps:
            n = rate * ms // 1000
            if f == noise:
                v = 0
                for i in range(n):
                    if i % NOISE_HOLD == 0:
                        v = random.randint(-LEVEL, LEVEL)
                    out.append(v)
            elif f <= 0:
                out.extend([0] * n)
            else:
                half = max(1, rate // (2 * f))
                for i in range(n):
                    out.append(LEVEL if (i // half) % 2 == 0 else -LEVEL)
        if self.channels == 2:      # the mixer opened in stereo: the same both sides
            st = array.array("h")
            for v in out:
                st.append(v)
                st.append(v)
            out = st
        return out.tobytes()

    def play(self, name):
        s = self.sounds.get(name)
        if s is not None:
            s.play()

    def step(self):
        pass                # the mixer plays on by itself
