"""Elite for the EMF Tildagon / Spaceagon badge: a flight combat game and a
ship viewer, drawn as hidden-line wireframes with the original ship data.

Flight (2026 Spaceagon)
    Joystick      pitch and roll
    C, or press the joystick    fire lasers (hold)
    B             fire a missile at the boxed target
    F / E         speed up / slow down
    A             pause
    D             re-zero tilt (only when steering by tilt)
The pause screen can switch steering to TILT: then tilting the badge steers,
and the joystick still works. The badge's LEDs flash red when you are hit.

Pause screen
    C or A resume, F back to the menu, joystick left / right changes steering

Keyboard
    W / S or up / down pitch, A / D or left / right roll, E / Q speed up /
    down, F or SPACE lasers, M missile, P pause

Ship viewer
    Joystick or buttons turn the ship, CONFIRM (or N) next ship, P previous
    ship, CANCEL back to the menu.

Ships come from ship_data.py, next to this file. Make it with
tools/import_ships.py from your own copy of the Elite source.

If something moves the wrong way, or you want other buttons, change the
constants below.
"""
import asyncio
import gc
import time

import app
from events.input import BUTTON_TYPES, ButtonDownEvent, ButtonUpEvent
from system.eventbus import eventbus

from . import bench, cockpit, game, viewer

try:
    import imu
except ImportError:
    imu = None

try:
    from events.keyboard import KEYBOARD_BUTTONS
except ImportError:
    KEYBOARD_BUTTONS = {}

try:
    from .ship_data import SHIPS
except Exception:
    SHIPS = ()

try:    # the joystick's directions and buttons A-F, told apart from each other
    from events.joystick import JOYSTICK_BUTTON_TYPES as JOY
    from frontboards.common import FRONTBOARD_BUTTON_TYPES as FB
except ImportError:
    JOY = FB = None     # older firmware: fall back to the plain direction buttons

try:    # lets the flight screen skip the 50 ms pause the badge adds to every frame
    from system.scheduler import scheduler
except Exception:
    scheduler = None

try:    # the badge's LEDs, used to flash red when you're hit
    from tildagonos import tildagonos
    from system.patterndisplay.events import PatternDisable, PatternEnable
except Exception:
    tildagonos = None

# Flight buttons (letters as printed on the badge)
BTN_SPEED_UP = "F"
BTN_SPEED_DOWN = "E"
BTN_MISSILE = "B"
BTN_PAUSE = "A"
BTN_REZERO = "D"

# Tilt control. Values are in g (1 g = 9.81 m/s^2). The axis directions are a
# first guess, so flip the signs if things tilt the wrong way.
TILT_DEFAULT = False    # True to start with tilt steering instead of the joystick
TILT_DEADZONE = 0.10    # ignore small wobbles around the neutral pose
TILT_FULL = 0.50        # tilt that gives full rate (about 30 degrees)
TILT_PITCH_SIGN = 1.0
TILT_ROLL_SIGN = 1.0
TILT_SWAP_AXES = False  # True if the badge's x axis should pitch, y roll

INVERT_PITCH = False    # False: joystick up raises the nose. True: up dives.
SHOW_FRAME_TIME = True  # small frame time (ms) at the top of the flight screen
USE_LEDS = True         # flash the badge's LEDs red when hit (else a ring on screen)
FAST_FRAMES = True      # in flight and the viewer, don't wait 50 ms between frames
PERF_LOG = 60           # print a PERF line to the console every this many flight
                        # frames (0 = never)

MENU = ("FLIGHT", "SHIP VIEWER", "SPEED TEST")
ANY = ("up", "down", "left", "right")           # joystick, buttons or arrow keys
STICK = ("j_up", "j_down", "j_left", "j_right")  # the joystick only
ARROWS = ("k_UP", "k_DOWN", "k_LEFT", "k_RIGHT")

try:
    _us = time.ticks_us
    _ms = time.ticks_ms
    _diff = time.ticks_diff
except AttributeError:   # off the badge (tests)
    def _us():
        return int(time.perf_counter() * 1000000)

    def _ms():
        return int(time.perf_counter() * 1000)

    def _diff(a, b):
        return a - b


