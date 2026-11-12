"""Elite demo: hidden-line wireframe ships for the EMF Tildagon / Spaceagon.

Controls
    Tilt badge    pitch and roll the ship (accelerometer)
    UP / DOWN     pitch the ship (joystick or buttons)
    LEFT / RIGHT  roll the ship (joystick or buttons)
    CONFIRM       next ship, and re-zero tilt to the way you're holding it
    CANCEL        exit
    Keyboard      W / S pitch, A / D roll, N next ship, P previous ship
                  (needs a keyboard the badge firmware supports)

If tilting moves the ship the wrong way, flip TILT_PITCH_SIGN or
TILT_ROLL_SIGN below (or swap TILT_SWAP_AXES).

Ships come from ship_data.py, which sits next to this file. Make it with
import_ships.py from your own copy of the Elite source; without it the app
only shows a message. Hidden lines are removed the way the original game does
it: an edge is drawn only if one of the two faces it sits between points at
the camera.

On the 2026 Spaceagon the 5-way joystick sends the same UP / DOWN / LEFT /
RIGHT / CONFIRM events as the buttons, so it works with no extra code.
"""
import math

import app
from events.input import Buttons, BUTTON_TYPES

try:
    import imu
except ImportError:
    imu = None

try:
    from events.keyboard import KEYBOARD_BUTTONS
except ImportError:
    KEYBOARD_BUTTONS = {}

try:
    from .ship_data import SHIPS as _BLUEPRINTS
except Exception:
    try:
        from ship_data import SHIPS as _BLUEPRINTS
    except Exception:
        _BLUEPRINTS = ()

CAM_DIST = 380.0
FOCAL = 300.0
FIT_RADIUS = 85.0  # every ship is scaled so its furthest vertex is this far out

# Tilt control. Values are in g (1 g = 9.81 m/s^2). The axis directions are a
# first guess, so flip the signs if the ship tilts the wrong way.
TILT_DEADZONE = 0.10    # ignore small wobbles around the neutral pose
TILT_FULL = 0.50        # tilt at which the ship turns at full rate (~30 degrees)
TILT_PITCH_SIGN = 1.0
TILT_ROLL_SIGN = 1.0
TILT_SWAP_AXES = False  # True if the badge's x axis should pitch, y roll


def _tilt(v):
    """Turn a tilt in g into -1..1, with a dead zone."""
    a = abs(v) - TILT_DEADZONE
    if a <= 0:
        return 0.0
    a = min(1.0, a / (TILT_FULL - TILT_DEADZONE))
    return a if v > 0 else -a


class Ship:
    """A ship in Elite's own form: vertices, edges tagged with the two faces
    they border, and one normal per face."""

    def __init__(self, name, verts, edges, normals):
        self.name = name
        r = max(math.sqrt(x * x + y * y + z * z) for x, y, z in verts) or 1.0
        s = FIT_RADIUS / r
        self.verts = [(x * s, y * s, z * s) for x, y, z in verts]
        self.edges = tuple(edges)
        self.normals = tuple(normals)


# Ships are built on demand, so only the one on screen takes up memory.
BUILDERS = tuple(
    (lambda b=b: Ship(b[0], b[1], b[2], b[3])) for b in _BLUEPRINTS
)


def _rotation(yaw, pitch, roll):
    """Return a flat 3x3 matrix equal to Rz(roll) * Rx(pitch) * Ry(yaw)."""
    sy, cy = math.sin(yaw), math.cos(yaw)
    sp, cp = math.sin(pitch), math.cos(pitch)
    sr, cr = math.sin(roll), math.cos(roll)
    # Rx * Ry
    a0 = (cy, 0.0, sy)
    a1 = (sp * sy, cp, -sp * cy)
    a2 = (-cp * sy, sp, cp * cy)
    # Rz * (Rx * Ry)
    return (
        cr * a0[0] - sr * a1[0], cr * a0[1] - sr * a1[1], cr * a0[2] - sr * a1[2],
        sr * a0[0] + cr * a1[0], sr * a0[1] + cr * a1[1], sr * a0[2] + cr * a1[2],
        a2[0], a2[1], a2[2],
    )


