# Run on the badge (mpremote connect PORT run tools/badge_checksums.py): prints
# "name sha256" for every .py and .mpy in /apps/ace_commander, to compare with a
# build (build/badge/ace_commander) after copying. MicroPython only.
import binascii
import hashlib
import os

d = "/apps/ace_commander/"
for n in sorted(os.listdir(d)):
    if not (n.endswith(".mpy") or n.endswith(".py")):
        continue
    h = hashlib.sha256()
    with open(d + n, "rb") as f:
        while True:
            b = f.read(2048)
            if not b:
                break
            h.update(b)
    print(n, binascii.hexlify(h.digest()).decode())
