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
`rxbuf=4096`; **at the same 10 m spot, app on screen:** 90 packets each, broadcast 1 lost
of 90 (32 B and 64 B), unicast none; round trips median 9.3-9.7 ms, p95 18-23, max 22-33 ms.
The extra ~5 ms over the desk test is the callback waiting for a gap in drawing, still well
under a frame. So the game's link: broadcast from the frame loop, receive by `irq`.

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

## Built: the shared world and the pose packet (branch multiplayer-pose)

- `game.Anchor` / `Game.set_anchor(x, y, z, m)` / `world_pose()` / `place(o, x, y, z, m)`:
  each device keeps the shared world's origin and axes in its own coordinates, turned
  and slid with everything else in `_rotate` / `_yaw` (cleared by `reset`). It uses exact
  sines: the game's whole-number ones don't square to 1, so objects grow or shrink a
  little each turn (55 units in 400 frames, unseen alone) and two worlds would drift.
  Without an anchor it costs one `is not None` a frame.
- `netplay.py`: the 32-byte POSE packet (magic, player, seq, position in quarter units,
  nose and roof times 16384, speed, flags FIRING / DEAD), packed into a buffer made once;
  `read_pose` remakes the side axis and can fill a given list; `newer` for the seq wrap.
- `tests/test_net_pose.py`: out 5,000 units and back lands within 0.00001; two Games
  (a duel's start: z -1000 facing +z, z +1000 facing -z) see each other dead ahead,
  and after both fly about agree on distance and angle; through a packet within 0.07 units.

## Built: DUEL (same branch)

- **Lobby, host and join (Brian, 2026-11-25):** everyone on the DUEL page says HELLO
  4 times a second with their commander's name (`cmdr_name`) and ship paint
  (`cmdr.colour`, `cockpit.SHIP_COLOURS`) and what they are doing (LOBBY / HOST / JOIN /
  FLYING, and for whom). The lobby page lists HOST A GAME, a JOIN line for each open
  game, and who is there; a host takes the first guest to ask (the game then shows as
  full); the host sees the guest's name in their colour and C starts: START to the guest
  (repeated for 1 s) and both fly at once, host from START[0], guest from START[1], 8000
  apart (2000 was too close: Brian), as far as practice's ships come in, on the radar. The
  other ship is drawn in its owner's paint with their name under it (`Obj.rgb`,
  `Obj.label`; the radar and both dashboards use the colour). This replaced slots by id
  and the "start again when the other starts flying" fix.
- **Leaving (Brian, 2026-11-25: when the host leaves, the game ends):** leaving the flight
  sends END three times. The host leaving ends the guest's game: back to the lobby, which
  shows HOST LEFT for 4 s; if every END is lost, the host's next HELLO from the lobby does
  it; a host not heard for 10 s (battery, window closed) ends it as HOST LOST. **The guest
  leaving ends the host's game too** (Brian): back to the lobby, "<NAME> LEFT" (or LOST).
