import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

RED12 = lambda v: {i: (v, 0, 0) for i in range(1, 13)}   # the front ring only


tick = bs.tick


def arcs(a):
    c = CountCtx(); a.draw(c)
    return c.calls.get("arc", 0)


# ---- with LEDs available ---------------------------------------------------
bs.install()
leds, bus = bs.install_leds()
import ace_commander
mod = ace_commander.ace
assert mod.tildagonos is not None
a = ace_commander.AceCommander()
tick(a); tick(a, fresh=["DOWN"]); tick(a, fresh=["UP"])
assert bus.events == [] and leds.writes == 0, "menu leaves the LEDs alone"
bs.choose(a, "COMBAT PRACTICE")     # into flight
g = a.game
g.spawn_t = g.rock_t = 1e9
tick(a)
assert bus.events == ["PatternDisable"] and leds.values == RED12(0) and leds.writes == 1
for _ in range(20):
    tick(a)
assert leds.writes == 1, "no LED traffic while nothing changes"
assert leds.power == [True], "LED power switched on once"

g._hurt(10.0)
tick(a)
assert leds.values == RED12(255), leds.values
assert arcs(a) == 0, "no red ring on screen when the LEDs do the job"
seen = [255]
for _ in range(12):
    tick(a)
    v = leds.values[1][0]
    if v != seen[-1]:
        seen.append(v)
assert seen == [255, 160, 80, 0], seen
assert leds.writes == 1 + len(seen), leds.writes
print("hit flash on LEDs, fading", seen, ": ok")

# your laser: each type its own colour, on screen and on the LEDs, at each shot
from ace_commander import cockpit
seen = {}
for kind in ("pulse", "beam", "military", "mining"):
    g.set_laser(kind); g.heat = 0.0; g.hot = False; g.cool = 0.0; g.flash = 0.0
    tick(a, held=["C"])
    assert g.beam > 0, kind
    r, gr, b = cockpit.LASER_COLOURS[kind]
    want = (int(r * 255), int(gr * 255), int(b * 255))
    assert leds.values[1] == want, (kind, leds.values[1])
    seen[kind] = want
    c = CountCtx(); cockpit.draw_world(c, g)
    for _ in range(10):
        tick(a)
    assert leds.values[1] != want, "and off again between shots"
assert len(set(seen.values())) == 4, "four different colours"
assert cockpit.ORANGE not in cockpit.LASER_COLOURS.values(), "none like the enemy's"
g.set_laser("pulse")
# the energy bomb flashes the LEDs white (as the screen), not red like a hit
g.bomb_t = 0.4; g.flash = 0.0; g.beam = 0.0; tick(a)
assert leds.values[1] == (255, 255, 255), leds.values[1]
g.bomb_t = 0.0; tick(a)
# missiles: the enemy's orange like their lasers, yours light purple; no laser shares them
assert cockpit.COLOUR["missile"] == cockpit.ORANGE
assert cockpit.COLOUR["pmissile"] == cockpit.LIGHT_PURPLE
assert cockpit.LIGHT_PURPLE not in cockpit.LASER_COLOURS.values()
print("laser colours on screen and LEDs, white bomb flash, missile colours: ok")
# the jump: white on the LEDs where the hyperspace streaks leave the screen
import math as _m
a1 = mod.LED_ANGLE1 * _m.pi / 180
assert a._led_at(_m.cos(a1) * 100, -_m.sin(a1) * 100) == 1, "LED 1 where it is"
a2 = a1 - (_m.pi / 6 if mod.LED_CLOCKWISE else -_m.pi / 6)
assert a._led_at(_m.cos(a2) * 100, -_m.sin(a2) * 100) == 2, "and the next round from it"
g.beam = 0.0; g.flash = 0.0
seen_lit = set()
WT = mod.game.WARP_TIME
g.warp = WT
for _ in range(int(WT / 0.04)):
    tick(a)
    for i in range(1, 13):
        v = leds.values[i]
        assert v[2] >= v[1] >= v[0], "blue-white, like the streaks"
        if v[2] > 0:
            seen_lit.add(i)
            if v[2] == 255:
                assert v == mod.HYPER_RGB, v
    lit_now = [i for i in range(1, 13) if leds.values[i][0] > 0]
assert len(seen_lit) >= 6, ("streaks leave all round the screen", seen_lit)
for _ in range(20):
    tick(a)
