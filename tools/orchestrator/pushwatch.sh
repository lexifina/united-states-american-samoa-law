#!/bin/bash
# The pointer loop's watchdog. Writes one line to alerts.log when:
#   - no repoint pass has completed for 30 min (heartbeat.json last_success_at; the loop runs one every 15 min);
#   - global-law has not been pushed for 60 min (was 15 min while the loop ran every ~30 s);
#   - the loop logs an error.
# Each alert fires once, and again only after the condition has cleared.
cd "$(dirname "$0")" || exit 1
echo $$ > pushwatch.pid
L=repoint_loop.log
HB=heartbeat.json
pc=$(grep -c "'pushed': '[0-9a-f]" "$L"); ec=$(grep -c "Traceback\|FAILED\|HTTPError" "$L"); last=$(date +%s); warned=0
started=$(date +%s); stalled=0
while [ ! -f stop-pushwatch ]; do
  p=$(grep -c "'pushed': '[0-9a-f]" "$L"); e=$(grep -c "Traceback\|FAILED\|HTTPError" "$L")
  if [ "$p" -gt "$pc" ]; then pc=$p; last=$(date +%s); warned=0; fi
  if [ "$e" -gt "$ec" ]; then ec=$e; echo "$(date -u +%FT%TZ) loop error: $(grep "Traceback\|FAILED\|HTTPError" "$L" | tail -1 | cut -c1-200)" >> alerts.log; fi
  now=$(date +%s)
  if [ $((now-last)) -gt 3600 ] && [ $warned = 0 ]; then echo "$(date -u +%FT%TZ) no global-law push for 60 min" >> alerts.log; warned=1; fi
  ok_at=$(grep -o '"last_success_at": "[^"]*"' "$HB" 2>/dev/null | cut -d'"' -f4)
  ok_s=$(date -d "$ok_at" +%s 2>/dev/null || echo "$started")
  [ "$ok_s" -lt "$started" ] && [ $((now-started)) -lt 1800 ] && ok_s=$started  # grace after a (re)start
  if [ $((now-ok_s)) -gt 1800 ]; then
    if [ $stalled = 0 ]; then
      echo "$(date -u +%FT%TZ) STALL repoint: no pass has completed for $(( (now-ok_s)/60 )) min (last ${ok_at:-never}); check repoint_loop.log and repoint-last-pass.log, then start.ps1" >> alerts.log
      stalled=1
    fi
  else
    stalled=0
  fi
  sleep 60
done
rm -f pushwatch.pid
