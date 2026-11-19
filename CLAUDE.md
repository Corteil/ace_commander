# Ace Commander for the EMF Tildagon / Spaceagon badge

Notes for picking this project up in a new session.


## What this is

A MicroPython app for the 2026 EMF Camp "Spaceagon" badge (Tildagon with the 2026 front
board): a wireframe flight combat game plus a ship viewer, using the ship geometry and stats
of BBC Micro Elite. Brian's constraints: plain MicroPython, **no custom firmware build**.
C or `@micropython.viper` is welcome only if measurements show it would help.

Built from `DESIGN.md`: phase 1 (title screen, saved commander with rank, three levels, new
button layout) and phase 2 (galaxy, local and galactic charts, system data, hyperspace,
fuel, docked screens as tabs, launch tunnel), and the start of phase 3 (build 26: planet,
sun, station, compass, jump drive, automatic docking; build 27: docking by hand; build
30: the market; 31: scooped cargo; 32: bounties, which finishes phase 3), and the start
of phase 4 (build 33: the Equip ship screen; build 36: every item's effect). Phases 4 and
5 are done, the system description sentence (build 52) and the disc version's two
missions (build 54). Phase 6's ship types are done (builds 78-84: Shipyard, Hangar, jump
ranges, stolen ships), with NPC escape pods (86), finding a system by name (88) and a
commander name (89); released as v0.3.0 (2026-11-18).

## Files

- `app.py` - **the loading screen** (build 50). The badge's launcher imports
  `<folder>.app` and starts its `__app_export__` (firmware `system/launcher/utils.py`), so
  this file must be `app.py` and stay tiny: it draws at once, imports the other modules one
  by one with a progress bar, then hosts the real app. On a PC (tests) the package's
  `__init__` gives `ace.AceCommander` directly.
- `letters.py` - the name in block letters (rectangles), shared by `title.py` and the
  loading screen; imports nothing.
- `ace.py` - **the real app** (it was `app.py` until build 49; older notes below that say
  `app._dock`, `app.py` and so on mean this file): menu, input (`Pad`), frame loop (`run`),
  LEDs, pause, PERF logging.
- `game.py` - game rules, including the star system (`Space`, `Game.enter`). No badge
  imports, so it runs on a PC.
- `cockpit.py` - flight view, HUD, radar. Built from rectangles (see Speed).
- `viewer.py` - ship viewer. `bench.py` - the speed test (DEBUG > DISPLAY > SPEED TEST since build 72).
- `title.py` - title screen: block-letter name from rectangles, tumbling ship, one menu line.
- `commander.py` - the saved commander (level, kills, rank, star system, fuel). Rules only,
  no badge imports. Saved to `commander.json` next to the app (gitignored).
- `galaxy.py` - the 256 star systems, worked out from three seeds. Rules only.
- `chart.py` - the local and galactic charts (imported the first time one is opened).
- `find.py` - finding a system by name on the Galactic chart (build 88): the keyboard's
  page; without a keyboard ace.py uses the firmware's TextDialog instead.
- `docked.py` - the docked tabs: Status, Market, Local chart, Galactic chart, System data.
- `market.py` - market prices, stock, buying and selling. Rules only, no badge imports.
- `equipment.py` - the Equip ship screen's rules: what is on sale, prices, fitting.
- `ships.py` - the ship types you can own and fly (build 78): price, hold, mounts, pylons,
  fuel tank (jump range), flight stats from the blueprint, the shipyard's stock, the
  hangar's entries. Rules only.
- `describe.py` - the system description sentence ("goat soup"): the original's extended
  tokens from `game_data.py`, put together as DETOK does; also the mission texts and the
  special system sentences. Rules only.
