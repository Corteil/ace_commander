"""The Pi's sounds (builds 140-141): the game's sound table (sfx.py, Elite's
with its data) played as square waves and noise through pygame's mixer, the
same tunes the badge plays on an I2S amp (i2s_sound.py). Each sound is made
once, at start; its parts are mixed together.

run.py makes a Player with --sound and gives the platform its play() and
step() (platform_pi.Platform.sound / sound_step). A sound starts on its
channel (sfx.CHANNELS, as Elite's flush), cutting off what was playing there.
"""
import array
import random

RATE = 22050
LEVEL = 19000           # of 32767, at level 126, made at the loudest (sfx.VOLUMES[11]):
                        # Options > VOLUME turns the channels down (build 145)


class Player:
    def __init__(self, pygame, sfx):
        """Raises if there is no sound device (run.py then carries on silent)."""
        self.pg = pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init(RATE, -16, 1, 512)
        self.rate, _, self.stereo = pygame.mixer.get_init()
        self.sfx = sfx
        names = list(sfx.SOUNDS)
        keys = []
        for n in names:
            k = sfx.CHANNELS.get(n, n)
            if k not in keys:
                keys.append(k)
        pygame.mixer.set_num_channels(max(8, len(keys)))
        self.channels = {k: pygame.mixer.Channel(i) for i, k in enumerate(keys)}
        self.volume = 1.0
        self.set_volume(sfx.VOLUME_DEFAULT)
        self.sounds = {}
        for name in names:
            self.sounds[name] = pygame.mixer.Sound(buffer=self._make(sfx.SOUNDS[name][1:]))

    def _part(self, steps):
        rate = self.rate
        out = []
        for st in steps:
            f, ms = st[0], st[1]
            amp = LEVEL * (st[2] if len(st) > 2 else 126) // 126
            n = rate * ms // 1000
            if f < 0:                   # noise, changing -f times a second
                hold = max(1, rate // -f)
                v = 0
                for i in range(n):
                    if i % hold == 0:
                        v = random.randint(-amp, amp)
                    out.append(v)
            elif f == 0 or amp == 0:
                out.extend([0] * n)
            else:
                half = max(1, rate // (2 * f))
                for i in range(n):
                    out.append(amp if (i // half) % 2 == 0 else -amp)
        return out

    def _make(self, parts):
        mixed = []
        for part in parts:
            samples = self._part(part)
            if len(samples) > len(mixed):
                mixed.extend([0] * (len(samples) - len(mixed)))
            for i, v in enumerate(samples):
                mixed[i] += v
        out = array.array("h", (max(-32767, min(32767, v)) for v in mixed))
        if self.stereo == 2:        # the mixer opened in stereo: the same both sides
            st = array.array("h")
            for v in out:
                st.append(v)
                st.append(v)
            out = st
        return out.tobytes()

    def set_volume(self, v):
        """Options > VOLUME 1-11: the same heights as the badge's (sfx.VOLUMES)."""
        v = max(1, min(self.sfx.VOLUME_MAX, v))
        self.volume = self.sfx.VOLUMES[v] / float(LEVEL)
        for c in self.channels.values():
            c.set_volume(self.volume)

    def stop(self):
        self.pg.mixer.stop()

    def play(self, name):
        s = self.sounds.get(name)
        if s is not None:
            c = self.channels[self.sfx.CHANNELS.get(name, name)]
            c.play(s)
            c.set_volume(self.volume)       # (play can reset it)

    def step(self):
        pass                # the mixer plays on by itself
