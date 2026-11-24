"""tools/espnow_link.py on the PC, with a pretend radio: two badges on one
"air", the echo badge answering at once, a few ms of flight time, and packets
dropped on purpose to check the loss counts. Proves the test's own logic, not
the radio: the numbers that matter come from running it on two badges.

    python tests/test_espnow_link.py
"""
import gc
import os
import sys
import time
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))


# ---- a pretend clock (MicroPython's ticks) ----------------------------------------------
class Clock:
    us = 0


def _ticks_us():
    return Clock.us


time.ticks_us = _ticks_us
time.ticks_ms = lambda: Clock.us // 1000
time.ticks_diff = lambda a, b: a - b
time.ticks_add = lambda a, b: a + b


def _sleep_us(n):
    Clock.us += n


time.sleep_us = _sleep_us
gc.mem_alloc = lambda: 0
gc.mem_free = lambda: 100000


# ---- a pretend radio --------------------------------------------------------------------
class Air:
    """Who is listening, and what gets through."""

    def __init__(self, flight_us=2000, drop=None):
        self.stations = []
        self.flight_us = flight_us
        self.drop = drop or (lambda n: False)   # n: packets sent so far over the air
        self.sent = 0


class FakeESPNow:
    BROADCAST = b"\xff" * 6

    def __init__(self, air, mac, on_receive=None):
        self.air, self.mac, self.peers = air, mac, set()
        self.inbox = []             # (arrival time, host, msg)
        self.on_receive = on_receive
        air.stations.append(self)

    def active(self, on):
        return True

    def add_peer(self, mac):
        if mac in self.peers:
            raise OSError("ESP_ERR_ESPNOW_EXIST")
        self.peers.add(mac)

    def send(self, peer, msg, sync=True):
        if peer not in self.peers:
            raise OSError("ESP_ERR_ESPNOW_NOT_FOUND")
        air = self.air
        air.sent += 1
        if air.drop(air.sent):
            return True
        for s in air.stations:
            if s is not self and peer in (self.BROADCAST, s.mac):
                s.deliver(Clock.us + air.flight_us, self.mac, bytes(msg))
        return True

    def deliver(self, at, host, msg):
        if self.on_receive:         # the echo badge answers as soon as it hears
            saved = Clock.us
            Clock.us = at
            self.on_receive(self, host, msg)
            Clock.us = saved
        else:
            self.inbox.append((at, host, msg))

    def irecv(self, timeout_ms):
        if self.inbox:
            at, host, msg = self.inbox[0]
            if at - Clock.us <= timeout_ms * 1000:
                self.inbox.pop(0)
                Clock.us = max(Clock.us, at)
                return host, bytearray(msg)
        Clock.us += timeout_ms * 1000
        return None, None


class FakeWLAN:
    def __init__(self, mac):
        self.mac, self.ch = mac, 6

    def active(self, on=None):
        return True

    def isconnected(self):
        return False

    def disconnect(self):
        pass

    def config(self, key=None, **kw):
        if "channel" in kw:
            self.ch = kw["channel"]
            return None
        return {"channel": self.ch, "mac": self.mac}[key]


PING_MAC = b"\x02\x00\x00\x00\x00\x01"
ECHO_MAC = b"\x02\x00\x00\x00\x00\x02"


def setup(air, echo=True):
    """The pinging badge's modules, with an echo badge on the same air."""
    import espnow_link as link
    if echo:
        peers = set()
        echo_e = FakeESPNow(air, ECHO_MAC, lambda e, host, msg: link.echo_one(e, peers, host, msg))
        echo_e.add_peer(FakeESPNow.BROADCAST)
    me = FakeESPNow(air, PING_MAC)
    sys.modules["espnow"] = types.SimpleNamespace(ESPNow=lambda: me)
    sys.modules["aioespnow"] = types.SimpleNamespace()
    sys.modules["network"] = types.SimpleNamespace(
        STA_IF=0, WLAN=lambda i: FakeWLAN(PING_MAC))
    return link


fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


# packets: header in, header out; someone else's packets ignored
import espnow_link as link  # noqa: E402
buf = bytearray(32)
link.packet(buf, 70000, 123456)
check("packet: magic and header round trip", link.read(buf) == (70000 & 0xFFFF, 123456))
check("packet: not ours ignored", link.read(b"XX" + bytes(30)) is None and link.read(None) is None)
check("packet: too short ignored", link.read(b"AC\x00") is None)

# stats
r = link.stats([1000, 2000, 3000, 4000], 5)
check("stats: counts and loss", (r["sent"], r["got"], r["lost"], r["loss_pct"]) == (5, 4, 1, 20.0))
check("stats: min / median / max", (r["min_ms"], r["med_ms"], r["max_ms"]) == (1.0, 3.0, 4.0))
check("stats: nothing back", link.stats([], 3)["loss_pct"] == 100.0 and "min_ms" not in link.stats([], 3))

# check(): imports, radio, channel set when not connected
link = setup(Air())
check("check() passes with espnow present", link.check())
e, sta, ch = link.radio()
check("radio: channel set to CHANNEL when not connected", ch == link.CHANNEL, "channel %d" % ch)

# check() fails cleanly without espnow
saved = sys.modules.pop("espnow")
sys.modules["espnow"] = None        # import espnow -> ImportError
check("check() fails cleanly without espnow", link.check() is False)
sys.modules["espnow"] = saved

# ping against a perfect echo: nothing lost, round trip = two flights
Clock.us = 0
link = setup(Air(flight_us=2000))
res = link.ping(count=30, rate=15, sizes=(32, 64))
check("ping: four runs (broadcast and unicast, two sizes)", sorted(res) == sorted(
    ["broadcast 32", "broadcast 64", "unicast 32", "unicast 64"]), str(sorted(res)))
check("ping: nothing lost on a perfect link",
      all(r["lost"] == 0 for r in res.values()), str([r["lost"] for r in res.values()]))
check("ping: round trip is two flights (4 ms)",
      all(abs(r["med_ms"] - 4.0) < 0.01 for r in res.values()), str([r["med_ms"] for r in res.values()]))

# every 5th packet over the air dropped: losses counted, late replies not matched
Clock.us = 0
link = setup(Air(flight_us=2000, drop=lambda n: n % 5 == 0))
res = link.ping(count=50, rate=15, sizes=(32,))
lost = res["broadcast 32"]["lost"]
check("ping: dropped packets counted as lost", 15 <= lost <= 25, "lost %d of 50" % lost)

# replies slower than TIMEOUT_MS are lost, and don't count for the next packet
Clock.us = 0
link = setup(Air(flight_us=link.TIMEOUT_MS * 1000))     # round trip 2 x timeout
res = link.ping(count=20, rate=15, sizes=(32,))
check("ping: replies past the timeout are lost", res["broadcast 32"]["got"] == 0
      and "unicast 32" not in res, str(res["broadcast 32"]))

# no echo badge: broadcast gets nothing, no unicast tried
Clock.us = 0
link = setup(Air(), echo=False)
res = link.ping(count=10, rate=15, sizes=(32,))
check("ping: no echo badge -> all lost, no unicast", res["broadcast 32"]["got"] == 0
      and list(res) == ["broadcast 32"])

# the rate is kept: 15 a second for 30 packets is about 2 s
Clock.us = 0
link = setup(Air())
t0 = Clock.us
link.run(sys.modules["espnow"].ESPNow(), FakeESPNow.BROADCAST, 32, count=30, rate=15)
secs = (Clock.us - t0) / 1e6
check("run: keeps the packet rate", 1.9 <= secs <= 2.1, "%.2f s" % secs)

print()
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL ESPNOW LINK TESTS PASSED")
