"""The ESP-NOW to USB dongle for Ace Commander (hosts/pi/net_bridge.py), for an ESP32
running stock MicroPython 1.21 or later: Brian's 2022 EMF badge (TiDAL, an ESP32-S3)
with the ESP32_GENERIC_S3 build. Copied on as main.py (with tidal_screen.py for the
2022 badge's screen) it starts with the dongle and passes packets both ways: what the
Pi sends is broadcast over ESP-NOW, and everything heard goes to the Pi with the
sender's address. On USB each packet is a line: ">" (from the Pi) or "<" (to it), the
6-byte address and the packet in hex (build 174; the address going out is ignored:
everything is broadcast). The 2024 badge's ESP-NOW Link app (Corteil/espnow_link) speaks the same.

On the 2022 badge its screen shows the channel, its own address, packets each way,
whether the Pi is talking, and the badges heard (Brian: "the 22 badge's screen should
display info"). Without that screen it runs the same, blind.

ESP-NOW only reaches radios on the same Wi-Fi channel. A badge off any network is on
net_espnow.CHANNEL (1); one on a network is on that network's (Brian's: 6). So the
dongle hunts: while it hears no badge it moves on every HOP_MS through HUNT, and it
stays on a channel while badges are heard there.
Ctrl-C works throughout (hex has no 0x03), so mpremote can always stop it; also:
- hold any button (A, B, front, joystick centre) while it starts;
- or send it STOP (net_bridge.Link.stop_dongle()).
A screen that won't start leaves its error in screen_error.txt.

A SystemExit in main.py makes MicroPython soft-reboot and run main.py again, so the
bridge is one function that returns: the REPL is then free (until the next reset).
"""
import sys
import time
import select
from binascii import hexlify, unhexlify
import network
import espnow
from machine import Pin

HUNT = (6, 1, 11, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13)   # channels tried, in this order
HOP_MS = 1500           # listened this long on a channel before trying the next
STAY_MS = 8000          # stays this long after the last badge heard
BROADCAST = b"\xff" * 6
SHOW_MS = 1000          # the screen redrawn this often
GONE_MS = 10000         # a badge not heard for this long drops off the list
STOP_ADDR = b"STOP!!"   # a frame from the Pi with this address ends the bridge
MAC_ASK = b"MAC?!!"     # the Pi asks our radio address (its id in the game) ...
MAC_IS = b"MAC=!!"      # ... answered from this address
INFO_ASK = b"INFO?!"    # the Pi asks the channel ...
INFO_IS = b"INFO=!"     # ... answered: channel, found (0 / 1)
BUTTONS = (2, 1, 6, 9)  # the 2022 badge's A, B, front and joystick centre


def bridge():
    global CHANNEL
    # a button held at start: don't start (the REPL stays usable)
    if any(Pin(n, Pin.IN, Pin.PULL_UP).value() == 0 for n in BUTTONS):
        print("bridge not started: a button held")
        return

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

    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    try:
        sta.disconnect()
    except OSError:
        pass
    hunt_i = 0
    CHANNEL = HUNT[0]
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
    fails = 0               # sends the radio refused
    fail_why = ""
    pi_t = None             # when the Pi last sent something
    start = time.ticks_ms()
    shown = start - SHOW_MS
    on_ch = start           # when this channel was picked
    last_badge = None       # when a badge was last heard (on this channel)


    def hexmac(m):
        return ":".join("%02x" % b for b in m)


    def draw(now):
        if screen is None:
            return
        s = screen
        T = tidal_screen
        s.clear()
        s.text("ACE BRIDGE", 4, 4, T.YELLOW, 2)
        found = last_badge is not None and time.ticks_diff(now, last_badge) < STAY_MS
        s.text("ch %d %s  %s" % (CHANNEL, "found" if found else "hunting", hexmac(MAC)[9:]),
               4, 24, T.GREEN if found else T.GREY)
        pi_ok = pi_t is not None and time.ticks_diff(now, pi_t) < 3000
        s.text("PI " + ("TALKING" if pi_ok else "quiet"), 4, 38, T.GREEN if pi_ok else T.RED)
        s.text("to Pi %d" % to_pi, 4, 52, T.CYAN)
        s.text("from Pi %d" % from_pi, 120, 52, T.CYAN)
        if fails:
            s.text("SEND FAILS %d %s" % (fails, fail_why[:12]), 4, 112, T.RED)
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
        # the radio to USB: every packet heard, with who sent it, as a "<" line of hex
        while e.any():
            mac, msg = e.recv(0)
            if msg:
                out.write(b"<" + hexlify(bytes(mac) + msg) + b"\n")
                heard[bytes(mac)] = now
                last_badge = now
                to_pi += 1
        # USB to the radio: ">" lines of hex, a byte at a time while there are any
        while poll.poll(0):
            c = inp.read(1)
            if c != b"\n":
                if len(buf) < 600:
                    buf += c
                continue
            line = bytes(buf).strip()
            buf = bytearray()
            if len(line) < 13 or line[:1] != b">":
                continue
            try:
                raw = unhexlify(line[1:])
            except ValueError:
                continue
            addr, msg = raw[:6], raw[6:]
            if addr == STOP_ADDR:           # the Pi says stop: back to the REPL
                print("bridge stopped by the Pi: to Pi %d, from Pi %d, send failures %d %s, channel %d"
                      % (to_pi, from_pi, fails, fail_why, CHANNEL))
                return
            if addr == MAC_ASK:
                out.write(b"<" + hexlify(MAC_IS + MAC) + b"\n")
                continue
            if addr == INFO_ASK:
                found = last_badge is not None and time.ticks_diff(now, last_badge) < STAY_MS
                out.write(b"<" + hexlify(INFO_IS + bytes((CHANNEL, 1 if found else 0))) + b"\n")
                continue
            if msg:
                try:
                    if e.send(BROADCAST, msg, False) is False:
                        fails += 1
                        fail_why = "False"
                    from_pi += 1
                    pi_t = now
                except OSError as err:
                    fails += 1
                    fail_why = str(err)[:20]
        # no badge here lately: try the next channel
        quiet = last_badge is None or time.ticks_diff(now, last_badge) >= STAY_MS
        if quiet and time.ticks_diff(now, on_ch) >= HOP_MS:
            hunt_i = (hunt_i + 1) % len(HUNT)
            CHANNEL = HUNT[hunt_i]
            try:
                sta.config(channel=CHANNEL)
            except Exception:
                pass
            on_ch = now
            last_badge = None
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


bridge()