assert not any(leds.values[i] == mod.HYPER_RGB for i in range(1, 13)), "and fade away"
# and with the jump drive, where the stardust streaks off the edge
z = 2000.0
fx = mod.cockpit.FOCAL
g.dust[:] = [[_m.cos(a1) * 110 * z / fx, _m.sin(a1) * 110 * z / fx, z]]   # y up in the world
g.jumping = True
mod.AceCommander._jump_flashes(a)
g.jumping = False
assert a.jump_leds[1] == 255 and sum(1 for v in a.jump_leds[1:] if v) == 1, a.jump_leds
print("jump: white LED flashes round the ring where the streaks leave: ok")

g._hurt(10.0); tick(a); assert leds.values[5] == (255, 0, 0)
tick(a, fresh=["A"]); tick(a)                       # paused
assert a.paused and leds.values == RED12(0)
a.fmenu = a._fitems_top().index("QUIT TO TITLE")      # (picked by name: lines come and go)
tick(a, fresh=["CONFIRM"])                              # QUIT TO TITLE
assert a.mode == "menu" and bus.events == ["PatternDisable", "PatternEnable"]
tick(a); tick(a)
assert bus.events == ["PatternDisable", "PatternEnable"]
bs.choose(a, "COMBAT PRACTICE"); tick(a)                 # back in
assert bus.events[-1] == "PatternDisable" and len(bus.events) == 3
g._hurt(1000.0); tick(a)
assert g.over and leds.values == RED12(48), "dim red at game over"
tick(a, fresh=["CANCEL"])
assert bus.events[-1] == "PatternEnable"
print("pause, menu and game over hand the LEDs back: ok")

# the LEDs failing mid-game must not crash, and brings the ring back
bs.choose(a, "COMBAT PRACTICE"); tick(a)
leds.fail = True
a.game._hurt(5.0)
tick(a)
assert not a.leds_on
assert arcs(a) == 1, "ring is the fallback"
leds.fail = False
print("LED failure falls back to the ring: ok")

# ---- the launch: the LEDs pulse in the station's colour --------------------
cockpit = ace_commander.cockpit
save = os.path.join(HERE, "shots", "test_leds_commander.json")
os.makedirs(os.path.dirname(save), exist_ok=True)
mod.SAVE_PATH = save
a.game.over = True; tick(a, fresh=["CANCEL"])
bs.choose(a, "NEW COMMANDER"); tick(a, fresh=["C"])
assert a.mode == "docked"
gov = a.galaxy.system(a.cmdr.system).government
col = cockpit.station_colour(gov)
assert col != cockpit.RED and cockpit.WHITE not in cockpit.STATION_COLOURS
assert len(set(cockpit.station_colour(i) for i in range(8))) == 8, "one colour per government"
assert cockpit.station_colour(None) == cockpit.GREEN
assert a.dock.here.name == "LAVE"
c = CountCtx(); a.draw(c)
assert any(t[0] == "DOCKED" for t in c.texts)
full = tuple(int(v * 255) for v in col)
writes = leds.writes
tick(a, fresh=["A"]); assert a.mode == "launch"
seen = []
while a.mode == "launch":
    v = leds.values[1]
    if not seen or v != seen[-1]:
        seen.append(v)
    tick(a, ms=20)
