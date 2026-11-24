"""ESP-NOW link tests for multiplayer (plans/MULTIPLAYER.md): can two badges talk
straight to each other, how fast, and how many packets get lost?

Runs on the badge (MicroPython; the firmware has `espnow` and `aioespnow`). Copy it
to the badge's root, then from the Pi:

    mpremote connect PORT fs cp tools/espnow_link.py :/espnow_link.py
    mpremote connect PORT exec "import espnow_link; espnow_link.check()"

    # two badges (both plugged in, or the echo one on its own power after starting it)
    mpremote connect PORT_B exec "import espnow_link; espnow_link.echo(120)"
    mpremote connect PORT_A exec "import espnow_link; espnow_link.ping()"

- check(): espnow imports, the radio starts, this badge's MAC and Wi-Fi channel,
  and how much garbage a send and a receive make (the game can't afford much,
  CLAUDE.md "Garbage costs more than drawing").
- echo(seconds): sends every packet it gets straight back to whoever sent it.
- ping(): sends packets the size of a game's ship update at 15 a second, first
  broadcast (no acknowledgement, as a game would send to everyone), then unicast
  to the echo badge (the radio retries until acknowledged), and prints round
  trip times and losses for each.

Both badges must be on the same Wi-Fi channel: a badge connected to a network is
on that network's channel. One that isn't connected is set to CHANNEL here, and
disconnected first, so it stops hopping channels looking for its network.

No game code here: just the link. tests/test_espnow_link.py runs it on the PC with
a pretend radio.
"""
import gc
import struct
import time

CHANNEL = 1             # used when the badge isn't connected to a Wi-Fi network
BROADCAST = b"\xff" * 6
RATE = 15               # packets a second, about a game's ship updates
COUNT = 150             # packets per run (10 s at RATE)
SIZES = (32, 64)        # bytes: a ship update (32) and one with a shot or two (64)
TIMEOUT_MS = 60         # a reply later than this counts as lost
HEAD = "<HI"            # sequence number, send time (ticks_us, low 32 bits)
MAGIC = b"AC"           # first two bytes of every packet: ours, not someone else's


def ticks_us():
    return time.ticks_us()


def ticks_diff(a, b):
    return time.ticks_diff(a, b)


def radio():
    """Start Wi-Fi in station mode and ESP-NOW; returns (ESPNow, WLAN, channel)."""
    import network
    import espnow
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    if not sta.isconnected():
        try:
            sta.disconnect()        # stop it hunting for a network on every channel
        except Exception:
            pass
        sta.config(channel=CHANNEL)
    e = espnow.ESPNow()
    e.active(True)
    try:
        e.add_peer(BROADCAST)
    except OSError:
        pass                        # already a peer (a second run without a reset)
    return e, sta, sta.config("channel")


def mac_str(mac):
    return ":".join("%02x" % b for b in mac)


def packet(buf, seq, now):
    """Fill buf (a bytearray, reused: no garbage) with our header."""
    buf[0:2] = MAGIC
    struct.pack_into(HEAD, buf, 2, seq & 0xFFFF, now & 0xFFFFFFFF)
    return buf


def read(msg):
    """(seq, sent ticks) from a packet, or None if it isn't ours."""
    if msg is None or len(msg) < 8 or bytes(msg[0:2]) != MAGIC:
        return None
    return struct.unpack_from(HEAD, msg, 2)


