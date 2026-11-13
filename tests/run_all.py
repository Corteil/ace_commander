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
for name in ("test_game.py", "test_app.py", "test_commander.py", "test_leds.py",
             "test_bench.py", "test_run.py"):
    r = subprocess.run([sys.executable, os.path.join(HERE, name)], capture_output=True, text=True)
    lines = [l for l in r.stdout.strip().split("\n") if not l.startswith(("PERF", "BENCH"))]
    print("%-14s %s" % (name, "ok" if r.returncode == 0 else "FAILED"), "-", lines[-1] if lines else "")
    if r.returncode:
        failed.append(name)
        print(r.stdout[-1500:])
        print(r.stderr[-3000:])
sys.exit(1 if failed else 0)
