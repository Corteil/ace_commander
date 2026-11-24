# Multiplayer combat (plan, 2026-11-24)

Nothing built yet but the link tests (run on two badges 2026-11-24: works). Brian's choices so far are marked; the rest
are suggestions.

## First: the link tests (`tools/espnow_link.py`)

Do two badges talk straight to each other over ESP-NOW, how fast, and how much is
lost? The firmware has `espnow` (MicroPython's default `MICROPY_PY_ESPNOW` 1, not
turned off for the Tildagon board) and freezes `aioespnow` (`tildagon/manifest.py`),
and both badges run it (below). **Ask Brian before copying or running on a badge.**

    mpremote connect PORT fs cp tools/espnow_link.py :/espnow_link.py
    mpremote connect PORT exec "import espnow_link; espnow_link.check()"
    mpremote connect PORT_B exec "import espnow_link; espnow_link.echo(120)"    # badge B
    mpremote connect PORT_A exec "import espnow_link; espnow_link.ping()"       # badge A

- `check()`: espnow imports, the radio starts, MAC, Wi-Fi channel, garbage per send
  and per receive, free heap. Prints CHECK OK.
- `echo(seconds)` on one badge, `ping()` on the other: 150 packets at 15 a second,
  32 and 64 bytes, broadcast then unicast; loss and round trip (min / median / p95 / max).
- Both on one channel: a badge on Wi-Fi uses its network's channel; one that isn't is
  disconnected (so it stops scanning) and set to `CHANNEL` (1).
- `tests/test_espnow_link.py` runs the same code on the PC with a pretend radio (in
  `tests/run_all.py`). It proves the test's logic, not the radio.

**First run (2026-11-24, both badges on the desk side by side, neither on Wi-Fi,
channel 1):** CHECK OK on both (7c:4f:ad:33:7a:c0 and 64:e8:33:72:25:2c; ~1.69 MB free
heap, no garbage per send; the receive figure was taken with nothing arriving, so it
isn't yet proof). Ping, 150 packets each at 15/s:

| run | lost | rtt ms min / median / p95 / max |
|---|---|---|
| broadcast 32 B | 0 | 3.7 / 4.9 / 8.6 / 10.8 |
| broadcast 64 B | 0 | 4.1 / 5.2 / 10.0 / 17.1 |
| unicast 32 B | 0 | 3.8 / 4.8 / 8.1 / 11.1 |
| unicast 64 B | 0 | 4.0 / 5.1 / 9.8 / 11.8 |

So one way is ~2.5 ms: far inside a frame (~18 ms+ on the badge). Broadcast is as good
as unicast at this range, so a game can broadcast to everyone.

**3 m apart (2026-11-24, as far as both USB cables reach):** the same again, 0 lost in
600; medians 4.6 / 4.9 / 4.6 / 4.9 ms, maxima 9.9 / 10.8 / 11.3 / 12.9 ms.

**Range on battery: the badge reboots when its USB is pulled** (2026-11-24), so an echo
started over USB dies with it (the first "far" run got nothing, and nothing back at the
desk either). `tools/espnow_echo_app/` is echo() as a badge app, started from the badge's
own menu after unplugging: copy its four files and `tools/espnow_link.py` to
`/apps/espnow_echo/`. It answers from the app's background task (polled every ~2 ms).

**10 m with a door in between (2026-11-24, the echo badge on battery running the app):**
the link holds. 60 packets each with a 250 ms reply window: broadcast and unicast both
5% lost, round trips ~96 ms median (30-133). At the desk the same app gave 33% / 4% lost
and ~100 ms, so the delay and losses are the app's, not the distance: **an app on screen
gets its background task only between frames (~100 ms), and ESP-NOW's default receive
buffer (~500 bytes) overflows meanwhile.** For the game: read the radio in the frame
loop or from `ESPNow.irq`, with a bigger `rxbuf`. The app now answers from `irq` with
`rxbuf=4096` (not yet on the badge): repeat at 10 m to see the radio's own round trip.

Still to record: further than 10 m, with one badge in a pocket, and with Wi-Fi
connected on one badge (both must then be on that network's channel); whether running
it upsets the badge's own Wi-Fi.

Next tests, once that works: the same inside the game's frame loop (the game drawing
while sending and receiving, frame time and garbage per frame), and the Pi on the
link (UDP, or through a bridge below).

## Transports

1. **ESP-NOW, badge to badge**: no router, works anywhere on the field.
2. **UDP over Wi-Fi**: badge, Tufty (Wi-Fi + Bluetooth 5.2, no ESP-NOW) and Pi
   together; needs a network that lets devices see each other (a Pi hotspot works,
   camp Wi-Fi may not).
3. **The Pi on ESP-NOW through a bridge**: an ESP32 on the Pi's USB passing packets
   between ESP-NOW and USB serial (length byte, then the packet). For testing, Brian's
   second Tildagon. **Later (Brian, 2026-11-24): the 2022 TiDAL badge as the dongle**
   (ESP32-S3; its own firmware is probably MicroPython 1.19, before ESP-NOW arrived in
   1.21, so likely stock `ESP32_GENERIC_S3` MicroPython flashed onto it). An ESP32-S3
   USB stick (M5Stack AtomS3U and the like) would do the same.

The game talks to one small interface (`send(bytes)`, `receive()`), so the transport
can change underneath.

## The game (suggestion)

1. A duel in the combat practice arena, no NPCs: each device flies its own ship and
   sends pose, speed and shots ~15 times a second in a fixed-size packet (no JSON:
   garbage); the shooter decides hits and tells the target. A MULTIPLAYER line on the
   title screen: HOST / JOIN.
2. The catch: the game is Elite's, the world moves round your ship. Each device must
   keep its own position and heading in a fixed frame and send those; the receiver
   turns them into its own frame (as `Game.enter_view` does for the four views).
3. Later: co-op against NPCs (one device runs them), then commanders meeting in a system.
