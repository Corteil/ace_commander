"""net_espnow.Link (build 161) on the PC, with a pretend radio modelled on MicroPython
1.28's modespnow.c and a pretend firmware ESP-NOW service: the service's reader paused
while the game has the radio and started again on close, power saving off, rxbuf
applied by a restart, only whole packets read (rx_packets), and a buffer error
recovered from. Proves the logic only: the radio's timing is the badge's.

    python tests/test_net_espnow.py
"""
import asyncio
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))
import badge_stubs as bs
import time
if not hasattr(time, "ticks_ms"):       # MicroPython's, for version_issues
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
    time.ticks_diff = lambda a, b: a - b

bs.install()
from ace_commander import net_espnow
SAVED = {k: sys.modules.get(k) for k in ("system", "system.espnow", "system.scheduler", "system.eventbus")}
fails = []


def check(name, cond, extra=""):
    print(("ok   " if cond else "FAIL ") + name + (("  " + extra) if extra else ""))
    if not cond:
        fails.append(name)


# ---- a pretend radio: one ESP-NOW for all ESPNow objects, as on the badge ----------------
class Radio:
    def __init__(self):
        self.reset()

    def reset(self):
        self.on = False
        self.rxbuf = 526            # the default
        self.buf_size = None        # the buffer as made by the last start
        self.buf = []               # whole packets, and "half" (a header written, the rest not yet)
        self.rx = 0                 # rx_packets: counted once a packet is all written
        self.peers = set()
        self.starts = 0
        self.sent = []


RADIO = Radio()


class ESPNow:
    def active(self, on=None):
        if on is None:
            return RADIO.on
        if on and not RADIO.on:
            RADIO.buf_size = RADIO.rxbuf
            RADIO.buf = []
            RADIO.starts += 1
        if not on:
            RADIO.peers = set()
        RADIO.on = bool(on)

    def config(self, rxbuf=None):
        RADIO.rxbuf = rxbuf

    def add_peer(self, mac):
        if mac in RADIO.peers:
            raise OSError(-12395)
        RADIO.peers.add(mac)

    def send(self, mac, msg, sync=True):
        if mac not in RADIO.peers:
            raise OSError("not found")
        RADIO.sent.append(bytes(msg))

    def stats(self):
        return (len(RADIO.sent), 0, 0, RADIO.rx, 0)

    def irecv(self, timeout=None):
        if not RADIO.buf:
            return (None, None)
        p = RADIO.buf.pop(0)
        if p == "half":
            raise ValueError("ESPNow.recv(): buffer error")
        return p


def env(mac, msg, ident=None, version=0xA1):
    """A game packet in the envelope (build 175): version, the sender's id ("AM" + msg)."""
    return (mac, bytes((version,)) + (ident or mac) + b"AM" + msg)


def arrive(mac, msg, ident=None, version=0xA1):
    RADIO.buf.append(env(mac, msg, ident, version))
    RADIO.rx += 1


def arrive_raw(mac, data):
    RADIO.buf.append((mac, data))
    RADIO.rx += 1


def rcv(link):
    """link.recv() with the game packet's "AM" taken off, as bytes."""
    who, msg = link.recv()
    if who is None:
        return (None, None)
    m = bytes(msg)
    assert m[:2] == b"AM", m
    return (bytes(who), m[2:])


def arrive_half():
    """The Wi-Fi task has written a header only: not counted yet."""
    RADIO.buf.append("half")


class WLAN:
    PM_NONE, PM_PERFORMANCE = 0, 1

    def __init__(self, i):
        pass

    def active(self, on=None):
        return True

    def isconnected(self):
        return False

    def disconnect(self):
        pass

    def config(self, *a, **k):
        if a:
            return {"mac": b"\x7c\x4f\xad\x33\x7a\xc0", "channel": 1}[a[0]]
        for key, v in k.items():
            WLAN.set[key] = v
    set = {}


sys.modules["espnow"] = types.SimpleNamespace(ESPNow=ESPNow)
sys.modules["network"] = types.SimpleNamespace(WLAN=WLAN, STA_IF=0)


# ---- the firmware: its ESP-NOW service, the scheduler, the event bus ----------------------
class Event:
    pass


class Service:
    def __init__(self):
        self.runs = 0

    async def background_task(self):
        self.runs += 1
        await asyncio.sleep(3600)


class Bus:
    def __init__(self):
        self.async_handlers = {}

    def on_async(self, ev, h, app):
        self.async_handlers.setdefault(app, {}).setdefault(ev, []).append(h)

    def remove(self, ev, h, app):
        self.async_handlers[app][ev].remove(h)


