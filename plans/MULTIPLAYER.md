# Multiplayer combat (plan, 2026-11-24)

Nothing built yet but the link tests. Brian's choices so far are marked; the rest
are suggestions.

## First: the link tests (`tools/espnow_link.py`)

Do two badges talk straight to each other over ESP-NOW, how fast, and how much is
lost? The firmware has `espnow` (MicroPython's default `MICROPY_PY_ESPNOW` 1, not
turned off for the Tildagon board) and freezes `aioespnow` (`tildagon/manifest.py`),
but nothing has run on a badge yet. **Ask Brian before copying or running on a badge.**

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

What to record from the badges: CHECK output from both; ping's table with the
badges close together, across a room, and with one in a pocket; whether running it
upsets the badge's own Wi-Fi.

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