def _tilt(v):
    """Turn a tilt in g into -1..1, with a dead zone."""
    a = abs(v) - TILT_DEADZONE
    if a <= 0:
        return 0.0
    a = min(1.0, a / (TILT_FULL - TILT_DEADZONE))
    return a if v > 0 else -a


class Pad:
    """Which controls are down, kept up to date from button events.

    The firmware's own Buttons.get() searches every known button each time it
    is asked, which is slow when a game asks about twenty things a frame. This
    does the matching once per press and then answers from a set.

    Controls are named: "up" / "confirm" / ... for any button of that kind,
    "j_up" ... for the joystick only, "A" to "F" for the lettered buttons and
    "k_W" ... for keyboard keys.
    """

    def __init__(self, owner):
        table = [(name.lower(), BUTTON_TYPES[name])
                 for name in ("UP", "DOWN", "LEFT", "RIGHT", "CONFIRM", "CANCEL")]
        if JOY is not None:
            for name in ("UP", "DOWN", "LEFT", "RIGHT"):
                table.append(("j_" + name.lower(), JOY[name]))
            for name in "ABCDEF":
                table.append((name, FB[name]))
        for name in ("W", "S", "A", "D", "E", "Q", "F", "M", "P", "N", "SPACE",
                     "UP", "DOWN", "LEFT", "RIGHT"):
            key = KEYBOARD_BUTTONS.get(name)
            if key is not None:
                table.append(("k_" + name, key))
        self.table = table
        self.names = {}      # button -> the control names it counts as
        self.pressed = {}    # button -> True while it is down
        self.count = {}      # control name -> how many buttons hold it down
        self.hits = set()    # control names pressed since the last end_frame()
        eventbus.on(ButtonDownEvent, self._down, owner)
        eventbus.on(ButtonUpEvent, self._up, owner)

    def _names(self, button):
        names = self.names.get(button)
        if names is None:
            names = tuple(n for n, kind in self.table if kind in button)
            self.names[button] = names
        return names

    def _down(self, event):
        button = event.button
        if self.pressed.get(button):
            return      # already down (key repeat)
        self.pressed[button] = True
        count = self.count
        for n in self._names(button):
            count[n] = count.get(n, 0) + 1
            self.hits.add(n)

    def _up(self, event):
        button = event.button
        if not self.pressed.get(button):
            return
        self.pressed[button] = False
        count = self.count
        for n in self._names(button):
            if count.get(n, 0) > 0:
                count[n] -= 1

    def held(self, name):
        return self.count.get(name, 0) > 0

    def hit(self, name):
        """True if the control was pressed since the last frame."""
        return name in self.hits

    def end_frame(self):
        if self.hits:
            self.hits = set()

    def clear(self):
        self.pressed = {}
        self.count = {}
        self.hits = set()


