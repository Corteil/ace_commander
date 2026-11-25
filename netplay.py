"""Multiplayer packets (plans/MULTIPLAYER.md): a ship's pose in the shared world
(Game.world_pose), 32 bytes, packed into a buffer made once (no garbage on the
badge) and read back. No radio here: a transport (ESP-NOW, UDP) only moves bytes.

    0  2s  MAGIC "AM"
    2  B   kind (POSE)
    3  B   player id (0-255)
    4  H   sequence number (wraps)
    6  3i  x, y, z in quarter units (Game positions are floats; ±500,000 units)
   18  3h  nose x, y, z times 16384
   24  3h  roof x, y, z times 16384 (side = roof x nose, made on arrival)
   30  B   speed (Elite units, 0-255)
   31  B   flags (FIRING, ...)
"""
import struct

MAGIC = b"AM"
POSE = 1
SIZE = 32
FMT = "<2sBBHiiihhhhhhBB"
FIRING = 1          # flags: lasers on this frame
DEAD = 2            # flags: blown up


def newer(seq, last):
    """True if seq comes after last, allowing for the 16-bit wrap."""
    return 0 < ((seq - last) & 0xFFFF) < 0x8000


def _s(v):
    """A unit-vector part as int16 times 16384 (clamped: 1.0 is 16384)."""
    v = int(round(v * 16384))
    return 32767 if v > 32767 else (-32768 if v < -32768 else v)


def pack_pose(buf, player, seq, pose, speed=0, flags=0):
    """Fill buf (bytearray(SIZE), reused) from pose = Game.world_pose()."""
    x, y, z, m = pose
    sp = int(speed)
    struct.pack_into(FMT, buf, 0, MAGIC, POSE, player & 0xFF, seq & 0xFFFF,
                     int(round(x * 4)), int(round(y * 4)), int(round(z * 4)),
                     _s(m[6]), _s(m[7]), _s(m[8]), _s(m[3]), _s(m[4]), _s(m[5]),
                     0 if sp < 0 else (255 if sp > 255 else sp), flags & 0xFF)
    return buf


def read_pose_i(msg, m):
    """read_pose in whole numbers (build 163: no floats, which are garbage on the badge):
    (player, seq, x, y, z, speed, flags), x y z in world units; m (9 ints) is filled with
    the side, roof and nose x 16384. None if it isn't a POSE packet."""
    if msg is None or len(msg) < SIZE or msg[0] != MAGIC[0] or msg[1] != MAGIC[1] or msg[2] != POSE:
        return None
    (_, _, player, seq, x, y, z, nx, ny, nz, rx, ry, rz,
     speed, flags) = struct.unpack_from(FMT, msg, 0)
    m[0] = (ry * nz - rz * ny) >> 14    # side = roof x nose
    m[1] = (rz * nx - rx * nz) >> 14
    m[2] = (rx * ny - ry * nx) >> 14
    m[3], m[4], m[5] = rx, ry, rz
    m[6], m[7], m[8] = nx, ny, nz
    return player, seq, x >> 2, y >> 2, z >> 2, speed, flags


def read_pose(msg, m=None):
    """(player, seq, x, y, z, m, speed, flags) from a POSE packet, or None if it
    isn't one. m (9 floats: side, roof, nose rows) is filled if given."""
    if msg is None or len(msg) < SIZE or bytes(msg[0:2]) != MAGIC or msg[2] != POSE:
        return None
    (_, _, player, seq, x, y, z, nx, ny, nz, rx, ry, rz,
     speed, flags) = struct.unpack_from(FMT, msg, 0)
    k = 1.0 / 16384
    nx, ny, nz = nx * k, ny * k, nz * k
    rx, ry, rz = rx * k, ry * k, rz * k
    if m is None:
        m = [0.0] * 9
    # side = roof x nose (the layout Obj.m and _ortho keep)
    m[0] = ry * nz - rz * ny
    m[1] = rz * nx - rx * nz
    m[2] = rx * ny - ry * nx
    m[3], m[4], m[5] = rx, ry, rz
    m[6], m[7], m[8] = nx, ny, nz
    return player, seq, x * 0.25, y * 0.25, z * 0.25, m, speed, flags
