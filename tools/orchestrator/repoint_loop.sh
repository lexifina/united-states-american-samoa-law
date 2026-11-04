#!/bin/bash
# global-law pointer loop: one pass every 15 minutes, so each pass makes at most one global-law commit carrying every
# pin that moved (batching since 2026-11-04; it was a pass every ~30 s). Checks every 30 s for:
#   stop-repoint  stop after the current pass
#   repoint-now   run a pass now (the file is removed when the pass starts)
# The pass's full output goes to repoint-last-pass.log; its last line (the summary) to repoint_loop.log. Each pass
# writes heartbeat.json; pushwatch.sh alerts when no pass has completed for 30 minutes.
cd "$(dirname "$0")" || exit 1
echo $$ > repoint.pid
INTERVAL=900
next=0
while [ ! -f stop-repoint ]; do
  now=$(date +%s)
  if [ -f repoint-now ] || [ "$now" -ge "$next" ]; then
    why=scheduled; [ -f repoint-now ] && why=requested
    rm -f repoint-now
    next=$((now + INTERVAL))
    echo "=== $(date -u +%T) ($why)"
    timeout 1800 python -X utf8 repoint_fast.py --push > repoint-last-pass.log 2>&1
    rc=$?
    tail -1 repoint-last-pass.log
    # pushwatch.sh greps this log for FAILED: a crashed or timed-out pass reaches alerts.log
    [ "$rc" -ne 0 ] && echo "pass FAILED (exit $rc); full output in repoint-last-pass.log"
  fi
  sleep 30
done >> repoint_loop.log 2>&1
rm -f repoint.pid
