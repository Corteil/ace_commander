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
mod = ace_commander.app
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

g._hurt(10.0); tick(a); assert leds.values[5] == (255, 0, 0)
tick(a, fresh=["A"]); tick(a)                       # paused
assert a.paused and leds.values == RED12(0)
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["CONFIRM"])  # PAUSE MENU
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["CONFIRM"])  # QUIT TO TITLE
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
tick(a, fresh=["C"]); assert a.mode == "launch"
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
assert fade[0] == full and fade[-1] == (0, 0, 0)
assert all(sum(fade[i + 1]) <= sum(fade[i]) for i in range(len(fade) - 1)), fade
a.game._hurt(5.0); tick(a); assert leds.values[1] == (255, 0, 0)
# another station, another colour, in the tunnel's mouth too
other = [i for i in range(256) if a.galaxy.system(i).government != gov][0]
a.cmdr.system = other
a.game.over = True; tick(a, fresh=["C"]); assert a.mode == "docked"
tick(a, fresh=["A"]); assert a.mode == "launch"
for _ in range(200):
    if a.mode != "launch":
        break
    last = leds.values[1]
    tick(a, ms=20)
want = tuple(int(v * 255) for v in cockpit.station_colour(a.galaxy.system(other).government))
assert last == want or leds.values[1] == want, (last, want)
os.remove(save)
print("launch: LEDs pulse in the station's colour, then fade: ok")

# ---- USE_LEDS off ----------------------------------------------------------
bs.install()
leds, bus = bs.install_leds()
import ace_commander
mod = ace_commander.app
mod.USE_LEDS = False
a = ace_commander.AceCommander()
bs.choose(a, "COMBAT PRACTICE"); tick(a)
a.game._hurt(5.0); tick(a)
assert bus.events == [] and leds.writes == 0 and arcs(a) == 1
print("USE_LEDS = False keeps the ring: ok")

# ---- firmware without the LED modules --------------------------------------
bs.install()
import ace_commander
mod = ace_commander.app
assert mod.tildagonos is None
a = ace_commander.AceCommander()
bs.choose(a, "COMBAT PRACTICE"); tick(a)
a.game._hurt(5.0); tick(a)
assert arcs(a) == 1
print("no LED modules: ring fallback: ok")
print("ALL LED TESTS PASSED")

print("ALL LED TESTS PASSED (v10)")