async def main():
    svc = Service()
    sched = types.SimpleNamespace(background_tasks={})
    bus = Bus()
    sys.modules["system.espnow"] = types.SimpleNamespace(espnow_service=svc, EspNowReceiveEvent=Event)
    sys.modules["system.scheduler"] = types.SimpleNamespace(scheduler=sched)
    sys.modules["system.eventbus"] = types.SimpleNamespace(eventbus=bus)
    task = asyncio.create_task(svc.background_task())
    sched.background_tasks[svc] = task
    RADIO.on = True             # the service started ESP-NOW at boot, with the default buffer
    RADIO.buf_size = 526
    RADIO.rx = 7                # and has read 7 packets since
    await asyncio.sleep(0)

    link = net_espnow.Link()
    await asyncio.sleep(0)
    check("the service's reader paused", svc not in sched.background_tasks and task.cancelled())
    check("we listen (so the service keeps the radio awake)", bus.async_handlers.get(link, {}).get(Event))
    check("power saving off", WLAN.set.get("pm") == WLAN.PM_NONE)
    check("restarted: rxbuf applied", RADIO.buf_size == net_espnow.RXBUF and RADIO.starts == 1)
    check("broadcast peer added", net_espnow.BROADCAST in RADIO.peers)
    check("the id is the MAC", link.id == b"\x7c\x4f\xad\x33\x7a\xc0")

    check("nothing yet", link.recv() == (None, None))
    arrive(b"A" * 6, b"one")
    arrive(b"B" * 6, b"two")
    got = [rcv(link), rcv(link), rcv(link)]
    check("two whole packets, then none", got == [(b"A" * 6, b"one"), (b"B" * 6, b"two"), (None, None)], str(got))
    # a packet being written: its header is there, not counted yet: left alone
    arrive_half()
    check("half a packet isn't read", link.recv() == (None, None) and RADIO.buf == ["half"])
    RADIO.buf = [env(b"C" * 6, b"three")]      # (the Wi-Fi task finishes it)
    RADIO.rx += 1
    check("once it is all written, it is", rcv(link) == (b"C" * 6, b"three"))
    # out of step anyway: restarted, not a crash
    RADIO.buf = ["half", env(b"D" * 6, b"lost")]
    RADIO.rx += 2
    starts = RADIO.starts
    r = link.recv()
    check("a buffer error restarts the radio, no crash", r == (None, None) and RADIO.starts == starts + 1
          and link.restarts == 1 and RADIO.buf == [] and net_espnow.BROADCAST in RADIO.peers)
    arrive(b"E" * 6, b"after")
    check("and packets come again", rcv(link) == (b"E" * 6, b"after") and link.recv() == (None, None))
    link.send(b"hi")
    check("send broadcasts, in the envelope: version, our id, the packet",
          RADIO.sent[-1] == bytes((0xA1,)) + link.id + b"hi", str(RADIO.sent[-1]))
    link.send(b"x")
    check("a shorter one after: only its own bytes", RADIO.sent[-1] == bytes((0xA1,)) + link.id + b"x")
    # the sender is the id in the envelope, not the radio address (a relaying Pi's link
    # badge sends many players' packets from one address)
    arrive(b"L" * 6, b"pc one", ident=b"1" * 6)
    arrive(b"L" * 6, b"pc two", ident=b"2" * 6)
    arrive(b"L" * 6, b"pc one again", ident=b"1" * 6)
    got = [rcv(link), rcv(link), rcv(link)]
    check("the id in the envelope is the sender", got == [(b"1" * 6, b"pc one"), (b"2" * 6, b"pc two"),
                                                          (b"1" * 6, b"pc one again")], str(got))
    who = link.recv()
    check("ids are bytes", got and isinstance(link.ids[b"L" * 6], bytes))
    # another version: skipped, and noted for UPDATE REQUIRED
    arrive_raw(b"O" * 6, b"AM\x02old badge")           # from before the envelope
    arrive(b"N" * 6, b"newer", version=0xA2)
    arrive(b"G" * 6, b"good")
    check("older and newer skipped, the current one read", rcv(link) == (b"G" * 6, b"good"))
    check("version_issues: one older, one newer", link.version_issues() == (1, 1), str(link.version_issues()))
    arrive_raw(b"J" * 6, b"not the game's")
    check("junk skipped, not counted", link.recv() == (None, None) and link.version_issues() == (1, 1))

    link.close()
    await asyncio.sleep(0)
    check("close: the service reads again", svc in sched.background_tasks and svc.runs == 2)
    check("close: we no longer listen", not bus.async_handlers[link][Event])
    link.close()
    check("close twice is fine", svc.runs == 2)
    link.send(b"again")             # back after minimise: opened again on use
    await asyncio.sleep(0)
    check("reopened on use: the service paused again", svc not in sched.background_tasks
          and RADIO.sent[-1][7:] == b"again")
    link.close()
    for t in list(sched.background_tasks.values()):
        t.cancel()

    # a firmware without the service: the counting and the restart only
    sys.modules["system.espnow"] = None     # (an import of it fails)
    RADIO.reset()
    link = net_espnow.Link()
    arrive(b"F" * 6, b"plain")
    check("no service: works", rcv(link) == (b"F" * 6, b"plain") and link.paused is None)
    link.close()


asyncio.run(main())
for k, v in SAVED.items():
    if v is None:
        sys.modules.pop(k, None)
    else:
        sys.modules[k] = v
if fails:
    print("%d FAILED: %s" % (len(fails), ", ".join(fails)))
    sys.exit(1)
print("ALL NET ESPNOW TESTS PASSED")
