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

# a line, and lines out of a stream that comes in pieces, with the firmware's own
# prints between (as the 2024 badge's ESP-NOW Link app has)
f = nb.frame(MAC, b"POSE-1")
assert f == b">010203040506504f53452d31\n", f
fr = nb.Frames()
stream = (b"ESP-NOW: listener(s) present\r\n" + nb.frame(MAC, b"POSE-1", nb.IN)
          + b"<zz not hex\n<0102\n" + nb.frame(MAC, b"second", nb.IN) + b"ACE LINK\r\n"
          + nb.frame(MAC, b"", nb.IN))
for i in range(0, len(stream), 3):          # three bytes at a time
    fr.feed(stream[i:i + 3])
got = []
while True:
    x = fr.next()
    if x is None:
        break
    got.append(x)
assert got == [(MAC, b"POSE-1"), (MAC, b"second"), (MAC, b"")], got
assert b"\x03" not in nb.frame(MAC, bytes(range(256))[:nb.MAX]), "no Ctrl-C on the wire"
print("lines: in pieces, prints and bad lines skipped, empty packets, no Ctrl-C: ok")
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
# the dongle answers MAC_ASK with its address, which becomes the link's id; a badge's
# packet that arrives meanwhile is kept for recv()
import threading    # noqa: E402
DONGLE = b"\xf4\x12\xfa\x4e\x4d\xb0"


def dongle():
    got = b""
    while nb.frame(nb.MAC_ASK, b"") not in got:
        got += os.read(master, 100)
    os.write(master, nb.frame(MAC, b"early") + nb.frame(nb.MAC_IS, DONGLE))


th = threading.Thread(target=dongle)
th.start()
link = nb.Link(os.ttyname(slave))
th.join()
assert link.id == DONGLE, link.id
who, msg = link.recv()
assert who == MAC and bytes(msg) == b"early", (who, msg)
os.write(master, nb.frame(nb.INFO_IS, b"\x06\x01"))
time.sleep(0.05)
assert link.recv() == (None, None) and link.channel == 6 and link.found
print("id: the dongle's address; a packet meanwhile kept; INFO_IS gives channel 6: ok")
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
