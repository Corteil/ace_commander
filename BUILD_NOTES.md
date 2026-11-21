# Ace Commander: build notes

Moved out of CLAUDE.md on 2026-11-16 so it is not loaded into every session. Read the
relevant part before changing a feature or chasing speed.

## Speed: what was measured on the badge

Speed test (build 10), ms per frame / of which drawing calls:
nothing 73 / 0, clear 80 / 7, 60 short lines 90 / 28, 60 thin lines 90 / 24,
20 long lines 87 / 18, 60 dots 79 / 8.5, 8 bars 79 / 7, 1 text 79 / 12, 6 texts 98 / 33.

So: a filled rectangle is about 0.03 ms, a line about 0.35 ms whatever its length or width,
a piece of text about 4 ms, a full clear about 7 ms.

Flight frame time, with about 11 objects:

| Build | Frame | What changed |
|---|---|---|
| 5-9 | 100-144 ms | first version |
| 11 | 130 ms | HUD rebuilt from rectangles (HUD 50 -> 5 ms), mid-distance ships as markers, 50 ms sleep skipped |
| 12 | 50-70 ms | event-driven input (`Pad`) |

Build 12 `PERF` lines: frame 65, update 15 (rules 14), draw 16.5, objs 11-12, fast 1. With
1-2 objects: frame about 48. So about 33 ms per frame is outside the app (sending the frame
to the screen plus the badge's own tasks) and looks fixed.

**The hitch is garbage collection (build 14, 2026-11-13, firmware v2.2.1-rc1 + PRs).** Build
14 forces no collection and lists the frames that ran 25 ms over the window's average:

| Objects | Average frame | Slow frames per 60 | Each one is over by | Time lost |
|---|---|---|---|---|
| 1-3 | 41 ms | 2 | 60 ms | 5% |
| 5-9 | 49 ms | 4.6 | 60 ms | 9% |
| 10-12 | 55 ms | 6.2 | 60 ms | 11% |

The slow frames are all the same size and their number follows the object count, and
`gc.mem_alloc()` saw-tooths between about 260 KB (live data) and 500 KB. So the badge collects
each time roughly 240 KB of garbage has built up: about 25 KB of garbage a frame with 12
objects. A forced `gc.collect()` took 41 ms in build 13. `gc.threshold()` is -1; the heap is
about 500 KB and `gc.mem_free()` counts memory the heap could still grow into, so "1.5 MB
free" does not mean collections are rare. `gc.mem_alloc()` itself takes 15 ms.

Brian could not feel the hitch in build 14 (he could with build 13's forced collection on
top). So this is a frame-rate cost of up to 11%, not a visible stutter.

**Build 16 in a real flight (2026-11-13, 66 windows):**

| Objects | Average frame | Slow frames per 60 | Each one is over by | Time lost |
|---|---|---|---|---|
| 1-3 | 38 ms | 0.7 | 71 ms | 2% |
| 5-9 | 46 ms | 2.5 | 66 ms | 6% |
| 10+ | 50 ms | 3.3 | 65 ms | 7% |

So collections are about half as frequent as in build 14 and the average frame is 3 to 5 ms
shorter, for the changes below.

**Where the garbage comes from (build 16, measured on the badge).** Every float result on
this port is a new 16-byte heap object; small whole numbers are free. To measure a function,
collect, `gc.disable()`, call it a few times, read `gc.mem_alloc()`, `gc.enable()`. Without
the disable a collection runs part-way and the figure comes out far too small (this fooled
one measurement). With 12 objects close enough to be wireframes, bytes per frame:

| Part | Build 15 | Build 16 | What changed |
|---|---|---|---|
| `cockpit.draw_world` | 28,000 | 700 | vertex, dust and explosion maths in whole numbers; screen positions in whole pixels |
| `cockpit.draw_hud` | 3,600 | 750 | radar blips in whole numbers |
| `Game._rotate` (turning) | 12,500 | 5,300 | positions in quarter units, directions times 16384; dust and explosion dots are whole numbers |
| `Game._think` | 13,400 | 6,400 | a ship re-plans on one frame in three (`THINK_EVERY`), staggered; it moves every frame |
| Whole frame, turning | about 59,000 | about 15,000 | |

Side effects: wireframes land on whole pixels (within a pixel of before); directions drift
by up to 0.35% in the tests, and rocks and canisters are squared up again in turn. Drawing
also got about 25% quicker. A REPL harness on a freshly booted badge has a small heap and
collects every few frames whatever you do, so judge the result from `slow` in the PERF lines
of a real flight, not from a harness.

Measured on the badge in build 15: the title screen takes about 29 ms to draw (clear 7,
133 title rectangles 3.5, the one menu text 9.6, the ship the rest). Filling each rectangle
by itself is faster than one fill for all of them (3.5 against 7.7 ms). Flight averaged
51 ms a frame over five minutes.

## Build history (builds 13 to 59)

This was the "Next steps" list in CLAUDE.md. Older entries say `app.py` / `app._dock` for
what is now `ace.py` (renamed in build 50).

1. Done: builds 13 and 14 were run and read; see above.
2. Done in build 16: float garbage cut by about three quarters (table above). What is left
   is mostly `_turn` / `_ortho` on the frames a ship re-plans, and storing results back as
   floats in `_rotate`. Going further means keeping object state in whole numbers.
3. Rules cost about 1.2 ms per object. Build 13 skips rotation maths when not turning;
   check what that saved.
4. Then gameplay: balance has only been judged by a crude autopilot in `tests/test_game.py`.
5. `DESIGN.md` has the rest of the game in phases, with all 11 decisions made. **Phase 1 is
   built (build 15) and Brian played it on the badge on 2026-11-13: title screen, new
   commander, rank messages, status, save and continue, and tap / hold D all worked.**
   **Phase 2, first part, is build 20 (2026-11-13): a commander is at a star system with
   fuel; LOCAL CHART in the in-flight menu picks a target; `Game.start_jump()` counts down
   5 s, clears the objects and sets `jumped`; `app._arrive` moves the commander, takes the
   fuel and saves.** Run over the REPL on the badge (not yet played by hand): making the
   galaxy 290 ms once, opening the chart 185 ms the first time, drawing it 14 ms, a change
   of selected system 28 ms (`Galaxy.system` twists the seeds from the start), the arrival
   streaks 11 ms.
   **Build 21 adds arriving docked.** After a jump `Game.arriving` is the number of ships
   to destroy (`max_hostile` for the level); when it reaches 0 no more come, and once none
   are left `dock_t` counts `DOCK_TIME` down and `Game.docked` is set. `app._dock` fills the
   tank (free until there is money to make), saves and shows mode `docked`. CONTINUE and
   NEW COMMANDER go to `docked` too, unless a flight was left part-way; every launch is a
   fresh `Game.reset()`. GAME OVER + C docks a commander where they last arrived. Brian
   asked for REFILL FUEL to stay on the DEBUG page; DOCK NOW is there too.
   **Build 22 finishes phase 2:** docked screens as tabs (`docked.Docked`; joystick
   changes tab, on charts E / B do and C sets `app.target`), the galactic chart
   (`chart.GalChart`), system data, a JUMP: name line in the in-flight menu when the target
   is in range, and a hexagon launch tunnel (`cockpit.draw_tunnel`, mode `launch`,
   `LAUNCH_TIME`). `Galaxy` now caches every system's seeds (1.5 KB), so `system()` no
   longer twists from the start. Measured over the REPL on the badge: Status and System
   data take about 90 ms to draw (all text), the local chart 26 ms, the galactic chart 35 ms
   to draw and 2 to 4 ms per cursor move (52 ms before its search used whole numbers), the
   tunnel 3 to 55 ms a frame. Build 23 (Brian's request): each station has its
   government's colour (`cockpit.station_colour`, eight, warm for anarchy to cool for
   corporate state, no red or white), used for the tunnel's mouth, the DOCKED label, the
   government's name and the LEDs, which pulse per ring (`cockpit.tunnel_glow`), flash full at
   the mouth and fade over the first half second of flight (`app.glow`). Left out: the description sentence ("goat soup"), which
   needs the original's text tables in `game_data.py`.
   **Build 26 starts phase 3: the star system** (2026-11-14). `Game.space` is a `Space`
   (planet and sun as centre + radius, the station an `Obj` of kind "station") for career
   flights; combat practice has none and keeps the waves. They are kept out of `Game.objs`
   and turned in floats (`_rot3`), because their distances (up to about 10^6) are beyond the
   cheap whole numbers `_rotate` uses. `app._enter_space` calls `Game.enter(radius_km,
   station, "launch" / "arrive", government)` on every fresh launch and on arriving.
   Arriving replaces build 21's "clear the ships and you are docked": the first group is
   `pending = max_hostile`, then `_encounters` sends a group every `ENCOUNTER` seconds (build 32 replaced both: see below),
   none in the safe zone. Reaching `DOCK_DIST` of the station sets `Game.docked`
   (docking option C); hitting the planet or sun is `_hurt(1e6)`. The jump drive
   (`JUMP_K`) needs speed up held at full speed, no ship or missile within radar range, and
   being outside the safe zone. New DEBUG cheat: TO THE STATION (`Game.to_station`). Build 31
   adds RELEASE CANISTER (`Game.release_canister`: one 700 ahead, drifting in to be
   scooped); build 32 made the DEBUG page a looping list (see below).
   The speed test has three circle tests. **Measured over the REPL on the badge (real ctx,
   not yet played by hand):** filled disc r20 1.3 ms, r100 7.2 ms; circle outline r20
   2.6 ms, r80 6.2 ms, and 4 to 5 ms for a big one whose edge crosses the screen. Cockpit
   draw (world + HUD): open space with nothing in it 10.3 ms; launch view (planet r about
   70) 17.6; arrived (small planet, station a dot) 14.1; station at 2500 19.4, at 900 21.1.
   Rules per step while turning: 1.05 ms / 480 bytes in open space, 1.9 ms / 2.6 KB in a
   system (the float turning of three bodies and the station's directions); with the jump
   drive on 1.1 ms / 1.1 KB. So the planet outline is the main new cost, up to about 7 ms a
   frame when big; a ring of rectangles would be cheaper if that matters. With the jump
   drive on the stardust is drawn as streaks (`STREAK_MIN`, two steps of `Game.fwd` long);
   Brian asked for them and confirmed they look good (2026-11-14). A real flight in a
   system that day: 36-38 ms a frame with no ships (draw 12.5-14), 38-47 ms with 1-4, one
   or two collections per 60 frames as before, no errors.
   **Build 27: docking by hand** (2026-11-14). `Game.docking` ("A" / "B" / "C", from
   `Commander.docking` via `Game.set_docking` in `app._enter_space`; `Game()` defaults to C
   so old tests keep working). The pause page has DOCKING: MANUAL / ASSISTED / AUTOMATIC
   (C or right goes on, left back; saved straight away). `Game._approach` runs within
   `CAPTURE_DIST` for A and B: you touch the station at `bp.front + PLAYER_R` from its
   centre (`Blueprint.front` is the slot face: 160 Coriolis, 196 Dodo). A docks if you are
   in front of the slot (`SLOT_CONE_A`, 22 deg), flying into it (`HEAD_A`, 26 deg), the slot
   level on screen (`LEVEL_A`, |station roof . screen x| >= cos 30 deg, either way up; the
   station spins at `STATION_SPIN` so you roll with it) and at `DOCK_SPEED` (20) or less. B:
   in the cone (`SLOT_CONE_B`), heading in (`HEAD_B`) and slow, the tractor beam takes over
   ("TRACTOR BEAM"): the station turns its slot to you (`PULL_TURN`) and closes at `PULL`;
   speeding up past `DOCK_SPEED` loses it ("TOO FAST"). Anything else is a crash
   ("STATION HIT" / "TOO FAST"): `STATION_HIT` + 1.5 x speed damage, speed 0, bounced
   `BOUNCE` out (`Game._shift` moves the whole system), 1 s before another hit counts.
   TO THE STATION now also turns the slot to face you (`to_station(dist, slot=True)`).
   Tested on the PC only (tests/test_game.py "docking by hand"; shot 4m_slot_level.png
   shows the slot as a level letterbox when A's roll rule is met).
   **Build 28: the docking scene** (Brian's request after trying build 27, which he said
   ran fine). Flying in (any style) sets app mode `docking` for `DOCK_TIME` (3 s, C skips):
   the launch tunnel the other way round (`cockpit.draw_tunnel(..., inward=True)`,
   `_draw_dock`): the mouth in the station's colour starts `DOCK_START` ahead, the rings
   come at you more and more slowly, and you stop with the bay doors (a dim filled hexagon)
   `DOCK_END` ahead. The LEDs (`cockpit.dock_glow`) rise as the mouth nears, flash going
   through it, pulse for each ring; then `_dock()` as before. DOCK NOW and GAME OVER + C
   skip the scene. Measured on the badge (real ctx, REPL): 14-19 ms a frame to draw.
   **Build 29: every station's tunnel is different** (Brian's requests, after trying
   several looks). `cockpit.Tunnel(system, station)`: every ring is the station's slot, a
   level letterbox that doesn't turn (`SLOT_ASPECT`: Coriolis 3:1, Dodo 2:1, from their
   slot vertices), so the tunnel is four corners with straight long edges. The gaps between
   rings follow one of `TUNNEL_SPACINGS` (even, widening, narrowing, pairs, threes, picked
   from the system's number). At the end the tunnel opens into the docking bay: the same
   shape `BAY_SCALE` (3) times bigger and `BAY_DEPTH` deep, its doors on the far wall
   filled dimly in the station's colour; docking stops at the way into the bay (`DOCK_END`).
   **Ships are parked in the bay**, a fresh random set on each launch and docking
   (`app._pick_tunnel`): `game.parked_ships(gov, tech)` draws 1 to 4 names from pools that
   suit the system (pirate craft where the government is weak, traders, police Vipers where
   it is strong, shuttles below tech 5, Asp / Fer de Lance from tech 10), and
   `Tunnel.park` keeps only ships that fit through the slot at `SHIP_SCALE` (150 ship units
   to a tunnel unit; e.g. the Boa is too tall for a Coriolis but fits a Dodo), one to each
   of `PARK_SPOTS`, resting on the floor, facing in or out a little askew. Until you are in
   the bay only ships seen through its opening are drawn. Launch and docking at one
   station use the same tunnel; the LED pulses follow the real spacing (`_pulse`). Tried
   and dropped at Brian's request: morphing between shapes, hexagon doors, a spinning
   tunnel. At the end of docking the bay stays in view for a random `DOCK_HOLD` (1-2 s).
   `tools/tunnel_sheet.py` draws six stations side by side into
   `tests/shots/tunnels.png`. Measured on the badge (REPL, real ctx): making a tunnel and
   parking 4 ships about 4 ms; drawing 16-25 ms a frame with 4 parked.
   **The station hides the planet behind it** (Brian's request): in `_draw_space`, when
   the station is nearer than the planet's centre and its screen size overlaps the
   planet's outline, `draw_ship(..., solid=True)` fills the station's outline black
   (`_fill_hull`, the convex hull of its projected vertices) before its edges. Costs about
   2 ms on the badge, only while they overlap. Ships don't hide the planet (not asked).
   **Build 30: the market** (phase 3). `tools/import_galaxy.py` now also reads the goods
   table (QQ23: name from each line's comment, base price, economic factor, unit, base
   quantity, mask) into `game_data.GOODS`. `market.py` works prices and stock out the way
   the original does (read from TT151 and GVL in the source, written afresh): price in
   tenths = 4 x ((base + (r AND mask) + economy x factor) mod 256); stock = (quantity +
   (r AND mask) - economy x factor) mod 256, none if >= 128, then mod 64; no alien items.
   r is a random byte picked when a commander first docks in a system after arriving
   (`app._arrive` clears `Commander.market`, `app._dock` makes a new one with
   `market.new`), saved with the commander, so the stock you change stays until you jump.
   Prices don't change with trading. The hold takes 20 t of the first 13 goods; gold,
   platinum, gem-stones and alien items don't use it, 200 of each at most. The commander
   now keeps `cash` in tenths of a credit (saved as `credits` for old saves), `cargo` (17)
   and `hold`; save version 3. Market tab (second): joystick up / down picks a good (6
   rows, scrolls), C buys one and D sells one, all repeating when held (`app._repeat`,
   `REPEAT_WAIT`, `REPEAT_EVERY`); the reason a trade fails shows for 1.5 s. Trades are
   saved on launching and on going to the title. `cockpit.text` takes `align` (-1 left,
   1 right). Measured on the badge (REPL, real ctx): making the market 40 ms, drawing the
   tab 115 ms (all text, every frame, so held buttons repeat about 6 times a second), a
   buy 0.7 ms. Fuel is still free on docking (the equipment screen comes in phase 4).
   Illegal goods (slaves, narcotics, firearms) are sold like the rest until legal status
   exists (phase 5).
   **Build 31: scooped cargo into the hold, and green LEDs in the safe zone.** In a career
   flight `Game.scoop` is `app._scoop` (`market.scoop`): a scooped canister holds a random
   one of the first `SCOOP_GOODS` (8) goods, food to computers, as in the original (read
   from the main flight loop, part 8); it goes into the commander's hold and its name is
   shown, or with no room it is lost ("HOLD FULL", a small explosion, no damage). In
   combat practice (Brian's request) a canister is a pick-up instead (`Game._pickup`):
   it recharges the shields to full, and with chance `PICKUP_MISSILE` (0.5) holds a
   missile too, up to `MAX_MISSILES` (4). Scooping is still free and from any side: needing fuel
   scoops and the canister below you come with the equipment (phase 4). Being destroyed
   loses the cargo (cleared before the game-over save). The in-flight status page shows
   the hold. In the station's safe zone (`Space.safe`) the LEDs are steady green
   (`SAFE_GREEN`, 60 of 255); a hit's red flash and the station colour fading after launch
   come first, and paused they are off.
   **Build 32: bounties.** `Game._kill` adds the blueprint's `bounty` (tenths of a credit,
   from the ship data; asteroids and boulders have small ones) to `Game.bounty`, and
   `app._bank` pays it into `Commander.cash` as it banks kills (`banked_cash`), showing
   the new cash for 1.5 s as the original does (a new rank shows instead, and nothing
   overwrites the hyperspace countdown). The original pays only when no other message is
   showing; this pays always. Combat practice pays nothing. The in-flight status page
   shows hold and cash. Tests read bounty values from the ship data rather than writing
   Elite's numbers into the public repo.
   **Also in build 32, encounters and the safe zone as in Elite** (Brian's request; read
   from the main game loop, parts 3 and 4, and the space station spawning in the main
   flight loop). The safe zone is `SAFE_K` (2) planet radii round the station
   (`Space.safe_r`; Elite's is a box of 2 radii, all its planets one size), replacing the
   fixed `SAFE_DIST`. Outside it, once the last ships have gone, every `ENCOUNTER_EVERY`
   (20) s a roll (`Game._encounter`, was `_roll`): certain in an anarchy, else `PIRATE_ROLL` (47%) and a
   number 0-7 at least the government, so a corporate state about 6%. Then a lone bounty
   hunter (`HUNTER_CHANCE`, 39%: `HUNTERS`) or a pack of 1 to `PACK_MOST` (4) `PIRATES`,
   capped by the level's `max_hostile`, small types more likely (two random bytes ANDed);
   the next rolls are skipped, one per extra ship (Elite's EV). Differences: Elite rolls
   whatever is around; this waits for the last group to go, because every ship here is
   hostile (no traders or police until phase 5). Arriving from hyperspace brings an ambush
   of `max_hostile` pirates only in an anarchy or feudal system (`AMBUSH_GOV`). Measured
   in the PC test: 10 minutes outside the safe zone, 23 pirates in an anarchy, 4 in a
   corporate state.
   **Waves are for combat practice only** (Brian's request): in a commander's flight no
   "WAVE" message, no wave and score on the HUD, no free missile per wave, no NEXT WAVE
   cheat.
   **DEBUG page and bay windows** (build 32, Brian's requests): the frame time counter is
   a DEBUG switch, FRAME TIME: ON / OFF (`app.show_ms`, starting from `SHOW_FRAME_TIME`).
   The DEBUG page shows `DEBUG_ROWS` (7) lines in size 14, the chosen one in the middle and
   the list going round above and below it. The docking bay has `BAY_WINDOWS` (3) lit
   windows high on each side wall, white frames only (`cockpit._draw_windows`, `WINDOW_Y`,
   `WINDOW_LEN`, `WINDOW_FRAME`), drawn behind the parked ships and, from the tunnel,
   only when seen through the bay's opening. Bay scene on the badge: 17-30 ms a frame.
   **Build 33 starts phase 4: the Equip ship tab** (third, after Market). `import_galaxy.py`
   also reads the equipment price list (PRXS: name from each line's comment, price in
   tenths) into `game_data.EQUIPMENT`. `equipment.py` (read from EQSHP, written afresh):
   a station sells the first (shown tech level + 2) items, all 14 from tech 10; fuel is
   2 Cr a light year and fills the tank; missiles up to 4; one of everything else ("ALREADY
   FITTED"); a new laser refunds the old one's price. The commander keeps `missiles`
   (a new one starts with 3, as in the original), `laser` and `extras` (names from
   `equipment.EXTRAS`); save version 4. **Docking no longer refuels for free** (unless
   game_data.py has no equipment). Each fresh career flight is fitted from the commander
   (`app._fit`): missiles (fired ones are gone: `_bank` copies them back), laser
   (`Game.set_laser`, `game.LASERS`: beam twice the rate and hotter, military 1.5x the
   damage too, mining = pulse until mining exists), the energy unit (`ENERGY_UNIT`, twice
   the recharge) and fuel scoops: in a career flight a canister is scooped only with
   scoops and passing below you (`o.y < 0`), as in the original, else it is hit; combat
   practice always scoops. Shown but not sold yet ("soon", `equipment.SOON`): ECM, escape
   pod, energy bomb, docking computer, galactic hyperdrive, mining laser. Joystick picks,
   C buys. The tab draws in about 109 ms on the badge.
   **DEBUG additions** (Brian's requests): +1000 CR (career), and SHIP CONFIG, a page that
   changes the ship at once, in the flight and for the commander: laser (C cycles), missiles
   (0-4), energy unit; in a career also cargo bay (20 / 35 t) and fuel scoops. Add each
   new item there as its effect is built.
   **Being destroyed works as in the original** (build 35, Brian's choice on 2026-11-15,
   replacing build 34's "start again at the last station, keeping everything but the
   cargo"). The commander is saved **only when docked** (`app._write`: on docking, on
   leaving the docked screens for the title or a launch, and a new commander), as the
   original could save only at a station; arriving from hyperspace and quitting a flight to
   the title no longer save. `app.saved` keeps a JSON copy of the last save. On game over
   in a career `app._restore` puts the commander back to that copy, so the kills, bounties,
   cargo, missiles used, fuel and system since the last dock are all lost, and sets
   `banked` / `banked_cash` and `Game.missiles` so the dead flight banks nothing more. C
   ("back to last save") docks there. Changing the docking style mid-flight writes only
   that setting into the save (`app._write_setting`). A badge restart mid-flight also goes
   back to the last dock. Starting a NEW COMMANDER no longer banks a flight the last
   commander left part-way (it set `career` False first). Still possible: quit a flight to
   the title, play combat practice, then CONTINUE docks the commander wherever they were,
   with the flight's progress. `Commander.docked_at` is still saved but no longer used.
   The escape pod (build 36) saves you from this: per the disc source's ESCAPE routine
   it loses the cargo, uses up the pod, gives a full tank and docks you, and docking saves
   the rest of the flight (kills, bounties). Legal status doesn't exist yet; what the
   original does to credits and other equipment is not checked yet.
   **Build 34: sun skimming** (Brian's request; main flight loop part 15). `Game._sun`:
   cabin temperature = 285 - `SUN_HEAT` x (distance / sun radius)^2, at least 30; at
   `SCOOP_TEMP` (224) or more with fuel scoops, every `SUN_CHECK` s `Game.refuel`
   (`app._refuel`) takes speed // 8 tenths of a LY ("FUEL SCOOPS ON"). CT and AL gauges
   at the top of the HUD only near the sun (`cockpit._sun_gauges`), with a FU fuel bar
   under them (`Game.fuel`, copied from the commander; red below a quarter); LEDs orange to red
   with heat (16 steps), yellow pulses while scooping. The jump drive is off near the
   sun. DEBUG: TO THE SUN (`Game.to_sun`) and FUEL TO 1/4 (career: 1.7 LY). Hyperspace has no distance limit, as in
   Elite (only not docked or mid-countdown). Then (Brian: the gauges seemed stuck, as
   the sun was twice the planet's size and crossing its heat took a minute): the sun is
   now the planet's size (`SUN_SIZE` 1.0, as in Elite, whose planet and sun share one
   radius); AL is full where the cabin starts to warm and empty at the surface, worked
   out from `SUN_HEAT` so it fits every sun (`cockpit.SUN_GAUGE_ALT`); CT is green when
   cool, through yellow and orange to red at the scooping band (`ct_colour`,
   `CT_COLOURS`); TO THE SUN starts at the edge of the heat heading in (`to_sun(1.15,
   1.6)`: about 18 s at full speed to the band). CT is Elite's cabin temperature, a raw
   0-255 value with no units (30 deep space, 255 fatal in the original).
   Then (Brian): a planet behind the sun was drawn as a black disc over it, because the
   "planet in front of the sun" fill never checked which was nearer; `_draw_space` now
   draws whichever is nearer last (the sun hides a planet behind it). Each system's sun
   has one of `cockpit.SUN_COLOURS` (red, orange, yellow, white, blue-white), from the
   system's number (`Space.sun`, `Game.enter(..., sun)`). Messages and the sun gauges
   have a dark band behind them so they read against the sun.
   Each system's planet is a filled disc with a brighter outline, in one of
   `cockpit.PLANET_COLOURS` (ocean blue, green, desert, red, grey, purple, teal; `Space.planet`,
   `Game.enter(..., planet)`), so a planet in front of the sun hides it in its own colour.
   The stardust is now drawn after the planet and sun (it is close to you). Measured on
   the badge: draw_world 13 ms with a small planet, 19 ms in the launch view, 25 ms with
   a planet of radius about 200 px.
   **Build 36: every item of equipment works** (`equipment.SOON` is empty; 2026-11-15).
   ECM (`Game.ecm`): an enemy missile within `ECM_RANGE` (2500) makes `_ecm` destroy every
   enemy missile, costs `ECM_COST` (10) shield, says "ECM" and flashes the LEDs violet.
   Energy bomb (`Game.bombs`, B in flight): `energy_bomb()` kills every ship, missile and
   rock within `BOMB_RANGE` (canisters are spared), counts the kills, flashes the screen and
   LEDs white, and the app takes "bomb" off the commander. Escape pod (`Game.pod`): dying
   sets `Game.ejected` ("ESCAPE POD" box instead of GAME OVER); the app empties the hold,
   removes the pod, fills the tank (as in the original) and after `EJECT_TIME` (3 s, C skips)
   docks you at the system you were in, and that docking saves the flight's kills and
   bounties (without a pod, `_restore` goes back to the last save as in build 35). An
   energy bomb or galactic hyperdrive used in a flight that ends in death without a pod
   comes back with the last save, as everything else does. Docking computer (`Game.computer`):
   in-flight menu DOCKING COMPUTER while in the safe zone, DOCK COMPUTER OFF while on;
   `Game._autopilot` rolls the station over the crosshair, pitches onto it, flies at full
   speed (8x beyond `AUTO_FAST`) and slows in `AUTO_SLOW`, and docks you within the
   station's front + 340 whatever the docking style; stick, throttle, fire or missile
   switch it off. 12 to 17 s from anywhere in the safe zone; on the badge 1.9 ms a step.
   Galactic hyperdrive: in-flight menu GALACTIC JUMP, the usual countdown with
   `jump_to = ("galaxy", 0)`; `_arrive` adds 1 to `Commander.galaxy` (0-7, saved), uses
   the drive up, remakes `app.galaxy` from `galaxy.seeds_for` (each seed byte rotated left,
   as in the original; 62 ms on the badge) and arrives at the system nearest (96, 96)
   (`GAL_ARRIVE`), no fuel used, `docked_at` cleared. Mining laser: a rock it destroys
   breaks into SPLINTERs (asteroid 2-3, boulder 1-2; `Game._splinters`), "can" objects with
   `Obj.good = MINERALS`, which scoop as minerals; its damage is 15 (pulse 12). SHIP CONFIG
   has a switch for each.
   **Build 37 (Brian's requests, 2026-11-15):** the escape pod's screen times out after
   `EJECT_TIME` into the docking scene (`app._fly_in`, shared with flying in). The docking
   computer lines up before going in, as the original's does (`Game._autopilot`,
   `auto_phase`): 0, from beside or behind the station, out to a point to the side of it; 1,
   out to `AUTO_LINE` (2500) + front straight out from the slot; 2, turn onto the station
   and fly in at 0.7 x `DOCK_SPEED`, rolling to match the slot (`auto_level`) within
   `AUTO_LEVEL` (1000) of it; it docks only in phase 2, within front + 100. 60 random starts in
   the PC sim all arrive inside docking A's cone and level, never within 400 of the back of
   the station; the worst took 29 s. On the badge, from behind with the slot facing away:
   23.5 s game time, 3.1 ms a step. DEBUG has LEVEL (EASY / NORMAL / HARD, C goes round):
   the enemies at once and, in a career, the commander's level and rank thresholds, written
   into the save (`_write_setting`) so a death doesn't undo it.
   **Build 38 (Brian, 2026-11-15):** the docking computer said OFF as soon as it was chosen,
   because the C that chose it was still held on the next frames and counted as firing.
   Now only a fresh press of a flight control (`app._took_controls`: joystick, C, D, E, F,
   keys; never tilt) hands back control. Its state (`autodock`, `auto_phase`,
   `auto_level`) is cleared on docking (`app._dock`, so DOCK NOW too), on a hyperspace jump
   and on entering a system. While it flies, the view is from behind and above your ship
   (`cockpit.draw_world`: everything is shifted by `CHASE_UP` / `CHASE_BACK` for the draw and
   back, and a Cobra Mk III is drawn in cyan, banking with `Game.auto_stick`); no crosshair.
   **Build 39 (Brian):** the lasers fired on leaving a menu and on launching, for the same
   reason (C still held). `app.fire_lock` is set by `_resume` and `_start_flight`; while it
   is set, fire is ignored until C (and F / SPACE on a keyboard) is let go.
   Copying to the badge: twice on 2026-11-15 the badge rebooted part-way through copying
   `app.py`; `mpremote connect PORT resume fs cp ...` (no soft reset first) then worked.
   **Build 40 (Brian):** your ship is shown in the launch and docking tunnels, seen from
   behind: `Tunnel.fly(bp)` (set in `app._pick_tunnel`, a Cobra Mk III if it fits the slot)
   and `cockpit._draw_me`, `ME_AHEAD` (2.0) tunnel units ahead of the view, `ME_LOW` below
   the slot's middle, cyan, filled black inside. Docking ends with it in the bay between the
   parked ships. At 1.4 ahead it looked wider than the tunnel further on.
   **Build 41 (Brian):** take-off and landing in the tunnel scenes: on launch your ship
   rises off the bay floor (where the parked ships stand) over the first `ME_LIFT` of the
   scene while the view closes in, then flies out; on docking it settles onto the floor
   over the last `ME_LAND` (`cockpit._draw_me(ctx, tun, ahead, down)`, `_ease`). A **Repair
   Shop** docked tab (after Equip ship) repaints your ship: `cockpit.SHIP_COLOURS` (8),
   `docked.PAINT_PRICE` 10.0 Cr, saved as `Commander.colour`, used in the tunnels
   (`Tunnel.fly(bp, rgb)`) and the docking computer's view (`Game.ship_rgb`). Brian asked
   for it to be optional for now: shown only when DEBUG's REPAIR SHOP is ON
   (`app.repair_shop`, not saved, applies from the next docking). Ship types are written
   up as a future phase 6 extra in `DESIGN.md`, not built.
   **Build 42 starts phase 5: traders, police and legal status** (2026-11-15; Brian had
   play-tested every build to 41 and was happy). `Game.legal` 0-255 (the original's FIST;
   `legal_name`: CLEAN 0, OFFENDER 1-49, FUGITIVE 50+), saved as `Commander.legal`, copied
   game to commander in `app._bank`, set from it in `_fit`. Launching with illegal goods
   (`ILLEGAL`: slaves and narcotics 2 a tonne, firearms 1) raises it to at least their
   weight (`Game.illegal_cargo`). The first hit on a trader adds `HIT_TRADER` (16), killing
   one `KILL_TRADER` (16) more; firing on the police or the station (`_hit_station`: a shot
   that hits nothing else with the station in the crosshair) makes you a fugitive
   (`_crime`, `_provoke`). Each jump halves it (`app._arrive`); the escape pod clears it;
   dying without one goes back to the saved value. Ships have `Obj.role` ("pirate",
   "trader", "police") and two new states, "trade" and "patrol", that leave you alone;
   only "attack" / "break" count as hostile for encounters. `Game._traffic` (called from
   `_encounters` before the safe-zone check, so in the safe zone too): every
   `TRADER_EVERY` (12 s), with fewer than 2 traders, one of `TRADERS` (Cobra Mk III,
   Python, Boa, Anaconda, Moray) turns up with chance 0.45 (0.8 in the safe zone) facing the
   station; it steers there and docks (vanishes) on reaching it; fired on, it attacks if
   it has a laser, else flees; no bounty. Every `POLICE_EVERY` (6 s) in the safe zone,
   with fewer than 3 police: a Viper hunting you always if a fugitive, with chance
   legal / 64 if an offender, else now and then a patrol (`PATROL_CHANCE`); they launch
   out of the slot when the station is within 8,400, else arrive like other ships; a patrol
   turns on a fugitive. Radar: pirates and attackers red, police blue (`POLICE_BLUE`),
   traders white. Status pages show the legal status. DEBUG: ADD A TRADER, ADD POLICE,
   LEGAL (CLEAN / OFFENDER / FUGITIVE), career only. Tests: `tests/test_traffic.py`. On the
   badge: 6.7 ms a step with three police and a trader.
   **Build 43 (Brian):** bounty hunters (the encounter rolls' lone `HUNTERS`, now
   `Obj.role` "hunter", `group_role`) attack offenders and fugitives and fly by the clean
   (state "patrol", turning on you if you become an offender); firing on one is a crime
   like a trader (`HIT_TRADER`), killing one pays no bounty. Pirates prey on traders:
   `Game._pick_prey` picks the nearest trader that is nearer the pirate than you are and
   within `PREY_RANGE` (6,000); the pirate steers and fires at it (50% hits, the trader
   flees), and a trader it destroys spills its cargo (`_spill`) with no kill, bounty or
   crime for anyone (`_kill(..., credit=False)`). Hitting a pirate turns it back on you.
   DEBUG: ADD A HUNTER. Police numbers (Brian asked): no set number per station; at most
   `POLICE_MOST` (3) about at once, a new one possible every `POLICE_EVERY` (6 s), so
   destroyed ones are replaced without end. On the badge: 6.9 ms a step with two traders,
   a hunter and three pirates. Not built yet from phase 5: Thargoids, and legal status
   changing the market or bounties.
   **Build 44: traffic and legal status as the original** (Brian: "go fully original",
   after reading `~/Code/elite-source-code-bbc-micro-disc`, `elite-source-flight.asm`).
   This replaces the build 42/43 rules above where they differ. Legal status (FIST)
   changes only by ORing in contraband on launch (`game.bad`, `illegal_cargo`; the app
   also keeps `Game.bad` current in `_bank`), ORing in `KILL_COP` (64) for destroying a
   police ship, halving on each jump (SOLAR), and clearing with the escape pod or the
   galactic hyperdrive. Firing on a trader (innocent) or the station makes the station
   hostile (`Game.anger_station`, `Space.hostile`; ANGRY / AN2), not your record worse. A
   hostile station refuses docking, checked before anything else on touching it
   (`_refused`, ISDK check 1): at `DEATH_SPEED` (5) or more you are killed, slower a 5
   damage dent, speed 1 and a bounce; the docking computer flies you in to the same end
   (the original's goes through the same checks); it launches police after you
   (`STATION_COPS` 4 at most, `STATION_COP_CHANCE` a second; TACTICS TN5) and no shuttles,
   until you leave. Otherwise the station launches a Shuttle or Transporter now and then
   (`SHUTTLE_CHANCE` a second, one at a time, making for the planet). Outside the safe zone,
   each `ENCOUNTER_EVERY` tick (`Game._tick`, main game loop parts 2 to 4): 35/256 something
   harmless (half the time a trader, making for the station or the planet: `Obj.dest`);
   else a police Viper with chance (2 x BAD, ORed with legal status if police are about)
   / 256; then, with no police about, the pirate / hunter roll (still only with no hostile
   ships about, as before). Nothing turns up in the safe zone, and a pirate that follows
   you in becomes "patrol" for good (TN3). Police and hunters attack at `HUNT_LEGAL` (40)
   or more (TN1; Vipers are hunters in the original's flags), else patrol; firing on any
   ship makes it attack you. Bounties are every ship's blueprint bounty (the police and
   most traders: 0). Kept although not in the original, as Brian asked: pirates preying
   on traders. DEBUG: ANGER STATION.
   **Build 45 (Brian):** a hostile station's tractor beam (docking B) no longer takes hold,
   and lets go if the station turns; the docking computer won't start at a hostile station
   ("STATION HOSTILE") and switches off if it turns (not as the original, whose computer
   flew you in to a refused docking). Leaving the safe zone ends the lockdown (`_measure`):
   the original drops the station from the local bubble outside it (the sun takes its slot)
   and makes a new, friendly one on the way back in (NWSPS). Police already launched stay.
   **Build 46 (Brian):** in the docking computer's view the station is always a wireframe
   (`draw_ship` with `wire_min` 0 never falls back to a dot or marker), and never smaller
   than `CHASE_STATION_MIN` (12 px radius): a far one is drawn as if nearer along the same
   line of sight, then put back (`_draw_space(ctx, sp, wire)`). The cockpit view is as before.
   **Build 47 (Brian: a ship coming out of the station hit him on the run in):** a friendly
   station launches no shuttle while the docking computer flies or you are within
   `SLOT_CLEAR` (6,000) in front of its slot, inside `SLOT_CLEAR_CONE` of its axis
   (`Game._slot_clear`); a hostile station's police still launch. A ship that isn't
   attacking you ("trade" / "patrol") dodges sideways out of your line of travel when it is
   within `AVOID_AHEAD` (3,000) ahead and `AVOID_SIDE` of your path, or within `AVOID_DIST`
   heading your way (turning straight away put it back down your path). 40 docking-computer
   runs from random directions with a shuttle already coming out: no hits, all docked.
   **Build 48 (Brian):** the station is drawn to scale in the docking computer's view again
   (build 46's 12 px minimum is gone); it stays a wireframe at any distance, never a dot or
   marker. What launches from a station: a friendly one only Shuttles and Transporters, a
   hostile one only police Vipers, as in the disc original (TACTICS for the station).
   **Build 49: witchspace and Thargoids, and a loading screen** (2026-11-15). Loading:
   the first start showed nothing for about 10 s because MicroPython compiles every module
   from source (measured on the badge: ship_data 0.8 s, game 1.1 s, cockpit 0.65 s, app
   about 1.3 s). `loader.py` (a few KB) draws at once (0.2 s) and imports `STEPS` one at a
   time, redrawing a progress bar between them (about 6.9 s in all over the REPL), then makes
   `app.AceCommander(host=self)` and runs it. The real app sends its button handlers
   (`Pad(self.host)`), `app_is_foregrounded` and `minimise` through the host, the only object
   the scheduler knows. If a module fails to import the screen says LOAD FAILED and why.
   Witchspace (MJP, GTHG, TACTICS, read from the disc source): each normal jump has a
   `MISJUMP_ODDS` (3/256) chance (DEBUG: MIS-JUMP NEXT, like the original's CTRL) of
   `app._arrive` using the fuel but calling `Game.witchspace()` instead: `Space.witch`, no
   station, planet and sun put 1e9 away, 3 stardust specks (`WITCH_DUST`), `THARGOIDS` (4)
   Thargoids each with a Thargon (role "thargoid"), no other spawns, no jump drive, no
   compass, no legal-status halving. `app.witch` is your chart position, the target's x
   and its y XOR 31; `c.system` stays the system you left. You leave by hyperspace from
   there (`Galaxy.distance_xy`, `chart.Chart(..., at=)`, `_jump_ok`); arriving clears it. A
   Thargoid launches a Thargon in place of a missile, only below half energy; a Thargon
   with no Thargoid left drifts (state "drift", quarter speed, harmless); any Thargon
   scooped from below with fuel scoops is `ALIEN_ITEMS`. The escape pod is no help there
   (GAME OVER, back to the save). Status page says WITCHSPACE. On the badge: 6.3 ms a step
   with eight Thargoid ships. Also: the galactic chart shows the right galaxy number.
   Tests: `tests/test_witchspace.py`, `tests/test_loader.py`.
   **Build 50 (Brian: no loading screen on the badge):** the launcher imports
   `<folder>.app` directly, not the package's class, so build 49's `loader.py` was never
   used. The loader is now `app.py` and the real app `ace.py`; `__init__.py` imports nothing
   on the badge. Checked the launcher's way on the badge: the loading screen is ready in
   0.28 s, the game in 6.7 s. Old `loader.py` removed from the badge.
   **Build 51 (Brian):** the loading screen matches the title screen: the name in the same
   yellow and white block letters in the same place (`letters.draw_name`, which `title.py`
   uses too; the loader imports `letters` before its first frame), and LOADING in green
   where the menu line will be.
   **Build 52: the system description sentence, and D for system data on the charts**
   (Brian). `tools/import_galaxy.py` also reads the extended tokens (TKN1, the ECHR / ETOK /
   ETWO / ERND / EJMP macros, EOR VE removed), the random-choice table (MTIN) and the
   two-letter tokens (TKN2, followed in memory by QQ16, which tokens from 228 and MT18's
   made-up names read) into `game_data.DESC_TOKENS` (only the 192 tokens reachable from
   token 5 and 153), `DESC_MTIN`, `DESC_PAIRS`; game_data.py is now 6.6 KB. `describe.py`
   follows PDESC / DETOK / DETOK2 / DTS / DASC: RAND seeded with the system's s1 and s2,
   DORND with the carry clear going in (as Ian Bell's reading; it gives the classic Lave
   line word for word), jump codes 1, 2, 3 (name), 13 (lower case), 17 (name + "ian",
   a final vowel dropped), 18 (1 to 4 random pairs from TKN2+2), 19 (single cap); `?` in
   made-up names is skipped; the mission-only RUTOK sentences are left out. `docked.system_page`
   draws System data, tighter, with the sentence wrapped below in cyan (`DESC_Y`,
   `DESC_WIDTHS`), for the tab and for D on the in-flight local chart (`fsub` "data",
   `ace._draw_data`; C, D or F go back). D on the docked charts opens System data for the
   selected system without changing the target (`Docked.show`). Charts say "D: DATA". On
   the badge: a description takes 11-15 ms (cached for the page). Tests: `tests/test_describe.py`.
   **Build 53 (Brian):** D on the System data tab goes back to the chart tab you came from
   (`Docked.chart_tab`, the last chart opened; the local chart if none), with the cursor on
   the system you were looking at (`Docked.go(tab, sel)`, `back_to_chart`).
   **Build 54: the disc version's two missions** (2026-11-15), as DOENTRY, BRIEF,
   DEBRIEF, BRIEF2, BRIEF3, DEBRIEF2, THERE, PDESC and the spawning code read from the disc
   source. `Commander.mission` is the original's TP byte (saved as "mission"); the rules
   are in `missions.py`, checked on every docking (`ace._mission_news`, after `_dock`
   saves; it saves again if a mission moves on). Mission 1: docked in galaxy 1 or 2 with
   256 kills (`KILLS_1`, divided by the level's `RANK_DIVISOR` like the ranks: EASY 51,
   NORMAL 128, HARD 256) starts it; at Orarra (galaxy 2, 144,33) the encounter roll's lone
   bounty hunter (`Game._encounter`, was `_roll`, `Game.hunt`) is the Constrictor (`role` "constrictor",
   `Obj.ecm`) if none is about, and every lone hunter there attacks (`Game.orarra`). Only
   the military laser hurts it, at `CONSTRICTOR_LASER` (1/4); its ECM destroys your
   missiles within `ECM_RANGE`; the energy bomb kills it, as in the original. Killing it
   sets `Game.got_constrictor`, which `_bank` turns into TP bit 1; the next docking
   anywhere pays 5000 Cr and 256 kills (scaled). Mission 2: mission 1 done, galaxy 3,
   1280 kills: go to Ceerdi (215,84), get the plans, take them to Birera (63,72); with the
   plans (`Game.plans`) each encounter tick brings a Thargoid with chance
   `PLANS_THARGOID` (56/256). Reward: 256 kills and the naval energy unit
   (`extras` "navy", replacing "energy"; `NAVY_UNIT` 3x recharge against 2x;
   `equipment.have` counts it as an energy unit). Orarra is a democracy, so the hunter
   turns up rarely (as in the original): about 2% of the 20 s ticks.
   Texts: `import_galaxy.py` also reads tokens 10, 11, 15, 216-223 and what they reach,
   the two standard tokens they print (TOKN 117, 108, from the comments in
   `elite-text-tokens.asm`), RUTOK and RUPLA / RUGAL into `DESC_TOKENS`, `DESC_RUTOK`,
   `DESC_RU` (game_data.py 11.9 KB). `describe.mission_pages` handles the extra jump codes
   (4 name, 5/6 standard token in Sentence Case, 8, 9/22/24/25 screen breaks, 12
   paragraph, 23/29 lower case, 27 captain, 28 the Constrictor's trail) and gives screens
   of paragraphs; `briefing.Briefing` shows INCOMING MESSAGE 2 s, then lays them out for
   the round screen (`briefing.layout`, `_width`), the Constrictor turning above mission
   1's briefing; C next, F skip (mode "brief"). The commander's name is the badge's
   Name setting (`settings.get("name")`), else "Jameson" (`ace.DEFAULT_NAME`). The special
   sentences show on the docked System data tab for the system you are at
   (`system_page(..., cmdr)`): Teorge, Arredi, Anreer always, the rest only while
   mission 1 is under way. Words come out as the source prints them in lower case
   (e.g. "looked bound for arexe"): DTS capitalises only after {single cap}.
   DEBUG: ADD THE CONSTRICTOR, MISSION: stage (the next of `missions.STAGES`, raising
   kills to what the next mission needs; written into the save), TO MISSION SYSTEM
   (to the stage's galaxy and system, arriving as from hyperspace). On the badge (REPL):
   making a briefing 40-190 ms, a special sentence 13 ms. Tests: `tests/test_missions.py`.
   Not yet played by hand.
   Then (Brian: text too small to read; then "use the joystick to scroll the text"): the
   message is one column of size 13 text (`briefing.SIZE`, was 10), `WIDTH` 22 characters
   a line so every line fits anywhere in the view (`VIEW_TOP` / `VIEW_BOTTOM`, +-66),
   with the original's screens run together (`PAGE_GAP`). Joystick up / down (held)
   scrolls at `SCROLL_SPEED` (only the joystick on the new front board, not A / D); C
   pages down and at the end goes on; F skips. Grey bars show more above / below. The
   Constrictor sits at the top of mission 1's column and goes once scrolled near the top.
   Then (Brian): the Constrictor turns up after `missions.QUICK_WAIT` (120 s) outside
   Orarra's safe zone while you hunt it (`Game.con_wait`, `con_t`, reset on entering a
   system; one at a time; the original's roll still applies too). Settings page:
   CONSTRICTOR: 2 MIN / ORIGINAL (`Commander.quick_con`, saved,
   default 2 MIN; ORIGINAL leaves only the roll). SHIP CONFIG (DEBUG) has NAVY ENERGY
   UNIT: ON / OFF, which takes the place of the usual unit (and ENERGY UNIT the reverse).
   Then (Brian): the in-flight PAUSE MENU is now SETTINGS (`fsub` "settings"): STEER,
   and with a commander DOCKING and CONSTRICTOR (always shown). QUIT TO TITLE moved to the
   top in-flight menu, after SETTINGS.
   Then (Brian: "add an option screen"): OPTIONS on the title screen (mode "options",
   `_update_options`, `_draw_options`, `omenu`) shows the same lines as the in-flight
   Settings, from one list (`_settings(cmdr)`, changed by `_change(item, left)`): STEER,
   with a commander DOCKING and CONSTRICTOR (written into the save), and LEDS: ON / OFF
   (`use_leds`, replacing the fixed `USE_LEDS`, which is now only the default). Steering
   and LEDs are kept in `options.json` beside the save (`options_path()`, gitignored);
   the test stubs delete it on each `install()`.
   Then (Brian): an OPTIONS docked tab too, the last (`docked.TABS`; `Docked(...,
   options=(items function, change function))`, given `_settings(True)` and `_change` by
   `_dock`; also with no game_data, after Status). Joystick up / down picks, C changes
   (left / right still change tab, so DOCKING only goes forward there).
   Then (Brian, option 2): DEBUG is a sub-menu of Settings / Options, no longer on the
   top in-flight menu, in groups (`DEBUG_GROUPS`: SHIP, SPAWN, TRAVEL, COMMANDER,
   DISPLAY). In flight: Settings > DEBUG (fsub "debug", the groups, title with the build)
   > a group (fsub "dgroup", `dgroup`) > a cheat (`_debug` as before); SHIP CONFIG (fsub
   "ship") goes back to the SHIP group; F goes back a level each time. Practice drops
   `CAREER_ONLY`; a commander's flight drops NEXT WAVE. Away from a flight (title
   Options, docked Options tab): mode "odebug" (`od_from`, `od_page`, `od_sel`), only
   `OFF_FLIGHT` cheats (SHIP CONFIG, +10 KILLS, +1000 CR, LEVEL, LEGAL, MISSION, FRAME
   TIME, REPAIR SHOP; the last two without a commander), each written into the save at
   once (`_write_setting`); SHIP CONFIG there works on the commander (`_ship_items_c`,
   `_ship_config_c`); REPAIR SHOP from the docked tab adds or removes the tab at once
   (`_make_dock`). Lists of at most `DEBUG_ROWS` are drawn in order (`_draw_list`). The
   in-flight Settings page no longer shows the frame / rules / world / hud timings.
   Tests reach a cheat with `mod.cheat_group(line)`.
   Then (Brian): a rank ACE (4000 kills in the original's count, so EASY 800, NORMAL 2000,
   HARD 4000) between DEADLY and ELITE (`commander.RANKS`; not in the original). The
   loading screen's LOADING flashes, on and off at each redraw (`app.AceCommander.shown`;
   redraws come between imports, about 0.4 s apart). Docked charts: the joystick changes
   tab as on every tab (E / B too); C hands it to the cursor (`Docked.use_cursor`,
   `Docked.cursor`, `Chart.active`), then C picks a target and F hands it back; D shows a
   system's data either way; D back from System data returns with the cursor on. The
   hints: "C: MOVE CURSOR" / "< >   D: DATA", then "D: DATA  F: DONE" (the in-flight
   chart keeps "FUEL ... D: DATA").
   Then (Brian): no hint lines on the in-flight menu pages (PAUSED, SETTINGS, DEBUG);
   DEBUG is on the top in-flight menu again as well as at the end of Settings (F goes
   back to wherever it was opened from, `debug_from`). The SHIP group is SHIP CONFIG
   itself: its cheats (INVINCIBLE, REFILL MISSILES, REFILL FUEL, FUEL TO 1/4) then the
   equipment switches (`_is_cheat`); away from a flight SHIP opens the commander's
   equipment directly. The charts (docked and in flight) have no hints either: the
   distance ("3.6 LY", "... TOO FAR", "YOU ARE HERE") and "RANGE 7.0 LY"; while the
   joystick changes tabs the name is "< LAVE >" and the cursor grey, with the cursor
   yellow and the name plain once C hands it over (`Chart.active`).
   Then (Brian picked MISSION in the docked DEBUG and then had no jump): TO MISSION
   SYSTEM also works from the docked Options tab's DEBUG (a TRAVEL group with just it):
   `_mission_move` puts the commander there and `_dock()` docks again, so that stage's
   message plays (`self.game` is dropped first). Not on the title screen's Options.
   Then (Brian): the in-flight menu always has a HYPERSPACE line in a commander's flight
   (replacing build 22's "JUMP: name", shown only with a target in range): "HYPERSPACE:
   DISO" with a target in range starts the countdown; plain "HYPERSPACE" opens the local
   chart to pick one. Hidden during a countdown.
   Then (Brian): each laser has its own beam colour (`cockpit.LASER_COLOURS`: pulse magenta,
   beam blue, military green, mining yellow; enemy beams stay ORANGE), and the ring LEDs
   flash that colour while `Game.beam` is set after each shot (`_leds_flight`, below the
   bomb, ECM and hit flashes, above the launch glow, scooping, sun and safe zone).
   Then (Brian): the energy bomb flashes the LEDs white as intended (it used `_leds`,
   which is red only, so it looked like a hit); enemy missiles are ORANGE like enemy
   lasers (all enemy fire), your missiles `LIGHT_PURPLE` (was cyan), so magenta is only
   the pulse laser.
   The top in-flight menu closes up (13 px lines, no help line) when
   it has more than six lines. Tests: `tests/test_equip_effects.py`.
   **Build 55: publishing prep begins, the game's own ships** (Brian: a full game with
   our own content, our own names, Claude designs the ships). `original_ships.py` (31
   roles: KESTREL in the Cobra Mk III's role, WARDEN police, GNAT, HORNET, STINGER, MULE,
   SKINK, KITE, GRUB, HARRIER, LANCET, BULWARK, BARGE, LEVIATHAN, MANTA, PHANTOM (mission
   1), VORN MOTHERSHIP and DRONE (aliens), SHUTTLE, HAULER, DRUM STATION (low tech, 3:1
   slot) and HALO STATION (high tech: a six-sided ring on three flat spokes round a hub,
   2:1 docking slot in the hub's front), rocks, canister, plate, missile, pod). Sizes near
   the originals' (the game's balance and the bay slots depend on them); stats our own
   (none within 3 values of Elite's, checked against ship_data.py); hit areas capped at
   9800. `ace.py` imports `ship_data` and falls back to `original_ships`
   (`ORIGINAL_SHIPS`, `HAVE_ELITE_SHIPS`); Options (title and docked, not in flight) has
   SHIPS: ELITE / OWN when ship_data.py is there, read from options.json at the next start
   (`_want_own_ships`). The viewer and title screen show the titles. The draw limits went
   from 48 vertices / 24 faces to 96 / 64 (`cockpit._PX`, `_VIS`). On the badge (real
   ctx): Halo 5.8-6.7 ms against Elite's Dodo 3.1-3.9; Drum 2.3-2.7 (Coriolis 2.4-4.8);
   Kestrel 2.6 (Cobra 2.8). The ring's faces point out from each segment's own middle
   (not the ring's radius, which flipped them). Stations still collide as the old ones
   did (by distance from the centre), so you can fly through the Halo's ring unharmed.
   Then (Brian: the Halo didn't hide all its hidden lines; Elite's rule is only right for
   convex shapes): a blueprint may have convex parts (entry[6], `Blueprint.parts`:
   vertices, edges and when it hides), drawn back to front by mean depth (`_PZ`); a part
   nearer than the centre blacks out its outline first (`_fill_hull(ctx, indices)`), the
   hub always, the ring's six pieces only side-on (|nose . view| < 0.5), the spokes
   never: each fill costs about 2 ms on the badge. Halo now 9-10 ms averaged over all
   angles (Elite's Dodo 3-6), about 8.7 face on, as you fly in to dock.
   Then (Brian: the slot looked wrong close up): Elite's slots are long up the station
   (along its roof), so lined up for docking (roof across the screen, docking A's rule
   and the docking computer's roll) they lie level, as the tunnels draw them; ours were
   long across it and stood upright. Both now stand like Elite's (Halo 34 x 68, Drum
   24 x 72); the test checks against ship_data.py when it is there.
   Then (Brian: the drum's back showed when docking): the hidden-line test is now made
   from a vertex on each face (`Blueprint.face_vert`, view-space positions in
   `cockpit._VX`, `_VY`, `_PZ`), not from the ship's centre as Elite's was; the centre
   test called a big ship's near-edge-on sides visible close up, drawing the back rim.
   Exact for convex shapes at any distance; also fixes Elite's Coriolis; no measurable
   cost on the badge.
   Tests: `tests/test_original_ships.py`; `test_app.py` runs a copy without ship_data.py.
   Next in publishing prep: our own galaxy, goods and equipment (56), our own words and
   mission texts (57), then the README, DEBUG off, level names and the app store (58).
   **Build 56: the game's own galaxy, market and equipment** (`original_data.py`,
   `content.py`). Seeds 0x7CBF 0x1FAB 0xE606 and our own 31 letter pairs (no TH, which
   made "THTHKAVE"; PA, not PE, which made "PEE..."), picked for readable names and
   checked for rude words in all eight galaxies; start at Daenor (128,141), a
   Confederacy, rich agricultural, tech 6, 12 systems within 7 LY. Goods keep each slot's
   job (0-7 in canisters, 3/6/10 illegal, 12 mining, 13-15 kg/g, 16 alien): GRAIN,
   FABRICS, ISOTOPES, CONTRABAND, SPIRITS, LUXURIES, STIMS, ELECTRONICS, MACHINERY,
   ALLOYS, WEAPONS, SILKS, ORE, GOLD, PLATINUM, GEMS, ALIEN RELICS; our own numbers, the
   same shape of economy (compared price and stock for every economy). Equipment: the
   same 14 in order, our own prices; GALACTIC HYPERDRIVE. Mission places: shipyard Tuelve
   and last seen Rotuvaga (galaxy 1), the Phantom at Elnada (galaxy 2, 13 jumps from
   where a galactic jump arrives), briefing Argatu and base Vedao (galaxy 3, 61 LY and
   13 jumps apart, like Ceerdi and Birera). Options' SHIPS became DATA: ELITE / OWN,
   saved as "own". Without our own text tables (build 57) the missions don't start and
   System data has no sentence in OWN. On the badge: content.py and its imports 2.6 s
   over the REPL. Brian's usual badge had SHIPS: OWN set, so it is now in our galaxy.
   Tests: `test_app.py` starts a commander in a copy without ship_data.py.
   Then (Brian): the Options line is DATA: ELITE / OWN, and each data set has its own
   commander: `commander.json` for our own data (what an app store player has),
   `commander_elite.json` for Elite's (`ace.SAVE_PATH`, `DATA_TAG`); a save records
   "data" and `commander.load(path, data)` won't load one from the other set (older saves
   without it load anywhere). Brian's usual badge: his Elite commander (380 kills, both
   missions done) was moved from commander.json to commander_elite.json (backup on the Pi
   in ~/Code/ace_commander_save_backups/).
   **Build 57: the game's own words** (`original_data.py`). System data sentences from
   our own grammar (`DESCRIBE`: `<word>` choices, %N name, %I adjective, %R made-up name;
   `describe._Grammar`, a 16-bit xorshift seeded from the system's s1 and s2, "a" made
   "an" before a vowel); every system in all eight galaxies has one that fits the page,
   over 240 different per galaxy. The agreed mission texts (`MISSION_TEXTS` by
   missions.py's numbers, [NAME] and [TRAIL] filled in by `describe.mission_pages`;
   `TRAIL` by galaxy: Rotuvaga in the first, "jumped to this galaxy" in the second).
   Trail clues (`SPECIAL`: galaxy, system, always, words; read by
   `missions.special_sentence` and `describe.special`): Tuelve, Rotuvaga, Kalimii in
   galaxy 1; Linaqu, Gaorsaka, Pamivaes, Soilliro, Reorrove, Litudade, Tudekai, Elnada
   along the route in galaxy 2; three always-on sentences. `_mission_news` runs with
   MISSION_TEXTS as well as Elite's DESC_TOKENS. With DATA: OWN the whole game now runs
   without Elite's files. Tests: `tests/test_original_data.py` plays both missions in a
   copy of the app without ship_data.py and game_data.py. Not yet on the badge (Brian
   asked to be asked first).
   **Build 58: release prep** (Brian: MIT licence; ask before publishing). `LICENSE`
   (MIT, "Corteil", with a note that it doesn't cover the Elite-derived files);
   `tildagon.toml` and `metadata.json` with license, url and a new description (134 of
   the store's 140 characters), version 58. The badge's app store (firmware
   `app_store.py`) downloads the GitHub release tarball, unpacks all of it in memory and
   installs it as `/apps/<owner>_<repo>` (Corteil_ace_commander): `.gitattributes` marks
   tests, tools, CLAUDE.md, DESIGN.md, deploy.bat and the git files export-ignore (the
   folders and `folder/**`: `check-attr` doesn't apply `folder/` to the files in it),
   so the tarball is 111 KB / 410 KB unpacked (231 / 809 before). Publishing (per the
   docs): the repo topic `tildagon-app` and a release; listed within about 15 minutes at
   apps.badge.emfcamp.org; errors at apps.badge.emfcamp.org/errors/. Not done yet: ask
   Brian first. `DEBUG_MENU = None`: shown only if `debug.txt` is in the app's folder
   (always on a PC), so store installs have no cheats (git-ignored). README rewritten for
   players. Level names EASY / NORMAL / HARD kept (no longer placeholders). Tests:
   `tests/test_install.py` builds the release's file list (git ls-files less
   export-ignore), installs it as Corteil_ace_commander and starts it through app.py.
   Then (Brian): the DEBUG menu stays in the release as an Easter egg. Dock at systems
   whose names start with the letters of `EGG_WORD` ("DRAKE", a male duck: no name in our
   galaxy starts with C or U, so DUCKS can't be spelled) in order, in the first galaxy;
   one docking elsewhere between letters is forgiven (`EGG_STOPS`, to refuel: no route has
   every step within one 7 LY tank), two start again (`AceCommander._egg`, progress
   `egg` / `egg_miss` in options.json). Then "QUACK!" (a `Briefing` with its own
   `pages`) and `DEBUG_MENU` is on for good ("debug": true in options.json, read by
   `_debug_wanted`). A route from the start: Daenor, (a stop such as Idei), Reares,
   Arorzu, Kasaxipa, Elkasoso. Not in the README on purpose.
   Then (Brian): lasers hit with Elite's power (`game.LASERS`: pulse 15, beam 15, military
   23, mining 50; were 12 / 12 / 18 / 15); the beam and military lasers are continuous
   (`CONTINUOUS`: the beam drawn and the LEDs lit while fire is held, a hit every 0.09 s,
   until overheated); the level scales every ship's energy (`LEVELS`' fourth value,
   `energy_k`: EASY 0.75, NORMAL 1, HARD 1.25, applied once as a ship joins `objs`,
   `Obj.max_energy` / `leveled`; the Thargon launch and flee thresholds use max_energy).
   At NORMAL the hits to kill match Elite's (a Gnat 5 pulse / 4 military / 2 mining hits,
   the Phantom 44 military).
   Brian chose to keep mission 2's Vorn as the original: no ambush on arrival, only the
   in-flight encounter ticks (PLANS_THARGOID) while carrying the plans. Not on the badge
   yet (he said no for now).
   Then (Brian: mission 2 good; the jump effect should flash the LEDs white where its
   particles leave the screen): `ace._jump_flashes` lights the ring LED nearest where
   each hyperspace streak (`cockpit._STREAKS`, while `Game.warp`) or, with the jump drive
   on, each stardust speck crosses the screen's edge (`EDGE_IN` to `EDGE_OUT` px from the
   middle), white, fading at `JUMP_FADE`; per-LED writes (`_leds_each`), below the bomb,
   ECM, hit and laser flashes; hyperspace flashes are blue-white (`HYPER_RGB`, Brian: more
   blue), the jump drive's white (`DUST_RGB`). Tried and reverted (Brian: it lost its flashing on
   the badge): flashing LOADING by the clock; redraws only come between imports, so in
   step with the clock they kept seeing the same phase. Then (Brian: no flashing at
   all) LOADING is steady. `_led_at` maps a screen direction to LED 1-12 with
   `LED_ANGLE1` (LED 1's angle, anticlockwise from 3 o'clock) and `LED_CLOCKWISE`: the
   firmware doesn't say where the LEDs are. Checked on the badge (LEDs 1, 2, 3 lit red,
   green, blue; Brian saw them at 0:10, 2:00 and 2:50 on a clock face): clockwise, and a
   30-degree fit puts LED 1 at 20 degrees past 12, so LED_ANGLE1 = 70; each reading is
   within 15 degrees (half a step) of the fit. The spacing may be uneven (pairs).
   **Build 59: released** (2026-11-15, Brian: "release it"). Version 59 merged to main
   (PR #20); release v59 from main (github.com/Corteil/ace_commander/releases/tag/v59);
   repo topic `tildagon-app` added. GitHub's v59 tarball checked: 112 KB, only the 25 app
   files (export-ignore works on GitHub too). All 18 test files pass on a clean clone of
   main. The store lists it within about 15 minutes at apps.badge.emfcamp.org; problems
   at apps.badge.emfcamp.org/errors/. A new version: bump `version` in tildagon.toml
   and metadata.json, merge to main, make a release.
   **Build 72** (2026-11-17, Brian): SPEED TEST kept but moved off the title screen to
   DEBUG > DISPLAY (title Options or docked Options, with DEBUG on); F from the test goes
   back to that page. Combat practice has its own page before the flight: LEVEL (saved as
   options.json "practice_level", default NORMAL) and HARDCORE (the shared setting). The
   practice flight uses that level's `game.LEVELS` row; a part-way practice fight is
   restarted if HARDCORE changed (before, it kept the old rules). Practice has no ECM, so
   Hardcore there means armed and locked missiles.
   **Build 73** (2026-11-17, Brian): practice's HARDCORE is independent of the commander's
   (`p_hardcore`, options.json "practice_hardcore"; Settings in a practice flight changes
   practice's), and the practice ship has an ECM (`g.ecm` set on a fresh practice flight:
   it fires by itself, or on its key in Hardcore). The commander's LEVEL is still only
   chosen at NEW COMMANDER or by DEBUG > COMMANDER > LEVEL (asked Brian whether Options
   should have it).
   **Build 74** (2026-11-17, Brian: "hardcore and level can only be selected when new
   commander is created. only debug can override this"): the NEW COMMANDER page has LEVEL
   and HARDCORE lines (shared `_draw_rows` with the practice page; up / down picks, left /
   right changes). `Commander.hardcore` is saved with the commander; HARDCORE left the
   Options page, docked Options tab and in-flight Settings. DEBUG > COMMANDER > HARDCORE
   toggles it (off flight: written to the save; in flight: this flight's rules and
   docking style at once, and the save). Old saves take options.json's old HARDCORE once.
   **Build 75** (2026-11-17, Brian): the title Options page hints moved down (y 82 / 96) so
   they clear a sixth line (LEDS shows on the badge, not in PC renders).
   **v0.2.0: released** (2026-11-17, Brian: "release it as a version, v0.2.0"): builds 60-75
   (Hardcore Mode, keyboard keys, four views, unpaused screens, practice and new-commander
   pages). Version string "0.2.0" in tildagon.toml and metadata.json. The firmware store
   compares versions as text lists (app_store.py compare_version), so badges with "59" are
   not offered it as an update (Brian chose 0.2.0 anyway; they must reinstall).
   **Build 76** (2026-11-18, Brian: "the effects are wrong on the side views when jumping,
   also check hyper space effect"): the jump drive's stardust streaks trail the way the
   dust came in each view (`cockpit._streak_tail`: front out at you, rear away into the
   middle, left/right across the screen), and the white LED flashes use `view_dust()`.
   Out of hyperspace or into witchspace the view goes to the front (`Game._hyper`), as
   Elite's TT110 / MJP call LOOK1 with X = 0. `tests/render.py` shoots the rear, left and
   right jump views. Docking computer: not missing, only sold from tech level 9 (Lave is 5;
   Leesti and Zaonce sell it), as the original's EQSHP; left as it is.
   **Build 77** (2026-11-18, Brian): C on the docked Inventory sells the whole hold at this
   station's prices (`Docked.sell_all`, green "SOLD: +x Cr"). Tabs: the Repair Shop after
   Equip ship; Options is no longer a tab but Status's sub-screen, opened with C (A already
   launches), F back to Status; Status shows "A: LAUNCH" and "C: options". = still opens
   Options. Elite opens Status (f8) on docking (BAY), as we do. Tests launch with A now.
   Only the current firmware matters (Brian: both badges, 2024 and 2026, run it); an
   older-firmware tweak for A on Status was taken out again.
   **Older-firmware fallback removed** (2026-11-18, Brian: "remove the old fallback"):
   `ace.py` imports `JOYSTICK_BUTTON_TYPES` and `FRONTBOARD_BUTTON_TYPES` directly; the
   `new = FB is not None` checks, the d-pad flight branch (tilt default, up/down speed,
   left missile) and the `joystick=False` test stub are gone.
   **Build 78** (2026-11-18, Brian: "next up is to be able to fly/buy other ships, plus a
   hangar"; "weapons range should be the same as elite"; "add select ship to debug").
   Ranges as Elite: your lasers hit anything in your sights in the bubble (HITCH has no
   distance check; `LASER_RANGE` = `DESPAWN`); enemy lasers only within `ENEMY_REACH` 8192
   on each of x, y, z (TA3: no high byte of x / y / z reaching 32), also ship against
   trader; enemy missiles at any distance; missile lock never had a range.
   Ship types (`ships.py`, rules only): `TYPES` gives price, hold, laser mounts (1 front,
   2 front+rear, 4 all), pylons, shipyard tech level and stolen-only (Viper: police;
   Constrictor: navy). From the blueprint against the Cobra in the same data: top speed
   (speed), toughness (energy: damage divided by it) and turning (energy as mass, square
   root, 0.6-1.4); standard weapons from laser power (2 pulse, 3-5 beam, 6+ military) and
   missiles. The Cobra flies exactly as before. Large cargo bay: hold + 3/4 (Cobra 20 to
   35). `Commander.ship`, `.stolen`, `.hangar` (save version 5; entries checked by
   `_hangar_entry`; hold and missiles clamped to the ship's own). `Game.set_ship(name,
   pylons)`: `max_speed`, `turn_k`, `tough`, `max_missiles` replace PLAYER_MAX / PITCH_RATE /
   ROLL_RATE / MAX_MISSILES in flight (the HUD speed bar is against `max_speed`). Equip
   ship: missiles up to the pylons ("NO PYLONS"), lasers only on mounted views ("NO LEFT
   MOUNT"; D cycles only those). Practice always flies a Cobra. DEBUG > SHIP CONFIG > SHIP:
   the next type, cheapest first (equipment cut to fit, saved). Brian's rules for the rest
   (build 79): Shipyard tab by tech level and government (pirate worlds sell stolen ships,
   buying one makes you an offender), each ship keeps its own equipment, a new one comes
   with its standard weapons, trade-in counts the equipment; the hangar goes with you,
   but in Hardcore a ship stays at the station where you left it. Tests: `tests/test_ships.py`.
   **Build 79** (2026-11-18): the SHIPYARD and HANGAR tabs, after the Repair Shop
   (`Docked(..., bps=ace._bp)`). Shipyard: `ships.for_sale` (up to 6 legal types by tech
   level, chosen per system; anarchy / feudal add 1-2 stolen of any type at 65%), one ship
   at a time turning, speed / hold / mounts / pylons, price and trade-in value; C buys
   (your ship packed into the hangar; at this station in Hardcore), D trades in (value =
   60% of price, half if stolen, plus half the equipment's cost; cargo that doesn't fit is
   sold here). A new ship: standard weapons (`ships.new_ship`), cargo moved as it fits
   (`ships.move_cargo`), the rest stays in the old ship. Stolen: legal |= 32 (offender).
   Hangar: the flown ship first ("flying"), then the kept ones ("here", or in Hardcore
   the system they are kept at); C flies one (the old one goes in, cargo moves across), D
   sells one with its cargo. Messages clear when the pick moves. The starting Cobra
   trades in for ~24,000 Cr, so a new commander can downgrade to a Worm and pocket
   ~21,000 Cr: left as is (Brian, 2026-11-18: "downgrading is a bad buy").
   Tests: `tests/test_shipyard.py`.
   Badge fix: MicroPython's `random` has no `Random` class, so `ships.for_sale` uses its
   own seeded generator (`ships._Rnd`). Found by a smoke test over the REPL after the PC
   tests passed; Shipyard buy / Hangar fly / sell then ran on the badge.
   **Build 80** (2026-11-18, Brian: "the ship yard should host the repairshop as a sub
   screen. and the keyboard short cut take to the ship yard instead of the repairshop, the
   hanger should have the current selected ship as 3d model with it fitout listed"). The
   Repair Shop is no longer a tab: the Shipyard's first page is your own ship (turning in
   its paint, its stats and trade-in value) and C there opens the Repair Shop over the
   Shipyard (`Docked.in_repair`, `name()` "REPAIR SHOP"); F goes back to the Shipyard
   (`Docked.back()`), < > leave it. The ships for sale are pages 2 on (`ysel - 1` in
   `yard`). `-` opens the Shipyard. DEBUG REPAIR SHOP off: no "C: repair shop"
   (`Docked.repair`). The Hangar shows one ship at a time, as the Shipyard does: its model
   in its own paint, "flying" / "here, worth x Cr" / "kept at x", and its fit-out
   (`_fitout`: lasers by view F/B/L/R, missiles / pylons, hold and tonnes used, the other
   equipment on one or two lines). Not a sub-screen: it fits on the tab.
   **Build 81** (2026-11-18, Brian: "the stats of each ship should be shown in the
   shipyard as a sub screen"; and not "YOUR ..."). The Shipyard's first page names your
   ship plainly (Brian chose name only); its hint is "C: repair shop   D: stats". On a
   ship for sale C opens SHIP STATS (`Docked.in_stats`, `open_stats`) and buying happens
   there: C buys, D trades in (Brian chose the two-press way), then back on the Shipyard's
   first page with the new ship; F goes back to the same page. Stats: price and trade-in,
   top speed, turning and shields as % of the Cobra (its shown name), hold with and
   without the bay, laser mounts, pylons, standard fit, and "from tech n" / "stolen only".
   Also build 81 (Brian: "if the cargo over spills, credit its value to the player's
   balance, also remove the repairshop flag"): whenever you change ship (buy, trade in,
   or fly a kept one) the cargo moves across and what doesn't fit is sold at this
   station's prices (`Docked._sell_off`, kept if there is no market), with "CARGO OVER: +x
   Cr" instead of the ship's name; a ship left in the hangar keeps no cargo. The DEBUG
   REPAIR SHOP switch and `AceCommander.repair_shop` are gone; `Docked(..., repair)` too.
   **Build 82** (2026-11-18, Brian: "the HUD should reflect the number of missile slots,
   swap C and D on the shipyard"; "the buttons should be the same across those screens").
   The HUD draws one missile slot per pylon (`Game.max_missiles`: none on the Worm,
   Shuttle and Transporter, five on the Boa and Constrictor). In the Shipyard C is a
   ship's stats on every page, your own included; D on your own ship's page is the Repair
   Shop. In the stats, C buys and D trades in, as before.
   **Build 83** (2026-11-18, Brian: "would some ships not be able to jump to hyperspace,
   like the shuttle, and would different ships have different jump ranges"; then "build
   the jump ranges as suggested"). Each ship has its own fuel tank (`ships.TANKS`, tenths
   of a LY; `Commander.max_fuel()`), which is its jump range: none for the Shuttle,
   Transporter and Worm (in-system craft); 5.0 LY Sidewinder, Gecko, Viper; 6.0 Adder,
   Cobra Mk I, Krait, Mamba, Moray; 7.0 Cobra Mk III (Elite's) and Fer-de-Lance; 8.0 Asp
   Mk II, Python, Boa; 10.0 Constrictor. Fuel is kept per ship (in `pack` / `unpack`; a
   new ship comes full; old entries without it are full). Fuel price, refuelling, sun
   skimming, the pod's refill, DEBUG REFILL / FUEL TO 1/4 and the sun gauge's FU bar
   (`Game.fuel_max`) use the ship's tank. No hyperdrive: no HYPERSPACE or GALACTIC JUMP
   line in flight, H says "NO HYPERDRIVE", Equip ship won't sell fuel or the galactic
   hyperdrive ("NO HYPERDRIVE"). Never stranded: the Shipyard won't sell (or trade you
   into) an in-system ship, and the Hangar won't sell a ship, if that leaves you no ship
   that jumps here (`ships.stranded`; in Hardcore it must be kept at this station):
   "NEED A SHIP THAT JUMPS". Shown: "jump range" on SHIP STATS, the range or "no jumps"
   on the Shipyard page, "fuel x of y LY" / "no hyperdrive" in the Hangar's fit-out.
   **Build 84** (2026-11-18, Brian: "the viper and the constrictor should be available to
   buy at high tech worlds legally"; for a hot ship "1, 2 and 4"; "add stolen status to the
   debug menu"; "it should be new transponder"). The Viper is sold legally from tech 12,
   the Constrictor only at tech 15 (no type is stolen-only now; pirate worlds can still
   sell any type stolen). A stolen ship (`Commander.stolen`): (1) keeps you an offender
   while you fly it: jumps, the galactic hyperdrive and the pod clear the legal status no
   further than `ships.STOLEN_LEGAL` (`ace._hot`); (2) in a law-abiding system
   (`game.LAWFUL_GOV` 5 and up) each police Viper that comes within `SPOT_DIST` 6000 looks
   once (`Obj.checked`) and with `SPOT_CHANCE` 0.5 knows it and attacks, "STOLEN SHIP
   SPOTTED" (`Game.stolen`); (4) the Repair Shop on pirate worlds (anarchy, feudal) sells a
   new transponder on D for a quarter of the ship's price (`Docked.transponder_price` /
   `buy_transponder`), "NEW TRANSPONDER FITTED": the ship is clean. DEBUG > SHIP CONFIG
   > STOLEN switches it, in flight or docked, saved. Not done: the long system names clip
   the docked tabs' titles at the top (e.g. "REPAIR SHOP  CEBETELA").
   **Build 85** (2026-11-18, Brian: "tilt should be able to be flipped in settings/options
   and saved, galactic jump clears a hot ship"; "the name does not need to be
   displayed"). A TILT line under STEER on Options, the docked Options and the in-flight
   Settings (when there is a tilt sensor): NORMAL, UP/DOWN FLIPPED, L/R FLIPPED, BOTH FLIPPED (build 87: "should say flipped")
   (`TILT_FLIPS`, `AceCommander.tilt_flip`, options.json "tilt_flip"); C or right goes on,
   left back. The galactic hyperdrive clears a stolen ship as well as the record. The
   docked tabs' titles no longer carry the system's name (it clipped on long names;
   Status shows where you are). Options pages: lines 17 px apart so seven fit.
   **Build 86** (2026-11-18, Brian: "is it possible to catch an escape pod?"; "add the
   escape pods, and add in the debug menu"). As the original's TACTICS part 4: a ship
   that carries a pod (`POD_SHIPS`, from bit 7 of the NEWB flags in each ship file's E%:
   Adder, Anaconda, Asp Mk II, Boa, Cobra Mk I, Cobra Mk III and its pirate, Fer-de-Lance,
   Krait, Mamba, Python and its pirate, Viper), below an eighth of its energy, bails out
   with `POD_CHANCE` 0.1 each time it thinks (`Game._bail`): the pod (an Obj of kind
   "can", the ESCAPE POD model, `good` = `SLAVES` 3) flies off at its own speed and the
   ship is left adrift ("drift": no shots, no turning). Scooped like a canister (fuel
   scoops, from below): a tonne of slaves, which are illegal cargo as usual. DEBUG >
   SPAWN: RELEASE ESCAPE POD (just ahead, as RELEASE CANISTER) and BAIL OUT (the
   nearest ship with a pod; "NO SHIP WITH A POD" if none).
   **Build 87** (2026-11-18, Brian: "the tilt menu should say flipped when flipped", "the
   flipped option does not seem to be working" (he steers with the joystick), "should
   only affect flight controls"). The setting is now CONTROLS: NORMAL / UP/DOWN FLIPPED /
   L/R FLIPPED / BOTH FLIPPED, always shown, and flips the flight steering after it is read
   (tilt, joystick, cursor keys, W A S D: `_update_flight`, after `_steer`), not inside
   `_steer`, so the charts' cursor, the ship viewer and the menus are untouched. Same
   options.json key ("tilt_flip").
   **Build 88** (2026-11-18, Brian: "a search function on the galactic viewer"; "keyboard
   entry for search with suggestion for auto complete and the badge's own text entry
   system when there is no keyboard attached"; "if the keyboard is fitted don't show the
   badge entry method"). B on the Galactic chart (in flight; docked once C has given the
   joystick to the cursor) finds a system by name, as Elite's "Planet Name?". Keyboard
   fitted (`AceCommander._keyboard`: the firmware's hexpansion manager runs a
   `KeyboardApp` or a header names a keyboard; else a keyboard key has been pressed,
   `Pad.keyboard`): the game's own page (`find.py`): typed letters (`Pad.typed`), the best
   match's rest shown dimmer to complete it, four matches listed (from the start
   alphabetically, then holding it anywhere), up / down picks, Backspace, Enter goes
   there, Esc back. No keyboard: the firmware's `app_components.dialog.TextDialog` (the
   six-button letter picker), drawn over the chart, its message set to the best match
   as you type; Done goes to it, Cancel back. Either way the chart's cursor lands on the
   system (`Chart.goto`, exact even where dots overlap); C then targets it as usual.
   Tests: `tests/test_find.py` (with a stand-in TextDialog). Next asked for: a custom
   commander name.
   **Build 89** (2026-11-18, Brian: a custom commander name, "fill out the badge name
   grayed out as an option, press tab to fill it, if no name, same name as elite").
   `Commander.name` (saved; "" in old saves: the badge's name). The NEW COMMANDER page has
   a NAME line above LEVEL (it opens on LEVEL, so C still starts at once); C or right on
   NAME enters it. Off flight, Options (and the docked Options) have "NAME: x" too. With a
   keyboard: `find.NameEntry`, the suggestion (the badge's name from settings, else
   Elite's JAMESON: `badge_name`) greyed after what is typed, Tab fills it, Backspace,
   Enter takes it (empty: the suggestion), Esc back; up to 12 letters, upper case. With
   no keyboard: the firmware's TextDialog, its message "NAME? (none: X)", Done on nothing
   takes the suggestion. The name is in the mission briefings (`cmdr_name(c)`) and the
   in-flight Status title, "COMMANDER X", as Elite.
   Build 89 fix (Brian: "the search function crashed when using the badge keyboard,
   keebd was ok"; badge log 2026-11-18 23:02: the dialog registered and drew, then
   nothing). The firmware's eventbus gives ButtonDownEvent (requires_focus) only to
   handlers whose app is `_focused`, and the focused app is the loader (`app.py`), not
   the game inside it; the TextDialog was registered to the game, so no button reached
   it, while the game passed all input to it: the badge froze. Both dialogs (find, name)
   are now registered to `self.host`. Checked with the firmware's real dialog.py on the
   PC (stand-ins for display and tokens only); `tests/test_loader.py` asserts the host.
   **Build 90** (2026-11-18, Brian: "the text size is too big in the text selector").
   Badge log of his test after the build 89 fix: search (v -> VEALE, Done put the cursor
   there) and the name ("AA") both worked; the only tracebacks were the keyboard driver's
   (ENODEV) as the hexpansion was pulled. The badge's text entry is now
   `find.small_dialog(TextDialog)`: the firmware's TextDialog working as before, drawn
   with the game's text (message 14 px green, typed text 18 px, the six button labels
   14 px where the firmware puts them) on solid black instead of its 80% hexagon.
   **v0.3.0: released** (2026-11-18, Brian: "all good, push, merge and release; update
   docs first"): builds 76-90. Version "0.3.0" in tildagon.toml and metadata.json (the
   store's text compare puts it after "0.2.0", so 0.2.0 badges are offered the update).
   README (ships, Shipyard, Hangar, jump ranges, stolen ships, escape pods, weapon ranges,
   CONTROLS, the name, search; the install list with ships.py and find.py), CLAUDE.md,
   DESIGN.md and the key guide (B: find on the Galactic chart row; still one page) updated.
   **Hosts, and the Raspberry Pi P0** (2026-11-19, Brian: "yes, start step 1 and the Pi P0",
   choosing one repo for the badge, the Pi and later the Tufty). Branch `pi-host` from main.
   `hosts/` holds other devices' runners, export-ignored so the app store tarball is unchanged
   (checked with git archive: 29 files, none from hosts/). `hosts/pi/`: the real ace.py on
   stand-ins for the firmware modules (`pi_firmware.py`: Button with the firmware's parent
   matching, the 2026 board's composite buttons, KEYBOARD_BUTTONS, a bus, the LED ring, App
   whose minimise ends the program), `ctx_pygame.py` (the ctx calls drawn at scale onto a
   pygame Surface, DejaVu Sans, text cached), `keys_pi.py`, `run.py` (`Host`: 480 x 480
   round screen in the case colour, the 12 LEDs round it where the game's LED_ANGLE1 puts
   them, 60 fps, saves under ~/.local/share/ace_commander). Played headless by the test:
   title, NEW COMMANDER with the keyboard name page, docked, launch, flight, menu, quit.
   **Build 91** (2026-11-19, Brian, seen on the Pi host: "the first line in Options clips
   the edge of the display"). With CONTROLS and NAME the Options pages have eight lines: the
   docked Options now start at y -62 (was -70), 15 px apart, size 13, the highlight 192 wide
   (it ran past the round edge); the title Options start at -50, 16 px apart, size 13, so
   DEBUG clears the hint lines on both.
   **Build 92** (2026-11-19, Brian: "if a ship is low risk the target box should be
   white"). The missile sights' diamond is red only for a dangerous ship, white for a
   low-risk one, and green once locked, as before. `cockpit.hostile(o)` is the one rule for
   the sights and the radar: a pirate, or anything attacking (attack / break); a hull left
   adrift after its crew bailed out (state "drift") is low risk on both now. Test in
   `tests/test_traffic.py`.
   **v0.3.1: released** (2026-11-19, Brian: "it's only a small version bump, but go ahead
   and release it"): builds 91-92 (Options fit eight lines; missile sights white for
   low-risk ships, one hostile rule with the radar). Version "0.3.1".
   **Build 93** (2026-11-19, Brian, on the Pi host: "use B to buy and S to sell"). On a
   keyboard (the Pi's, or the Keyboard Hexpansion on the badge) B buys and S sells, docked:
   the market (both repeat when held, as C / D), Equip ship (B), a ship's stats in the
   Shipyard (B buys, S trades yours in), the Hangar (S sells the picked ship) and Inventory
   (S sells the hold). The badge buttons are unchanged (C buys, D sells). `Pad` now listens
   for the B key (it had a fixed list of letters). Tests in `tests/test_keys.py`; the Pi trip
   test buys and sells with B and S. Key guide: Market C/B buys, D/S sells; Equip ship C/B;
   Inventory C/S. Not yet on the badge.
   Then (same day, Brian: "s not required for selling"): S no longer sells, trades in or
   sells the hold; B still buys on the badge's keyboard. On the Pi host keyboard B is the
   badge's B when docked ("badges b everywhere"), so there C buys and D sells. Key guide:
   Market C/B buys, D sells.
   Then (same day, Brian: "when docked the letter keys on the keyboard act the same as
   the badge keys, apart when entering text", "badges b everywhere", "should be the same
   everywhere"): build 93's B buys is dropped too. Instead the game's `Pad` makes the
   keyboard's A-F the badge's buttons A-F (each the lettered button and its direction: A
   up, B right, C confirm, D down, E left, F cancel) off the flight (docked, the title and
   its pages), not while typing a name or a search (`as_buttons`, set at the end of each
   update; a key goes up as the names it went down as). In flight, pause menu included,
   they stay Elite's keys. Same on the badge's Keyboard Hexpansion and the Pi (its own
   mapping removed). Tests in `tests/test_keys.py`; key guide footer line.
   **Build 94** (2026-11-19, Brian, for the Pi's game pad: "analog controls", left stick
   left / right "pan"). `AceCommander.analog`: a host's analogue controls (roll, pitch, yaw
   -1..1, speed 0..1 where the power stick sits, or None), added to the steering in
   `_update_flight`; speed steers the throttle to that fraction of `max_speed` (at the top
   it holds speed up, so it is the jump drive); CONTROLS' left / right flip turns yaw too; a
   stick pushed past half takes over from the docking computer. Yaw is new (Elite has none):
   `Game.step(..., yaw=0.0)` and `Game._yaw` turn everything about the up axis in floats,
   only when yaw is not 0, so the badge (which never sets analog) pays only an `if`.
   `YAW_RATE` 0.6 rad/s. Tests: `tests/test_analog.py`. The Pi's pad map is in
   `hosts/pi/PLAN.md` (P2).
   **Build 95** (2026-11-19, Brian, playing on the Pi with his Boa: "selected ship is not
   displayed ... when leaving or entering the scene", "when docking the station should be
   bigger before the tunnel scene"; chose "fly on into the slot"). (1) The ship you fly
   always shows in the launch and docking tunnels: one too big for the slot level (Boa,
   Python, Anaconda in a Coriolis, whose slot is 3:1) is drawn shrunk to just fit
   (`Tunnel.fly`, `_MeInTunnel(bp, k)`: the scale in its matrix); it used to be left out.
   (2) The docking computer flies on into the slot: docked at `game.AUTO_IN` (40) inside the
   face (was `front + PLAYER_R + 60` outside), and the chase camera closes in on the final
   run (`cockpit.chase_back`: from `CHASE_BACK` 760 to `CHASE_DOCK` 220 outside the face,
   half a unit per unit, height in proportion), so the station fills the screen before the
   tunnel; once your ship's nose is in the slot it is drawn before the station, which hides
   it. Tests in `tests/test_equip_effects.py`. Docking by hand is unchanged.
   Then (same day, Brian: "did not line up to the face correctly"): measured, the run in
   came at ~3 degrees to the axis (it aimed at the station's middle) and ~3 degrees off the
   slot's roll (lagging the spin), and the camera looked down from above. Now on the run in
   it aims at a point on the axis halfway from the middle out to you (`AUTO_LEAD`); once
   rolled to the slot it pitches and yaws onto it (`auto_yaw`: the new yaw, so sideways
   error can be put right without rolling); the roll matching follows the station's spin
   (`AUTO_SPIN`, feed-forward `STATION_SPIN / (ROLL_RATE * turn_k)`); the chase camera
   drops onto your ship's axis as it closes in. At the face: 0 off the axis, 0 degrees off
   the roll, the face square on. Test in `tests/test_equip_effects.py`.
   **v0.3.2: released** (2026-11-19, Brian: "badge is ok, release should be 0.3.2"): builds
   93-95 (keyboard A-F as the badge's buttons off the flight; analogue controls and yaw for
   a host's pad; your ship always in the tunnels; the docking computer flies into the slot,
   lined up with it, the station filling the screen). Version "0.3.2".
   **Build 96** (2026-11-19, for the Pi's Elite layout, Brian: "start P3 full screen, HUD
   should match the Tufty"). The Tufty port's view-size patches put into the game:
   `cockpit.VIEW_HW` / `VIEW_HH` (half the 3D view's width and height, 120 / 120 on the
   badge) in place of the hard-coded 120s (ship and sphere culling, the enemy beam, the
   whole-view fills), and `game.DUST_X` (stardust's sideways spread, 500). At the defaults
   nothing changes: all 59 `tests/render.py` frames are pixel-identical before and after.
   **Build 97** (2026-11-19, Brian on the Pi: "there should also be a quit option on the
   title page"). `ace.TITLE_QUIT` (False on the badge, where F leaves): a host sets it for a
   QUIT line at the end of the title menu, which leaves as F does. The Pi sets it. Also on
   the Pi only: no mouse pointer over the game, and no frame time counter in full screen.
   **Build 98** (2026-11-20, Brian on the badge: after buying a new ship the docking
   computer's view from behind still showed the old ship). `cockpit._my_ship` cached your
   ship's blueprint per `Game`, and the same `Game` is kept between flights (`_fit` only
   calls `set_ship`); it now also checks `g.ship_name`. Test in `tests/test_shipyard.py`.
   **Build 99** (2026-11-20, Brian: "make it the same as Elite"). The sun's heat as in the
   disc source (main flight loop part 15): the sun has no surface to hit; the heat kills you
   once the cabin temperature would pass 255 (`game.FATAL_CABIN`), about 0.91 sun radii from
   its centre (285 - 36 x (d / r)^2, the same formula and numbers as Elite's). Heat never
   drained energy in the original, so it doesn't here. The planet is still deadly at its
   surface. Elite checks the heat on one frame in 32; this checks every frame.
   Then (Brian: "would not the edge of the sun be on the horizon if collecting fuel?"): the
   sun vanished two seconds into the scooping band, because `_sphere` drops a sphere whose
   centre is under half a radius ahead and circles over `MAX_ARC` are skipped. Within
   `SUN_BANDS_K` (3) sun radii it is now drawn as bands of `SUN_BAND` (4) rows
   (`cockpit._sun_bands`, as Elite draws its sun in lines), each filled where a ray through
   the band's middle row meets the sphere: its true edge, a horizon across the view that
   slides off the side as you pass; inside the edge, all sun. Within 0.5% of the pixels of a
   per-pixel ray test. Not measured on the badge: up to 60 rectangles (about 2 ms) and
   roughly 30 float results a band, so watch the frame time and collections near the sun;
   a bigger `SUN_BAND` costs less. Tests in `tests/test_game.py`.
   **Build 100** (2026-11-20, the platform layer's step 1, `hosts/NEXT_SESSION.md` B1:
   settings and storage). New `config.py` (imports nothing): `data_dir` (the save,
   options.json and debug.txt; None = the app's folder, as on the badge) with `data(name)`,
   and a host's switches `debug_menu`, `perf_log`, `log_keys`, `title_quit`, `wire_min`.
   `content.py`, `ace.py` and `cockpit.py` read them as they load; `app.py` loads it first.
   The Pi's `load_game` sets config before importing the game, so its tricks are gone
   (content.py under a false `__file__`, SAVE_PATH / TITLE_QUIT / DEBUG_MENU / PERF_LOG /
   LOG_KEYS overwritten after import, and `__defaults__` changed for WIRE_MIN); only a
   second Host in one process (the tests) still points the loaded game at its folder.
   The badge is unchanged: all 59 `tests/render.py` frames pixel-identical before and
   after. The app store package gains `config.py`. Not yet run on the badge or the Pi.
   **Build 101** (2026-11-20, the platform layer's step 2, `hosts/NEXT_SESSION.md` B2:
   input as control names). `ace.Pad` split in two: `controls.Controls` (no imports: the
   names held, hit, typed, the keyboard flag, `as_buttons`), fed by `press(key, names, ch,
   badge)` / `release(key)`; and `platform_tildagon.Input` (the badge: today's matching of
   firmware buttons to names, moved, not rewritten; `config.log_keys` prints each event).
   `ace.py` no longer imports `events.input`, `events.joystick`, `events.keyboard` or
   `frontboards.common`, and loses `Pad`, `BY_NAME` and `LOG_KEYS`; it makes a `Controls`
   and either calls `config.input(controls, host)` or makes a `platform_tildagon.Input`.
   The Pi sends names itself: `hosts/pi/controls_pi.py` (every key and button with the
   names, letter and badge button the badge would give it; `Feed`), so `pi_firmware.py`
   lost its buttons and button events (204 to 108 lines). `tests/test_pi_controls.py`
   checks all 91 Pi keys against `platform_tildagon.Input` on the test stubs. The badge
   is unchanged: all 59 frames pixel-identical; per frame nothing new (a press costs one
   more call). The app store package gains `controls.py` and `platform_tildagon.py`.
   Not yet run on the badge or the Pi.
   **Build 102** (2026-11-21, Brian's requests). The Pi: Esc (cancel) on the title screen
   no longer quits, only its QUIT line does (`config.title_cancel`, default True: the badge's
   F still leaves); the DEBUG menu stays behind `--debug`, now in both desktop shortcuts.
   Off the flight (not while typing) a keyboard's Enter and Esc count as the badge's C and F,
   as A-F already did (`platform_tildagon.Input.badge_keys`, `controls_pi._AS_BADGE`): Enter
   buys on the Market, Esc goes back. Docking computer chase view: your ship's pitch was
   drawn the wrong way (nose up while the computer pitched down; `cockpit._my_ship`); on the
   run in it now shrinks over the last `CHASE_SHRINK` (600) to fit the slot (`_slot_fit`:
   a Cobra is 256 across, a Coriolis slot 60) and is drawn over the station, so it is seen
   going in; the computer slows to `AUTO_CRAWL` (0.25) of DOCK_SPEED inside `AUTO_SLOW`
   (300) of the face and docks `AUTO_IN` 70 inside (40 before; 100 missed on a Dodo, too
   near its middle). The tunnel scene is unchanged (DOCK_TIME). Run on the badge (as
   .mpy) and played by Brian: all OK.
   **Build 103** (2026-11-21, the platform layer's step 3, `hosts/NEXT_SESSION.md` B3).
   `ace.py` imports no firmware any more (it lost `app`, `system.eventbus`, `imu`,
   `system.scheduler`, `tildagonos`, `system.patterndisplay.events`, `settings`,
   `system.hexpansion.app`, `app_components.dialog` and `asyncio`). What only the device can
   do is `self.platform`, from `PLATFORM.Platform(self)`: `platform_tildagon` on the badge,
   or `config.platform` (a host's module with `App`, `Platform`, `owner_name`). Moved, not
   rewritten: the LED takeover and writes (`leds_rgb`, `leds_each`, `leds_release`, with
   `leds_on` / `led_level`; ace keeps which effect to show and the LEDS option), tilt
   (`tilt()` sets `tx` / `ty`, no new object per frame), `keyboard_fitted()`,
   `text_dialog(title)` (the small TextDialog on the host), the frame loop `run` and
   `minimise`; `App` is the game's base class (the firmware's `app.App`). The Pi's
   `hosts/pi/platform_pi.py` replaces `pi_firmware.py` (no stand-in modules at all now;
   its LED ring goes dark when the game lets go, as the badge's pattern takes over). The
   badge is unchanged: all 59 frames pixel-identical; the release gains no file. Run on
   the badge (as .mpy) and played by Brian, 2026-11-21: LEDs, tilt, text entry, the
   keyboard pages, frame rate and leaving all OK.
