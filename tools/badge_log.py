#!/usr/bin/env python3
"""Save what the badge prints over USB to badge_log.txt (next to deploy.bat).

Usage: python tools/badge_log.py [seconds] [port]

Needs pyserial, which mpremote installs. With no port given it picks the
badge's port itself. It keeps trying if the badge restarts.
"""
import os
import sys
import time

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    sys.exit("pyserial is missing: run  pip install pyserial")

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "badge_log.txt")
ESPRESSIF = 0x303A


def find_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if p.vid == ESPRESSIF:
            return p.device
    for p in ports:
        if p.vid is not None:     # any USB serial device
            return p.device
    return None


def main():
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
    port = sys.argv[2] if len(sys.argv) > 2 else None
    end = time.time() + seconds
    conn = None
    with open(LOG, "a", encoding="utf-8", errors="replace") as log:
        log.write("\n--- badge output, %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        log.flush()
        try:
            while time.time() < end:
                if conn is None:
                    name = port or find_port()
                    if name is None:
                        time.sleep(0.5)
                        continue
                    try:
                        conn = serial.Serial(name, 115200, timeout=0.5)
                        print("listening on", name)
                    except (serial.SerialException, OSError):
                        conn = None
                        time.sleep(0.5)
                        continue
                try:
                    data = conn.read(4096)
                except (serial.SerialException, OSError):
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = None     # the badge restarted: reconnect
                    continue
                if data:
                    text = data.decode("utf-8", "replace").replace("\r", "")
                    log.write(text)
                    log.flush()
                    sys.stdout.write(text)
                    sys.stdout.flush()
        except KeyboardInterrupt:
            pass
        finally:
            if conn is not None:
                conn.close()
    print("\nsaved to", LOG)


if __name__ == "__main__":
    main()
