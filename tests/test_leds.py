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
tick(a, fresh=["CONFIRM"])          # into flight
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
tick(a, fresh=["CANCEL"])                           # to the menu
assert a.mode == "menu" and bus.events == ["PatternDisable", "PatternEnable"]
tick(a); tick(a)
assert bus.events == ["PatternDisable", "PatternEnable"]
tick(a, fresh=["CONFIRM"]); tick(a)                 # back in
assert bus.events[-1] == "PatternDisable" and len(bus.events) == 3
g._hurt(1000.0); tick(a)
assert g.over and leds.values == RED12(48), "dim red at game over"
tick(a, fresh=["CANCEL"])
assert bus.events[-1] == "PatternEnable"
print("pause, menu and game over hand the LEDs back: ok")

# the LEDs failing mid-game must not crash, and brings the ring back
tick(a, fresh=["CONFIRM"]); tick(a)
leds.fail = True
a.game._hurt(5.0)
tick(a)
assert not a.leds_on
assert arcs(a) == 1, "ring is the fallback"
leds.fail = False
print("LED failure falls back to the ring: ok")

# ---- USE_LEDS off ----------------------------------------------------------
bs.install()
leds, bus = bs.install_leds()
import ace_commander
mod = ace_commander.app
mod.USE_LEDS = False
a = ace_commander.AceCommander()
tick(a, fresh=["CONFIRM"]); tick(a)
a.game._hurt(5.0); tick(a)
assert bus.events == [] and leds.writes == 0 and arcs(a) == 1
print("USE_LEDS = False keeps the ring: ok")

# ---- firmware without the LED modules --------------------------------------
bs.install()
import ace_commander
mod = ace_commander.app
assert mod.tildagonos is None
a = ace_commander.AceCommander()
tick(a, fresh=["CONFIRM"]); tick(a)
a.game._hurt(5.0); tick(a)
assert arcs(a) == 1
print("no LED modules: ring fallback: ok")
print("ALL LED TESTS PASSED")

print("ALL LED TESTS PASSED (v10)")
