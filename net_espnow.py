"""The badge's radio link for multiplayer (duel.py): ESP-NOW broadcast, no router.
Measured with tools/espnow_link.py (plans/MULTIPLAYER.md): ~5 ms each way, no
loss side by side, ~1% at 10 m through a door. All badges must be on one
Wi-Fi channel: one on a network uses that network's; one that isn't is set to
CHANNEL (and disconnected first, so it stops hunting for its network).

recv() is read every frame by the game, so the bigger receive buffer (RXBUF)
holds a few frames' packets; the default ~500 bytes dropped packets.

Build 161 (a host crashed with "ESPNow.recv(): buffer error", 2026-11-25, four
badges), read from the firmware and MicroPython 1.28's source:
- The firmware has an ESP-NOW service (system.espnow.espnow_service, started at
  boot) whose background task reads every packet too, into the same buffer (all
  ESPNow objects share one radio, and espnow.ESPNow._data is one class buffer):
  it took some of our packets, and the two readers broke together. While we have
  the radio, its reader is paused (its task cancelled) and started again on
  close() (Platform.minimise).
- The radio writes a packet into the receive buffer in three pieces (header, sender,
  message: modespnow.c recv_cb, on the Wi-Fi task); a read between them finds the
  header but not the rest and raises "buffer error", and the buffer is then out of
  step for good. rx_packets (stats()[3]) counts a packet only once it is all
  written, so recv() reads no more than it has counted: never half a packet. If a
  read fails anyway, the radio is restarted (an empty buffer).
- rxbuf takes effect only when ESP-NOW starts (espnow_init), and the service had
  already started it: RXBUF never applied. We restart it (active False, True).
- The service sets Wi-Fi power saving (which drops ESP-NOW packets) every 10 s
  unless someone listens for its EspNowReceiveEvent: we listen (never called, its
  reader being paused) and switch power saving off.
On a firmware without the service, only the counting and the restart apply.
"""
CHANNEL = 1
VERSION = 0xA1          # the envelope (hosts/pi/envelope.py, build 175): VERSION, the sender's
HEAD = 7                # 6-byte player id, the game's packet. The id, not the radio address,
FRESH_MS = 10000        # says who sent it. Other versions are noted for UPDATE REQUIRED
RXBUF = 4096
BROADCAST = b"\xff" * 6
_NONE = (None, None)


def open_env(r, mismatch, ids):
    """(sender's player id, packet) from an envelope (r: the radio's [address, data]),
    or None: another version of the game is noted in mismatch (address -> (ms, newer)).
    The id is bytes (the game compares and keeps it), kept in ids by radio address and
    made again only when it changes (a relaying Pi sends many players' from one address):
    no new bytes per packet."""
    msg = r[1]
    n = len(msg)
    if n >= HEAD + 2 and msg[0] == VERSION and msg[HEAD] == 0x41 and msg[HEAD + 1] == 0x4D:
        mac = r[0]
        ident = ids.get(mac)
        if ident is None or not _same(ident, msg):
            ident = bytes(memoryview(msg)[1:HEAD])
            ids[mac] = ident
        return ident, memoryview(msg)[HEAD:]
    newer = None
    if n >= 2 and msg[0] == 0x41 and msg[1] == 0x4D:            # "AM": from before the envelope
        newer = False
    elif n >= HEAD + 2 and 0xA0 <= msg[0] <= 0xAF and msg[HEAD] == 0x41 and msg[HEAD + 1] == 0x4D:
        newer = msg[0] > VERSION
    if newer is not None:
        import time
        mismatch[bytes(r[0])] = (time.ticks_ms(), newer)
    return None


def _same(ident, msg):
    for i in range(6):
        if ident[i] != msg[1 + i]:
            return False
    return True


def _hex(b):
    return ":".join("%02x" % x for x in b)


async def _never(event):
    pass                        # (the service's reader is paused: nothing comes)


def _service():
    """The firmware's ESP-NOW service, the scheduler and the event bus, or None."""
    try:
        from system.espnow import espnow_service, EspNowReceiveEvent
        from system.scheduler import scheduler
        from system.eventbus import eventbus
    except Exception:
        return None
    return espnow_service, EspNowReceiveEvent, scheduler, eventbus


