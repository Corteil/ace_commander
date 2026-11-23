"""The Tildagon badge's side of the platform layer: what only the badge's
firmware can do, so the rest of the game doesn't import it.

Step 2 (build 101): input. Input listens for the firmware's button events and
tells controls.Controls which control names each one counts as.

Step 3 (build 103): the rest, moved out of ace.py, not rewritten. Platform is
what the game asks of the device it runs on; another device (hosts/) gives
config.platform its own module with the same names, App, Platform and
owner_name:

    App                         the game's base class (the firmware's app.App)
    Platform(app)               made once by the game (app: ace.AceCommander)
      .leds                     True if there is a ring of 12 LEDs
      .leds_rgb(r, g, b)        the whole ring one colour (0-255 each); written
                                only when it changes
      .leds_each(values, rgb)   each LED in colour rgb at its own level (values[1]
                                to [12], 0-255)
      .leds_release()           give the LEDs back to the device
      .tilt_ok                  True if there is a tilt sensor
      .tilt()                   read the sensor: True, with .tx and .ty the
                                acceleration in g; False if it failed
      .keyboard_fitted()        True if a keyboard is known to be fitted
      .text_dialog(title)       the device's own text entry (the firmware's
                                TextDialog: .text, .message, ._result), or None
      .fast                     True if run() can skip the wait between frames
      run(render_update)        the frame loop (async)
      .minimise()               leave the game
      .gamepad                  optional: True / False if the device can switch a
                                gamepad on and off (DEBUG > DISPLAY), with
                                .set_gamepad(on); missing or None: no such line
      .sound_ok                 optional: True if it can play sfx.py's sounds, with
                                .sound(name) to start one and .sound_step() each
                                frame (build 140); missing or False: no SOUND line
      .sound_port               optional: the hexpansion port the I2S amp is on
                                (1-6, build 145), with .set_sound_port(n); missing
                                or None: no SOUND PORT line
      .set_volume(v)            optional: Options > VOLUME, 1-11 (build 145);
                                missing: no VOLUME line
      .sound_stop()             optional: cut off what is playing (SOUND: MUTED)
    owner_name()                the device owner's name, or None
"""
import asyncio
import gc

import app as _app
from events.input import BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from events.joystick import JOYSTICK_BUTTON_TYPES as JOY
from frontboards.common import FRONTBOARD_BUTTON_TYPES as FB
from system.eventbus import eventbus

try:
    from events.keyboard import KEYBOARD_BUTTONS
except ImportError:
    KEYBOARD_BUTTONS = {}

try:
    import imu
except ImportError:
    imu = None

try:    # lets the flight screen skip the 50 ms pause the badge adds to every frame
    from system.scheduler import scheduler
except Exception:
    scheduler = None

try:    # the badge's LEDs, used to flash red when you're hit
    from tildagonos import tildagonos
    from system.patterndisplay.events import PatternDisable, PatternEnable
except Exception:
    tildagonos = None

from . import config

# Room for garbage (build 108). The badge's Python heap grows only when a
# collection can't free enough, and hands back any area left empty, so with
# the game's ~450 KB in use there was room for only ~60 KB of garbage: a 100 ms
# collection every 10-15 flight frames, seen as the stardust stuttering (Brian;
# every slow frame in the PERF lines was one). So at the start the heap is
# grown by about HEAP_ROOM, one small piece kept at the far end of the new area
# so it isn't handed back. Measured: 5 times fewer collections, each 30 -> 44 ms.
HEAP_ROOM = 512 * 1024     # grow if it has less free than this
HEAP_CHUNK = 16 * 1024
SYSTEM_KEEP = 300 * 1024   # and only if the system keeps this much (Wi-Fi and the rest)

App = _app.App      # the game's base class: the scheduler's app (on a PC, its own host)

# keyboard keys not in the firmware's KEYBOARD_BUTTONS, by the name a driver
# would give them, and the control name they count as
BY_NAME = {"TAB": "k_TAB", "LSHIFT": "k_LSHIFT", "RSHIFT": "k_RSHIFT"}