- `missions.py` - the disc version's two missions (Constrictor, Thargoid plans). Rules only.
- `briefing.py` - INCOMING MESSAGE and the mission texts, a screen at a time, on docking.
- `original_ships.py` - **the game's own ships** (build 55), committed: 31 original
  designs, one for each role the game knows by Elite's names, with their own names
  (entry[5], `Blueprint.title`). Made by `tools/make_original_ships.py` with
  `tools/shipmaker.py` (convex hulls from corner points, explicit faces, lines on faces).
  Used when the Elite files are missing, or with Options > DATA: OWN (see `content.py`).
- `original_data.py` - **the game's own galaxy, market and equipment** (build 56),
  committed: seeds, letter pairs, start (Daenor), goods, equipment prices, and where the
  missions happen (`MISSION_PLACES`, read by `missions.use`).
- `content.py` - decides once at start-up whose content is used: Elite's
  (`ship_data.py` + `game_data.py`) or the game's own (`original_*`). Own if either Elite
  file is missing or options.json has "own" (old key "own_ships"). `ace.SHIPS`,
  `ace.game_data` and `docked.game_data` come from it.
- `ship_data.py`, `game_data.py` - generated, **gitignored** (see Licensing). 31 ships; the
  galaxy's seeds, name letter pairs, starting place, the market's 17 goods and the 14
  equipment prices. Both must be copied to the badge.
- `tools/import_ships.py`, `tools/import_galaxy.py` - make those two from the Elite source.
- `tools/badge_log.py`, `deploy.bat` - copy to the badge, restart it, save its serial output
  to `badge_log.txt`.
- `tests/` - PC test suite with stand-ins for the badge firmware.
- `hosts/` - the same game on other devices, left out of release tarballs (`.gitattributes`).
  `hosts/pi/` (2026-11-19, P0): pygame window; `pi_firmware.py` stand-ins for the firmware
  modules (real `ace.py` unchanged), `ctx_pygame.py` (the ctx calls at scale), `keys_pi.py`
  (arrows = joystick, F1-F6 = badge A-F, the rest = Keyboard Hexpansion), `run.py` (`Host`:
  loop, round mask, LED ring). Tests: `hosts/pi/tests/test_pi_host.py` and `test_pi_trip.py`
  (P1: a whole trip by keys; SDL dummy driver), run by `tests/run_all.py` when pygame is there.
  `run.load_game` keeps save, options.json and debug.txt in `~/.local/share/ace_commander/`
  (content.py loaded with its `__file__` there); DEBUG and PERF only with `--debug`. Plan: `hosts/pi/PLAN.md`.

The repo folder must be called `ace_commander`: the tests import the app as that package, and
it installs to `/apps/ace_commander/` on the badge.

## Working with the badge

- **On Brian's Raspberry Pi the badge is plugged in and Claude can reach it:** copy files
  with `mpremote connect auto fs cp ... :/apps/ace_commander/`, `mpremote connect auto reset`,
  and log with `python3 tools/badge_log.py SECONDS PORT` (only one program can hold the port).
  On 2026-11-14 the badge was `/dev/ttyACM1`. Brian has two badges: serial
  `7c4fad337ac00000` (the usual one) and `64e83372252c0000` (build 34 put on it
  2026-11-14 over an older build; it keeps its own `commander.json`). Both run
  MicroPython 1.28; check `/dev/serial/by-id/` to see which is plugged in. To test over the REPL (`mpremote run x.py`),
  `import system.scheduler` first, or importing the app fails with
  `ImportError: can't import name eventbus` (the firmware's eventbus and scheduler import
  each other; at boot the scheduler comes first).
  The rest of this list is the older Windows / cloud-session workflow.
- Claude cannot reach the badge's serial port from its sandbox, and cannot type into a
  terminal by screen control (terminals are click-only). The loop that works: Claude writes
  files into this folder, Brian double-clicks `deploy.bat`, uses the badge, then says so, and
  Claude reads `badge_log.txt`.