def stats(rtts, sent):
    """Round trip times (µs) and how many were sent -> a dict of results."""
    got = len(rtts)
    s = sorted(rtts)
    r = {"sent": sent, "got": got, "lost": sent - got,
         "loss_pct": 100.0 * (sent - got) / sent if sent else 0.0}
    if s:
        r["min_ms"] = s[0] / 1000
        r["med_ms"] = s[got // 2] / 1000
        r["p95_ms"] = s[min(got - 1, (got * 95) // 100)] / 1000
        r["max_ms"] = s[-1] / 1000
    return r


def report(name, r):
    line = "%-16s sent %3d  got %3d  lost %5.1f%%" % (name, r["sent"], r["got"], r["loss_pct"])
    if r["got"]:
        line += "  rtt ms min %.1f med %.1f p95 %.1f max %.1f" % (
            r["min_ms"], r["med_ms"], r["p95_ms"], r["max_ms"])
    print(line)


def garbage(e, peer, size=32, n=50):
    """Bytes of garbage per send and per receive (irecv reuses its buffers)."""
    buf = bytearray(size)
    packet(buf, 0, 0)
    gc.collect()
    gc.disable()
    try:
        a = gc.mem_alloc()
        for _ in range(n):
            e.send(peer, buf, False)
        b = gc.mem_alloc()
        for _ in range(n):
            e.irecv(0)
        c = gc.mem_alloc()
    finally:
        gc.enable()
    return (b - a) / n, (c - b) / n


def check():
    """espnow imports, the radio starts; MAC, channel, garbage. True if all is well."""
    try:
        import espnow  # noqa: F401
        import aioespnow  # noqa: F401
    except ImportError as err:
        print("FAIL: no ESP-NOW in this firmware:", err)
        return False
    e, sta, ch = radio()
    print("espnow ok  mac %s  channel %d  wifi %s" % (
        mac_str(sta.config("mac")), ch, "connected" if sta.isconnected() else "not connected"))
    send_g, recv_g = garbage(e, BROADCAST)
    print("garbage per send %.0f bytes, per receive %.0f bytes" % (send_g, recv_g))
    print("free heap %d bytes" % gc.mem_free())
    print("CHECK OK")
    return True


def echo_one(e, peers, host, msg):
    """One packet in: if it is ours, send it back to its sender. True if sent back."""
    if read(msg) is None:
        return False
    host = bytes(host)
    if host not in peers:
        try:
            e.add_peer(host)
        except OSError:
            pass
        peers.add(host)
        print("echoing to", mac_str(host))
    try:
        e.send(host, msg, False)
    except OSError:
        return False
    return True


def echo(seconds=120):
    """Send every packet of ours straight back to its sender, for this long."""
    e, sta, ch = radio()
    print("echo  mac %s  channel %d  for %d s" % (mac_str(sta.config("mac")), ch, seconds))
    peers = set()
    n = 0
    end = time.ticks_add(time.ticks_ms(), seconds * 1000)
    last = time.ticks_ms()
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        host, msg = e.irecv(200)
        if not echo_one(e, peers, host, msg):
            continue
        n += 1
        if time.ticks_diff(time.ticks_ms(), last) > 5000:
            last = time.ticks_ms()
            print("echoed", n)
    print("ECHO DONE: %d packets" % n)
    return n


def run(e, peer, size, count=COUNT, rate=RATE):
    """Send count packets of size bytes to peer at rate a second; round trips back."""
    buf = bytearray(size)
    gap = 1000000 // rate
    rtts = []
    replier = None
    while e.irecv(0)[1]:            # empty anything left from before
        pass
    for seq in range(count):
        t0 = ticks_us()
        packet(buf, seq, t0)
        try:
            e.send(peer, buf, False)
        except OSError:
            pass
        while True:                 # wait for this one's reply (older ones are late: lost)
            left = TIMEOUT_MS - ticks_diff(ticks_us(), t0) // 1000
            if left <= 0:
                break
            host, msg = e.irecv(left)
            got = read(msg)
            if got is not None and got[0] == seq & 0xFFFF:
                rtts.append(ticks_diff(ticks_us(), t0))
                replier = bytes(host)
                break
        wait = gap - ticks_diff(ticks_us(), t0)
        if wait > 0:
            time.sleep_us(wait)
    return stats(rtts, count), replier


def ping(count=COUNT, rate=RATE, sizes=SIZES):
    """Broadcast then unicast runs against an echo badge. Returns the results."""
    e, sta, ch = radio()
    print("ping  mac %s  channel %d  %d packets at %d/s" % (mac_str(sta.config("mac")), ch, count, rate))
    results = {}
    echo_mac = None
    for size in sizes:
        r, who = run(e, BROADCAST, size, count, rate)
        results["broadcast %d" % size] = r
        report("broadcast %dB" % size, r)
        echo_mac = echo_mac or who
    if echo_mac is None:
        print("PING FAIL: no replies. Is echo() running on the other badge, on channel %d?" % ch)
        return results
    print("echo badge", mac_str(echo_mac))
    try:
        e.add_peer(echo_mac)
    except OSError:
        pass
    for size in sizes:
        r, _ = run(e, echo_mac, size, count, rate)
        results["unicast %d" % size] = r
        report("unicast %dB" % size, r)
    print("PING DONE")
    return results
