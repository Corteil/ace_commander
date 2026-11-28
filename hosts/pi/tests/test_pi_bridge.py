"""The Pi's link through a USB ESP-NOW dongle (net_bridge.py, --bridge): frames both
ways, packets in pieces, resyncing after junk; and the Link on a pretend serial port
(a pty pair), the dongle's side played by the test.

    python3 hosts/pi/tests/test_pi_bridge.py
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import net_bridge as nb     # noqa: E402

MAC = bytes(range(1, 7))

# a frame, and frames out of a stream that comes in pieces, with junk between
f = nb.frame(MAC, b"POSE-1")
assert f == bytes((0xA5, 12)) + MAC + b"POSE-1", f
fr = nb.Frames()
stream = b"\x00\x13" + f + b"\xa5\x02junk" + nb.frame(MAC, b"second") + nb.frame(MAC, b"")
for i in range(0, len(stream), 3):          # three bytes at a time
    fr.feed(stream[i:i + 3])
got = []
while True:
    x = fr.next()
    if x is None:
        if len(got) >= 3 or not fr.buf:
            break
        continue
    got.append(x)
assert got[0] == (MAC, b"POSE-1") and (MAC, b"second") in got and got[-1] == (MAC, b""), got
print("frames: in pieces, junk skipped, empty packets: ok")
try:
    nb.frame(MAC, bytes(nb.MAX + 1))
    raise AssertionError("too long")
except ValueError:
    pass
print("a packet over ESP-NOW's 250 bytes is refused: ok")

# the Link on a pty: the test is the dongle
import pty, tty     # noqa: E401,E402
master, slave = pty.openpty()
tty.setraw(slave)
tty.setraw(master)
link = nb.Link(os.ttyname(slave))
link.send(b"HELLO")
time.sleep(0.05)
out = os.read(master, 100)
assert out == nb.frame(nb.BROADCAST, b"HELLO"), out
print("send: a broadcast frame to the dongle: ok")
os.write(master, nb.frame(MAC, b"from a badge")[:7])     # half a frame
time.sleep(0.05)
assert link.recv() == (None, None), "not yet"
os.write(master, nb.frame(MAC, b"from a badge")[7:] + nb.frame(b"\x09" * 6, b"next"))
time.sleep(0.05)
who, msg = link.recv()
assert who == MAC and bytes(msg) == b"from a badge", (who, msg)
who, msg = link.recv()
assert who == b"\x09" * 6 and bytes(msg) == b"next", (who, msg)
assert link.recv() == (None, None)
link.close()
os.close(master)
print("recv: the sender's address and packet, half frames waited for: ok")
print("ALL PI BRIDGE TESTS PASSED")