class Link:
    def __init__(self, channel=CHANNEL):
        self.channel_wanted = channel
        self.e = None
        self.paused = None      # the service's reader task we cancelled (to restart)
        self.listening = None
        self.restarts = 0       # radio restarts after a bad read (for the log)
        self.mismatch = {}      # address -> (ms, newer): players on another version
        self.ids = {}           # radio address -> the player id last heard from it
        self._open()

    def _open(self):
        import network
        import espnow
        sta = network.WLAN(network.STA_IF)
        sta.active(True)
        if not sta.isconnected():
            try:
                sta.disconnect()
            except Exception:
                pass
            sta.config(channel=self.channel_wanted)
        self._pause_service()
        try:
            sta.config(pm=sta.PM_NONE)  # power saving drops ESP-NOW packets
        except Exception:
            pass
        self.e = espnow.ESPNow()
        self._restart()
        self.id = bytes(sta.config("mac"))
        self.out = bytearray(HEAD + 250)
        self.out[0] = VERSION
        self.out[1:HEAD] = self.id
        self.channel = sta.config("channel")

    def _restart(self):
        """ESP-NOW off and on: an empty receive buffer of RXBUF, the broadcast peer."""
        e = self.e
        try:
            e.active(False)
        except Exception:
            pass
        try:
            e.config(rxbuf=RXBUF)
        except Exception:
            pass
        e.active(True)
        try:
            e.add_peer(BROADCAST)
        except OSError:
            pass                # already a peer
        self.seen = e.stats()[3]    # packets written so far (the count never resets)
        self.ready = 0          # counted but not yet read

    def _pause_service(self):
        s = _service()
        if s is None or self.paused is not None:
            return
        svc, event, scheduler, eventbus = s
        task = scheduler.background_tasks.get(svc)
        if task is not None:
            task.cancel()
            del scheduler.background_tasks[svc]
            self.paused = svc
        if self.listening is None:  # so the service keeps the radio awake
            eventbus.on_async(event, _never, self)
            self.listening = (eventbus, event)

    def net_info(self):
        """The NETWORK INFO page's lines (ace._draw_netinfo): (text, kind), kind
        "ok", "warn" or "" (plain)."""
        import network
        sta = network.WLAN(network.STA_IF)
        try:
            ch = sta.config("channel")
        except Exception:
            ch = self.channel if self.e is not None else None
        lines = [("LINK: ESP-NOW (RADIO)", "ok"),
                 ("CHANNEL: %s" % ("?" if ch is None else ch), "")]
        if sta.isconnected():
            try:
                ssid = sta.config("ssid")
            except Exception:
                ssid = "?"
            lines.append(("WI-FI: " + str(ssid)[:16], "warn"))
            try:
                lines.append(("IP: " + sta.ifconfig()[0], ""))
            except Exception:
                pass
            lines.append(("OTHERS MUST BE ON CH %s" % ch, "warn"))
        else:
            lines.append(("WI-FI: NOT CONNECTED", ""))
        if self.id:
            lines.append(("YOU: " + _hex(self.id[3:]), ""))
        return lines

    def can_leave_wifi(self):
        """On a network (so on its channel, not CHANNEL): NETWORK INFO offers to leave."""
        import network
        return network.WLAN(network.STA_IF).isconnected()

    def leave_wifi(self):
        """Off the network and onto CHANNEL, where badges off any network are."""
        import network
        sta = network.WLAN(network.STA_IF)
        try:
            sta.disconnect()
        except Exception:
            pass
        try:
            sta.config(channel=self.channel_wanted)
        except Exception:
            pass
        try:
            self.channel = sta.config("channel")
        except Exception:
            self.channel = self.channel_wanted

    def close(self):
        """Give the radio back: the firmware's ESP-NOW service reads it again."""
        if self.e is None:
            return
        self.e = None
        if self.listening is not None:
            eventbus, event = self.listening
            self.listening = None
            try:
                eventbus.remove(event, _never, self)
            except Exception:
                pass
        svc = self.paused
        self.paused = None
        if svc is not None:
            s = _service()
            if s is not None:
                import asyncio
                s[2].background_tasks[svc] = asyncio.create_task(svc.background_task())

    def send(self, msg):
        if self.e is None:
            self._open()        # back after minimise
        n = len(msg)
        out = self.out          # the envelope, made once: no garbage per packet
        out[HEAD:HEAD + n] = msg
        try:
            self.e.send(BROADCAST, memoryview(out)[:HEAD + n], False)
        except OSError:
            pass                # a full send queue: the next pose will do

    def recv(self):
        """(sender, packet) or (None, None). Both are buffers the radio reuses:
        copy what you keep. Only packets the radio has finished writing."""
        e = self.e
        if e is None:
            self._open()
            e = self.e
        if self.ready <= 0:
            n = e.stats()[3]
            self.ready = n - self.seen
            self.seen = n
            if self.ready <= 0:
                self.ready = 0
                return _NONE
        self.ready -= 1
        try:
            r = e.irecv(0)
        except ValueError:      # "buffer error": out of step; start the buffer afresh
            self.restarts += 1
            print("net_espnow: receive buffer error, radio restarted (%d)" % self.restarts)
            self._restart()
            return _NONE
        if r[0] is None:
            self.ready = 0      # (dropped as the buffer was full: none left)
            return r
        got = open_env(r, self.mismatch, self.ids)
        if got is None:
            return self.recv()  # another version, or not the game's: the next one
        return got

    def version_issues(self):
        """(older, newer): players heard lately on another version of the game."""
        import time
        now = time.ticks_ms()
        live = [nw for t, nw in self.mismatch.values() if time.ticks_diff(now, t) < FRESH_MS]
        return sum(1 for x in live if not x), sum(1 for x in live if x)
