import os, random, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named ace_commander
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE)
sys.path.insert(0, PARENT)
import badge_stubs as bs
from badge_stubs import CountCtx

bs.install()
import ace_commander
from ace_commander import commander, game
mod = ace_commander.app
tick, choose = bs.tick, bs.choose
SAVE = os.path.join(HERE, "shots", "test_commander.json")
os.makedirs(os.path.dirname(SAVE), exist_ok=True)
if os.path.exists(SAVE):
    os.remove(SAVE)
mod.SAVE_PATH = SAVE


def texts(a):
    c = CountCtx(); a.draw(c)
    for s, (x, y), size in c.texts:
        assert (x * x + y * y) ** 0.5 + size / 2 <= 120.5, (s, x, y, size)
    return [t[0] for t in c.texts]


# ---- ranks and levels -------------------------------------------------------
assert commander.thresholds(2) == (0, 8, 16, 32, 64, 128, 512, 2560, 6400), "hardest is the original"
assert commander.thresholds(0)[-1] == 640 and commander.thresholds(1)[-1] == 1600
for level in range(3):
    t = commander.thresholds(level)
    assert t[0] == 0 and all(b > a for a, b in zip(t, t[1:])), t
c = commander.Commander(0)
assert c.rank() == "HARMLESS" and c.next_rank() == ("MOSTLY HARMLESS", 1)
assert c.add_kills(1) == "MOSTLY HARMLESS"
assert c.add_kills(0) is None
c.add_kills(700)
assert c.rank() == "ELITE" and c.next_rank() is None
c = commander.Commander(2)
assert c.add_kills(7) is None and c.add_kills(1) == "MOSTLY HARMLESS"
assert commander.Commander(9).level == 2 and commander.Commander(-3).level == 0
print("ranks and levels: ok", [commander.thresholds(i)[-1] for i in range(3)])

# ---- save and load ----------------------------------------------------------
c = commander.Commander(2); c.add_kills(40); c.docking = "C"
assert c.save(SAVE)
d = commander.load(SAVE)
assert (d.level, d.kills, d.docking, d.credits, d.rank()) == (2, 40, "C", 100.0, "AVERAGE")
assert not c.save(os.path.join(HERE, "no", "such", "folder", "x.json")), "a failed save doesn't raise"
assert commander.load(os.path.join(HERE, "nothing.json")) is None
for junk in ("", "{", "[1, 2]", '{"level": "x"}', '{"kills": null}'):
    with open(SAVE, "w") as f:
        f.write(junk)
    assert commander.load(SAVE) is None, junk
with open(SAVE, "w") as f:
    f.write('{"level": 1, "kills": 3, "docking": "Z", "future": 1}')
d = commander.load(SAVE)
assert d.kills == 3 and d.docking == "B", "unknown values fall back, unknown keys are ignored"
os.remove(SAVE)
print("save and load: ok")

# ---- the level changes the enemies ------------------------------------------
def fight(level, seed, seconds=240):
    """Sit still and let them shoot: returns (damage taken, most hostile ships at once)."""
    random.seed(seed)
    g = game.Game(mod.SHIPS, level)
    taken = 0.0
    most = 0
    for _ in range(int(seconds / 0.05)):
        before = g.shield + g.hull
        g.step(0.05, 0.0, 0.0, 0.0, False, False)
        taken += max(0.0, before - (g.shield + g.hull))
        most = max(most, sum(1 for o in g.objs if o.kind == "ship" and o.state != "flee"))
        if g.over:
            g.reset()
        g.wave = 9      # late-game numbers, where the cap on ships matters
    return taken, most

res = [[fight(level, seed) for seed in (1, 2, 3)] for level in range(3)]
dmg = [sum(r[0] for r in rs) for rs in res]
most = [max(r[1] for r in rs) for rs in res]
assert dmg[0] < dmg[1] < dmg[2], dmg
assert most[0] <= 3 and most[1] <= 4 and most[2] <= 5 and most[2] > most[0], most
g = game.Game(mod.SHIPS)
assert g.level == 1, "the default is the middle level"
print("level changes enemy damage %s and numbers %s: ok" % ([int(d) for d in dmg], most))

