#!/bin/bash
# Exits (waking the coordinator) as soon as the push loop stalls or a push fails:
# - no "--- pass" line in the autopush log for STALL seconds (default 480), or
# - a pass that reports "push failed", "build failed", "check failed" or a crashed pass.
# Prints the reason and the last pass. Run it in the background; rerun it after each wake-up.
LOG=/c/Users/alany/Documents/lexifina/scripts/south-america-law/logs/autopush.log
STALL=${STALL:-480}
seen=$(grep -c -- "--- pass" "$LOG")
while true; do
  sleep 30
  last=$(grep -- "--- pass" "$LOG" | tail -1 | sed -E 's/--- pass at ([0-9T:-]+)Z.*/\1/')
  age=$(( $(date -u +%s) - $(date -u -d "${last/T/ }" +%s) ))
  if [ "$age" -gt "$STALL" ]; then echo "STALL: no autopush pass for ${age}s (last ${last}Z)"; tail -3 "$LOG"; exit 0; fi
  # RAM: 35+ agents share this machine; wake the coordinator before memory runs out.
  free_mb=$(powershell -NoProfile -Command "[int]((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024)" 2>/dev/null | tr -d '\r')
  if [ -n "$free_mb" ] && [ "$free_mb" -lt 1500 ]; then echo "LOW RAM: ${free_mb} MB free"; exit 0; fi
  # Per country (each country runs its own loop): any started country whose BUILD_STATUS.json is older than 15 min.
  for f in /c/Users/alany/Documents/lexifina/scripts/*-law/BUILD_STATUS.json; do
    a=$(( $(date +%s) - $(stat -c %Y "$f") ))
    if [ "$a" -gt 900 ]; then echo "STALL: $(basename $(dirname $f)) has not completed a pass for ${a}s"; exit 0; fi
  done
  now=$(grep -c -- "--- pass" "$LOG")
  if [ "$now" -gt "$seen" ]; then
    new=$(awk -v n="$seen" '/--- pass/{c++} c>n' "$LOG")
    # New failures only: lines repeating an old result ("unchanged since ... failed") are not news.
    fails=$(echo "$new" | grep -E "push failed|build failed|check failed|pass exited|scheduler exited|FAILED" | grep -v "unchanged since")
    if [ -n "$fails" ]; then
      echo "FAILURE in pass at ${last}Z:"; echo "$fails"; exit 0
    fi
    seen=$now
  fi
done
