"""Run every test. From the repo folder:  python tests/run_all.py

Needs ship_data.py in the repo folder (make it with tools/import_ships.py), and
the repo folder itself must be called ace_commander, because the tests import the
app as the package `ace_commander`. render.py also needs Pillow.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
failed = []
for name in ("test_game.py", "test_app.py", "test_commander.py", "test_galaxy.py", "test_market.py",
             "test_equipment.py", "test_ships.py", "test_shipyard.py", "test_find.py", "test_equip_effects.py", "test_traffic.py", "test_witchspace.py", "test_loader.py", "test_describe.py", "test_missions.py", "test_original_ships.py", "test_original_data.py", "test_install.py",
             "test_leds.py", "test_hardcore.py", "test_views.py", "test_keys.py", "test_analog.py",
             "test_bench.py", "test_run.py", "test_pi_controls.py", "test_build_mpy.py",
             "test_sound.py", "test_espnow_link.py"):
    r = subprocess.run([sys.executable, os.path.join(HERE, name)], capture_output=True, text=True)
    lines = [l for l in r.stdout.strip().split("\n") if not l.startswith(("PERF", "BENCH"))]
    print("%-14s %s" % (name, "ok" if r.returncode == 0 else "FAILED"), "-", lines[-1] if lines else "")
    if r.returncode:
        failed.append(name)
        print(r.stdout[-1500:])
        print(r.stderr[-3000:])
# the Raspberry Pi host (hosts/pi), where pygame is installed
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
try:
    import pygame  # noqa: F401
    for pi_name, label in (("test_pi_host.py", "pi host"), ("test_pi_trip.py", "pi trip"),
                            ("test_pi_pad.py", "pi pad"), ("test_pi_elite.py", "pi elite")):
        pi_test = os.path.join(os.path.dirname(HERE), "hosts", "pi", "tests", pi_name)
        r = subprocess.run([sys.executable, pi_test], capture_output=True, text=True)
        lines = [l for l in r.stdout.strip().split("\n") if l and not l.startswith(("pygame ", "Hello from"))]
        print("%-14s %s" % (label, "ok" if r.returncode == 0 else "FAILED"), "-", lines[-1] if lines else "")
        if r.returncode:
            failed.append("hosts/pi/tests/" + pi_name)
            print(r.stdout[-1500:])
            print(r.stderr[-3000:])
except ImportError:
    print("pi host, trip  skipped - no pygame")
# the Tufty's buzzers (builds 140, 146)
bz = os.path.join(os.path.dirname(HERE), "hosts", "tufty", "tests", "test_buzzer_tufty.py")
r = subprocess.run([sys.executable, bz], capture_output=True, text=True)
lines = r.stdout.strip().split("\n")
print("%-14s %s" % ("tufty buzzer", "ok" if r.returncode == 0 else "FAILED"), "-", lines[-1] if lines else "")
if r.returncode:
    failed.append("hosts/tufty/tests/test_buzzer_tufty.py")
    print(r.stdout[-1500:])
    print(r.stderr[-3000:])
# the Tufty 2350 host (hosts/tufty), on Badgeware v3 stand-ins drawn with Pillow
tufty_test = os.path.join(os.path.dirname(HERE), "hosts", "tufty", "tests", "test_tufty_host.py")
r = subprocess.run([sys.executable, tufty_test], capture_output=True, text=True)
lines = [l for l in r.stdout.strip().split("\n") if l and not l.startswith("PERF")]
print("%-14s %s" % ("tufty host", "ok" if r.returncode == 0 else "FAILED"), "-", lines[-1] if lines else "")
if r.returncode:
    failed.append("hosts/tufty/tests/test_tufty_host.py")
    print(r.stdout[-1500:])
    print(r.stderr[-3000:])
sys.exit(1 if failed else 0)
