#!/bin/bash
# Writes one line to alerts.log when global-law has not pushed for 15 min or the loop logs an error.
cd "$(dirname "$0")" || exit 1
echo $$ > pushwatch.pid
L=repoint_loop.log
pc=$(grep -c "'pushed': '[0-9a-f]" "$L"); ec=$(grep -c "Traceback\|FAILED\|HTTPError" "$L"); last=$(date +%s); warned=0
while [ ! -f stop-pushwatch ]; do
  p=$(grep -c "'pushed': '[0-9a-f]" "$L"); e=$(grep -c "Traceback\|FAILED\|HTTPError" "$L")
  if [ "$p" -gt "$pc" ]; then pc=$p; last=$(date +%s); warned=0; fi
  if [ "$e" -gt "$ec" ]; then ec=$e; echo "$(date -u +%FT%TZ) loop error: $(grep "Traceback\|FAILED\|HTTPError" "$L" | tail -1 | cut -c1-200)" >> alerts.log; fi
  now=$(date +%s)
  if [ $((now-last)) -gt 900 ] && [ $warned = 0 ]; then echo "$(date -u +%FT%TZ) no global-law push for 15 min" >> alerts.log; warned=1; fi
  sleep 60
done
rm -f pushwatch.pid
