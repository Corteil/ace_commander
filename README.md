# Ace Commander

A wireframe space trading and combat game for the EMF Camp Tildagon / Spaceagon badge.
Fly between the stars, trade, fight pirates and bounty hunters, dock at space stations, and
take on two missions for the Commonwealth Navy across eight galaxies. Plain MicroPython: no
C and no custom firmware.

It is a fan-made game inspired by BBC Micro Elite (1984), written from scratch, with its own
ships, galaxy, market and words. It is not official, licensed or endorsed. See
[Credits](#credits-and-original-material).

## Install

From the badge's **App store**: Games > Ace Commander.

By hand: copy the files below to `/apps/ace_commander/` on the badge (for example with
`mpremote fs cp`), then restart it:

```
__init__.py app.py ace.py bench.py briefing.py chart.py cockpit.py commander.py content.py
describe.py docked.py equipment.py find.py galaxy.py game.py letters.py market.py missions.py
original_data.py original_ships.py rules.py screens.py ships.py title.py viewer.py
tildagon.toml metadata.json
```

The game shows a loading screen for a few seconds while it starts.

## The title screen

A ship tumbles under the name. Joystick left / right picks, C chooses, F leaves the app.

- **New commander** / **Continue**: the game. A new commander has a NAME (the badge's own
  name is suggested, or Elite's Jameson if it has none: with a keyboard `Tab` fills it in),
  a level (EASY, NORMAL or HARD: it sets how many kills each rank takes, how many enemies
  attack at once, and how many hits they take) and HARDCORE (ON: the E.C.M. fires only on
  its key, missiles must be armed, docking by hand). Level and HARDCORE stay as chosen for
  that commander; the name can be changed in Options. Your
  commander is saved each time you dock, and only then. Being destroyed takes you back to
  your last save, unless you have an escape pod.
- **Combat practice**: endless waves of ships, with nothing kept. Pick the level
  (EASY, NORMAL, HARD) and HARDCORE on its page before you fly; practice's HARDCORE is
  its own, apart from your commander's. The practice ship has an E.C.M.
- **Ship viewer**: every ship in the game, turning.
- **Options**: steering (joystick or tilt), CONTROLS (flip the flight controls up / down,
  left / right or both), your commander's name, the docking style, how soon mission 1's
  target turns up, and the badge's LEDs.

## Flying

| Input | Action |
|---|---|
| Joystick | pitch and roll |
| C, or press the joystick (hold) | lasers (pulse and mining fire shots; beam and military a steady beam) |
| D | fire a missile at the boxed target (it locks after two seconds in the sights) |
| B | energy bomb, if fitted |
| F / E | speed up / slow down |
| A | the in-flight menu, which pauses the game |

The in-flight menu: **Hyperspace** (to your target, or open the local chart to pick one),
**Local chart**, **Status**, **Settings** and **Quit to title**, plus **Docking computer**
or **Galactic jump** when you have them. Joystick up / down picks, C chooses, F goes back,
A resumes. **Status** and the charts don't pause: as in Elite they replace the view of space
while the game runs on, so you can still be shot. The joystick and buttons work the screen,
and C or F goes back to space. On a chart C makes the system your target; jump with
**Hyperspace** (or `H`).

With tilt steering, tilting the badge steers and the joystick still works; a tap on D
re-zeroes the tilt and holding it fires a missile. A USB keyboard works too: `W` / `S` and
`A` / `D` (or the arrows) steer, `E` / `Q` or `+` / `-` speed up / down, `F` or space
lasers, `M` missile, `P` the menu. The number row is Elite's f0-f9: `1`-`4` front, rear,
left and right views, `5` galactic chart, `6` local chart, `7` system data, `8` market
prices, `9` status, `0` inventory (press it again to go back to space; docked, the same keys
pick the screen: `1` launches, `3` opens the market on what you carry, `0` the inventory, `-` the
Shipyard and `=` Options). `H` hyperspace, `Shift`+`H` galactic jump, `J` jump drive, `Esc` the escape pod (in flight;
back on menus), `Tab` or `Backspace` the energy bomb, `C` / `P` the docking computer on / off
(`P` is the menu otherwise).
On a status, market or chart screen only steering, speed and lasers work (and the lasers
can't hit anything), as in Elite.

The badge's LEDs: red when you are hit, your laser's colour as you fire (pulse magenta,
beam blue, military green, mining yellow), white for the energy bomb, violet for the ECM,
green in a station's safe zone, orange to red near a sun, yellow pulses while you scoop
fuel from it.

## In a star system

You arrive from hyperspace a long way out. The compass points to the station; hold speed
up at full speed for the jump drive, which works only with no ships about and outside the
station's safe zone.

- **Encounters**: pirates and bounty hunters turn up from time to time, more often in
  anarchies and feudal systems; traders and the police go about their business. Nothing
  turns up in the safe zone.
- **Legal status**: carrying contraband, stims or weapons, or destroying a police ship,
  makes you an offender or a fugitive, and the police and bounty hunters come after you.
  Each jump halves it. Firing on a trader or the station makes the station refuse you.
  A stolen ship keeps you an offender while you fly it, and the police in law-abiding
  systems may recognise it; the galactic hyperdrive leaves both behind.
- **Weapons** reach as far as Elite's: your lasers hit anything in your sights, enemy
  lasers only fire from close by, missiles fly any distance.
- **Docking**: three styles, in Settings or Options. Automatic takes you in when you reach
  the station. Assisted: line up with the slot, slow down, and a tractor beam pulls you in.
  Authentic: fly into the slot yourself, level with it and slowly. A docking computer can
  fly you in from the safe zone.
- **The sun**: fly close with fuel scoops to skim fuel, watching the cabin temperature.
- **Cargo**: destroyed ships drop canisters; scoop them (with fuel scoops) by passing over
  them. A mining laser breaks rocks into splinters you can scoop as ore.
- **Escape pods**: a badly damaged ship may bail out, leaving its hull adrift; with fuel
  scoops you can scoop the pod from below, for a tonne of slaves.
- **Witchspace**: now and then a jump goes wrong and leaves you between the stars with the
  alien Vorn.

## Docked

Screens, shown by the squares at the top: **Status**, **Inventory**, **Market**,
**Equip ship**, **Shipyard**, **Hangar**, **Galactic chart**, **Local chart**
and **System data**.
Joystick left / right (or E / B) goes round them; A launches from any screen; C on
Status opens **Options**; F goes back to Status, then to the title.

- **Inventory**: what is in the hold; C sells all of it at this station's prices.
- **Market**: joystick up / down picks a good, C buys, D sells. Prices depend on the
  system's economy: cheap food in agricultural systems, cheap machinery in industrial ones.
- **Equip ship**: fuel, missiles, lasers, a larger hold, ECM, fuel scoops, escape pod,
  energy bomb, energy unit, docking computer and galactic hyperdrive; more is on sale at
  higher tech levels. Missiles go on the ship's pylons and lasers on its laser mounts.
- **Shipyard**: buy other ships. First your own ship (D opens the **Repair Shop** to
  repaint it), then the ships for sale, one at a time (up / down for the others). C on any
  of them shows its stats: price, jump range, speed, turning, shields, hold, laser mounts,
  missile pylons and what it comes with; for one for sale, C there buys it (your ship goes
  into the hangar) and D trades yours in. F comes back.
  - Each ship flies differently: small ones are fast and nimble but fragile, big ones slow
    and tough with big holds. Jump ranges run from 5 to 10 light years; the Shuttle,
    Transporter and Worm are in-system craft that can't jump at all, and you can't end up
    with no ship that jumps.
  - Bigger ships need higher tech levels (the police Viper from 12, the navy's Constrictor
    only at 15). Pirate worlds also sell stolen ships, cheap, but a stolen ship keeps you an
    offender and the police may spot it; a pirate world's Repair Shop sells a new
    transponder (D) that makes it clean.
  - A new ship comes with its standard weapons and a full tank; cargo moves across, and
    what doesn't fit is sold here for its value. Each ship keeps its own equipment and fuel.
- **Hangar**: the ships you own, one at a time, each turning with its fit-out listed. C
  flies the picked one, D sells it. In Hardcore Mode a ship stays at the station where
  you left it.
- **Galactic chart search**: B finds a system by name (docked, after C): type it on a
  keyboard, with the best match suggested and a list to pick from, or use the badge's own
  text entry without one. Also in flight, on the Galactic chart.
- **Charts**: press C to move the cursor (F gives the joystick back to the screens); C picks
  a hyperspace target, D shows a system's data.
- **System data**: the system's government, economy, tech level, population and a line
  about it.

## Missions

Once you have enough kills, docking in the first or second galaxy brings an incoming
message from the Navy: a prototype ship has been stolen. Stations along its trail have
heard things (System data, while you hunt it). Only a military laser hurts it, and its ECM
stops missiles. Later, in the third galaxy, the Navy has a second job for you, and the Vorn
won't like it. The messages call you by your commander's name.

## Your own copy of Elite's data (optional)

The game has its own ships and galaxy. If you have your own copy of the Elite source, you
can make Elite's ships, galaxy, market, texts and missions for your own use:

```
python3 tools/import_ships.py path/to/elite-source-code-bbc-micro-disc
python3 tools/import_galaxy.py path/to/elite-source-code-bbc-micro-disc
```

for example from [Mark Moxon's annotated source](https://github.com/markmoxon/elite-source-code-bbc-micro-disc).
Copy the resulting `ship_data.py` and `game_data.py` to the badge with the rest, and choose
**Options > DATA: ELITE** (it applies from the next start). Each data set keeps its own
commander (`commander.json` for the game's own, `commander_elite.json` for Elite's). These
two files are derived from Elite (c) Acornsoft 1984, whose source has no licence: they are
git-ignored and must not be published or put in the app store.

## For developers

- `python3 tests/run_all.py` runs the PC test suite, with stand-ins for the badge firmware
  (`tests/badge_stubs.py`). The repo folder must be called `ace_commander`.
  `tests/test_install.py` checks the app as the app store installs it.
- `tools/make_original_ships.py` makes `original_ships.py` from the ship designs, using
  `tools/shipmaker.py` (convex hulls from corner points, explicit faces, convex parts for
  shapes like the ring station).
- `original_data.py` holds the game's own galaxy, goods, equipment, words and missions;
  `content.py` picks it or Elite's at start-up.
- A file called `debug.txt` in the app's folder on the badge shows a **Debug** page of
  cheats (at the end of Settings and Options, and on the in-flight menu). It is always shown
  on a PC.
- Release tarballs leave out tests, tools and notes (`.gitattributes`), so only the app goes
  onto the badge.
- `CLAUDE.md` has project notes: firmware facts, measurements and the build history.
  `DESIGN.md` has the design.

## Credits and original material

Elite was written by David Braben and Ian Bell and published by Acornsoft in 1984. This
project is a fan-made game inspired by it, for the EMF Camp badge.

- **Code**: written from scratch in MicroPython. It contains no original Elite code and
  nothing translated from it.
- **Ideas re-implemented in new code**: the hidden-line rule, steering by rotating the
  universe around the player, the radar with height sticks, galaxies worked out from seed
  numbers, and the shape of the two missions. One message, "RIGHT ON COMMANDER!", is a line
  from the original.
- **Ships, galaxy, market and words**: the game's own (`original_ships.py`,
  `original_data.py`), designed for Ace Commander.
- **Badge firmware**: `tests/badge_stubs.py` mirrors the button-matching rules of the
  [badge firmware](https://github.com/emfcamp/badge-2024-software) so the tests behave like
  the badge.

The game was first called Elite and was renamed Ace Commander to keep clear of the
original's name.

## Licence

MIT, see [LICENSE](LICENSE). The licence covers this repository's own work, not the
optional Elite-derived files you make yourself.