class Elite(app.App):
    def __init__(self):
        super().__init__()
        self.pad = Pad(self)
        self.mode = "menu"      # menu | flight | viewer | bench
        self.bench = None
        self.menu = 0
        self.game = None
        self.viewer = None
        self.paused = False
        self.tilt_ok = imu is not None   # the accelerometer is there and working
        # steer by tilt as well as the joystick. Without the joystick's own
        # button names (older firmware) tilt is the default, as the direction
        # buttons are then needed for speed and missiles.
        self.use_tilt = self.tilt_ok and (TILT_DEFAULT or JOY is None)
        self.zero = None                 # accelerometer reading taken as "level"
        self.ms = 0.0                    # smoothed frame time
        self.leds_on = False             # we have taken over the LEDs
        self.led_level = -1              # red level last written, 0-255
        # smoothed time, in ms, spent in the game rules and in drawing calls
        self.t_step = 0.0
        self.t_world = 0.0
        self.t_hud = 0.0
        self.fast = FAST_FRAMES and scheduler is not None
        # totals for the PERF line
        self.p_n = 0
        self.p_frame = 0.0
        self.p_max = 0.0
        self.p_update = 0.0
        self.p_rules = 0.0
        self.p_draw = 0.0

    # ---- frame loop -------------------------------------------------------

    async def run(self, render_update):
        """The badge's own loop waits 50 ms after every update before the next
        one, which caps any app at about 14 frames a second. In flight and the
        viewer this asks for a redraw directly and carries on as soon as it
        has been drawn. Menus, and anything unexpected, use the normal path."""
        last = _ms()
        while True:
            now = _ms()
            self.update(_diff(now, last))
            last = now
            if self.fast and (self.mode == "flight" or self.mode == "viewer"):
                try:
                    scheduler.render_needed.set()
                    await asyncio.sleep(0)      # the renderer and other tasks run here
                    if scheduler.app_is_foregrounded(self):
                        continue
                except Exception:
                    self.fast = False           # firmware differs: stay on the normal path
            await render_update()

    # ---- LEDs -------------------------------------------------------------

    def _leds(self, level):
        """Set the ring of 12 LEDs to red at level 0-255, taking them over
        from the badge's own pattern first. Only writes when the level changes."""
        if tildagonos is None or not USE_LEDS:
            return
        try:
            if not self.leds_on:
                eventbus.emit(PatternDisable())
                try:
                    tildagonos.set_led_power(True)
                except Exception:
                    pass
                self.leds_on = True
                self.led_level = -1
            if level != self.led_level:
                self.led_level = level
                leds = tildagonos.leds
                for i in range(1, 13):      # the front ring is LEDs 1 to 12
                    leds[i] = (level, 0, 0)
                leds.write()
        except Exception:
            self.leds_on = False

    def _leds_release(self):
        """Hand the LEDs back to the badge's own pattern."""
        if self.leds_on:
            self.leds_on = False
            try:
                eventbus.emit(PatternEnable())
            except Exception:
                pass

    def _leds_flight(self):
        g = self.game
        if self.paused:
            self._leds(0)
        elif g.over:
            self._leds(48)
        elif g.flash > 0.18:    # full, then fading over the 0.3 s after a hit
            self._leds(255)
        elif g.flash > 0.09:
            self._leds(160)
        elif g.flash > 0:
            self._leds(80)
        else:
            self._leds(0)

    # ---- steering ---------------------------------------------------------

    def _steer(self, tilt, dirs, arrows):
        """(roll, pitch) as -1..1 each, from tilt, the four direction controls
        named in dirs, and the keyboard. Pitch is negative for up."""
        held = self.pad.held
        jx = jy = 0.0
        if tilt and self.tilt_ok:
            try:
                ax, ay, _ = imu.acc_read()
            except Exception:
                self.tilt_ok = False
                self.use_tilt = False
            else:
                ax /= 9.81
                ay /= 9.81
                if self.zero is None:
                    self.zero = (ax, ay)
                dx = ax - self.zero[0]
                dy = ay - self.zero[1]
                if TILT_SWAP_AXES:
                    dx, dy = dy, dx
                jx = TILT_ROLL_SIGN * _tilt(dx)
                jy = TILT_PITCH_SIGN * _tilt(dy)
        if dirs is not None:
            if held(dirs[0]):
                jy -= 1.0
            if held(dirs[1]):
                jy += 1.0
            if held(dirs[2]):
                jx -= 1.0
            if held(dirs[3]):
                jx += 1.0
        if arrows:      # not already counted in dirs
            if held("k_UP"):
                jy -= 1.0
            if held("k_DOWN"):
                jy += 1.0
            if held("k_LEFT"):
                jx -= 1.0
            if held("k_RIGHT"):
                jx += 1.0
        if held("k_W"):
            jy -= 1.0
        if held("k_S"):
            jy += 1.0
        if held("k_A"):
            jx -= 1.0
        if held("k_D"):
            jx += 1.0
        return max(-1.0, min(1.0, jx)), max(-1.0, min(1.0, jy))

    # ---- update -----------------------------------------------------------

    def update(self, delta):
        t0 = _us()
        self.ms += (delta - self.ms) * 0.1
        pad = self.pad
        hit = pad.hit
        cancel = hit("cancel")
        confirm = hit("confirm")
        dt = delta / 1000.0

        if self.mode == "menu":
            if cancel:
                pad.clear()
                self.minimise()
            elif not SHIPS:
                pass    # nothing to choose without ship_data.py
            elif hit("up"):
                self.menu = (self.menu - 1) % len(MENU)
            elif hit("down"):
                self.menu = (self.menu + 1) % len(MENU)
            elif confirm:
                self.zero = None
                if self.menu == 0:
                    if self.game is None:
                        self.game = game.Game(SHIPS)
                    elif self.game.over:
                        self.game.reset()
                    self.paused = False
                    self.mode = "flight"
                elif self.menu == 1:
                    if self.viewer is None:
                        self.viewer = viewer.Viewer(SHIPS)
                    self.mode = "viewer"
                else:
                    self.bench = bench.Bench()
                    self.mode = "bench"
        elif self.mode == "viewer":
            self._update_viewer(dt, cancel, confirm)
        elif self.mode == "bench":
            if cancel:
                self.mode = "menu"
                self.bench = None
            else:
                self.bench.step(delta)
        else:
            flying = self._update_flight(dt, cancel, confirm)
            if self.mode == "flight":
                self._leds_flight()
            else:
                self._leds_release()
            if flying and PERF_LOG:
                self._perf(delta, _diff(_us(), t0) / 1000.0)
        pad.end_frame()

    def _perf(self, delta, update_ms):
        """Every PERF_LOG flight frames, print where the time went."""
        self.p_n += 1
        self.p_frame += delta
        if delta > self.p_max:
            self.p_max = delta
        self.p_update += update_ms
        if self.p_n >= PERF_LOG:
            n = self.p_n
            used = getattr(gc, "mem_alloc", lambda: 0)()
            t0 = _us()
            gc.collect()
            gc_ms = _diff(_us(), t0) / 1000.0
            print("PERF frame %.0f max %.0f update %.1f rules %.1f draw %.1f objs %d fast %d"
                  " gc %.0f used %d free %d" % (
                      self.p_frame / n, self.p_max, self.p_update / n, self.p_rules / n,
                      self.p_draw / n, len(self.game.objs), 1 if self.fast else 0,
                      gc_ms, used, getattr(gc, "mem_free", lambda: 0)()))
            self.p_n = 0
            self.p_frame = self.p_max = self.p_update = self.p_rules = self.p_draw = 0.0

    def _update_viewer(self, dt, cancel, confirm):
        v = self.viewer
        pad = self.pad
        if cancel:
            self.mode = "menu"
            return
        if confirm or pad.hit("k_N"):
            v.switch(1)
            self.zero = None
        elif pad.hit("k_P"):
            v.switch(-1)
            self.zero = None
        jx, jy = self._steer(self.use_tilt, ANY, False)
        v.step(dt, jx, jy)

    def _update_flight(self, dt, cancel, confirm):
        """Returns True if the game moved on a step."""
        pad = self.pad
        hit = pad.hit
        held = pad.held
        g = self.game
        new = FB is not None    # joystick and lettered buttons are told apart
        pause = hit(BTN_PAUSE) if new else cancel
        if hit("k_P"):
            pause = True

        if g.over:
            if confirm:
                g.reset()
                self.zero = None
            elif cancel:
                self.mode = "menu"
            else:
                g.step(dt, 0.0, 0.0, 0.0, False, False)   # let the wreckage drift
            return False
        if self.paused:
            if confirm or (pause and new):
                self.paused = False
                self.zero = None
            elif cancel:
                self.paused = False
                self.mode = "menu"
            elif hit("j_left" if new else "left") or hit("j_right" if new else "right"):
                if self.tilt_ok:
                    self.use_tilt = not self.use_tilt
                    self.zero = None
            return False
        if pause:
            self.paused = True
            return False

        tilt = self.use_tilt and self.tilt_ok
        throttle = 0.0
        missile = False
        if new:                 # joystick steers; lettered buttons do the rest
            if held(BTN_SPEED_UP):
                throttle += 1.0
            if held(BTN_SPEED_DOWN):
                throttle -= 1.0
            if hit(BTN_MISSILE):
                missile = True
            if tilt and hit(BTN_REZERO):
                self.zero = None
            roll, jy = self._steer(tilt, STICK, True)
        elif tilt:              # older firmware: the d-pad is free for speed and missiles
            if held("up"):
                throttle += 1.0
            if held("down"):
                throttle -= 1.0
            if hit("left"):
                missile = True
            if hit("right"):
                self.zero = None
            roll, jy = self._steer(True, None, False)
        else:
            roll, jy = self._steer(False, ANY, False)
        if held("k_E"):
            throttle += 1.0
        if held("k_Q"):
            throttle -= 1.0
        if hit("k_M"):
            missile = True
        fire = held("confirm") or held("k_F") or held("k_SPACE")
        pitch = jy if INVERT_PITCH else -jy
        t0 = _us()
        g.step(dt, pitch, roll, max(-1.0, min(1.0, throttle)), fire, missile)
        rules = _diff(_us(), t0) / 1000.0
        self.t_step += (rules - self.t_step) * 0.1
        self.p_rules += rules
        return True

    # ---- draw -------------------------------------------------------------

    def draw(self, ctx):
        ctx.save()
        if self.mode == "viewer":
            self.viewer.draw(ctx)
        elif self.mode == "bench":
            self.bench.draw(ctx)
        elif self.mode == "flight":
            t0 = _us()
            cockpit.draw_world(ctx, self.game)
            t1 = _us()
            cockpit.draw_hud(ctx, self.game, self.ms if SHOW_FRAME_TIME else None,
                             not self.leds_on)
            if self.paused:
                self._draw_pause(ctx)
            else:
                world = _diff(t1, t0) / 1000.0
                hud = _diff(_us(), t1) / 1000.0
                self.t_world += (world - self.t_world) * 0.1
                self.t_hud += (hud - self.t_hud) * 0.1
                self.p_draw += world + hud
        else:
            self._draw_menu(ctx)
        ctx.restore()

    def _draw_menu(self, ctx):
        text = cockpit.text
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        text(ctx, "ELITE", 0, -58, 40, cockpit.WHITE)
        if not SHIPS:
            text(ctx, "ship_data.py", 0, -10, 16, cockpit.YELLOW)
            text(ctx, "not found", 0, 10, 16, cockpit.YELLOW)
            text(ctx, "copy it next to app.py", 0, 36, 12, cockpit.GREY)
            return
        for i, label in enumerate(MENU):
            y = -14 + i * 27
            if i == 0 and self.game is not None and not self.game.over:
                label = "CONTINUE"
            if i == self.menu:
                ctx.rgb(*cockpit.DIM).rectangle(-80, y - 13, 160, 26).fill()
            text(ctx, label, 0, y, 18, cockpit.GREEN if i == self.menu else cockpit.GREY)
        text(ctx, "CONFIRM: choose", 0, 74, 12, cockpit.GREY)
        text(ctx, "CANCEL: exit", 0, 89, 12, cockpit.GREY)

    def _draw_pause(self, ctx):
        text = cockpit.text
        ctx.rgba(0, 0, 0, 0.85).rectangle(-100, -80, 200, 142).fill()
        text(ctx, "PAUSED", 0, -44, 22, cockpit.WHITE)
        stick = "JOYSTICK" if FB is not None else "STICK"
        if self.tilt_ok:
            steer = "TILT" if self.use_tilt else stick
            text(ctx, "steer: %s  (LEFT/RIGHT)" % steer, 0, -16, 12, cockpit.YELLOW)
        else:
            text(ctx, "steer: %s (no tilt sensor)" % stick, 0, -16, 12, cockpit.YELLOW)
        text(ctx, "C: resume", 0, 6, 12, cockpit.GREY)
        text(ctx, "F: menu", 0, 22, 12, cockpit.GREY)
        # where the time goes: whole frame, game rules, and my drawing calls
        text(ctx, "frame %d  rules %d" % (self.ms, self.t_step), 0, 40, 11, cockpit.GREY)
        text(ctx, "world %d  hud %d  objs %d" % (
            self.t_world, self.t_hud, len(self.game.objs)), 0, 54, 11, cockpit.GREY)


__app_export__ = Elite