- **Combat (Brian, 2026-11-25: damage, lasers, missiles, ramming; the ECM by hand):**
  a laser hit is the shooter's to decide: HIT (damage x16) and the target takes it
  (`Game._hurt`); its beam shows on the target's screen when its nose points at them
  (pose flag FIRING). A missile is the target's: MISSILE (number, launch point and way,
  sent 3 times) and the target's game flies it as an enemy missile; it says GONE (hit, or
  its ECM) and the shooter's harmless copy (`Obj.ghost`) goes ("ECM" if it was that).
  Ramming: each game hurts its own ship, not again for `RAM_AGAIN` s. The ECM is by hand
  (`rules.manual_ecm` while dueling): E on a keyboard, both speed buttons, **B on the
  badge** (Brian: the energy bomb can't touch the other player), LB on the Pi pad.
  Destroyed: the pose flag DEAD; the other sees the explosion and "<NAME> DESTROYED k-d";
  fly again (C) starts you at your end. Players can be locked and fired at like ships
  (`_pick`), but the AI, the energy bomb and encounters still leave them alone.
  `tests/test_duel_combat.py`.
- **Rounds and loadout (Brian, 2026-11-25):** every round starts both ships the same
  (`Duel.loadout`: shields and energy full, an ECM, a full missile rack, lasers cool, no
  energy bomb since B is the ECM; the ECM was missing before: `_start_flight` thought the
  new game wasn't fresh). Destroyed: the duel's own end screen (DESTROYED / BY <NAME> in
  their colour / the score / C: next round / F: leave duel; `Duel.over_lines`, drawn by
  cockpit instead of GAME OVER). C sends NEXT (the round number, 3 times) and both go
  back to their ends with fresh loadouts, "ROUND n"; the score is kept.
- Title screen DUEL (only when the platform has `radio()`: the badge always; the Pi with
  `run.py --duel [PORT]`; not the Tufty yet). Its page says HELLO 4 times a second and
  shows SEARCHING / PLAYER FOUND; C flies (alone until the other comes), F back.
- `duel.py` (imported only when DUEL is chosen): slots by id (smaller id at z -1000
  facing +z, the other at z +1000 facing -z), `Game.quiet` (no waves or rocks), its
  pose 15 times a second, the other's ship as kind "player" (not "ship", so the AI,
  missiles, the energy bomb, encounters and mass lock leave it; not rammed or shot yet),
  placed from its last pose moved on by its speed; older packets dropped; 3 s silent
  "LINK LOST" (the ship goes), then "LINK BACK"; fly again (reset) puts you back at
  your start; leaving the flight ends the duel.
- Links: `net_espnow.py` (badge: broadcast, rxbuf 4096, read every frame) and
  `hosts/pi/net_udp.py` (UDP broadcast, a random id per run; two windows on one Pi play).
- `tests/test_duel.py`: two Games on a pretend radio (finding, slots, the same distance
  both ways, half the packets lost, late packets, LINK LOST / BACK, reset, stop) and the
  app's DUEL page and flight. A sees B a frame behind (~14 units at starting speed).

Not yet on a badge. Next: shots and hits (the shooter decides, sends a HIT with damage;
the target takes it and sends DEAD), then the Tufty (UDP on its Wi-Fi) and the Pi bridge.

## Built: up to four players and modes (build 148, 2026-11-25)

Brian: "make it support up to four players. Modes Free for all, teams and capture the flag.
Protect the convoy ship from pirates." Capture the flag: "Two rings in teams colours set
distance apart. To capture the flag you must fly through the ring the changes colour and you
must fly back to your ring and pass though to score. Destroyed ship spawn close/behind to
their home ring after a set time." The convoy: "could be coop or p v p. Convoy ship will need
to be a new large design".

- **Lobby:** DUEL on the title screen is MULTIPLAYER. The host picks the mode (left / right)
  and takes the first three to join; HELLO carries the mode and the host's guests (46 bytes),
  so the lobby shows each game's mode and how full it is, and the guests see who else is in.
  START carries the guests in order: slot 0 the host, 1-3 the guests. Team modes: even slots
  RED, odd BLUE. Each mode has its least and most players (`MODE_MIN`, `MODE_MAX`).
- **Modes:** DUEL (unchanged), FREE FOR ALL (10 kills), TEAMS (10 team kills, no friendly
  fire), CAPTURE FLAG (rings 10000 apart; through the other's ring takes its flag, the ring
  goes grey; back through your own scores; 3 wins), CONVOY CO-OP and CONVOY RAID (the BULK FREIGHTER,
  `convoy_ship.py`, flies 12000 units in 150 s to a station; pirates every 25 s; it arriving
  is red's / everyone's win, it destroyed the raiders' / pirates'). Not a duel: back after 5 s
  at your start; a result for 10 s, then the next match (scores, flags and convoy afresh).
- **Who decides:** your game what hits you (as the duel); the host everything shared, said
  in STATE (22 bytes, 4 a second and at once on a change): match, result, time, per-slot
  scores, team scores, the flag carriers, the convoy's energy. Others ask: CLAIM (through a
  ring), KILLED (by whom: the last hit within 10 s). The convoy's place is worked out from
  the match time on every device; only its energy is sent.
- **The pirates** are ordinary ships in the host's game, so they fight as practice's do.
  `Game._pick_prey` asks `Duel.prey_for`: the convoy (twice as likely), the host or another
  player (not raiders in a raid); a pirate shot by a guest turns on that guest. Their poses go
  out in NPCS (ten a second; 22 bytes each, at most 10 a packet, 224 bytes); a destroyed one
  is sent with DEAD for half a second so the others see it explode. The others' copies are
  kind "npc": hits go to the host (NPC_HIT), missiles too (MISSILE with `NPC_BIT`: the host
  flies it and says GONE). A pirate's hit on another player is a HIT from `NPC_SRC`.
- **Leaving:** the host leaving ends the game for everyone (as before); a guest leaving drops
  out ("<NAME> LEFT"), and the game ends when nobody else is left, except CONVOY CO-OP.
- `tests/test_multiplayer.py`: four players in each mode on a pretend radio.

Not yet on badges: the frame time with three other ships, eight pirates and the convoy (92
lines in 6 parts close up) needs measuring; and how busy the radio is with four (each sends
15 poses a second; the host also 10 NPCS and 4 STATE).

## The game (suggestion)

1. A duel in the combat practice arena, no NPCs: each device flies its own ship and
   sends pose, speed and shots ~15 times a second in a fixed-size packet (no JSON:
   garbage); the shooter decides hits and tells the target. A MULTIPLAYER line on the
   title screen: HOST / JOIN.
2. The catch: the game is Elite's, the world moves round your ship. Each device must
   keep its own position and heading in a fixed frame and send those; the receiver
   turns them into its own frame (as `Game.enter_view` does for the four views).
3. Later: co-op against NPCs (one device runs them), then commanders meeting in a system.