assert seen[-1] == full, (seen[-1], full)
bright = [v for v in seen if v != (0, 0, 0)]
assert bright and all(v == tuple(x * max(v) // max(full) for x in full) or
                      max(abs(v[i] - full[i] * max(v) / max(full)) for i in range(3)) <= 18
                      for v in bright), "always the station's colour"
peaks = sum(1 for i in range(1, len(seen) - 1) if sum(seen[i]) > sum(seen[i - 1]) and
            sum(seen[i]) > sum(seen[i + 1]))
assert peaks >= 5, ("a pulse for each ring", peaks, len(seen))
assert leds.writes - writes < 200, "not written every frame regardless"
# out in space the colour fades, then the hit flash still works
fade = [leds.values[1]]
for _ in range(30):
    tick(a)
    fade.append(leds.values[1])
# just launched you are in the station's safe zone: the colour fades to green
green = (0, mod.SAFE_GREEN, 0)
assert a.game.space.safe and fade[0] == full and fade[-1] == green, fade
before = fade[:fade.index(green)]
assert all(sum(before[i + 1]) <= sum(before[i]) for i in range(len(before) - 1)), fade
a.game._hurt(5.0); tick(a); assert leds.values[1] == (255, 0, 0), "a hit still flashes red"
for _ in range(15):
    tick(a)
assert leds.values[1] == green
a.game.to_station(a.game.space.safe_r + 5000); tick(a)
assert not a.game.space.safe and leds.values[1] == (0, 0, 0), "off outside the safe zone"
a.game.to_sun(); tick(a)
v = leds.values[1]
assert v[0] > 150 and v[2] == 0 and v[1] < v[0] // 3, ("near the sun: hot red", v)
a.game.fuel_scoops = True; a.game.speed = 40.0; a.cmdr.fuel = 10
seen = set()
for _ in range(60):
    tick(a, held=["F"])
    if a.game.scooping:
        seen.add(leds.values[1])
assert seen and all(c[2] == 0 and c[1] == c[0] * 3 // 4 for c in seen) and len(seen) == 2, seen
a.game.to_station(4000); tick(a); assert leds.values[1] == green, "and green again inside it"
tick(a, fresh=["A"]); assert a.paused and leds.values[1] == (0, 0, 0), "off while paused"
tick(a, fresh=["A"]); assert leds.values[1] == green
# another station, another colour, in the tunnel's mouth too
other = [i for i in range(256) if a.galaxy.system(i).government != gov][0]
a.cmdr.system = other
a._dock(); assert a.mode == "docked"
tick(a, fresh=["A"]); assert a.mode == "launch"
for _ in range(200):
    if a.mode != "launch":
        break
    last = leds.values[1]
    tick(a, ms=20)
want = tuple(int(v * 255) for v in cockpit.station_colour(a.galaxy.system(other).government))
assert last == want or leds.values[1] == want, (last, want)
os.remove(save)
print("launch: LEDs pulse in the station's colour, then fade to green in the safe zone: ok")

# ---- USE_LEDS off ----------------------------------------------------------
bs.install()
leds, bus = bs.install_leds()
import ace_commander
mod = ace_commander.ace
mod.USE_LEDS = False
a = ace_commander.AceCommander()
bs.choose(a, "COMBAT PRACTICE"); tick(a)
a.game._hurt(5.0); tick(a)
assert bus.events == [] and leds.writes == 0 and arcs(a) == 1
print("USE_LEDS = False keeps the ring: ok")

# ---- the title screen's OPTIONS page -----------------------------------------
bs.install()
leds, bus = bs.install_leds()
import ace_commander
mod = ace_commander.ace
save = os.path.join(HERE, "shots", "test_options.json")
if os.path.exists(save):
    os.remove(save)
mod.SAVE_PATH = save
a = ace_commander.AceCommander()
assert "OPTIONS" in a.choices()
bs.choose(a, "OPTIONS"); assert a.mode == "options"
c = CountCtx(); a.draw(c)
tx = [t[0] for t in c.texts]
assert "OPTIONS" in tx and "STEER: JOYSTICK" in tx and "LEDS: ON" in tx
assert "more with a commander" in tx, "no commander: no docking or Constrictor"
for s_, (x, y), size in c.texts:
    assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s_, y)
tick(a, fresh=["JOYRIGHT"]); assert a.use_tilt, "right changes the steering"
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["JOYDOWN"]); assert a.omenu == 2   # past TILT
tick(a, fresh=["C"]); assert not a.use_leds
tick(a, fresh=["F"]); assert a.mode == "menu"
# kept for next time
b = ace_commander.AceCommander()
assert b.use_tilt and not b.use_leds
bs.choose(b, "COMBAT PRACTICE"); tick(b)
b.game._hurt(5.0); tick(b)
assert leds.writes == 0 and arcs(b) == 1, "LEDS: OFF keeps the ring on screen"
# with a commander: docking style and the Constrictor too, saved in the commander
b.mode = "menu"
bs.choose(b, "NEW COMMANDER"); tick(b, fresh=["C"])
b.dock.go(0); tick(b, fresh=["F"])
bs.choose(b, "OPTIONS")
items = b._settings(True)
assert items[1] == "TILT: NORMAL", items      # (build 85)
assert items[2].startswith("DOCKING") and items[3] == "CONSTRICTOR: 2 MIN", items
b.omenu = 2; tick(b, fresh=["JOYLEFT"])
assert b.cmdr.docking == "A"
b.omenu = 3; tick(b, fresh=["C"])
assert not b.cmdr.quick_con
from ace_commander import commander as cm
d = cm.load(save); assert d.docking == "A" and d.quick_con is False
# DATA: ELITE / OWN, with Elite's files there: kept for the next start
import json as _json
items = b._settings(True)
assert "DATA: ELITE" in items and mod.HAVE_ELITE_SHIPS and not mod.ORIGINAL_SHIPS
b.omenu = items.index("DATA: ELITE"); tick(b, fresh=["C"])
assert "DATA: OWN (RESTART)" in b._settings(True)
assert _json.load(open(mod.options_path()))["own"] is True
tick(b, fresh=["C"]); assert "DATA: ELITE" in b._settings(True)
assert _json.load(open(mod.options_path()))["own"] is False
# Options > DEBUG away from a flight: only the cheats that work there, in groups
assert b._settings(True)[-1] == "DEBUG"
b.omenu = len(b._settings(True)) - 1; tick(b, fresh=["C"])
assert b.mode == "odebug" and b._od_items() == ["SHIP", "COMMANDER", "DISPLAY"]
c = CountCtx(); b.draw(c); assert any(t[0].startswith("DEBUG - BUILD") for t in c.texts)
b.od_sel = 1; tick(b, fresh=["C"])
assert b._od_items() == ["+10 KILLS", "+1000 CR", "LEVEL: " + cm.LEVELS[b.cmdr.level], "HARDCORE: OFF",
                         "LEGAL: CLEAN", "MISSION: NONE"], b._od_items()
