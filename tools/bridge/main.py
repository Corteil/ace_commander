"""The ESP-NOW to USB dongle for Ace Commander (hosts/pi/net_bridge.py): copied onto an
ESP32 running stock MicroPython 1.21 or later (Brian's 2022 EMF TiDAL badge is an
ESP32-S3: the ESP32_GENERIC_S3 build) as main.py, it starts with the dongle and passes
packets both ways: what the Pi sends is broadcast over ESP-NOW, and everything heard is
sent to the Pi with the sender's address. Frames on USB: 0xA5, length, 6-byte address,
packet (the address going out is ignored: everything is broadcast).

The badges all use one Wi-Fi channel (net_espnow.CHANNEL): CHANNEL below must match.
Ctrl-C is switched off while it runs (a packet could contain 0x03); to get the REPL
back, hold BOOT while plugging it in, or erase main.py with a fresh flash.
"""
import sys
import select
import micropython
import network
import espnow

CHANNEL = 1
SYNC = 0xA5
BROADCAST = b"\xff" * 6

micropython.kbd_intr(-1)        # binary on stdin: no Ctrl-C
sta = network.WLAN(network.STA_IF)
sta.active(True)
try:
    sta.disconnect()
except OSError:
    pass
sta.config(channel=CHANNEL)
try:
    sta.config(pm=sta.PM_NONE)  # power saving drops ESP-NOW packets
except (AttributeError, ValueError):
    pass
e = espnow.ESPNow()
e.config(rxbuf=4096)
e.active(True)
e.add_peer(BROADCAST)

out = sys.stdout.buffer
inp = sys.stdin.buffer
poll = select.poll()
poll.register(inp, select.POLLIN)
buf = bytearray()

while True:
    # the radio to USB: every packet heard, with who sent it
    while e.any():
        mac, msg = e.recv(0)
        if msg:
            out.write(bytes((SYNC, 6 + len(msg))) + mac + msg)
    # USB to the radio: a byte at a time while there are any (packets are small)
    while poll.poll(0):
        buf += inp.read(1)
    while buf:
        if buf[0] != SYNC:
            buf = buf[1:]
            continue
        if len(buf) < 2 or len(buf) < 2 + buf[1]:
            break
        n = buf[1]
        if n > 6:
            try:
                e.send(BROADCAST, bytes(buf[8:2 + n]), False)
            except OSError:
                pass
        buf = buf[2 + n:]
    poll.poll(2)                # a short wait for USB, then look at the radio again