- The badge was on **COM13** (`set BADGE_PORT=` at the top of `deploy.bat`).
- `deploy.bat` copies the code files; `deploy.bat all` also copies `ship_data.py`.
- A crashed app prints a traceback to serial, so it lands in `badge_log.txt`.
- All files on the badge must come from the same build. A mismatch between `app.py` and
  `cockpit.py` caused the one crash seen so far.

## Tests

`python tests/run_all.py` from the repo folder (needs `ship_data.py`). `tests/render.py`
draws real frames to `tests/shots/*.png` with Pillow, which is how layout was checked.
`tests/badge_stubs.py` copies the firmware's button matching rules, so joystick-versus-button
logic is tested for real. Also compile with the badge's own compiler, which the firmware
build in `~/Code/tildagon-firmware-builds` leaves behind (v1.28.0, the badge's version; runs
on the Pi without Docker):
`~/Code/tildagon-firmware-builds/work/2026-v2.2.1-rc1-mirror/badge-2024-software/micropython/mpy-cross/build/mpy-cross -march=xtensawin -o /tmp/x.mpy app.py`
for each `.py` file. Don't use `pip install mpy-cross`: it is a newer MicroPython (v1.29).

Nothing here proves behaviour on the badge. Say so when reporting.

## Firmware facts (read from the source, not guessed)

Source: `github.com/emfcamp/badge-2024-software`, folder `modules/`. Brian's own working app
`github.com/Corteil/file_explorer` is a good reference for app structure.

- Apps are packages: `__init__.py`, `app.py`, `tildagon.toml`, `metadata.json`. The app class
  must call `super().__init__()`.
- Buttons A to F are also UP, RIGHT, CONFIRM, DOWN, LEFT, CANCEL (`BUTTON_TYPES`). To tell a
  lettered button from the joystick use `frontboards.common.FRONTBOARD_BUTTON_TYPES["A".."F"]`
  and `events.joystick.JOYSTICK_BUTTON_TYPES["UP"/"DOWN"/"LEFT"/"RIGHT"/"SELECT"]`. The
  joystick is a digital 5-way switch. Only the current firmware, which has both, is
  supported (Brian, 2026-11-18): `ace.py` imports them directly, with no fallback.
- `Buttons.get()` / `.pressed()` search every known button in Python on each call. Polling
  about 25 controls a frame was a large hidden cost; `Pad` in `app.py` listens for
  `ButtonDownEvent` / `ButtonUpEvent` on `system.eventbus` instead.
- Frame loop (`modules/app.py`, `modules/system/scheduler/__init__.py`): the default
  `App.run` awaits `render_update`, which sleeps 50 ms after every update. `AceCommander.run`
  overrides it: sets `scheduler.render_needed`, yields once, continues. It falls back to
  `render_update` if anything raises or the app is not foregrounded.
- LEDs: `tildagonos.leds[1..12]` is the front ring (0 and 13-18 are other LEDs), values
  0-255, then `.write()`. Emit `PatternDisable()` first and `PatternEnable()` after
  (`system.patterndisplay.events`). `tildagonos.set_led_power(True)`.
- IMU: `imu.acc_read()` gives m/s^2. `imu.mag_read()` works on the 2026 board.
- Keyboard: `events.keyboard.KEYBOARD_BUTTONS` (letters, `SPACE`, `ENTER`, arrows...).
- `ctx` draws straight into the framebuffer; `display.end_frame` then sends it to the screen.
- A screen-reader hook prints every changed `ctx.text` string to serial, another reason to
  avoid per-frame text.

## Build history and speed measurements

