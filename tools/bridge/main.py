"""The ESP-NOW to USB dongle for Ace Commander (hosts/pi/net_bridge.py), for an ESP32
running stock MicroPython 1.21 or later: Brian's 2022 EMF badge (TiDAL, an ESP32-S3)
with the ESP32_GENERIC_S3 build. Copied on as main.py (with tidal_screen.py for the
2022 badge's screen) it starts with the dongle and passes packets both ways: what the
Pi sends is broadcast over ESP-NOW, and everything heard goes to the Pi with the
sender's address. Frames on USB: 0xA5, length, 6-byte address, packet (the address
going out is ignored: everything is broadcast).

On the 2022 badge its screen shows the channel, its own address, packets each way,
whether the Pi is talking, and the badges heard (Brian: "the 22 badge's screen should
display info"). Without that screen it runs the same, blind.

The badges all use one Wi-Fi channel (net_espnow.CHANNEL): CHANNEL below must match.
Ctrl-C is switched off while it runs (a packet may hold 0x03). To get the REPL back:
- connect within GRACE_MS of it starting (plugging in): Ctrl-C still works then;
- or hold any button (A, B, front, joystick centre) while it starts;
- or send it STOP (net_bridge.Link.stop_dongle(): a frame from STOP_ADDR).
A screen that won't start leaves its error in screen_error.txt.
"""
import sys
import time
import select
import micropython
import network
import espnow
from machine import Pin

CHANNEL = 1
SYNC = 0xA5
BROADCAST = b"\xff" * 6
SHOW_MS = 1000          # the screen redrawn this often
GONE_MS = 10000         # a badge not heard for this long drops off the list
GRACE_MS = 3000         # Ctrl-C still works this long after starting
STOP_ADDR = b"STOP!!"   # a frame from the Pi with this address ends the bridge
BUTTONS = (2, 1, 6, 9)  # the 2022 badge's A, B, front and joystick centre

# a button held at start: don't start (the REPL stays usable)
if any(Pin(n, Pin.IN, Pin.PULL_UP).value() == 0 for n in BUTTONS):
    raise SystemExit("bridge not started: a button held")
# Ctrl-C still works for GRACE_MS: connect then for the REPL
time.sleep_ms(GRACE_MS)

try:
    import tidal_screen
    screen = tidal_screen.Screen()
except Exception as err:        # another ESP32, or no screen: run blind, but say why
    screen = None
    try:
        with open("screen_error.txt", "w") as f:
            sys.print_exception(err, f)
    except Exception:
        pass

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
MAC = sta.config("mac")

out = sys.stdout.buffer
inp = sys.stdin.buffer
poll = select.poll()
poll.register(inp, select.POLLIN)
buf = bytearray()
heard = {}              # badge address -> when last heard (ms)
to_pi = from_pi = 0     # packets passed each way
pi_t = None             # when the Pi last sent something
start = time.ticks_ms()
shown = start - SHOW_MS


def hexmac(m):
    return ":".join("%02x" % b for b in m)


def draw(now):
    if screen is None:
        return
    s = screen
    T = tidal_screen
    s.clear()
    s.text("ACE BRIDGE", 4, 4, T.YELLOW, 2)
    s.text("ch %d  %s" % (CHANNEL, hexmac(MAC)[6:]), 4, 24, T.GREY)
    pi_ok = pi_t is not None and time.ticks_diff(now, pi_t) < 3000
    s.text("PI " + ("TALKING" if pi_ok else "quiet"), 4, 38, T.GREEN if pi_ok else T.RED)
    s.text("to Pi %d" % to_pi, 4, 52, T.CYAN)
    s.text("from Pi %d" % from_pi, 120, 52, T.CYAN)
    live = [(m, t) for m, t in heard.items() if time.ticks_diff(now, t) < GONE_MS]
    s.text("BADGES HEARD: %d" % len(live), 4, 68, T.WHITE)
    y = 82
    for m, t in sorted(live, key=lambda mt: mt[1], reverse=True)[:5]:
        ago = time.ticks_diff(now, t) // 1000
        s.text("%s  %ds" % (hexmac(m)[9:], ago), 12, y, T.GREEN if ago < 2 else T.GREY)
        y += 10
    up = time.ticks_diff(now, start) // 1000
    s.text("up %d:%02d" % (up // 60, up % 60), 168, 124, T.GREY)
    s.show()


while True:
    now = time.ticks_ms()
    # the radio to USB: every packet heard, with who sent it
    while e.any():
        mac, msg = e.recv(0)
        if msg:
            out.write(bytes((SYNC, 6 + len(msg))) + mac + msg)
            heard[bytes(mac)] = now
            to_pi += 1
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
        if n >= 6 and bytes(buf[2:8]) == STOP_ADDR:   # the Pi says stop: back to the REPL
            micropython.kbd_intr(3)
            raise SystemExit("bridge stopped by the Pi")
        if n > 6:
            try:
                e.send(BROADCAST, bytes(buf[8:2 + n]), False)
                from_pi += 1
                pi_t = now
            except OSError:
                pass
        buf = buf[2 + n:]
    if time.ticks_diff(now, shown) >= SHOW_MS:
        shown = now
        for m in [m for m, t in heard.items() if time.ticks_diff(now, t) > 60000]:
            del heard[m]            # forget badges long gone
        try:
            draw(now)
        except Exception as err:    # a drawing fault mustn't stop the bridge
            screen = None
            try:
                with open("screen_error.txt", "w") as f:
                    sys.print_exception(err, f)
            except Exception:
                pass
    poll.poll(2)                # a short wait for USB, then look at the radio again