class EliteDemo(app.App):
    def __init__(self):
        self.buttons = Buttons(self)
        self.keys = KEYBOARD_BUTTONS
        self.idx = 0
        self.ship = BUILDERS[0]() if BUILDERS else None
        self.zero = None  # accelerometer reading taken as "level"
        self.tilt_ok = imu is not None
        self.yaw = 2.6
        self.pitch = 0.35
        self.roll = 0.0

    def _switch(self, step):
        if not BUILDERS:
            return
        self.idx = (self.idx + step) % len(BUILDERS)
        self.ship = BUILDERS[self.idx]()
        self.zero = None  # re-zero tilt to the current pose

    def update(self, delta):
        dt = delta / 1000.0
        b = self.buttons

        if b.get(BUTTON_TYPES["CANCEL"]):
            b.clear()
            self.minimise()
            return
        if self.ship is None:
            return  # nothing to fly without ship_data.py
        if b.get(BUTTON_TYPES["CONFIRM"]):
            b.clear()
            self._switch(1)

        self.yaw += 0.8 * dt

        jx = jy = 0.0
        if self.tilt_ok:
            try:
                ax, ay, _ = imu.acc_read()
            except Exception:
                self.tilt_ok = False
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
        if b.get(BUTTON_TYPES["UP"]):
            jy -= 1.0
        if b.get(BUTTON_TYPES["DOWN"]):
            jy += 1.0
        if b.get(BUTTON_TYPES["LEFT"]):
            jx -= 1.0
        if b.get(BUTTON_TYPES["RIGHT"]):
            jx += 1.0

        keys = self.keys
        for name, kx, ky in (("W", 0, -1), ("S", 0, 1), ("A", -1, 0), ("D", 1, 0)):
            key = keys.get(name)
            if key is not None and b.get(key):
                jx += kx
                jy += ky
        for name, step in (("N", 1), ("P", -1)):
            key = keys.get(name)
            if key is not None and b.pressed(key):
                self._switch(step)

        jx = max(-1.0, min(1.0, jx))
        jy = max(-1.0, min(1.0, jy))
        self.pitch += jy * 2.0 * dt
        self.roll += jx * 2.0 * dt

    def _draw_message(self, ctx, lines):
        ctx.save()
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()
        ctx.rgb(1, 1, 1)
        ctx.font_size = 16
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        y = -10 * (len(lines) - 1)
        for line in lines:
            ctx.move_to(0, y).text(line)
            y += 20
        ctx.restore()

    def draw(self, ctx):
        ship = self.ship
        if ship is None:
            self._draw_message(ctx, ("ship_data.py", "not found", "copy it next to", "app.py"))
            return

        m00, m01, m02, m10, m11, m12, m20, m21, m22 = _rotation(
            self.yaw, self.pitch, self.roll)

        screen = []
        for x, y, z in ship.verts:
            rx = m00 * x + m01 * y + m02 * z
            ry = m10 * x + m11 * y + m12 * z
            rz = m20 * x + m21 * y + m22 * z
            k = FOCAL / (rz + CAM_DIST)
            screen.append((rx * k, -ry * k))

        # Elite's own rule: the ship sits straight ahead, so a face is visible
        # when its normal points back towards the camera. A face with no
        # normal (face-less edges, as on the plate) is always drawn.
        visible = []
        for nx, ny, nz in ship.normals:
            visible.append(
                (nx == 0 and ny == 0 and nz == 0)
                or m20 * nx + m21 * ny + m22 * nz < 0
            )

        ctx.save()
        ctx.rgb(0, 0, 0).rectangle(-120, -120, 240, 240).fill()

        ctx.rgb(1, 1, 1)
        ctx.line_width = 1.5
        ctx.begin_path()
        for a, b, f1, f2 in ship.edges:
            if visible[f1] or visible[f2]:
                ax, ay = screen[a]
                bx, by = screen[b]
                ctx.move_to(ax, ay)
                ctx.line_to(bx, by)
        ctx.stroke()

        ctx.rgb(0.4, 1, 0.4)
        ctx.font_size = 13
        ctx.text_align = ctx.CENTER
        ctx.text_baseline = ctx.MIDDLE
        ctx.move_to(0, 103).text(ship.name)
        ctx.restore()


__app_export__ = EliteDemo