Build history (builds 13 to 59, Brian's decisions per feature) and the badge speed
measurements (cost of each drawing call, garbage per frame) are in `BUILD_NOTES.md`. Read
the relevant build there before changing a feature.

## Next steps

**v0.3.0 (2026-11-18)** has ship types (`ships.py`: `Game.set_ship`, Shipyard / Hangar,
`Commander.ship` / `.stolen` / `.hangar`, per-ship fuel tanks), Elite's weapon ranges, NPC
escape pods, the CONTROLS flip, Galactic chart search (`find.py`) and the commander's
name. Brian's rules are in BUILD_NOTES.md builds 76-90. **The firmware's dialogs
(TextDialog) must be registered to `self.host`** (app.py's loader is the focused app; the
eventbus gives buttons only to focused apps), or the badge freezes (build 89).

1. **Tilt steering needs tuning: Brian doesn't like how it feels** (2026-11-13). Build 85
   added Options > TILT, build 87 made it CONTROLS (flips the flight steering up/down,
   left/right or both, joystick included; saved). Ask before changing
   the rest: sensitivity (`TILT_FULL`), dead zone (`TILT_DEADZONE`), or the D hold time
   (`HOLD_MISSILE`).
2. Missile lock (build 19): the diamond is red, then green after `LOCK_TIME` (2 s, Brian's
   choice after playing with 1 s) and only then will D fire.
3. The in-flight menu has a DEBUG page of cheats (`DEBUG_MENU` in `app.py`, on by default
   while the game is being built; `Game.god` is the invincibility flag). Add a cheat there for
   each new thing that is slow to reach by playing, and turn it off before publishing.
   Its title shows the build (build 54), read from `metadata.json` by `app.build()`, so
   bump `version` in `metadata.json` and `tildagon.toml` for every build.
4. Level names are EASY / NORMAL / HARD (kept for release, build 58); their numbers are
   `commander.py` (`RANK_DIVISOR`) and `game.py` (`LEVELS`).

## Not yet confirmed on the badge

- Tilt axis directions (`TILT_PITCH_SIGN`, `TILT_ROLL_SIGN`, `TILT_SWAP_AXES`).
- The local chart and hyperspace (build 20): cursor speed (`CURSOR_SPEED` in `chart.py`),
  whether the ring and dots read well, the streaks on arriving.
- Arriving (build 21, kept in build 26): whether 3 / 4 / 5 ships is the right fight.
- The star system (build 26): whether the planet, sun, station and compass read well;
  `ARRIVE_DIST`, `SAFE_K`, `JUMP_K`, `ENCOUNTER_EVERY` and `DOCK_DIST` by feel; the frame
  rate with the planet in view.
- Docking by hand (build 27): whether A is possible with the digital joystick (the
  tolerances above), whether B's beam feels right, crash damage and bounce; not yet on
  the badge (deployed and checked over the REPL; Brian's first test run was fine).
- The docking scene (build 28, confirmed by Brian) with build 29's varied tunnels: whether
  the shapes, morphing and spacings look good on the badge.
- The market (build 30): the layout on the badge, C / D and the repeat speed.
- Scooping into the hold, combat practice pick-ups and the green safe-zone LEDs (build 31).
- The Equip ship tab and the lasers, energy unit and fuel scoops in flight (build 33).
- Bounties (build 32): the cash message on a kill. Encounters by government and the
  planet-sized safe zone (build 32): whether the danger now feels right.
- Whether `deploy.bat`'s copy step reports failures properly (the log step is known to work).

Confirmed by Brian on 2026-11-13: F is faster and E slower; the LEDs flash on a hit and the
badge's own pattern comes back on leaving flight; ships switch from cross markers to
wireframes at a distance that looks fine (`WIRE_MIN`).

Confirmed by Brian on 2026-11-14 (build 25): the DEBUG page shows the build; the launch
tunnel's look and length; the station colours and the LED pulses on launch; the galactic
chart, cursor speed included (`G_CURSOR_SPEED`). Build 25 also flew 5 minutes with docking
and launching and no errors in the log.

## Controls (Brian's choices)

Joystick steers by default. C or joystick press fires, D missile, B energy bomb (not built
yet, says so), F/E speed up/down, A in-flight menu (status, settings with steering
and quit). Docked, on the market: joystick up / down picks a good, C buys, D sells (held
buttons repeat); on Equip ship: joystick picks an item, C buys. In tilt steering a tap on D re-zeroes and a hold fires the missile. Hostile ships red on the radar. Hit flash on the LEDs, not a ring
on screen. Enemy lasers run from the ship's gun to the bottom of the screen (the cockpit).

## Hardcore Mode (branch `hardcore-mode`, started 2026-11-16, not merged)

Brian's plan ("Ace Commander: Hardcore Mode & Keyboard Support"): switch the assists to manual and
control them from the keyboard (Tildagon Keyboard Hexpansion, and the Tufty's Keebdeck). Standard mode
must not change. `rules.py` (`GameRules`, no badge imports, shared with the Tufty port) holds one flag
per assist; `Game.rules` is standard by default and `ace.py` gives a flight `GameRules(...)` when it
starts. **Build 74 (Brian): HARDCORE and LEVEL are picked on the NEW COMMANDER page and then fixed;
only DEBUG > COMMANDER (LEVEL, HARDCORE; in flight at once) changes them.** `Commander.hardcore` is in
the save (`ace._hardcore()`); a save from before has None and takes options.json's old "hardcore"
(`old_hardcore`). No HARDCORE line in Options/Settings any more. Practice's own is `p_hardcore`. Built so far: manual ECM (`Game.fire_ecm`; E key, or both speed buttons together) and armed
missiles (`Game.arm_missile` / `unarm_missile`; T / U keys, D arms then fires; lock builds only while
armed). Tests: `tests/test_hardcore.py` (needs no Elite files). Mass lock (all modes, `Game._massed`, `MASS_LOCK_K` 2 radii): the local jump drive drops out near the
planet or sun, "MASS LOCKED"; the station's mass is its safe zone, which is kept (the planet's sphere
does not cover it: the station is 3 radii out). The sun is also covered by the heat rule. Docking: the DOCKING setting exists in every mode, and Hardcore's flag `manual_docking` forces MANUAL (by hand;
the saved style is untouched and the Settings line says "MANUAL"); the only help is a docking computer you
have bought (`Game.computer`). The other jump lock-outs and save-only-when-docked already exist, so they are
not Hardcore flags.
**Four views, in every mode (not a Hardcore flag: Brian, 2026-11-16; checked against the disc source's
VIEW, LOOK1, PU1, PU2, LASER, SIGHT).** `Game.view` 0 front, 1 rear, 2 left, 3 right (`VIEW_NAMES`); the
dashboard, radar and controls don't change. The world stays in the front frame; `Game.enter_view()` /
`leave_view()` flip or swap it as Elite's PU1 / PU2 do (rear: -x, -z; left: (z, -x); right: (-z, x); objects,
their axes, explosion dots, planet, sun, station, `Game.new`) to draw it (`cockpit.draw_world`) and to aim
(`Game._weapons` runs inside it, and the missile is made after leaving it: it always goes straight ahead, as
in Elite; lock follows the view's crosshair). Whole-number exact. Stardust is a copy per view
(`Game.view_dust`, `DUST_MID`): from the rear it rushes away, from the sides it streams past. A laser per
view (`Game.lasers`, `set_laser(kind, view)`; `Game.laser` is the current view's, None if none: "NO LASER", no
crosshair); `Commander.lasers` (save key "lasers", old saves load) with `laser` still the front one. The shop
(`equipment.buy(..., mount)`): D on Equip ship picks the view, a new laser refunds only that view's old one.
SHIP CONFIG has a LASER line for each view (none is possible except at the front). A view change shows
"REAR VIEW" etc. and a grey label while not looking ahead. Change it: top in-flight menu `VIEW: FRONT`
(second line; C or right the next view, left back, and the menu stays open: Brian, 2026-11-16), number
keys 1-4 (the keyboard plan's f0-f3: front, rear, left, right), V for the next. Docking computer forces the
front view. Tests: `tests/test_views.py`. Tufty: `DUST_X` (the wider view) isn't used by `view_dust` yet.
**Keyboard, confirmed by Brian on the badge (2026-11-16):** Enter and Space fire the laser (the
firmware makes Enter a CONFIRM button, so it also works menus as C does); Esc is CANCEL, so it leaves
the pause menu. The cursor keys count as the joystick too (`Pad` gives them the `j_` names on the 2026
board), so they pick menu lines, change Settings and the VIEW line, and move tabs and chart cursors.
**The rest of the keys, Elite's scheme (Brian's choice, 2026-11-16; his written plan isn't on the
Pi, so this is the agreed fallback):** `+` / `-` speed in every mode (`=` and `_` too, the same keys
without shift); J holds speed up, so at full speed it is the jump drive under the usual rules; H
hyperspace and Shift+H the galactic hyperdrive (Brian, build 65: the Keyboard Hexpansion never sends
Ctrl, so Elite's Ctrl+H can't work; a badge key log showed it sends Shift down, H down, Shift up, H
up inside one frame, so `Pad` records Shift / Ctrl at key-down as hit("mod+k_H"); Ctrl+H still works
on a keyboard that sends Ctrl; not G). `LOG_KEYS = True` prints every button event to serial.
Esc is Elite's escape pod looking at space (`Game.eject`; on a screen or menu Esc is still back) and
Tab the energy bomb (build 66); Backspace too (build 68), since an unpatched driver drops Tab. C
switches the docking computer on and P off, as Elite (P is the pause menu when it is off; both read
in any view, not while paused). Ctrl+H needs the patched driver; Shift+H works with either. The Keyboard Hexpansion driver (github.com/sodoku/tildagon-keebdexpansion,
on the EEPROM as app.mpy, the same source) sends only keys named in the firmware's KEYBOARD_BUTTONS,
so it drops TAB and LCTRL; `Pad` also matches a button named TAB (`BY_NAME`), and a driver LCTRL
with CTRL as its parent counts as Ctrl.
After the escape pod (crash or Esc) the docking scene flies the ESCAPE POD in, to scale (Brian, build
67: `_fly_in(pod=True)` / `_pick_tunnel(pod)`). The ship you fly is `_ship_name()` (always the Cobra
Mk III until ship types are built): the tunnels, the Repair Shop and the chase view (`Game.ship_name`)
all ask there.
The printable key guide is `tools/make_key_guide.py` (writes key_guide.pdf, gitignored): change it
when a key changes. The number row is f0-f9:
in flight 1-4 the views, 5 galactic chart, 6 local chart, 7 the target's (or here's) system data, 8
Market Prices, 9 Commander Status, 0 Inventory. Docked (`DOCK_KEYS`, build 69): 1 launch, 2 / 8 market, 3
market on the first good in the hold (Elite's Sell Cargo), 4 equip ship, 5 galactic chart, 6 local
chart, 7 system data, 9 status, 0 Inventory (a tab since build 70, drawn by `screens.draw_inventory`), and the two screens
Elite lacks on the keys after 0 (Brian): - (or _) Shipyard (was the Repair Shop), = (or +) Options. The joystick goes
round the tabs in `docked.TABS` (Brian, builds 77-80): Status, Inventory, Market, Equip ship,
Shipyard, Hangar, Galactic chart, Local chart, System data. The Repair Shop is the Shipyard's
sub-screen (D on its first page, your own ship; C there and on every page is that ship's
stats, where C buys and D trades in; `-` opens the Shipyard). Options is not a tab: C on Status opens it over
Status (`Docked.in_options`, `name()` gives "OPTIONS"), F goes back; A launches. Only the current
firmware matters (Brian, 2026-11-18: both badges run it). C on Inventory sells the whole hold (`Docked.sell_all`).
The Repair Shop is always there (build 81: its DEBUG switch removed). Tests: `tests/test_keys.py`.
**In-flight screens don't pause (Brian, build 62: "as Elite"; checked against the disc source).**
Status, Inventory, Market Prices, both charts and system data are `SCREENS`: `fsub` names one while
`paused` is False, and it is drawn instead of the space view (`_draw_screen`; the three new ones in
`screens.py`, imported on first use). The menu's STATUS / LOCAL CHART / HYPERSPACE lines open them
too, and resume. `_screen_keys` (flying, on a screen or in the menu) opens, switches and closes them:
the open screen's own key closes it, 1-4 fly on looking that way; each only when `_fitems_top()` has
its line (nothing in combat practice or during a countdown). On a screen, as Elite: the joystick,
buttons, cursor keys, Enter and Esc work the screen (C or F back); only the primary flight controls
fly (W/A/S/D or tilt, speed keys, Space / F fire); the secondary keys (M, T, U, E as ECM, J, V, the
energy bomb) do nothing (Elite's DK2 only reads them in a space view); lasers fire, heat and cost
energy but can't hit, and missile lock stops (`Game.looking` False: Elite skips laser and missile
locking off a space view, MA15). Market Prices works out the system's market on first use and keeps
it with the commander, so docking shows the same prices; nothing can be bought or sold in flight. A
jump closes any screen. On the in-flight charts C only selects (Brian, build 64): the system becomes
the target (C on where you are clears it) and the chart stays, its distance line saying "TARGET";
H or the menu's HYPERSPACE line jumps, as Elite. `Game.condition()` is Elite's GREEN / YELLOW / RED for Status. The fire lock
(the C that chose something isn't a shot) applies to C / Enter only, so Space held through closing
a screen keeps firing.
**Combat practice's page (build 72, Brian):** COMBAT PRACTICE opens `mode == "practice"` first: LEVEL
(`AceCommander.p_level`, options.json "practice_level") and HARDCORE (build 73: its own,
`p_hardcore`, "practice_hardcore", apart from the commander's; the in-flight Settings line in a practice
flight is practice's, `_practising()`); up / down picks the line, left / right changes it, C flies, F
back. Practice flies with an ECM (build 73; automatic, or by hand in Hardcore). A part-way practice fight carries on only
if level and HARDCORE are unchanged. SPEED TEST left the title screen (Brian: keep it, hidden) for
DEBUG > DISPLAY (off flight only; F returns to that page).
Not built yet: a HARDCORE marker on the HUD.
All 21 test files pass with Elite's files; without them 9 of 18 did when this was started.

## Licensing

`ship_data.py` and `game_data.py` are derived from Elite (c) Acornsoft 1984, via
`github.com/markmoxon/elite-source-code-bbc-micro-disc`, which has no licence. They are
gitignored and must not be committed, published or put in the badge app store. Brian
generated it from his own clone. The converter that reads it is fine to publish.

The GitHub repo (`Corteil/ace_commander`, called `elite_demo` until 2026-11-13)
is **public** as of 2026-11-13, so check every commit
for Elite-derived data before pushing. Describe the project as a fan-made game inspired by
Elite, written from scratch, not as a port: no original code is used. The README's
"Credits and original material" section has the wording; Brian read it and agreed to merging it on 2026-11-13.

## Pitfalls for an agent working here

- On the Pi the badge sometimes drops off USB for a moment during an mpremote copy
  (`Input/output error`, then `no device found`); it comes back as the same port. Copy
  again and check every file's checksum before resetting.
- After writing files into this folder from a cloud session, **verify by checksum**. Once, a
  write reported success but delivered a stale cached copy of the same staging path. Staging
  each build under a fresh path avoided it.
- Git inside the sandbox cannot delete its own lock and temp files unless Brian grants delete
  permission, so a commit made there leaves `.git/*.lock` and `tmp_obj_*` behind. So far
  Brian has run commits and pushes himself.
- Say plainly what was tested only on a PC. Several early builds would have crashed on the
  badge (missing `super().__init__()`) while passing every PC test.