cash = b.cmdr.cash
b.od_sel = 1; tick(b, fresh=["C"])
assert b.cmdr.cash == cash + 10000 and cm.load(save).cash == cash + 10000, "saved at once"
assert b.od_msg == b.cmdr.cash_text()
b.od_sel = 5; tick(b, fresh=["C"]); assert b.cmdr.mission == 1 and cm.load(save).mission == 1
tick(b, fresh=["F"]); assert b.od_page is None
b.od_sel = 0; tick(b, fresh=["C"]); assert b.od_page == "SHIP", "straight to the equipment"
items = b._od_items()
b.od_sel = items.index("NAVY ENERGY UNIT: OFF"); tick(b, fresh=["C"])
assert "navy" in b.cmdr.extras and "navy" in cm.load(save).extras
tick(b, fresh=["F"]); assert b.od_page is None
tick(b, fresh=["F"]); assert b.mode == "options", "back where it came from"
# and from the docked Options, back to it
tick(b, fresh=["F"]); bs.choose(b, "CONTINUE"); assert b.mode == "docked"
assert b.dock.repair, "always there (Brian, build 81)"
b.dock.open("OPTIONS"); b.dock.osel = len(b._settings(True)) - 1
tick(b, fresh=["C"]); assert b.mode == "odebug" and b.od_from == "docked"
b.od_sel = b._od_items().index("DISPLAY"); tick(b, fresh=["C"])
assert not any(t.startswith("REPAIR") for t in b._od_items()), "no REPAIR SHOP switch"
tick(b, fresh=["F"]); tick(b, fresh=["F"]); assert b.mode == "docked" and b.dock.name() == "OPTIONS"
b.dock.go(0); tick(b, fresh=["F"]); bs.choose(b, "OPTIONS")
# no commander: just DISPLAY
n_ = ace_commander.AceCommander(); n_.cmdr = None
assert n_._cheat_groups(False) == ["DISPLAY"]
# the in-flight Settings page has the same lines
tick(b, fresh=["F"]); bs.choose(b, "CONTINUE")
b.dock.go(0); tick(b, fresh=["C"])
for _ in range(200):
    tick(b)
    if b.mode == "flight":
        break
tick(b, fresh=["A"]); b.fsub = "settings"
assert b._fitems() == b._settings(True)
os.remove(save)
print("OPTIONS page: steering, LEDs, docking, Constrictor; saved: ok")

# ---- firmware without the LED modules --------------------------------------
bs.install()
import ace_commander
mod = ace_commander.ace
assert mod.tildagonos is None
a = ace_commander.AceCommander()
bs.choose(a, "COMBAT PRACTICE"); tick(a)
a.game._hurt(5.0); tick(a)
assert arcs(a) == 1
print("no LED modules: ring fallback: ok")
print("ALL LED TESTS PASSED")

print("ALL LED TESTS PASSED (v10)")
