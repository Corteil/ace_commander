import asyncio, os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)            # the app folder, which must be named elite_demo
PARENT = os.path.dirname(REPO)
sys.path.insert(0, HERE); sys.path.insert(0, PARENT)
import badge_stubs as bs


class Stop(Exception):
    pass


class Sched:
    def __init__(self, foreground=True, broken=False):
        if not broken:
            self.render_needed = asyncio.Event()
        self.foreground = foreground
        self.renders = 0

    def app_is_foregrounded(self, app):
        return self.foreground

    async def render_task(self, app):
        while True:
            await self.render_needed.wait()
            self.render_needed.clear()
            app.draw(bs.CountCtx())
            self.renders += 1
            await asyncio.sleep(0)


def load(sched):
    bs.install()
    sys.modules.pop("system.scheduler", None)    # left over from the previous case
    if sched is not None:
        m = types.ModuleType("system.scheduler")
        m.scheduler = sched
        sys.modules["system.scheduler"] = m
    import elite_demo
    return elite_demo, elite_demo.app


async def drive(sched, mode, n=40, other_task=True):
    pkg, mod = load(sched)
    a = pkg.Elite()
    if mode != "menu":
        a.game = mod.game.Game(mod.SHIPS)
        a.viewer = mod.viewer.Viewer(mod.SHIPS)
        a.mode = mode
    counts = {"update": 0, "normal": 0, "other": 0}
    real_update = a.update

    def update(delta):
        counts["update"] += 1
        if counts["update"] > n:
            raise Stop
        real_update(delta)
    a.update = update

    async def render_update():
        counts["normal"] += 1
        if sched is not None and hasattr(sched, "render_needed"):
            sched.render_needed.set()
        await asyncio.sleep(0.001)

    async def other():          # some other badge task that needs its turn
        while True:
            counts["other"] += 1
            await asyncio.sleep(0)

    tasks = []
    if sched is not None and hasattr(sched, "render_needed"):
        tasks.append(asyncio.create_task(sched.render_task(a)))
    if other_task:
        tasks.append(asyncio.create_task(other()))
    try:
        await a.run(render_update)
    except Stop:
        pass
    for t in tasks:
        t.cancel()
    return a, counts


async def main():
    # fast path: flight, in the foreground
    s = Sched()
    a, c = await drive(s, "flight")
    assert c["normal"] == 0 and a.fast, c
    assert s.renders == 40, (s.renders, "one redraw per update")
    assert c["other"] >= 39, (c, "other tasks still get a turn every frame")
    print("flight: 40 updates, %d redraws, normal path used %d times, other task ran %d times: ok"
          % (s.renders, c["normal"], c["other"]))

    s = Sched()
    a, c = await drive(s, "viewer")
    assert c["normal"] == 0 and s.renders == 40
    print("viewer uses the fast path: ok")

    # menu keeps the badge's normal pacing
    s = Sched()
    a, c = await drive(s, "menu")
    assert c["normal"] == 40, c
    print("menu uses the normal path: ok")

    # not in the foreground: hand over to the normal path, which waits
    s = Sched(foreground=False)
    a, c = await drive(s, "flight")
    assert c["normal"] == 40 and a.fast, c
    print("in the background the normal path is used: ok")

    # firmware without the bits this relies on
    a, c = await drive(None, "flight")
    assert c["normal"] == 40 and not a.fast, c
    s = Sched(broken=True)
    a, c = await drive(s, "flight")
    assert c["normal"] == 40 and not a.fast, c
    print("scheduler missing or different: falls back, no crash: ok")

    # switched off
    bs.install()
    pkg, mod = load(Sched())
    mod.FAST_FRAMES = False
    assert not pkg.Elite().fast
    print("FAST_FRAMES = False: ok")
    print("ALL FRAME LOOP TESTS PASSED")

asyncio.run(main())
