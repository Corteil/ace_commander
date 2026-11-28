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
   **Build 104** (2026-11-21, Brian: "is the planet horizon the same as the sun? the horizon
   just pops out of view"; after a first try with bands near the planet: "looks rough
   compared to the full planet, and it should not lose the bright ring", "should not see the
   transfer", "make the same for the sun as well"). The planet was always a circle round its
   centre's image (`_sphere`), dropped once the centre was under half a radius ahead, so
   skimming past it vanished. And a sphere in perspective isn't that circle: measured, 12
   pixels out at 40 pixels across near the side of the view, worse close by, so no switch
   between the circle and the true edge could go unseen. Now the sun and the planet are both
   drawn to their true edge unless tiny (`GLOBE_MIN` 6 pixels across in radius, where the
   circle is within a pixel): `cockpit._globe` works out each row's ends every `GLOBE_STEP`
   (4) rows (closer for a small one) and at the exact top and bottom, then fills one shape
   down the left ends and up the right (`_globe_draw`), and for the planet strokes its bright
   ring along the true edge, not along the screen's. The sun's build 99 bands went
   (`_sun_bands` is kept as a name), and `_covers` / `MAX_ARC`. Tests: `tests/test_game.py`
   checks the shapes against a ray through each pixel; `test_commander.py` checks the draw
   order by colour. Frames with the planet in view changed by its truer edge, nothing else.
   Speed, measured on the badge (the maths and calls, drawing not included): row by row
   everywhere took 20-35 ms, so wholly in front of you (the usual case) the edge is the exact
   ellipse it is, from tan(angle off ahead +- angular radius) and f sin(r) / sqrt(cos^2 -
   sin^2), its points from a table (`GLOBE_N` 48; 24 or 12 for a smaller one) worked out
   once for the fill and the ring; rows only close by (`GLOBE_ROWS` at most 28, over the rows
   it covers, constants once per frame). Then: a dot 0.7 ms, approaching 1.2 ms, big or
   huge 3 ms, skimming the planet 9 ms, close to the sun 17 ms (build 99's sun used about
   60 rows).
   Brian's play test: good, but the colours of the planet (and the sun) and space swapped
   now and then: the shapes reached up to 2700 pixels off the screen, where the badge's
   drawing overflows (no such fault on a PC; the old circles stopped at `MAX_ARC` 2000). Past
   `GLOBE_SAFE` (600) the ellipse is now cut to the screen plus `CLIP_M` (4) first
   (`_poly_clipped`: Sutherland-Hodgman for the fill, Liang-Barsky for each line of the ring,
   so the ring is never drawn along the cut); the largest coordinate in a 1500-position sweep
   is now 590. And (Brian) the altitude gauge near the planet: within `PLANET_GAUGE_ALT` (1)
   radius of its surface, AL alone, centred under the frame time (Brian), full at 1 radius, red in its last
   tenth (`_planet_gauge`). Played by Brian on the badge (as .mpy): all working, no colour
   swap, frame time about 50-56 ms near the planet.
   **Build 105** (2026-11-21, the platform layer's step 4 begun, `hosts/NEXT_SESSION.md` B4).
   New `layout.py` (imports nothing): `Layout`, how flight sits on the screen: the 3D view's
   and the tunnels' half sizes (`view_hw` / `view_hh`, `tunnel_hw` / `tunnel_hh`) and
   `view(ctx)`, `tunnel(ctx)`, `hud(ctx, g, ms, ring)` (True if it drew its own HUD; False:
   the round one) and `done(ctx)`. `cockpit.draw_world`, `draw_hud` and `draw_tunnel` ask
   `config.layout` (`layout.BADGE` when None) and set `VIEW_HW` / `VIEW_HH` from it, then put
   them back; the bodies are `_world`, `_hud`, `_draw_tunnel`, unchanged. `Game` keeps the
   stick last given to `step` (`stick_pitch`, `stick_roll`: two floats, no new object). The
   Pi's `hosts/pi/layout_pi.py` (`PiLayout`, following F10 and the window's size) replaced
   its hooks on the three functions and its wrapper round `Game.step`. Unchanged: all 59
   badge frames and five seeded Pi frames (both layouts, flight and tunnel, the roll and
   dive meters moving) pixel-identical. The release gains `layout.py`. Played by Brian on the
   badge: as before (the slower frames near the planet were the planet's own: build 106).
   **Build 106** (2026-11-21, Brian: build 105's frame time was 10-15 ms slower near the
   planet). It wasn't build 105: on the badge its layout wrappers cost under 1 ms, and an
   A/B flight with PERF lines (build 104's files put back, then 105 again) showed both at
   104-117 ms frames near the planet, about half of them 150-195 ms. Measured on the badge
   from the REPL: filling the planet's shape costs 1-1.5 ms; the cost was garbage, the
   floats of `_globe`'s rows (6-8 KB a frame near the planet), bringing the 103 ms
   collection every few frames (CLAUDE.md, firmware facts). Now `_globe` goes round the
   edge: the circle of directions at the sphere's angular radius round its centre's,
   `GLOBE_N` (96; 48 or 24 for a smaller one) from a table in whole numbers (`GLOBE_ONE`
   4096), each put on the screen with whole-number division; directions more than 60
   degrees off ahead (z under `GLOBE_ZMIN`, half) are cut off, where nothing is on the
   screen (its corners are 39 degrees off), so no point lands more than about 361 pixels out
   and nothing needs cutting to the screen (a first try cut just in front of you: points
   13000 pixels out, and cutting them back took 20 ms); where the edge passes the cut the
   shape is closed by an arc off the screen from the same table (`_far_arc`, the way round
   that is inside the sphere's image). The rows (`_globe_row`, `_globe_draw`) went; the
   ellipse case is the same code. `_poly` / `_poly_clipped` stroke only the lines that are
   the sphere's edge (`_EL`), in whole numbers (`_clip_side`, Cohen-Sutherland `_clip_seg`).
   On the badge near the planet: garbage 7.5 -> 1.4 KB a frame, about 7.5 ms. A sweep of 1500
   positions (down to 0.5% of a radius up, beside and behind you) matches a ray test
   everywhere. PERF lines now split the drawing: `(world, space, hud)`, space being the sun,
   planet and station (`cockpit.T_SPACE`, timed only while PERF lines are printed). Brian's
   flight: 62-73 ms frames near the planet (from 104-117), slow frames 5-7 per 60 as in plain
   flight; he saw about 50 ms at half the AL gauge and 60 closer. Still in the game near the
   planet: space 15-28 ms, against 7.5 ms for the planet at the REPL (not yet explained).
   **Build 107** (2026-11-21, the platform layer's step 4 finished). `Layout.dust_x`: how far
   the stardust spreads (500 on the badge); `cockpit.draw_world` gives it to the game
   (`Game.dust_x`, which `reset`, `enter` and `_rotate` use instead of the module's
   `DUST_X`), so the Pi no longer overwrites `game.DUST_X` (`PiLayout.fit`: 800 at 384
   wide). `Layout.leds`: False if no LEDs can be seen round the screen; `cockpit.draw_hud`
   then shows being hit on the screen (the round HUD's red ring, or the layout's own: the
   Pi's dashboard frame) whatever the device's LEDs do (`PiLayout`: True in the badge layout,
   which draws the ring, False in the Elite one). The shared Elite dashboard waits for the
   Tufty (step 5). Badge: all 59 frames pixel-identical. Seeded Pi frames: the stardust
   starts at 500 wide until the first frame (it was 800 from the start), so the specks and
   the random choices after them (the ships parked in the bay) differ. Played by Brian on the
   badge (as .mpy): fine.
   **Build 108** (2026-11-21, Brian: "a stutter in the space dust", "more notable at speed").
   Not build 107 (the stardust moves identically to 106, checked frame by frame on a PC).
   A diagnostic noting memory in use on every slow PERF frame showed all of them were
   collections (each right after one: ~452 KB in use, climbing to 470-510 between). The
   badge's heap grows only when a collection can't free enough and hands back empty areas
   (MicroPython's split heap), so with the game's ~450 KB it had ~60 KB of room: a 100-150 ms
   collection every 10-15 frames, the stardust jumping furthest at speed. A try that moved
   the game on by only an average frame after a long one ("no catch-up") didn't help and was
   dropped. `platform_tildagon.Platform._grow_heap`, once at start: if the heap has under
   `HEAP_ROOM` (512 KB) free and the system would keep `SYSTEM_KEEP` (300 KB), it allocates
   16 KB chunks until one makes the firmware add an area (seen as the system's largest
   free block shrinking), keeps that chunk as an anchor so the area isn't handed back, and
   lets the rest go. Prints a HEAP line with the PERF lines. On the badge: "HEAP 499 KB, 71
   free, system 1344: grown, now 558 free, system 848"; slow frames 0-1 per 60 (from 5-7),
   average frame 40-53 ms (from 46-58), each collection 165-180 ms, every ~4-5 s. Brian: the
   stutter is much better and the frame rate improved. The release is unchanged in files.
   **Build 109** (2026-11-21, the platform layer's step 5: the Tufty 2350 into `hosts/tufty/`).
   The Tufty port (`Corteil/tufty_ace_commarder`: a vendored game, 11 patches, firmware
   stand-ins, Badgeware v2) is now host files on the shared game, as the Pi's: platform,
   controls, layout + its dashboard (gauges following the ship: SP against `max_speed`, FU
   against `fuel_max`, a lamp per pylon), the ctx adapter brought to Badgeware v3, the host
   and app entry (`run(update)`), and `build_tufty.py`. Badgeware v3.1.1 on the Tufty is older
   than the picovector source in places; four crashes on the way, each fixed and then every
   call tried on the Tufty from the REPL: builtins found by plain name; `screen.text(s, x, y)`
   (a point was ignored: all text top left); `shape.custom` takes one list of `vec2`, not a
   list of outlines nor `array('f')`; `screen.circle(vec2, r)`. The PC stand-ins are as strict.
   On the Tufty (Brian): it works, frames about 60 ms (PERF: 59-64; world 13-17, of which space
   8-11, HUD 31-33: the dashboard; almost no slow frames: ~8 MB of RAM). Not yet tried: the Pad
   in detail, saving and loading, search and name entry (no keyboard: the keyboard page can't
   be typed into with the Pad).
   Then (Brian): a loading screen as the badge's (a module a frame, `host_tufty.STEPS`: the
   name, a bar, the module, LOADING where the menu line will be; LOAD FAILED and the reason
   instead of a crash), with one of the game's own ships tumbling on it (the Kestrel, from
   `original_ships`, loaded second), held at least `LOAD_HOLD` (3 s) to see it.
   `build_tufty.py --mpy` compiles every module but the two `__init__.py` with MicroPython
   1.29's mpy-cross (mpy v6.3, as the Tufty's `sys.implementation._mpy` 7942; installed in
   `~/.local/share/venvs/mpycross129`): 557 KB -> 215 KB, about 340 KB less on the TUFTY drive,
   and the game loads in 1.5 s (a LOADED line on serial).
   **Build 110** (2026-11-21, Brian: the Tufty's loading screen "should have a ship on it from
   one of our ships", then the icons, and "change the loader for each system"). `letters.py`
   draws the loading screens' ship (`load_ship`, `draw_ship`: the Kestrel, the game's own
   design in the Cobra Mk III role, turning, its name under it; `SHIP_Y`, `SHIP_SIZE`,
   `BAR_Y`), shared by the badge's `app.py` (which loads `original_ships` straight after
   `letters`; a build without them shows none), the Tufty's host (held 3 s) and the Pi's
   new loading screen (`run.Host.loading`, 3 s, any key skips it; not in the tests or with
   `--frames`). `tools/make_icons.py` draws the Kestrel as the icons: the Tufty's 24 x 24
   pixel art (`hosts/tufty/app/icon.png`) and the Pi's 256 x 256 (`hosts/pi/icon.png`,
   installed as `~/.local/share/icons/ace-commander.png`, the old one kept as
   `ace-commander-title-old.png`). On the badge the ship turns in steps (the loader draws
   only between imports). Not yet on the badge.
   **Build 111** (2026-11-21, Brian: the Tufty's own buttons "need to act as cursor keys, A
   left, B select, up up, down down; act as the joystick in flight, B = fire; should only work
   for combat practice"). Without a Pad (`host_tufty` finds none at start) the Tufty's five
   buttons use `controls_tufty.ALONE`: A / C / UP / DOWN are the joystick (cursor keys off the
   flight, steering in flight), B is the badge's C (select, fire), and `config.practice_only`
   (new, off on the badge and the Pi) leaves only COMBAT PRACTICE on the title screen
   (`ace.choices`). With a Pad, everything as before. Test: both, in
   `hosts/tufty/tests/test_tufty_host.py`. On the Tufty, not yet tried by Brian.
   **Build 112** (2026-11-21, Brian: "the buttons should be the same for both modes, the labels
   need renaming in badge only mode, auto missiles and more drops of missiles", then "the lock
   time should be increased and if the laser is firing the launch is delayed"). The Tufty's
   buttons are always `controls_tufty.TUFTY` (A / C / UP / DOWN the joystick, B the badge's C),
   Pad or not. Without the Pad the host also sets `config.auto_missiles` (new: `Game.auto_missile`
   fires one missile at each ship once locked, after `AUTO_LOCK_TIME` 4 s rather than
   `LOCK_TIME` 2 s, and not while the laser fires: it goes when you let go) and
   `config.practice_missile` 1.0 (new: `Game.pickup_missile`, every scooped canister in combat
   practice holds a missile; `PICKUP_MISSILE` 0.5 otherwise), and the hints name the Tufty's
   buttons (`ctx_tufty.relabel`, `controls_tufty.LABELS`: C is B, F is HOME). All off on the
   badge and the Pi. `tests/test_install.py` now writes the release as ustar, as `git archive`
   does (Python's default PAX added ~40 KB and tipped it past its 600 KB bar: the release is
   573 KB). Equipment upgrades for practice: to think about (Brian).
   **Build 113** (2026-11-21, Brian: option 1 of the upgrade ideas, "remove the screen LED
   effects for lasers all modes on the Tufty and Pi", "should refill the missiles if auto
   missiles are on", "the canister is indestructible and the next wave starts after a 5 second
   count down; include this for all versions"). Combat practice (`config.practice_upgrades`,
   on for every device): each wave cleared drops an upgrade canister (`Obj.upgrade`, drawn
   green on screen and radar, `cockpit.UPGRADE_RGB`; the laser passes it by, the bomb already
   spared canisters) and the next wave waits `WAVE_WAIT` (5 s), "WAVE n IN 5..1" then "WAVE n"
   (`Game.wave_wait`, nobody new meanwhile; ships already there stay). Scooped, it fits the next
   of `UPGRADES` (beam laser, energy unit, military laser, energy bomb), then a used bomb
   back, else full shields (`Game._upgrade`); with `auto_missile` it also fills the missile
   rack. `config.laser_leds` (off on the Tufty and the Pi): your laser no longer colours the
   LEDs (the Tufty's border, the Pi's drawn ring); the badge keeps it. The badge's practice
   changes too (upgrades, countdown). Then (Brian) the canister appears just ahead,
   `UPGRADE_AHEAD` 400 (was 1200), so flying on picks it up; and the countdown starts only
   once it is collected (`Game.wave_hold`, "UPGRADE AHEAD"; missed, it goes after
   `UPGRADE_WAIT` 20 s and the countdown starts anyway).
   **Build 114** (2026-11-21, Brian: "labels should reflect local button names, auto target
   time 2 s, increases with level, need a way to change speed in the game, press two buttons
   at the same time?", and HOME leaves for the app select screen). The auto-missile lock is
   `AUTO_LOCK_TIMES` by level (EASY 2 s, NORMAL 3, HARD 4). On the Tufty two buttons together
   are the badge's F and E (`controls_tufty.PAIRS`): A + C speeds up (and is "back" off the
   flight), UP + DOWN slows down; and the hints name the Tufty's buttons with or without the
   Pad (`LABELS`: C is B, F is A+C, E is UP+DOWN; HOME no longer, as it leaves the app). A
   button pressed a moment before its pair counts alone for that moment.
   **Build 115** (2026-11-21, Brian: "add gamepad off in debug menu and add debug.txt so the
   debug menu works"). DEBUG > DISPLAY > GAMEPAD: ON / OFF, shown when the platform has a
   `gamepad` setting (`platform_tildagon`'s interface: optional `gamepad` + `set_gamepad`):
   the Tufty's, when a Pad was found at start. OFF plays as without the Pad (practice only,
   auto missiles, a missile in every canister: `host_tufty.set_gamepad` / `_alone`; in a
   flight at once), ON as with it. `/state/ace_commander/debug.txt` made on the Tufty, so its
   DEBUG menu shows (`ace._debug_wanted`); that folder already held its save and options.
   **Build 116** (2026-11-21, Brian: "change the speed on the Tufty: A+B to slow down and B+C
   to speed up", "only in flight mode"). `controls_tufty.PAIRS`: A + B the badge's E (slower),
   B + C its F (faster), in flight only (not paused); off the flight every button counts at
   once, alone. In flight B alone waits `PAIR_WAIT` (60 ms, on the host's frame clock) for its
   partner, so an uneven pair doesn't fire first. The hints: `LABELS` in flight (C is B, F is
   B+C, E is A+B), `LABELS_OFF` off it (C is B).
   **Build 117** (Brian: "A and C to go back has stopped working, and F = back"): off the
   flight A + C is the badge's F, back (`PAIRS_OFF`; on the title screen that leaves the game,
   as F does). Any button in the current pairs, held alone, waits `PAIR_WAIT` for its partner
   (`host_tufty.waits`), so an uneven A + C doesn't move the cursor first. Hints off the
   flight: C is B, F is A+C.
   **Build 118** (Brian: "hold A + C to toggle up/down buttons to change speed"): in flight A + C
   held is a shift (`controls_tufty.SHIFT`, `SHIFTED`): UP then the badge's F (faster), DOWN its
   E (slower), no roll or pitch meanwhile; A + B / B + C are gone, so B alone fires at once.
   Off the flight A + C is still back. A or C alone waits `PAIR_WAIT`. Hints in flight: F is
   A+C+UP, E is A+C+DOWN.
   **Build 119** (Brian: "hold A + C will turn the up and down buttons into speed control
   buttons"): a toggle, not a shift. In flight each press of A + C switches UP / DOWN between
   pitch and speed (`host_tufty.speed_mode`; "UP/DOWN: SPEED" / "UP/DOWN: PITCH" said), staying
   so once let go; a new flight starts in pitch. Off the flight A + C is back.
   **Build 120** (Brian: "both up/down need to be held for the pause menu"): in flight, paused
   or not, UP + DOWN held is the badge's A (`controls_tufty.MENU_PAIR`, `MENU`): the pause menu,
   and closing it; UP or DOWN alone waits `PAIR_WAIT` there. In the menu UP / DOWN move, B
   chooses, A + C goes back.
   **Build 121** (Brian: "the gamepad should still operate outside of combat practice"): DEBUG >
   GAMEPAD OFF now plays only combat practice as without the Pad (`host_tufty.pad_off`: the Pad
   ignored in a practice flight, auto missiles, a missile in every canister); the Pad works
   everywhere else and the title keeps the whole game (only a Tufty with no Pad at all is
   practice only). Auto missiles are practice only on every device (`ace._start_flight`).
   **Build 122** (Brian: "sort out text entry for the Tufty: up/down change letter, B selects
   it, C backspace, A enter"). `hosts/tufty/dialog_tufty.py`, `LetterDialog`: what
   `platform_tufty.text_dialog` now gives the game (the badge's firmware TextDialog interface:
   `.text`, `.message`, `._result`, `draw`), for the Galactic chart's search and the commander's
   name. UP / DOWN go through `LETTERS` (space, A-Z, 0-9, "-"; held, they repeat), B adds the
   letter, C deletes the last, A is done (nothing typed: no match / the suggested name). While
   it is open `host_tufty._typing` gives it the Tufty's buttons and the game none. The letter
   stays where it was after adding.
   Then (Brian: "select letter, cursor moves right when selected"): drawn as a row of
   `MAX_LEN` places (`SLOT` 12 px) with the cursor's place highlighted; B keeps the letter and
   the cursor moves right (the same letter there to start from); C moves it back onto the
   last letter to change it.
   **Build 123** (Brian: "buttons for the gamepad so it can be used as well"): typing on the
   Qw/ST Pad too (`controls_tufty.PAD_TYPING`): the D-pad's up / down the letter, A or right
   keeps it, B or left goes back, + is done.
   **Build 124** (Brian: "also build for the Pi version when using the game pad, plus for the
   badge as an option"). The letter picker is the game's own now, `picker.py` (`LetterPicker`;
   the Tufty's `dialog_tufty` just makes one). Where the game drives it (`driven`:
   `ace._drive_picker`, from its controls): the joystick's up / down the letter (held, it
   repeats), C or right keeps it, left goes back, A done, F cancels; while it is open the game
   doesn't clear its controls (so holding works), only when it closes. The badge: Options >
   TEXT ENTRY: BADGE / PICKER (`use_picker`, options.json "picker"; `platform_tildagon`'s
   `picker_choice` and `text_dialog`); BADGE (its firmware dialog) stays the default. The Pi:
   with the game pad used last (`platform_pi.pad_in_use`, from `run.Host.pad_last`) text entry
   is the picker (pad: D-pad up / down, south or right keep, left back, Start done, east
   cancel), with the keyboard its typing pages as before. Not yet on the badge.
   **Build 125** (Brian: "button on pad to enter search, maybe Y?"): the Tufty's Qw/ST Pad, off
   the flight, has Y as the badge's B too (`controls_tufty.PAD_MAP_OFF`): the search on the
   Galactic chart (cursor on, C, first), the next tab elsewhere; in flight Y stays E (slower).
   The Pi pad's Y already was the badge's B.
   **Build 126** (Brian: "hints must use local buttons / keys names"). The Tufty's hints name
   whatever was pressed last (`host_tufty.pad_last`): the Pad's buttons (`PAD_LABELS` in
   flight: A is +, B is -, C is A, D is B, E is Y, F is X; `PAD_LABELS_OFF`: B is Y) or the
   Tufty's own (`LABELS`, `LABELS_OFF`). The Pi's keyboard in flight, where it is Elite's keys:
   C is ENTER, F is ESC, A is P (`run.KEY_LABELS_FLIGHT`); off the flight its A-F are the
   badge's buttons and the hints stay; the Pi pad's names as before (`pad_pi.labels`). The
   badge's hints were always its own.
   **Build 127** (Brian: "the letter picker does not update its hints on the Tufty"): the
   picker's own two hint lines can come from the host (`LetterPicker.hints`); the Tufty's sets
   them each frame by what was pressed last (`controls_tufty.TYPING_HINTS` / `PAD_TYPING_HINTS`).
   **Build 128** (Brian: "the + launches the ship when exiting the letter picker"): the press
   that closes the Tufty's picker was still held next frame and counted as the badge's A
   (launch when docked). Now any Tufty button or Pad button held when it closes is ignored
   until let go (`host_tufty.stale` / `stale_pad`).
   **Build 129** (Brian: "hints should reflect the selected controls, there's enough room in the
   Pi / Tufty versions to show hints on most screens"). `config.more_hints` (the Tufty; the
   Pi's Elite layout, set in `run.Host._fit`; off on the badge and the Pi's round badge
   layout, which have no room): a hint line on both charts (`chart._hint`: docked before C
   "C: cursor  < > screens  F: status", then "C: target  D: data  B: find  F: back", the
   local chart without B; its texts move up a little) and on the title screen ("< > choose
   C: select"). The Tufty's own buttons name "< >" as "A/C" (`LABELS["< >"]`, `relabel`).
   **Build 130** (Brian: "the labels on the Pi picker don't match when the gamepad is being
   used"): the picker's own hints had no colons ("C next"), so `relabel` left them; now
   "C: next", "A: done", "F: cancel", which the Pi pad names A, START and B.
   **Build 131** (Brian: "the hints clash with the menu on Options on the badge"): with TEXT
   ENTRY, Options has nine lines (docked and the title's), one more than fits above the hints.
   `cockpit.menu_lines` shows eight and scrolls with the selection, a small bar above / below
   when there is more.
   **Build 132, release 0.4.0** (Brian: "how do we sort out the releases for the Pi and Tufty
   versions? EMF badge, next version number and compiled files to reduce the size"). The app
   store installs GitHub's tarball of the tagged commit (`firmware_apps/app_store.py`:
   `install_app`, from the listing's `tarballUrl`), so a compiled release must be committed:
   `tools/make_release.py V [--commit] [--push]` builds the badge app compiled (no Elite
   files) onto the `release` branch, one commit a release, tagged there; main stays source.
   Tarball 230 KB against 584 KB of source (limit 600 KB). The store's update writes over the
   old folder and deletes nothing, so 0.3.2's .py would stay and be imported before the new
   .mpy: `app.py` (still source) now removes every x.py with an x.mpy beside it before
   importing anything. Checked on the badge: v0.3.2 installed store-style into
   /apps/Corteil_ace_commander, 0.4.0's tarball written over it, the loader removed the 23
   old .py files. Also built: `ace_commander-tufty-V.zip` (build_tufty --mpy, unzip into the
   TUFTY drive's apps/) and `ace_commander-pi-V.zip` (source with hosts/pi, README_PI.txt),
   attached to the GitHub release. Compiled code needs the badge's MicroPython (1.28's mpy
   format): a firmware with another would need a new release.
   **Build 133** (Brian: "Hardcore mode, auto save switched off. Add a save option to the docking
   menu"). A Hardcore commander isn't saved by itself any more: not on docking, launching,
   leaving for the title, or a mission's news (`ace._auto_write`; `rules.manual_save` names it).
   Docked, Options has SAVE COMMANDER at the top (C saves; it reads "SAVE COMMANDER: SAVED"
   until Options is left). Being destroyed goes back to the last save, as before. Still saved
   in Hardcore: a new commander as it's made, and the settings and DEBUG changes that write
   one field into the last save (`_write_setting`). Standard mode unchanged. Test in
   `tests/test_hardcore.py`.
   **Build 134** (Brian couldn't find SAVE COMMANDER: his "Hardcore" commander was saved with
   HARDCORE off; on NEW COMMANDER C starts from any line, so C on HARDCORE: OFF started a
   standard one). The hint there reads "< > change   C: start" on LEVEL and HARDCORE, and the
   HARDCORE note "ECM, missiles, saving by hand" (practice's page keeps "ECM by hand, armed
   missiles": practice saves nothing).
   **Build 135** (Brian: "when the game is saved the menu option should say COMMANDER SAVED"):
   the line reads COMMANDER SAVED after C, until Options is left (C there saves again).
   **Release 0.4.1** (2026-11-22): builds 133-135 (Hardcore saving by hand), by
   `tools/make_release.py 0.4.1 --push`.
   **Build 136** (Brian: "on the systems where tilt steer is impossible just show the pitch swapped
   status", "also remove the background box around the selected option"). Without a tilt sensor
   (the Pi, the Tufty, a badge whose sensor failed) Settings / Options have no STEER line and
   CONTROLS becomes PITCH: NORMAL / SWAPPED (bit 1 of `tilt_flip`; a roll flip left from tilt
   isn't used then). The chosen line on menu pages (Options, the pause menu and Settings, the
   DEBUG pages, NEW COMMANDER, practice) is green text without the box behind it; the market,
   Equip and shipyard lists keep their row highlight.
   **Build 137** (Brian: "the tractor beam was on at the space station with Hardcore on"). A
   launch carries on the `Game` from the last flight and rebuilt its rules only when the level
   or career changed; a new commander docks at once (career again), so a new Hardcore commander
   flew with a standard one's rules: ASSISTED docking, the tractor beam. `_start_flight` now
   starts afresh when HARDCORE differs from the last flight's, for a commander as for practice.
   Test in `tests/test_hardcore.py`.
   **Build 138** (Brian: "when a new commander is created all flags should be reset").
   `ace._forget_flight()` on NEW COMMANDER: the game left from before is dropped (its rules,
   docking style, ship, kills; a part-way practice fight too), and the target, countdown,
   witchspace, open screen / chart / search, banked kills and cash, last save, DEBUG page
   and LED effects are cleared. Kept: the settings (options.json), the galaxy (remade if it
   differs), the tilt sensor's level. Test in `tests/test_hardcore.py`. Then (Brian: "the galaxy
   map should be reset to the first galaxy as well"): the galaxy is dropped too and made afresh
   for the new commander, galaxy 1.
   **Build 139** (Brian: "the radar grid should be brighter on the badge"): the round HUD's radar
   ellipse and cross, and the compass ring beside it, are `cockpit.RADAR_GRID`, was 0.38, 0.38,
   0.48. Then ("they should be the same colour as the Tufty and Pi versions"): near white, the
   Pi dashboard's `SCAN_RGB` (0.85, 0.85, 0.9), and the Tufty's scanner and compass, which were
   still the dim grey, use `RADAR_GRID` too.
   **Release 0.4.2** (2026-11-22): builds 136-139, by `tools/make_release.py 0.4.2 --push`.
   **Build 140, sound** (Brian: "add sound"; the badge has no speaker and the Tufty 2350 no
   buzzer, so a SparkFun Qwiic Buzzer on I2C for both, or I2S amp hexpansions later). One table,
   `sfx.py`: each sound a short run of (Hz, ms) steps (0 a rest, `NOISE` a noise burst) with a
   priority. The game asks by name (`Game.sfx`, a list `Game.sounds` that `ace._sounds` hands to
   the device each frame, flying and not paused): laser, overheat, hurt, explode, die, lock,
   missile, incoming, ecm, bomb, tick (hyperspace and wave countdowns), jump, scoop, upgrade,
   wave, tractor; ace.py plays launch and dock. `buzzer.py`: the Qwiic Buzzer (0x34, ID 0x5E;
   register 0x03 frequency / volume / duration, 0x08 on) stepped each frame, never blocking, a
   lower-priority sound not cutting in. The badge looks on the six hexpansion ports' I2C buses
   at start (`platform_tildagon._find_buzzer`), the Tufty on its Qw/ST port (`host_tufty._buzzer`).
   The Pi: `hosts/pi/sound_pi.py` makes each sound once as square waves and noise for pygame's
   mixer, with `--sound` (added to both desktop shortcuts). Options > SOUND: ON / OFF
   (options.json "sound") only where there is sound. Platform interface: optional `sound_ok`,
   `sound(name)`, `sound_step()`. Tests: `tests/test_sound.py` (a stand-in I2C bus), the Pi and
   Tufty host tests. **Not tried on a real buzzer** (Brian hasn't got one yet).
   **Build 141** (Brian: "how close are the sounds to Elite's?", then "match Elite"). They were
   invented; now, with Elite's data, Elite's own. `tools/import_sfx.py CLONE` reads the SFX table
   (main source) and the four envelopes E% (loader), plays each SOUND on a model of the BBC
   Micro's sound system (envelopes stepped each centisecond; pitch 53 = middle C, 4 a semitone;
   the noise channel's rates, and rate 3 following channel 1, which Elite's death sound sweeps
   unheard to colour the noise) and writes `elite_sfx.py` (gitignored, Elite-derived; with
   `build_mpy --elite` / `build_tufty --elite` if made, never in a release: `DERIVED`). Events
   as the original calls them: laser 0, hit and explode 24 (EXNO), hurt 8, crash and die 16+24
   (EXNO3: a collision, hit with no shields), lock 32 (BEEP), unarm 40, missile / incoming /
   launch 48, jump 56 (LL164), ecm 64; the rest silent, as in Elite. `sfx.py` uses it when
   `content.OWN` is False, else the game's own (now with hit, crash, unarm too). Format: a sound
   is (priority, part, ...), parts played together; steps (Hz, ms[, level 0-126]), negative Hz
   noise at that rate; `CHANNELS` (the Pi restarts a sound on its channel, Elite's flush). The
   buzzer plays the first part, levels as its volume 1-4, and skips steps shorter than a frame
   to keep time; the badge checks for the buzzer before importing it (heap).
   **Build 142** (Brian: "the sounds should be as close to Elite as possible in both games; add
   the missing sounds and warnings"). Every NOISE / BEEP / EXNO call in both halves of the
   source, flight and docked, now has its event: `beep` (32, short high: FUEL SCOOPS ON and
   ENERGY LOW, whose messages hold a {beep}, and docked after each trade message or refusal,
   Elite's dn / dn2: `Docked.msg_n` counts them), `boop` (40, long low: the jump drive refused,
   WA1, once a second while speed is held up at full; a search that finds nothing, HME6),
   `crash` (EXNO3) also for a missile exploding (TA34) and a canister lost scooping (MA59).
   New warning ENERGY LOW (Elite: energy under 50 of 255, checked every 32 main loops): the
   hull under `ENERGY_LOW` (20), every `LOW_EVERY` (2 s). The game's own sounds (no
   elite_sfx.py, or DATA: OWN, so the store release) were rewritten for the same events in
   Elite's style, by ear, not taken from it (a repeating low-then-falling zap, a shield warble,
   noise bursts, 1.9 kHz and 150 Hz beeps), on the same channel layout (`OWN_CHANNELS`), and
   silent where Elite is (countdowns, scooping, docking, the bomb, practice's waves and
   upgrades). `test_install` now measures the compiled release tarball (with the badge's
   mpy-cross), not the source.
   **Build 143** (Brian: "the fuel scoops should stop filling above a fixed point above the sun,
   even if the cabin temperature is high"; "also add a fuel full message"). Suns are 11,000 to
   28,000 units in radius, so the heat band (cabin 224, 1.3 radii) reached 3,400 to 8,300 units
   above the surface. Now the scoops also need to be within `SCOOP_ALT` (2000 units) of the
   surface (`Game._sun`), marked in yellow on the AL gauge (`cockpit.SCOOP_ALT`, the same). With
   a full tank in the band: FUEL FULL, once a pass (`Game.full_said`). DEBUG > TO THE SUN now
   passes half SCOOP_ALT above the surface. Tests in test_game, test_commander, test_leds; a
   market check in test_commander made safe for a stock of exactly 20 (NONE LEFT).
   **Build 144** (Brian: "the mass lock should only bleep once when held in the same mass field,
   and can sound if a new mass field stops the jump"). `Game._blocker` names what keeps the jump
   drive off: "station" (its safe zone), "planet" / "sun" (mass lock), "heat", "ships"; the boop
   plays when that changes to something new while speed is held up at full (`Game.refused`),
   and letting go resets it. (Was: once a second while held.)
   **Release 0.4.3** (2026-11-22): builds 140-144 (sound, ENERGY LOW, the fixed scooping height,
   FUEL FULL); the Pi zip's README names --sound.
   **Build 145** (Brian, 2026-11-23: a MAX98357A I2S amp on port 2; "can this be used for
   sound for ace instead of the buzzer, remove the buzzer code"; "needs a volume control and
   mute on the options menu"; "make it 11"). Built from `plans/I2S_SOUND.md`. `i2s_sound.py`:
   `Synth` plays `sfx.py`'s sounds as they go (nothing stored), one voice per part (at most 4;
   the lowest priority goes first), a sound restarting its channel (`sfx.CHANNELS`), square waves
   from a 16.16 phase and noise from xorshift, mixed into one reused 512-sample buffer, 11025 Hz
   mono 16 bit. Each frame `step()` writes only what plays before `LEAD_MS` (120 ms) from now, so
   the I2S buffer (`IBUF` 8 KB, ~370 ms) is never full and the frame doesn't wait; after a long
   frame it starts again from now (the gap is silence); nothing is written while idle (the
   firmware's I2S has `auto_clear`: it sends silence when it runs dry). Inner loops are viper on
   the badge, plain Python on a PC (same numbers). `open_i2s(port)` as BadgeRadio: I2S 0 on the
   port's HS1 BCLK, HS2 LRC, HS3 DIN, opened small and closed first. `platform_tildagon`: sound
   whenever `machine.I2S` exists (an amp can't be detected), opened on the first sound, closed in
   `minimise` (so BadgeRadio can have it); a port that won't open stays silent until SOUND PORT
   changes. Options: SOUND: ON / MUTED (muting cuts off what plays: `sound_stop`), VOLUME: 1-11
   (`sfx.VOLUMES`, about 4 dB a step, 11 one past 10; stops at the ends; beeps at the new
   level), SOUND PORT: 1-6 (wraps; beeps), the last two hidden while muted; saved as "volume" and
   "sound_port". The Pi has VOLUME too (sounds made at the loudest, channels turned down).
   **The Qwiic buzzer is gone** (`buzzer.py`, `_find_buzzer`, the Tufty's `_buzzer`): the Tufty
   has no sound now (no free I2S pins). Tests: `test_sound.py` (pitch, levels, rests, mixing,
   noise, voices, channels, keeping ahead, every sound of both tables, VOLUME, MUTED, SOUND
   PORT), the Pi and Tufty host tests. **PC only: not yet heard on the badge**; the frame-time
   cost of the viper loops isn't measured.
   Build 145 on the badge (2026-11-23, MAX98357A on port 2, played from the REPL): each 551-sample
   write first blocked as long as it plays (46 ms): the firmware keeps 16-bit stereo in DMA
   (`IBUF` 8 KB = ~186 ms) and right after opening all of it is in use, so the first sound cost
   43-67 ms. Now the I2S opens at start with SOUND ON (`Platform.sound_warm`) and `Synth.settle()`
   writes nothing for `SETTLE_MS` (250 ms) after opening; the buffer clear is viper too
   (`_clear`). Measured: a sound's first frame 0.6-1.9 ms (the lead written), then 0.3-0.7 ms a
   frame; about 60 bytes of garbage a frame while playing (memoryview slices, voices).
   **Build 146** (Brian, 2026-11-23: "are they the same sounds on the pi build?" — "yes and add
   back sound for the tufty build"; "use the sparkfun buzzer or the arduino modulino buzzer").
   The Pi now makes its sounds with the badge's synthesiser (`i2s_sound.Synth.render`, at the
   mixer's 22050 Hz and VOLUME 11, then turned down by VOLUME): exact pitches (its own square
   waves rounded the period to whole samples: 1838-2100 Hz all came out 2205 Hz, 700 Hz 735),
   the same noise and mixing; 15 sounds in 0.13 s at start on the Pi 5. `test_sound` checks
   `render` gives the very samples the badge streams. The Tufty's sound is back as a host file,
   `hosts/tufty/buzzer_tufty.py` (in `HOST_FILES`; `i2s_sound.py` is `BADGE_ONLY` now): the
   build 140 SparkFun Qwiic Buzzer (0x34) or, if not, an **Arduino Modulino Buzzer** (7-bit
   0x1E, Arduino's 0x3C; from arduino-modulino-mpy: one `writeto` of 8 bytes a tone, frequency
   then ms, each 32-bit little-endian, all zeros to stop; no volume; nothing under 180 Hz, so
   lower notes are raised to 180), on the Qw/ST port (`host_tufty._buzzer`, `open_buzzer`).
   VOLUME 1-11 maps onto the SparkFun's 1-4 (8 gives its old default 3); MUTED stops it. Tests:
   `hosts/tufty/tests/test_buzzer_tufty.py` (new, in run_all), the Tufty host test. **Neither
   buzzer tried for real** (PC only).
   **Build 147** (Brian, 2026-11-23, on the Tufty with the Modulino: "is there no way for the
   static sound on the tufty"). Seven test bursts from the REPL (a new random pitch every 20, 5,
   3, 2 or 1 ms; 250-1333 Hz or 200-8000 Hz): Brian couldn't tell 3 ms from 2 ms, and the wide
   range "sounded like bleeps with static". So noise steps on a Tufty buzzer now change pitch
   every `NOISE_FAST` (3 ms) from a `machine.Timer` (soft callback, `Buzzer._tick`), over the
   same pitches as before (rate / 16 to rate / 3, 80-4000 Hz); on only during a noise step
   (`_slow` turns it off at a tone, a rest, the end, stop). Without a timer (a PC) the old
   way: a new pitch each frame at most (`NOISE_STEP`). Both buzzers. About 333 I2C writes a
   second while noise plays (each ~0.25 ms). Tests in test_buzzer_tufty.
   **Release 0.4.4** (2026-11-23): builds 145-147 (I2S sound on the badge with VOLUME 1-11 and
   MUTED, the Pi's sounds made as the badge's, the Tufty's SparkFun or Modulino buzzer).
   **Release 0.5.0** (2026-11-25): DUEL, two badges over ESP-NOW (plans/MULTIPLAYER.md): a
   lobby with commander names and ship colours, one player hosts and starts; lasers, missiles
   and ramming do damage, the E.C.M. by hand (B); rounds with a fresh loadout and the score;
   either leaving ends it. The Pi duels over UDP with --duel. Key guides for the Pi and Tufty
   in their zips.
   **Build 148** (Brian, 2026-11-25: "make it support up to four players. Modes Free for all,
   teams and capture the flag. Protect the convoy ship from pirates"; capture the flag: "Two
   rings in teams colours set distance apart ... fly through the ring then changes colour and
   you must fly back to your ring and pass though to score. Destroyed ship spawn close/behind
   to their home ring after a set time"; the convoy "could be coop or p v p. Convoy ship will
   need to be a new large design"). DUEL on the title screen is now **MULTIPLAYER**; the host
   picks the mode (left / right on HOSTING) and takes up to three guests (`duel.MAX_PLAYERS`);
   slot 0 is the host, then the guests in the order they joined; in team modes even slots are
   RED and odd BLUE. Modes (`duel.MODE_NAMES`): DUEL (as before: two, rounds by C), FREE FOR
   ALL (`FFA_WIN` 10 kills), TEAMS (`TEAM_WIN` 10, no friendly fire: a teammate is
   `Obj.friend`, not locked or hit), CAPTURE FLAG (rings `RING_Z` 5000 either side of the
   middle, `RING_PASS` 460 to count as through; a ring goes grey while its flag is away;
   `CTF_WIN` 3; a carrier destroyed: the flag goes home; the compass points at the ring to
   fly to), CONVOY CO-OP (1-4 players guard the new BULK FREIGHTER, `convoy_ship.py` from
   `tools/make_convoy_ship.py`, on a straight run of `CONVOY_TIME` 150 s to a station; pirate
   waves every `WAVE_EVERY` 25 s) and CONVOY RAID (red defends, blue raids; the pirates are
   blue's friends). Except a duel, destroyed ships come back after `RESPAWN` 5 s at their
   start (`spawn_pose`; behind the home ring in Capture Flag, by the convoy for defenders); a
   result shows `RESULT_FOR` 10 s, then the next match. **The host decides** the score, the
   flags, the convoy and the pirates (`STATE` 4 a second and on a change; `CLAIM` for a ring
   passed, `KILLED` with who did it, the last hit within 10 s); the pirates are ordinary ships
   in the host's game (`Game._pick_prey` asks `Duel.prey_for`: the convoy, the host or another
   player), sent as `NPCS` 10 a second (22 bytes each, up to 10 in a packet: 224 bytes, inside
   ESP-NOW's 250); the others draw them as kind "npc" and send hits (`NPC_HIT`) and missiles
   (`MISSILE` with `NPC_BIT`) to the host. A pirate hitting another player sends that player a
   `HIT` (who: `NPC_SRC`). HIT and MISSILE now name their target's slot. The host respawning
   keeps its pirates where they were in the shared world. Leaving: the host ends it for all; a
   guest drops out, and it ends when nobody else is left (CONVOY CO-OP goes on alone). HUD: the
   score (or the convoy's energy and time left) along the top (`cockpit.draw_net_line`, the Pi
   and Tufty dashboards too); the compass (`cockpit.compass_target`) on all three. Tests:
   `tests/test_multiplayer.py` (new, in run_all; four Games on a pretend radio), test_duel and
   test_duel_combat updated. **PC only: not yet on badges** (and nothing yet known of the
   frame time with four ships, the convoy close up (92 lines, 6 parts) or 8 pirates).
   **Build 149** (Brian, 2026-11-25: "Not sure about the ship design, have to see it in the
   game ... yes add it to the ship viewer"). The convoy's ship is last in the Ship Viewer
   (`viewer.with_convoy`), and is called BULK FREIGHTER (the game's own ships already have a
   HAULER). The viewer now draws a ship made of convex parts as the game does: back to front,
   a nearer part blacking out what is behind it (`viewer._fill_hull`; the Halo and the freighter
   gain hidden lines there). `test_app`'s viewer check counts 32. Not yet seen on the badge.
   **Build 150** (Brian, 2026-11-25: "The convoy game should have a p v p mode as well" (it
   had: CONVOY RAID) ... "add team choice in the lobby and a no-pirates option. The defenders
   should not be overwhelmed"). Team modes: each player picks red / blue (in a raid DEFEND /
   RAID) with left / right, the host on its HOSTING page's YOU line (up / down picks MODE,
   YOU, PIRATES); anyone who hasn't picked (`NO_TEAM`) joins the smaller team, red if level
   (`Duel.lobby_teams`). HELLO grew to 52 bytes: the team asked for, the host's options
   (`OPT_PIRATES`) and each slot's team, which START fixes (`Duel.teams`, `Duel.team_of`).
   It can start only with a player on each team. Teammates start side by side (`MATE_X`).
   CONVOY RAID: PIRATES ON / OFF (the host's; off, none come). Balance: defenders come back
   after `DEFEND_RESPAWN` 3 s; each raider more than there are defenders adds
   `RAID_EXTRA_RESPAWN` 2 s to the raiders' wait and a defender's worth of energy to the
   convoy (1 v 3: three times `CONVOY_ENERGY`); a pirate wave is 1 + defenders - raiders
   ships (none if the raiders are more). Tests in test_multiplayer (team choice, 1 v 3, 2 v 1,
   pirates off, the app's TEAM line). PC only.
   **Build 151** (Brian, 2026-11-25: "Remove the none ship items from the view. In combat mode
   the wave and kills overlap the view labels. The pirates skill level should be selectable.
   In the loading scene you can see though ships. Also can see lines that should be hidden
   when the station is in view and on the loading and start screens"). The Ship Viewer leaves
   out what isn't a ship (`viewer.NOT_SHIPS`: canister, plate, the three rocks, the missile;
   26 entries with the freighter; stations and the escape pod stay). The view label (REAR
   VIEW...) moved below the practice score / multiplayer line: y -84 on the round screen, 26
   below the top of a dashboard layout's view (the Pi's own label went; the Tufty's was off
   its view). Multiplayer: PIRATES on the HOSTING page is their skill, EASY / NORMAL / HARD
   (and OFF in a raid; CONVOY CO-OP has the line too), the game's level (`game.LEVELS`) set on
   the host's game (`Duel.pirate_level`, options bits 1-2). Hidden lines: the loading screen's
   ship drew every line; the title screen and Ship Viewer judged a face by its normal alone, as
   if from far off, so close up the far side showed. All three now judge from a point on the
   face, in perspective, as cockpit.draw_ship does (`letters.face_dots`: n.v + distance x the
   turned normal's z < 0), and draw ships made of parts back to front (`letters.draw_edges`,
   `fill_hull`). In flight, ships beyond the station are drawn before it and it is drawn solid
   over them (`cockpit._draw_space(..., g)`, `_draw_obj`), and it is solid wherever it is over
   the planet's or sun's filled disc (before: only over the planet's outline). PC renders only.
   **Build 152** (Brian, 2026-11-25: "Can see the spokes line entering the wheel on the halo
   render"). The Halo (the game's own DODO) had its ring's six pieces black out what is behind
   them only side-on (`HIDES_SIDE_ON`), so seen at a slant a spoke's end was drawn across a
   nearer piece of the ring. Now `HIDES_ALWAYS` (tools/make_original_ships.py, original_ships.py
   remade): a piece nearer than the middle hides what is behind it, in flight, on the title
   screen and in the Ship Viewer. Seen dead face-on the spokes still meet the ring's inner wall
   in its middle, which is right (and no piece is nearer than the middle then, so none fills).
   Cost: up to three more fills a frame close to a Halo (about 2 ms each on the badge, from the
   earlier measurements); Elite's Dodo is one convex shape and is unchanged. PC renders only.
   **Build 153** (Brian, 2026-11-25: "build it, two new modes, 1 and 2 should be selectable
   all 4 station types depending if elite data loaded, if more than a set number of pirate
   ships dock or the station is destroyed game over"). STATION CO-OP (1-4, everyone defends)
   and STATION RAID (red defends, blue raids; the convoy raid's team choice, PIRATES setting
   and help for outnumbered defenders). The station sits at the world's middle, slot to +z;
   `STATION_ENERGY` 2500. The host picks on HOSTING: STATION (`duel.STATIONS`: the game's
   own Drum and Halo, Elite's Coriolis and Dodo only when `ship_data.py` imports;
   `available_stations`; a guest without Elite's data draws the game's own of the same role,
   `station_blueprint`), TIME (`STATION_TIMES` 2 / 3 / 5 minutes, 3 by default) and WAVES
   (STEADY, or GROWING: one more pirate a wave each `GROW_EVERY` 60 s). Options byte: bit 0
   pirates, 1-2 skill, 3-4 time, 5 growing, 6-7 station. Pirates come from every side; every
   other one makes to dock (state "trade", `net_prey` "dock": `Game._think`'s trading
   steering towards `Duel.dock_target`; reaching the station sets `Obj.docked`). The host
   counts dockings (`Duel.docked`, in STATE, now 23 bytes; NPCS flag `DOCKED`: gone without an
   explosion), says PIRATE DOCKED n/3. Lost when the station is destroyed or more than
   `DOCK_LIMIT` (3) have docked (the 4th); held for the time: won (STATION HELD / STATION
   LOST, and PIRATES DOCKED n when that lost it). A docker shot turns to fight. HUD: STATION
   energy and time on the top line, DOCKED n/3 under it (red at 3; `Duel.hud` entries can
   now have a second line), the view label below that. Tests in test_multiplayer (options to
   the guest, the station for both, dockers closing in and docking, the limit, time up,
   destroyed, growing waves, the raid, Elite's four with a stand-in ship_data). PC only.
   **Build 154** (Brian, 2026-11-25: "the shield must be destroyed before a pirate ship can
   dock"). The station modes' station has a shield (`STATION_SHIELD` 1000; in a raid scaled as
   its energy is). The host's `Duel._shield_step` sees each frame's hits as the station's lost
   energy (whoever made them: the host's pirates, lasers, missiles, the guests' NPC_HIT) and
   gives back what the shield takes. Pirates that mean to dock (`Obj.net_docker`, every other
   one) attack the station (`net_prey` "c") while the shield is up, and only with it down turn
   to dock (state "trade", "dock"); `dock_target` gives no station while the shield is up, so
   even one at the slot can't dock. Unhit for `SHIELD_WAIT` 5 s it recharges `SHIELD_RECHARGE`
   20 a second; back up, the dockers still outside go back to attacking. STATE 24 bytes (the
   shield, 0-255); STATION SHIELDS DOWN / UP said to everyone; HUD's second line SHIELD n%
   DOCKED n/3 (red with the shield down). Tests in test_multiplayer. PC only.
   **Build 155** (Brian, 2026-11-25: "Defending Player respawn launch from the station, just
   the tunnel screen, there should be time penalty and one life option"). Station modes: a
   destroyed defender waits `STATION_PENALTY` 10 s (the end screen says LAUNCH IN n), then
   `Duel.wants_launch`; ace shows the launch tunnel (new mode "mlaunch", `_mp_launch`: a
   `cockpit.Tunnel` for the station being defended, your ship in your colours, LAUNCH_TIME, C
   skips; `flight_step` and, while destroyed, `Game.step` keep running so the radio stays up
   and the host's pirates fly on), then `Duel.launched` puts you `LAUNCH_OUT` 300 in front of
   the slot, facing out (teammates 250 further each). Raiders (station raid) come back as
   before. HOSTING has a LIVES line in the station modes (UNLIMITED / ONE; HELLO 53 bytes, the
   new last byte `OPT2_ONE_LIFE`); the mode's note line is left out when there are 6 or more
   lines. One life: destroyed, you are out till the next match (OUT: ONE LIFE; every device
   keeps `Duel.out` from KILLED); every defender out: STATION LOST (DEFENDERS ALL OUT); in the
   raid every raider out: STATION HELD (RAIDERS ALL OUT). Tests in test_multiplayer, one
   through the app. PC only.
   **Build 156** (Brian, 2026-11-25: "Or fixed lifes"). LIVES in the station modes is now
   UNLIMITED, 1, 2, 3 or 5 (`duel.LIVES_CHOICES`, `Duel.lives`, `step_lives`; HELLO's last byte
   is the number, `OPT2_ONE_LIFE` gone). Every device counts each slot's deaths from KILLED
   (`Duel.lives_lost`); at the number the player is out till the next match (OUT: NO LIVES
   LEFT). Before that the end screen's last line says "n LIVES LEFT   F: leave". A whole side
   out ends it as before. Tests in test_multiplayer. PC only.
   **Build 157** (Brian, 2026-11-25: "defenders colour should be configurable"). CONVOY RAID
   and STATION RAID have a DEFENDERS line on HOSTING: any of the ship paints
   (`cockpit.SHIP_COLOURS`, RED by default, `duel.DEFEND_COLOUR`), drawn in that colour;
   `Duel.step_defend_colour`. The raiders stay blue, or are red when the defenders are blue or
   cyan (`duel.raid_rgb`, `BLUES`). HELLO and START carry it (54 bytes, the last byte);
   the ships in flight, the radar and the party lists on HOSTING and JOINING use it
   (`Duel.team_rgb`). Other team modes keep red and blue. With eight lines (STATION RAID)
   the HOSTING page is closer packed. Tests in test_multiplayer. PC only.
   **Build 158** (Brian, 2026-11-25: "Just between red and blue is ok"). DEFENDERS is RED or
   BLUE only (`Duel.defend_colour` 0 / 1, left or right switches); the raiders are the other
   (`duel.raid_rgb`: `TEAM_RGB[team ^ defend_colour]`). Build 157's eight paints and the
   cyan rule are gone. Tests in test_multiplayer. PC only.
   **Build 159** (Brian, 2026-11-25: "Add a random player colour selection. Team size to be
   defined by the host"). Team modes (TEAMS, CAPTURE FLAG, both raids) have two more HOSTING
   lines: SIDES (`duel.SIDES_CHOICES`: ANY, or red / defenders v blue / raiders 1v1, 1v2,
   2v1, 2v2, 1v3, 3v1; `Duel.sides`, `most_players`: the game is capped at their sum, so a
   full game drops out of the others' lobby and further joins are refused) and PICK: CHOOSE /
   RANDOM (taken to mean the team colour drawn at random). CHOOSE: a player's pick is kept
   while that team has room, else the one with more room (`lobby_teams`). RANDOM: the YOU line
   goes, the party shows "?" (`UNKNOWN`), and START carries teams drawn then
   (`lobby_teams(final=True)`: red's share of the sizes, at least one each side, a shuffle by
   hand as MicroPython has no `random.shuffle`). HELLO 55 bytes (the last byte: SIDES number,
   bit 4 `RANDOM_TEAMS`). JOINING shows SIDES and CHOOSE / RANDOM, and "TEAMS DRAWN AT THE
   START". The HOSTING page shows `AceCommander.SHOWN` (6) lines at a time, scrolling with the
   one picked, "..." above / below; the mode's note only with fewer than 5 lines. Tests in
   test_multiplayer. PC only.
   **Build 160** (review of PR #61, 2026-11-25). The station's shield is part of its energy
   (`c.energy` = its own + the shield; `Duel.hull` its own, for the HUD's STATION %): before,
   the game took a hit from its energy and `_shield_step` gave it back on the host's next frame,
   so a hit bigger than the energy left destroyed it at once with the shield up (a guest's
   laser, pirate fire, the host's laser in a raid, a missile). Recharging adds to both.
   test_multiplayer's station section runs as without Elite's ship data even where it is on
   disc (`sys.modules["ace_commander.ship_data"] = None`), so it passes on both. PC only.
   **Build 161** (a STATION CO-OP host crashed on the badge with four playing, 2026-11-25:
   `ValueError: ESPNow.recv(): buffer error` in `net_espnow.Link.recv`, and the firmware's
   own ESP-NOW service crashed with it). Read from the firmware (`system/espnow/service.py`,
   started at boot) and MicroPython 1.28's `modespnow.c`: the service's background task reads
   every packet too, from the one radio into the one class buffer, so it took some of ours;
   the radio writes a packet in three pieces from the Wi-Fi task, and a read between them
   raises "buffer error" and leaves the buffer out of step; `rxbuf` applies only when ESP-NOW
   starts, which the service had done (so RXBUF never applied); the service turns Wi-Fi power
   saving on (dropping packets) every 10 s unless someone listens. `net_espnow.Link` now pauses
   the service's reader (cancels its task; started again by `close()`, from
   `Platform.minimise`; opened again on use), listens for its event so the radio stays awake,
   restarts ESP-NOW so RXBUF applies, reads only as many packets as `stats()[3]` (rx_packets,
   counted once a packet is all written) says, and restarts the radio on a buffer error
   instead of crashing. Test: `tests/test_net_espnow.py` (pretend radio and service). On four
   badges over the REPL (the service not running there): 4096 bytes, no errors, every counted
   packet read. Not yet in a real game.
   **Build 162** (Brian, 2026-11-25: "the station does not need to be named"). The station
   modes' station and the convoy's end station have no label (the convoy keeps CONVOY). The
   HUD's STATION % is rounded: on the badge (32-bit floats) its own energy, the total less
   the shield, came out a hair under full unhurt, showing 99% (seen in the four-badge test).
   That test (four badges, STATION CO-OP, build 161): no crash, no radio restarts; the
   firmware's service kept the radio awake for our listener. Frames averaged 90-108 ms (about
   10 a second) on all four, HUD 32-35 ms of it (its text lines), and 5-7 frames in 100 were
   collections of 140-340 ms. Not yet improved.
   **Build 163** (Brian, 2026-11-25: "do both and remove convoy label", "use integer maths").
   The convoy has no label either. Multiplayer's HUD line is gauges and rectangle digits, no
   text (`Duel.hud_rows`, drawn by `cockpit.draw_net_line`; `hud()` keeps the text for the
   tests): the station modes a yellow energy bar, the time left as m:ss, a cyan shield bar
   and DOCK_LIMIT marks lit red per pirate docked; the convoy modes its bar and the clock;
   TEAMS / CAPTURE FLAG the two team scores in their colours; FREE FOR ALL your kills, a bar,
   the best. (The screen reader no longer reads it.) Whole-number placement: `Game.anchor_ints`
   (the anchor as ints once a frame: axes x 16384 and x 4096), `Game.place_i` (ints in, only
   o.m's nine values floats; ~65 floats a call before), `netplay.read_pose_i`; remote ships
   and the host's pirates are placed only when a pose comes and coast along their nose in
   `Game._think` between (your own flight already moves every object); the rings and station
   every MARK_FRAMES (12) frames, the convoy every CONVOY_FRAMES (3); the host packs its
   pirates' poses in ints and stops copying lists each frame. Measured on the badge (three
   games on one badge, MicroPython's gc.mem_alloc): multiplayer's own garbage 6.6 KB (host)
   / 9.3 KB (guest) a frame -> 2.0 KB; `Game.step` (the shared rules, mostly the pirates'
   AI) is now the largest, 4.9-6.6 KB. A scripted game on all four badges (`bot.py` over the
   REPL: the real Duel, Game and ESP-NOW link, a bot pilot, every frame drawn; no LEDs, sound
   or input, the app not running), STATION CO-OP, four players, eight pirates, 60 s, the
   same script on both builds: build 162 averaged 83-90 ms a frame (draw 63-65, update 20-27),
   a collection every 20-21 frames; build 163 56-64 ms (draw 39-42, update 16-21), every
   33-43 frames. Not yet played by hand.
   **Build 164** (Brian, 2026-11-25: "can shared game rules use integer maths?", then
   "measure first then do step 1"). Measured first (three games on one badge, build 163):
   `Game.step` made 6.8 KB (host) / 5.1 KB (guest) a frame, of it `_rotate` 3.5 / 3.4 KB
   (each object's position and axes turned in whole numbers but stored back as floats,
   ~26 floats an object), `_think` 2.2 / 0.6 KB (the AI's planning, and moving along the
   nose every frame), collisions and weapons ~0.6 KB. Step 1: every object turns and moves
   on whole-number masters, `Obj.q` (position in quarter units), `Obj.qf` (what `_move` has
   left over below a quarter, so slow drifts add up) and `Obj.mi` (axes x 16384);
   `o.x / y / z` are stored as whole numbers (rounded from q) and `o.m` as floats made from
   mi (its nine, no temporaries); `game._move` moves along the nose in whole numbers. The
   230-odd readers of o.x / o.m are unchanged: anything else that moves or turns an object
   (spawns, the AI's `_turn` / `_look`, duel's `place_i`, view flips, `_shift`, a new o.m
   list) is seen by x, y, z no longer matching q (by value) or o.m's numbers no longer
   being the very floats last put there (`Obj.mf`, by identity), and the masters are read
   again (`_pos_q`, `_axes_i`). `Game.step` makes a new objs list only when one has gone.
   Turning error against exact floats over 200 frames is as before (18 units at 2500: the
   rounded sines). Tests: `tests/test_int_masters.py`; test_game's game-over check compares
   kills before and after (an idle ship rammed by a rock now counts one, the random fight
   being a hair different). Measured the same way: `Game.step` 3.7 KB (host) / 3.3 KB
   (guest), `_rotate` 2.2 / 2.3 KB (o.m's nine floats an object, and the multiplayer anchor,
   kept in exact floats on purpose), `_think` 0.8 / 0.3 KB. The four-badge bot game
   (STATION CO-OP, as build 163): a collection every 44-57 frames (33-43 before), average
   frame 56-61 ms (56-64), update 15-19 ms (16-21); slow frames about the same or a few
   more (53-103 against 53-92: one run each, not enough to tell). Not yet played by hand,
   and the main game (docking, the sun, practice) only by the PC tests.
   Brian played build 164 by hand (four badges, Capture Flag): "game play seems ok"; the
   logs had no tracebacks or radio errors, frames 52-95 ms (about 75; build 161's station
   game ~100), still 2-3 collections a minute of 200-330 ms.
   **Build 165** (Brian, 2026-11-25: "the flags do not need to be labeled", "add a number
   to repeated names", "have an option to drop player names"). The flags (CTF's rings) have
   no label; a carrier still has NAME *FLAG*. Two players with one name (two JAMESONs, the
   default, seen in that game): `Duel._number_names` gives the one with the lowest radio
   address the name and the others NAME 2, NAME 3 (`Player.base` as sent, `Player.name` /
   `Duel.name` as shown, `Duel.my_name` sent); every badge hears the same names and
   addresses, so all number them alike; not while flying. Options and in-flight Settings,
   where there is a radio: NAMES: SHOWN / HIDDEN (`AceCommander.use_names`, options.json
   "names", `cockpit.SHOW_NAMES`); hidden leaves only a carrier's *FLAG*. Tests in
   test_multiplayer.py; test_find's "no NAME line in flight" now looks for "NAME:".
   Build 165 played by hand (four badges, duels; two named JAMESON): confirmed by Brian,
   NAMES: HIDDEN hides the names. The logs: no tracebacks or radio errors; the lobby showed
   "BRIAN, JAMESON 2, THOMAS" and each badge agreed who was JAMESON 2 (a badge that had
   joined before hearing the other JAMESON renamed its host while waiting, as designed:
   not once flying); duel frames 41-75 ms.
   **Build 166** (Brian, 2026-11-25: "freeze the names once joined"). `Duel._number_names`
   keeps the names of our party (joined and accepted: the host and its guests; hosting:
   ourselves and our guests) as they are; anyone heard after is numbered round them (the
   lowest number not taken). So a badge that joined JAMESON before hearing a second one
   keeps calling its host JAMESON, and the newcomer is JAMESON 2 to it. Badges outside the
   party still number by address, so they may see the names the other way round (the
   newcomer calls itself JAMESON); inside the party everyone agrees. Test in
   test_multiplayer.py.
   Build 166 on the badges (Brian, 2026-11-25): no errors; names agreed on every badge and
   none changed after joining (the frozen case itself didn't come up: the lower-addressed
   JAMESON was always there first). It showed a lobby bug from before: BRIAN hosted a DUEL,
   both JAMESONs joined (the lobby offered it at "DUEL 2/2") and the game couldn't start.
   **Build 167** (Brian: "yes, fix it"). The guest limit (`Duel.most_players`,
   `Player.open_slots`) used four for every mode without teams; it is now no more than the
   mode's MODE_MAX (a duel: 2), so a full game isn't offered and a host takes no more guests
   than it can start with. Changing the mode or the sides to fewer places keeps the first
   guests (`Duel._trim_guests`); the others are back to "asking to join" and are taken again
   if room comes. test_duel's lobby section hosts FREE FOR ALL now (it relied on a duel
   taking four); new tests in test_multiplayer.py.
   Build 167 on the badges (Brian, 2026-11-26): a full duel wasn't offered, FREE FOR ALL
   took a third, back to DUEL kept the first guest. Then four-player FREE FOR ALL games
   (45-92 ms a frame) and a docking flight with the docking computer, no errors. But the
   names: one badge listed "BRIAN, JAMESON, JAMESON", and both JAMESON badges called
   themselves JAMESON. Build 166's freeze kept what each badge had, and a player heard
   afresh was kept with its plain name.
   **Build 168**. `Duel._number_names`, run each `lobby_step`: in a game (joined and
   accepted, or hosting with guests) repeated names are numbered by the game's order, the
   host then its guests as they joined; every member has that order from the host, so all
   agree, and a newcomer, last, renames nobody. Outside a game, by radio address, round
   the game's names. So on joining, a name may change once (address order to the game's).
   Test in test_multiplayer.py (fails on build 167: the late JAMESON called itself JAMESON).
   Build 168 on the badges (Brian, 2026-11-26; BRIAN hosting FREE FOR ALL, two JAMESONs):
   every badge agreed. The first to join was JAMESON and the second JAMESON 2 on all
   three; when the first left and joined again it came second, so the two swapped (the
   game's order), and in the game the kill messages matched on every badge ("JAMESON
   DESTROYED BY JAMESON 2" on the host, "YOU DESTROYED JAMESON" on JAMESON 2, "YOU
   DESTROYED JAMESON 2" on JAMESON). No errors; frames 44-88 ms.
   **Build 169** (Brian, 2026-11-26: "reduce the remaining garbage in Game.step").
   `Obj.m` is a property: `_rotate` turns only the whole-number axes (`Obj.mi`) and sets
   `Obj.mstale`; the nine floats are made again (`game._fresh_m`) only when something
   reads o.m (the AI's steering, a laser drawn, a view flip). `draw_ship`, `_move16` and
   duel's `_send_npcs` read mi; `Game.place_i` writes mi (no floats at all now). The
   anchor's exact turn is written out (no tuples) and, like `_rot3` (the planet, sun and
   station), skips the axis not turned (a digital joystick turns one at a time); the
   sines once a frame; `Blueprint.crash_r` (the crash radius, once per type; `_collide`
   made two floats an object a frame); no arithmetic on zero throttle, pitch or roll;
   coasting ships move by `round(speed * Game.k16)` (one float, was three). Measured
   (three games on one badge, as builds 164-168): `Game.step` 2.2 KB (host) / 1.5 KB (guest)
   a frame steering on both axes at once, 1.8 / 1.1 KB on one (build 164: 3.7 / 3.3; 163:
   6.8 / 5.1); `_collide` 0. Left: the anchor (0.5-0.9 KB, exact floats on purpose) and
   the host's pirate AI planning (~0.75 KB). The four-badge bot game (STATION CO-OP, as
   before): a collection every 61-94 frames (164: 44-57), frames 56-61 ms as before (the
   drawing, ~40 ms, is most of a frame now). The main game's (planet, sun, station) not
   measured on the badge.
   **Release 0.6.0** (2026-11-27): builds 148-169. Multiplayer for up to four: FREE FOR ALL,
   TEAMS, CAPTURE FLAG, CONVOY (and CONVOY RAID), STATION CO-OP and STATION RAID; teams picked
   in the lobby or drawn at random, SIDES set by the host, pirates on / off and their skill,
   LIVES, the defenders' colour; repeated names numbered, Options > NAMES. The ESP-NOW buffer
   error crash fixed (the firmware's service paused). HUD in gauges and digits, whole-number
   placement and turning (frames 83-90 -> 56-61 ms in a four-badge station game).
   **Build 170** (2026-11-27/28, branch cardputerzero-phase1; CardputerZero Phase 1, notes/
   cardputerzero_phase0.md). Game-side, all off on the badge, the Pi and the Tufty:
   `config.menu_k` (list menus' lines further apart, fewer shown, scrolling: `cockpit.menu_rows`,
   used by `menu_lines`, the pause / Settings menu, the DEBUG lists, the lobby and HOSTING; a
   small arrow at the right says there is more) and `config.wide` (the charts' line under the
   name and RANGE side by side; Brian). The badge's screens change in one way (Brian: "would it
   not be more efficient for the duplicated screens to be the same, docked and in flight?" ...
   "merge both"): **Status and Market are one screen each, docked and in flight**
   (`screens.draw_status`, `screens.draw_market`). Status is Elite's Commander Status; docked,
   its condition says DOCKED in the station's colour, a level row is added, then A: LAUNCH and
   the hints right under the rows (no equipment: Equip ship lists it). The docked Status no
   longer shows the government and economy / tech (System data has them); the hyperspace line
   is red when the target is beyond the fuel (was docked only). The market shows
   `screens.MARKET_ROWS` (7) goods docked and in flight (docked 6, in flight 8 before), its
   header and rows lower so "hold" is inside the round screen; docked it keeps the bar behind
   the good picked, the message and C / D. Inventory, the charts and System data were already
   shared. Tests changed to match (test_commander, test_keys). PC only: not yet on the badge.
   The CardputerZero host (`hosts/cardputerzero/`) and `fit_cz.py` are in its README.
   Then (Brian: "hangar and ship yard don't make use of the wide screen"): `config.wide` is a
   number, how many times wider than tall the host draws the 240 screens at most (0 on the
   badge; the CardputerZero 1.5, `fit_cz.MAX_ASPECT`). With it the Shipyard's pages and the
   Hangar put the ship turning on the left and the rest down the right
   (`Docked._wide_page`, `_ship_facts`, `_fitout(e, wide)`: shorter lines), and
   `_spin_ship` draws ships that much narrower so the stretch leaves them their shape.
   The local chart with config.wide (Brian: "the range should be round but the star field should
   fill out the sides"): `Chart` takes systems out to wide times further left and right
   (`_inside`: a box, not the circle) and draws everything wide times narrower (`_Cursor.kx`:
   dots, the range as a 48-point oval, the box, cursor and you-are-here), so the host's stretch
   leaves the range round; the cursor and distances are unchanged. The Pi gets it with --wide too.
   **Wide by default** (2026-11-28, Brian: "the wide screen should be for the pi and tufty" ...
   "wide should be on by default"). The fitting's shared part is `hosts/fit_core.py` (plain
   Python, MicroPython too: `is_hint` without `re`, `screen_key`, `fit` with an `aspect`,
   `fits`, `clear`, `nudges`, `Recorder` that stands in for a ctx, `replay` through any ctx,
   `Placer`); `hosts/pi/fit_pygame.py` uses its maths. The Pi: wide is the default (`--no-wide`
   turns it off). The Tufty (`host_tufty.WIDE`): whole-frame screens drawn into a Recorder,
   placed (aspect 4 / 3, its fonts keep their pixel sizes: `Ctx.measure`) and replayed, the
   hints in one row along the bottom; `config.wide` 4 / 3, so its charts, Shipyard and Hangar
   use the wide pages; build_tufty copies fit_core.py in. Not yet on the Tufty itself (tested
   on the sim_badgeware stand-ins only).
   **Release 0.7.0** (2026-11-28): builds 170-171 and the hosts since 0.6.0. The badge: one
   Status and one Market screen docked and in flight (170); in-flight menus on black, DEBUG
   pages 5 lines, long menus loop (171). The M5 CardputerZero (hosts/cardputerzero, in the Pi
   zip); wide screens on by default on the Pi (--no-wide) and the Tufty (hosts/fit_core.py);
   the 8BitDo Micro's own layout. make_release: the Pi zip carries hosts/fit_core.py and
   hosts/cardputerzero, and is started (pi_smoke) before anything is published.
   **Build 172** (2026-11-28, Brian: "tilt needs a test and setup screen. Think the cardputer
   has an IMU sensor as well"). TILT SETUP in Options (title and docked; wherever there is a tilt
   sensor): a live test (a circle for full tilt, one for the dead zone, a dot where tilt steers
   now, roll / pitch %) and FULL TILT (17-44 degrees), DEAD ZONE (3-12 degrees), SWAP AXES, TILT
   PITCH / TILT ROLL (flipped for tilt only; CONTROLS still flips all steering) and LEVEL: SET NOW;
   saved in options.json ("tilt_setup"). Tilt is now measured across the level pose's gravity
   (`_level_axes`, `_tilt_xy`), so the device can be held at any angle; flat, a badge's x and y as
   before (the badge's platform reads z too). The CardputerZero's BMI270 (iio, run_cz.Accel, on
   by default, --no-tilt) gives it STEER: TILT; `platform_pi.TILT` is the hook. On wide hosts the
   test's circle is drawn 1/config.wide as wide so it stays round. Tests: test_cz_tilt (new),
   test_app, test_leds, test_commander. PC only: not yet on the badge or the CardputerZero.
   Build 172 on the badge (Brian, 2026-11-28): TILT SETUP's dot was "left is up, right is down"
   with the IMU's x taken as across, so the badge's tilt had been turned a quarter all along;
   with `Platform.tilt_axes = (1, 1.0)` (y across) "dot goes the correct way", both ways. The
   CardputerZero's (1, -1.0) set from Brian's "tilt up is left"; its roll direction not yet
   confirmed. FULL TILT / DEAD ZONE a degree at a time (17-44 / 3-12); an all-zero first IMU
   read (seen on the badge right after start) isn't taken as level.
   **Release 0.7.1** (2026-11-28): build 172 and the hosts since 0.7.0. TILT SETUP (a live test,
   FULL TILT / DEAD ZONE a degree at a time, SWAP AXES, TILT PITCH / ROLL, LEVEL), tilt at any
   holding angle, the badge's tilt axes corrected and each device's in device.json; the
   CardputerZero's accelerometer and its key guide; the game pad guide (PAD_GUIDE.pdf) and
   --pad; the fitted title screen steady; README and README_PI for Windows and --duel.
   **Build 173** (2026-11-28, Brian: "22 badge link", "should there be an ip info sub menu"):
   the Pi and the CardputerZero play badges through a dongle, Brian's 2022 EMF badge (TiDAL)
   flashed with stock MicroPython 1.28 (its own 1.18 firmware has no espnow; full flash backup
   kept off the repo) running `tools/bridge/main.py` with a status page on its screen
   (`tools/bridge/tidal_screen.py`); `run.py --bridge DEVICE` (`hosts/pi/net_bridge.py`). The
   dongle hunts the badges' Wi-Fi channel (6, 1, 11, then the rest): a badge on a network is on
   its channel (Brian's: 6), not 1. The link's id is the dongle's radio address (MAC_ASK). The
   lobby's last line NETWORK INFO: the link (ESP-NOW, UDP or bridge), channel, Wi-Fi and IP,
   your id, who is heard; on a badge on Wi-Fi, C leaves it for channel 1. Dongle tried with
   Brian's badge (packets both ways, channel 6 found); NETWORK INFO tested on the PC only.
   **Build 174** (2026-11-28): the badge link is now text lines (">" / "<", address and packet in
   hex), so a 2024 badge's firmware prints can share the port and no byte is Ctrl-C;
   `--bridge` probes Espressif ports, then badges, for one that answers MAC_ASK. The 2024
   badge's side is its own app, ESP-NOW Link (`~/Code/espnow_link`, Brian: "the link app
   should be it own app", "a general tool"); the 2022 dongle's main.py speaks the same lines
   (not yet copied to it). The 2022 dongle was one-way: the Pi heard Brian's badge, the badge
   never heard the Pi (104 packets sent, no failures, same channel); cause not found.
