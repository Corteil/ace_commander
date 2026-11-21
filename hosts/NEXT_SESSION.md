# Plan for the next session (written 2026-11-19)

Two strands, in this order: **A. the Tufty's first run on hardware (G1)**, since a Tufty 2350 is
now plugged into the Pi, then **B. the platform layer** that makes the game run on any device
without hosts patching it. A's findings (the real Badgeware behaviour) shape B's interface, and
B's last step moves the Tufty into `hosts/tufty/`.

## Where things stand
- **Released:** v0.3.2 (2026-11-19), builds 93-95. Main has since gained builds 96-97 (no badge
  behaviour change) and the Pi's P1-P3 (PRs #26-#29, last merge `41bd50c`). No release needed for
  those unless the badge changes.
- **Badge:** the usual one (`7c4fad337ac00000`, `/dev/ttyACM0`) runs build 95's game files.
- **Pi host** (`hosts/pi/`): keyboard, game pad with analogue sticks and yaw, badge layout and
  Elite layout (F10), full screen (F11), screenshots (F12), resizable, `pi.json`. Plan:
  `hosts/pi/PLAN.md` (P3 remaining: KMS without a desktop, HyperPixel Round; P4 extras).
- **Tufty port:** `~/Code/tufty_ace_commarder` (`Corteil/tufty_ace_commarder`, main `ea5d504`),
  never run on hardware. Its `vendor/` is an old snapshot of the game; `tools/build_app.py` applies
  `tools/patches.py` (11 edits) to it.
- **Devices on the Pi now:** Tufty 2350 MicroPython (serial `cf39515354ec6c00`, `/dev/ttyACM1`),
  Raspberry Pi Debug Probe (`/dev/ttyACM2`), the badge (`/dev/ttyACM0`), the 8BitDo pad.
- **Rule:** copy / reset / REPL on the badge **or the Tufty** only after Brian says OK.

## A. Tufty G1 (first run on hardware)
Checklist: `~/Code/tufty_ace_commarder/G1_CHECKLIST.md`. Steps:
1. **Sync the game into the Tufty repo** (`tools/sync_from_ace.py`) from `ace_commander` main.
   **Expect `build_app.py` to stop:** patches 1-7 (`VIEW_HW` / `VIEW_HH`, `DUST_X`) are in the game
   itself since build 96, so their `old` text is gone. Drop those entries from `tools/patches.py`
   (or make the build skip a patch whose `new` text is already there); keep any that remain.
   Re-run its tests (`tests/test_host.py`, `test_dashboard.py`, `test_patch_identity.py`).
2. **Bring the Tufty up to date with the game** (from its PLAN "Update 2026-11-18"): `scenes.py`
   launches with A; `dash_tufty` follows the ship (`g.max_speed`, `g.max_missiles` up to 5 lamps,
   `g.fuel_max`, blank FU at 0); a `TextDialog` stand-in; `dash_tufty` uses `cockpit.hostile`.
   The Pi's `dash_pi.py` already does the ship-following parts: copy from there.
3. **Ask Brian**, then look at the Tufty over `mpremote connect /dev/ttyACM1` (read-only first:
   `ls /`, firmware version, free space), then copy the probe (`apps/ace_test`) and the built game.
4. **Run the probe and the game** with Brian, ticking G1_CHECKLIST sections 1 and 2 (resolution,
   frame rate raster vs vector lines, I2C / Qw/ST Pad at 0x21, `qwstpad` import, launcher loop
   mode; then title, buttons, docked, launch, flight, saving, leaving). Fix by symptom (section 3).
5. Note what the real Badgeware does differently from the sim: it feeds B's platform interface.

## B. The platform layer (make the game universal)
Today the rules (`game`, `galaxy`, `commander`, `market`, `equipment`, `ships`, `missions`,
`describe`, `rules`, `find`, `original_*`) are portable; the drawing is portable but laid out
for the round 240x240 screen; `ace.py` (3,185 lines) has 14 firmware imports tangled with the
game's screens. Hosts get round it by stand-in firmware modules (`hosts/pi/pi_firmware.py`),
loading `content.py` under a false `__file__`, overwriting module variables after import
(`SAVE_PATH`, `DEBUG_MENU`, `PERF_LOG`, `LOG_KEYS`, `TITLE_QUIT`), replacing `cockpit.draw_world` /
`draw_hud` / `draw_tunnel`, changing functions' defaults (`WIRE_MIN`) and wrapping `Game.step`.

Steps, each a small PR with the badge's behaviour unchanged:
1. **Settings and storage. Done 2026-11-20 (build 100, `config.py`), not yet run on the badge
   or the Pi.** One settings object (debug menu, PERF log, key log, title QUIT, draw distance)
   and a storage interface (where the save, `options.json`, `debug.txt` live). `content.py`
   gets the options path from it instead of its own `__file__`. The Pi's `load_game` tricks
   went. View size was left for step 4 (it changes per frame with the Pi's layout).
2. **Input as controls. Done 2026-11-20 (build 101: `controls.py`, `platform_tildagon.Input`,
   the Pi's `controls_pi.py`), not yet run on the badge or the Pi.** The platform sends the game control names (`confirm`, `j_up`, `A`-`F`,
   `k_*`), not firmware buttons; the badge's platform does today's `Pad` matching (firmware
   `Button` parents, Keyboard Hexpansion quirks: Shift at key-down, TAB / LCTRL by name). Most of
   `pi_firmware.py` goes.
3. **`platform_tildagon.py`. Done 2026-11-21 (build 103), tested OK on the badge.** LEDs (`tildagonos`, pattern disable / enable), tilt (`imu`),
   `TextDialog` (registered to the loader host), hexpansion keyboard detection, `settings`
   (badge name), the scheduler frame loop: moved out of `ace.py`, not rewritten. `ace.py` loses
   its firmware imports; `app.py` (the loader) still imports module by module.
4. **Layout object for drawing. Started 2026-11-21 (build 105: `layout.py`, `config.layout`,
   the Pi's `layout_pi.PiLayout` instead of its drawing hooks, `Game.stick_pitch` /
   `stick_roll` instead of wrapping `Game.step`). Still to do: `DUST_X` (the Pi sets
   `game.DUST_X`), the shared Elite dashboard (with the Tufty, step 5) and a hit signal.** Screen size and shape, view rectangle, which HUD (round badge,
   Elite dashboard), line thickness, draw distance. `draw_hud` asks the layout instead of hosts
   replacing functions. Menus and docked screens stay on the 240-unit canvas (they work centred
   on any screen). One shared Elite dashboard for the Pi and the Tufty (merge `dash_pi.py` and
   `dash_tufty.py`), a hit signal for screens with no LEDs.
5. **Move the Tufty** into `hosts/tufty/` on the shared code; its patches and vendored copy go.

Checks for every step: `tests/render.py` frames pixel-identical before and after (59 frames,
the build 96 method: render to a scratch folder, change, render, compare with PIL
`ImageChops.difference`); `python3 tests/run_all.py` (29 files); every changed badge file
compiled with the badge's mpy-cross (CLAUDE.md "Tests"); a run on the badge with Brian's OK.
Badge constraints: no per-frame dictionary lookups or new objects in the frame path (bind
methods once); the app store package gains only `platform_tildagon.py` (check `git archive`).

## Questions for Brian at the start
- Tufty first (A), or the platform layer first (B)?
- Is the Qw/ST Pad attached to the Tufty? Is the Keebdeck in use yet?
- OK to look at the Tufty over USB (read-only), then copy to it?
- What is the Debug Probe connected to (for the Tufty's RP2350, or something else)?
