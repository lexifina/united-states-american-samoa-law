#!/bin/bash
# Private (never published). gitlaw-scraper-dell 2026-10-31 (rewritten 2026-11-01): publishes a Brazilian city build
# year by year, newest first, one br_city_verify.sh run (= one year, a small PUBLISH batch) at a time.
#
#   bash br_city_loop.sh <folder> <years-cmd> <done-cmd> <claim>
#
# <years-cmd> (run in <folder>) prints the years whose fetch is complete, separated by spaces or commas, brackets
# allowed. Years already in <folder>/.verified-years are skipped; a year that fails is added to .failed-years, logged,
# and skipped (look at it by hand: bash br_city_verify.sh <folder> <year>). When no year is left and the fetch whose
# PID is in <folder>/fetch.pid is gone: if <done-cmd> succeeds (the whole list fetched) the claim file is deleted,
# otherwise the claim is kept. Restart everything with: powershell -File world-law/br_city_resume.ps1
D=$(cd "$(dirname "$0")" && pwd)
F=$1; YEARS=$2; DONE=$3; CLAIM=$4
cd "$F" || exit 1
touch .verified-years .failed-years
while :; do
  pid=$(cat fetch.pid 2>/dev/null)
  alive=0; [ -n "$pid" ] && alive=$(tasklist //FI "PID eq $pid" | grep -c " $pid ")
  next=$(eval "$YEARS" | tr -c '0-9\n' ' ' | tr ' ' '\n' | grep -E '^[0-9]{3,4}$' | sort -rn | \
         grep -vxF -f .verified-years | grep -vxF -f .failed-years | head -1)
  if [ -n "$next" ]; then
    echo "$(date -u +%FT%TZ) year $next"
    out=$(bash "$D/br_city_verify.sh" . "$next" 2>&1); rc=$?
    if [ $rc -eq 0 ]; then echo "$out" | grep -E "PUBLISHED|nothing new|acts'|versions checked"
    elif [ $rc -eq 3 ]; then echo "locked; waiting"; sleep 60
    else echo "$out" | tail -15; echo "VERIFY FAILED $next"; echo "$next" >> .failed-years; fi
    continue
  fi
  if [ "$alive" = 0 ]; then
    if (eval "$DONE"); then rm -f "$CLAIM"; echo "$(date -u +%FT%TZ) list done and published; claim $CLAIM deleted"
    else echo "$(date -u +%FT%TZ) fetch gone before the list was done; claim kept (resume: br_city_resume.ps1)"; fi
    exit 0
  fi
  sleep 120
done
