"""The Pi's sounds (builds 140-141, 146): the game's sound table (sfx.py,
Elite's with its data) made by the badge's own synthesiser (i2s_sound.py) once
at start and played through pygame's mixer, so the Pi and the badge sound the
same.

run.py makes a Player with --sound and gives the platform its play() and
step() (platform_pi.Platform.sound / sound_step). A sound starts on its
channel (sfx.CHANNELS, as Elite's flush), cutting off what was playing there.
"""
import array

RATE = 22050
LEVEL = 19000           # of 32767, at level 126, made at the loudest (sfx.VOLUMES[11]):
                        # Options > VOLUME turns the channels down (build 145)


class Player:
    def __init__(self, pygame, sfx, i2s_sound):
        """Raises if there is no sound device (run.py then carries on silent).
        sfx, i2s_sound: the game's modules (the table and the synthesiser)."""
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
        self.synth = i2s_sound.Synth(None, rate=self.rate)
        self.synth.set_volume(sfx.VOLUME_MAX)       # made at the loudest: LEVEL
        self.sounds = {}
        for name in names:
            self.sounds[name] = pygame.mixer.Sound(buffer=self._make(name))

    def _make(self, name):
        """One sound, made by the badge's synthesiser (i2s_sound.Synth.render,
        build 146) at the mixer's rate and the loudest volume, so the Pi and
        the badge play the same: exact pitches, the same noise and mixing."""
        out = self.synth.render(name)
        if self.stereo == 2:        # the mixer opened in stereo: the same both sides
            st = array.array("h", bytes(4 * len(out)))
            st[0::2] = out
            st[1::2] = out
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
