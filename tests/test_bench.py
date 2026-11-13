import io, os, sys, contextlib
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE); sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

tick = bs.tick


bs.install()
import ace_commander
mod = ace_commander.app
a = ace_commander.AceCommander()
c = CountCtx(); a.draw(c)
labels = [t[0] for t in c.texts]
assert labels == ["< NEW COMMANDER >"], labels
for s, (x, y), size in c.texts:
    assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, y)
tick(a, fresh=["UP"]); assert a.menu == 3, "back from the first choice wraps to the last"
assert a.choices()[a.menu] == "SPEED TEST"
out = io.StringIO()
with contextlib.redirect_stdout(out):
    tick(a, fresh=["CONFIRM"])
    assert a.mode == "bench"
    frames = 0
    kinds = set()
    while not a.bench.done:
        c = CountCtx(); a.draw(c)
        kinds.add(tuple(sorted(c.calls)))
        tick(a, ms=50 + a.bench.i)       # pretend each test takes a different time
        frames += 1
        assert frames < 2000
c = CountCtx(); a.draw(c)
lines = out.getvalue().strip().split("\n")
n = len(mod.bench.TESTS)
assert lines[0].startswith("BENCH start") and lines[-1] == "BENCH done" and len(lines) == n + 2, lines
assert len(c.texts) == n
for s, (x, y), size in c.texts:
    assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, y)
for i, (name, avg, drawn) in enumerate(a.bench.results):
    assert abs(avg - (50 + i)) < 1e-6, (name, avg)   # skipped frames don't pollute the next test
    assert 0 <= drawn < 50, drawn
assert abs(frames - n * (mod.bench.FRAMES + mod.bench.SKIP)) <= 1, frames
print("\n".join(lines[1:4]), "...")
print("frames:", frames, " distinct kinds of frame drawn:", len(kinds))
tick(a, fresh=["CANCEL"]); assert a.mode == "menu" and a.bench is None
print("SPEED TEST: ok")