class Input:
    """The firmware's button events in, control names out (to controls).

    The firmware's own Buttons.get() searches every known button each time it
    is asked, which is slow when a game asks about twenty things a frame. This
    does the matching once per button (a firmware button counts as each of
    its parents: the badge's A is also UP and Frontboard A) and remembers it.
    """

    def __init__(self, owner, controls):
        self.controls = controls
        table = [(name.lower(), BUTTON_TYPES[name])
                 for name in ("UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "CANCEL")]
        for name in ("UP", "DOWN", "LEFT", "RIGHT"):
            table.append(("j_" + name.lower(), JOY[name]))
        for name in "ABCDEF":
            table.append((name, FB[name]))
        for name in ("W", "S", "A", "D", "E", "Q", "F", "M", "P", "N", "T", "U", "V", "C", "SPACE",
                     "BACKSPACE",
                     "UP", "DOWN", "LEFT", "RIGHT"):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append(("k_" + name, key))
                if name in ("UP", "DOWN", "LEFT", "RIGHT"):
                    # the cursor keys count as the joystick too, so every menu,
                    # tab and chart that reads "j_up" ... takes them (Brian)
                    table.append(("j_" + name.lower(), key))
        # the views are Elite's f0 (front), f1 (rear), f2 (left), f3 (right), on the number
        # keys 1 to 4 as the keyboard plan has it (top row 1-0 are f0-f9)
        for n in range(4):
            key = KEYBOARD_BUTTONS.get(str(n + 1))
            if key is not None:
                table.append(("k_view%d" % n, key))
        # the rest of Elite's keys (Brian chose Elite's scheme, 2026-11-16): the
        # number row is f0-f9 ("k_1" ... "k_0"), H hyperspace (Ctrl+H the galactic
        # hyperdrive, as Elite), J the jump drive, + / - speed ("=" and "_" too,
        # the same keys without shift)
        for name in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "H", "J", "SHIFT", "CTRL",
                     "ESCAPE"):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append(("k_" + name, key))
        for name, control in (("+", "k_faster"), ("=", "k_faster"),
                              ("-", "k_slower"), ("_", "k_slower")):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append((control, key))
        self.table = table
        # the letters a keyboard types, for finding a system by name (build 88)
        self.letters = {}
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            key = KEYBOARD_BUTTONS.get(ch)
            if key is not None:
                self.letters[key] = ch
        key = KEYBOARD_BUTTONS.get("SPACE")
        if key is not None:
            self.letters[key] = " "
        # the keyboard's A-F, which off the flight are the badge's buttons
        # (controls.Controls.as_buttons)
        self.badge_keys = {}
        for ch, sysname in (("A", "up"), ("B", "right"), ("C", "confirm"),
                            ("D", "down"), ("E", "left"), ("F", "cancel")):
            key = KEYBOARD_BUTTONS.get(ch)
            if key is not None:
                self.badge_keys[key] = (ch, sysname)
        # and Enter and Esc are C and F there (Brian, build 102)
        for name, as_badge in (("ENTER", ("C", "confirm")), ("ESCAPE", ("F", "cancel"))):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                self.badge_keys[key] = as_badge
        self.names = {}      # button -> the control names it counts as
        eventbus.on(ButtonDownEvent, self._down, owner)
        eventbus.on(ButtonUpEvent, self._up, owner)

    def _names(self, button):
        names = self.names.get(button)
        if names is None:
            names = tuple(n for n, kind in self.table if kind in button)
            # keys the firmware's KEYBOARD_BUTTONS lacks, matched by name in case
            # a keyboard driver sends them anyway: Tab (Elite's energy bomb)
            if getattr(button, "name", None) in BY_NAME:
                names += (BY_NAME[button.name],)
            self.names[button] = names
        return names

    def _down(self, event):
        button = event.button
        if config.log_keys:
            print("KEY DOWN", repr(button))
        self.controls.press(button, self._names(button), self.letters.get(button),
                            self.badge_keys.get(button))

    def _up(self, event):
        button = event.button
        if config.log_keys:
            print("KEY UP", repr(button))
        self.controls.release(button)


def owner_name():
    """The badge owner's name from the badge's settings, or None."""
    try:
        import settings
        n = settings.get("name")
        if isinstance(n, str) and n.strip():
            return n.strip()
    except Exception:
        pass
    return None


try:
    import time
    _ms = time.ticks_ms
    _diff = time.ticks_diff
except AttributeError:   # off the badge (tests)
    def _ms():
        return int(time.perf_counter() * 1000)

    def _diff(a, b):
        return a - b


class Platform:
    """The badge's firmware, for the game (see the top of this file)."""

    def __init__(self, app):
        self.app = app
        self.host = app.host        # the app the scheduler knows (app.py's loader)
        self.leds = tildagonos is not None
        self.leds_on = False        # we have taken over the LEDs
        self.led_level = None       # (r, g, b) last written to the whole ring
        self.tilt_ok = imu is not None
        self.tx = self.ty = 0.0     # the last tilt reading, in g
        self.picker_choice = True   # Options > TEXT ENTRY: its own dialog or the letter picker
        self.fast = scheduler is not None
        self.anchor = self._grow_heap()
        try:        # an I2S amp or DAC on a hexpansion port (build 145): can't be
            from machine import I2S     # detected, so Options > SOUND PORT says where
            self.sound_ok = I2S is not None
        except ImportError:
            self.sound_ok = False
        self.sound_port = 2 if self.sound_ok else None  # (i2s_sound.PORT; ace.py sets the saved one)
        self.synth = None           # i2s_sound.Synth, made on the first sound
        self.i2s = None             # its machine.I2S
        self.sound_failed = False   # the port wouldn't open: silent until it changes
        self.volume = 8             # Options > VOLUME 1-11 (sfx.VOLUME_DEFAULT; ace.py sets it)

    def _open_sound(self):
        """The synthesiser on the SOUND PORT's I2S, the first time a sound plays."""
        if self.sound_failed:
            return None
        try:
            from . import i2s_sound
            self.i2s = i2s_sound.open_i2s(self.sound_port)
            self.synth = i2s_sound.Synth(self.i2s)
            self.synth.set_volume(self.volume)
            print("I2S sound on hexpansion port %d" % self.sound_port)
        except Exception as e:
            print("I2S sound on port %s failed: %r" % (self.sound_port, e))
            self.sound_failed = True
            self.close_sound()
        return self.synth

    def close_sound(self):
        """Give I2S back (leaving the game, or a new port), so other apps can use it."""
        self.synth = None
        if self.i2s is not None:
            try:
                self.i2s.deinit()
            except Exception:
                pass
            self.i2s = None

    def set_sound_port(self, port):
        if port != self.sound_port:
            self.close_sound()
            self.sound_port = port
            self.sound_failed = False

    def set_volume(self, v):
        self.volume = v
        if self.synth is not None:
            self.synth.set_volume(v)

    def sound_stop(self):
        """SOUND: MUTED cuts off what is playing."""
        if self.synth is not None:
            self.synth.stop()

    def sound(self, name):
        s = self.synth or self._open_sound()
        if s is not None:
            s.play(name)

    def sound_step(self):
        if self.synth is not None:
            self.synth.step()

    @staticmethod
    def _grow_heap():
        """Grow the heap once (by about its own size: the firmware doubles it)
        if it has less than HEAP_ROOM free and the system would keep at least
        SYSTEM_KEEP; keep the chunk that lands in the new area so the area isn't
        handed back (see HEAP_ROOM). Returns the kept chunk, or None."""
        try:
            import esp32
        except ImportError:
            return None     # not the badge

        def split():        # the largest block the heap could grow into
            return max([r[2] for r in esp32.idf_heap_info(esp32.HEAP_DATA)] or [0])
        try:
            s0 = split()
            free = gc.mem_free() - s0       # mem_free counts that block too
            total = gc.mem_alloc() + free
            if free >= HEAP_ROOM or s0 - total < SYSTEM_KEEP:
                if config.perf_log:
                    print("HEAP %d KB, %d free, system %d: left as it is" % (
                        total // 1024, free // 1024, s0 // 1024))
                return None
            chunks = []
            anchor = None
            for _ in range(HEAP_ROOM // HEAP_CHUNK + 8):
                c = bytearray(HEAP_CHUNK)
                if split() < s0 - HEAP_CHUNK:   # this one made a new area: keep it
                    anchor = c
                    break
                chunks.append(c)
            chunks = None
            gc.collect()
            if config.perf_log:
                s1 = split()
                print("HEAP %d KB, %d free, system %d: grown, now %d free, system %d" % (
                    total // 1024, free // 1024, s0 // 1024,
                    (gc.mem_free() - s1) // 1024, s1 // 1024))
            return anchor
        except MemoryError:
            gc.collect()
            return None

    # ---- LEDs -------------------------------------------------------------

    def _take_leds(self):
        if not self.leds_on:
            eventbus.emit(PatternDisable())
            try:
                tildagonos.set_led_power(True)
            except Exception:
                pass
            self.leds_on = True
            self.led_level = None

    def leds_rgb(self, r, g, b):
        """Set the ring of 12 LEDs to (r, g, b), 0-255 each, taking them over
        from the badge's own pattern first. Only writes when the colour changes."""
        if tildagonos is None:
            return
        try:
            self._take_leds()
            rgb = (r, g, b)
            if rgb != self.led_level:
                self.led_level = rgb
                leds = tildagonos.leds
                for i in range(1, 13):      # the front ring is LEDs 1 to 12
                    leds[i] = rgb
                leds.write()
        except Exception:
            self.leds_on = False

    def leds_each(self, values, rgb):
        """Each ring LED in colour rgb at its own level (values[1] to [12],
        0-255)."""
        if tildagonos is None:
            return
        try:
            self._take_leds()
            leds = tildagonos.leds
            r, gr, b = rgb
            for i in range(1, 13):
                v = int(values[i])
                leds[i] = (r * v // 255, gr * v // 255, b * v // 255)
            leds.write()
            self.led_level = None       # the next whole-ring colour is written afresh
        except Exception:
            self.leds_on = False

    def leds_release(self):
        """Hand the LEDs back to the badge's own pattern."""
        if self.leds_on:
            self.leds_on = False
            try:
                eventbus.emit(PatternEnable())
            except Exception:
                pass

    # ---- tilt -------------------------------------------------------------

    def tilt(self):
        """Read the accelerometer into tx, ty (in g): True, or False if it
        failed (then tilt_ok is False from then on). No new object per frame."""
        if not self.tilt_ok:
            return False
        try:
            ax, ay, _ = imu.acc_read()
        except Exception:
            self.tilt_ok = False
            return False
        self.tx = ax / 9.81
        self.ty = ay / 9.81
        return True

    # ---- keyboard and text entry -----------------------------------------

    def keyboard_fitted(self):
        """True if a keyboard is fitted: its hexpansion's driver (KeyboardApp)
        is running, or its header names a keyboard."""
        try:
            from system.hexpansion.app import _hexpansion_manager as m
            if m is not None:
                for a in m.hexpansion_apps.values():
                    if a is not None and type(a).__name__ == "KeyboardApp":
                        return True
                for h in m.hexpansion_headers.values():
                    if h is not None and "KEYB" in str(getattr(h, "friendly_name", "")).upper():
                        return True
        except Exception:
            pass
        return False

    def text_dialog(self, title):
        """The letter picker (picker.py) if Options > TEXT ENTRY says so (build
        124), else the firmware's TextDialog with the game's smaller text
        (build 90), or None if there is none. Registered to the host (app.py's loader): the
        firmware's eventbus gives the buttons only to the focused app, and the
        game itself never is (build 89 fix: it froze the badge)."""
        if getattr(self.app, "use_picker", False):
            from .picker import LetterPicker
            return LetterPicker(title, driven=True)
        try:
            from app_components.dialog import TextDialog
            from . import find
            return find.small_dialog(TextDialog)(title, self.host)
        except Exception:
            return None

    # ---- the frame loop ---------------------------------------------------

    async def run(self, render_update):
        """The badge's own loop waits 50 ms after every update before the next
        one, which caps any app at about 14 frames a second. On the title
        screen, in flight and in the viewer this asks for a redraw directly and
        carries on as soon as it has been drawn. The other screens, and
        anything unexpected, use the normal path. app.fast switches it off."""
        a = self.app
        last = _ms()
        while True:
            now = _ms()
            a.update(_diff(now, last))
            last = now
            if a.fast and (a.mode == "flight" or a.mode == "viewer"
                           or a.mode == "launch" or a.mode == "docking"
                           or (a.mode == "menu" and a.title is not None)):
                try:
                    scheduler.render_needed.set()
                    await asyncio.sleep(0)      # the renderer and other tasks run here
                    if scheduler.app_is_foregrounded(self.host):
                        continue
                except Exception:
                    a.fast = False              # firmware differs: stay on the normal path
            await render_update()

    def minimise(self):
        """Leave the game: the host (the loading screen) is the app the
        scheduler knows; the game is its own host only on a PC (the tests)."""
        self.close_sound()
        if self.host is not self.app:
            self.host.minimise()
        else:
            _app.App.minimise(self.host)