# ---- new commander, kills, rank, save, continue -----------------------------
a = ace_commander.AceCommander()
assert a.cmdr is None and "CONTINUE" not in a.choices()
choose(a, "NEW COMMANDER")
assert a.mode == "level" and a.level == 1
tx = texts(a)
assert "< NORMAL >" in tx and "top rank at 1600 kills" in tx
assert not any("replaces" in t for t in tx)
tick(a, fresh=["JOYLEFT"]); assert a.level == 0 and "< EASY >" in texts(a)
tick(a, fresh=["JOYLEFT"]); assert a.level == 2 and "top rank at 6400 kills" in texts(a)
tick(a, fresh=["JOYRIGHT"]); assert a.level == 0
tick(a, fresh=["F"]); assert a.mode == "menu" and a.cmdr is None, "F backs out without making one"
choose(a, "NEW COMMANDER")
tick(a, fresh=["JOYLEFT"]); tick(a, fresh=["C"])
assert a.mode == "flight" and a.career and a.cmdr.level == 0 and a.game.level == 0
assert commander.load(SAVE).level == 0, "saved as soon as it is made"
g = a.game
g.spawn_t = g.rock_t = 1e9
g.objs[:] = []

def kill(g, n=1):
    for _ in range(n):
        o = game.Obj(g.types["SIDEWINDER"], "ship", 0.0, 0.0, 3000.0)
        g.objs.append(o)
        g._kill(o)

kill(g); tick(a)
assert a.cmdr.kills == 1 and g.msg == "RANK: MOSTLY HARMLESS", (a.cmdr.kills, g.msg)
kill(g, 4); tick(a)
assert a.cmdr.kills == 5 and a.cmdr.rank() == "AVERAGE"
assert commander.load(SAVE).kills == 0, "not written every kill"
tick(a, fresh=["A"])
tx = texts(a)
assert "STATUS" in tx
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); assert a.fsub == "status"
tx = texts(a)
assert "AVERAGE" in tx and any("5 kills" in t and "EASY" in t for t in tx), tx
assert any("more for ABOVE AVERAGE" in t for t in tx)
tick(a, fresh=["C"]); assert a.fsub is None and a.paused
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); assert a.fsub == "pause"
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a.mode == "menu" and commander.load(SAVE).kills == 5, "quitting to the title saves"
assert a.choices()[0] == "CONTINUE" and a.menu == 0
assert texts(a) == ["< CONTINUE >"]

# practice doesn't touch the commander, and each kind of game starts fresh
choose(a, "COMBAT PRACTICE")
assert not a.career and a.game.level == 1 and a.game.kills == 0
kill(a.game, 3); tick(a)
assert a.cmdr.kills == 5
tick(a, fresh=["A"]); assert "STATUS" not in texts(a)
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
assert a.mode == "menu" and commander.load(SAVE).kills == 5
choose(a, "CONTINUE")
assert a.career and a.game.level == 0 and a.game.kills == 0

# dying saves; flying again keeps the commander
g = a.game; g.spawn_t = g.rock_t = 1e9; g.objs[:] = []
kill(g, 2); tick(a)
g._hurt(1000.0); tick(a)
assert g.over and commander.load(SAVE).kills == 7, "saved at game over"
tick(a, fresh=["C"]); assert not g.over and a.career and a.cmdr.kills == 7
kill(g); tick(a); assert a.cmdr.kills == 8

# a new app instance (the badge restarted) finds the commander
tick(a, fresh=["A"]); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"])
tick(a, fresh=["JOYDOWN"]); tick(a, fresh=["C"]); assert a.mode == "menu"
b = ace_commander.AceCommander()
assert b.cmdr.kills == 8 and b.cmdr.level == 0 and b.choices()[0] == "CONTINUE"
choose(b, "NEW COMMANDER")
assert any("replaces your saved commander" in t for t in texts(b))
tick(b, fresh=["JOYRIGHT"]); tick(b, fresh=["C"])
assert b.cmdr.kills == 0 and b.cmdr.level == 2 and b.game.level == 2
assert commander.load(SAVE).level == 2

# a save that can't be written doesn't stop the game
mod.SAVE_PATH = os.path.join(HERE, "no", "such", "folder", "x.json")
c = ace_commander.AceCommander()
assert c.cmdr is None
choose(c, "NEW COMMANDER"); tick(c, fresh=["C"])
assert c.mode == "flight" and c.career
kill(c.game); tick(c); c.game._hurt(1000.0); tick(c)
assert c.cmdr.kills == 1
os.remove(SAVE)
print("new commander, rank, status, save, continue, practice kept apart: ok")
print("ALL COMMANDER TESTS PASSED")
