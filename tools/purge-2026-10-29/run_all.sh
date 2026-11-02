#!/bin/bash
# Runs purge_rewrite.py --push over every lexifina/<slug>-law repo, 6 at a time; repeats for repos skipped as not yet
# archived until the archive run has finished and nothing is left to retry. Results: results.jsonl
cd "$(dirname "$0")"
for pass in 1 2 3 4 5 6; do
  todo=$(ls -d /c/Users/alany/Documents/*-law 2>/dev/null | xargs -n1 basename | while read r; do
    grep -q "\"repo\": \"$r\".*\"status\": \"\(pushed and verified\|nothing to change\)\"" results.jsonl 2>/dev/null || echo $r; done)
  [ -z "$todo" ] && break
  echo "=== pass $pass: $(echo "$todo" | wc -w) repos $(date -u +%T)"
  echo "$todo" | xargs -P 6 -I{} python -X utf8 purge_rewrite.py {} --push >> results.jsonl
  pgrep -f archive_all.py >/dev/null 2>&1 || [ $pass -ge 2 ] || continue
  sleep 120
done
echo "=== done $(date -u +%T)"
