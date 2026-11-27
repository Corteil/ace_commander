#!/bin/sh
# Start Ace Commander on the CardputerZero's LCD (the launcher's entry runs this).
# Output goes to ~/.cache/ace_commander/play-<time>.log (kept across reboots; the
# newest 10 kept). Stop it from a shell: touch ~/.cache/ace_commander/stop
HERE=$(dirname "$(readlink -f "$0")")
LOG="$HOME/.cache/ace_commander"
mkdir -p "$LOG"
ls -1t "$LOG"/play-*.log 2>/dev/null | tail -n +10 | xargs -r rm -f
T=$(date +%Y%m%d-%H%M%S)
PYTHONUNBUFFERED=1 python3 "$HERE/run_cz.py" --perf "$@" > "$LOG/play-$T.log" 2>&1
RC=$?
echo "exit $RC" >> "$LOG/play-$T.log"
sync
exit $RC
