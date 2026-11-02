#!/bin/bash
# global-law pointer loop: one pass every ~30 s; stops when the file "stop-repoint" exists.
cd "$(dirname "$0")" || exit 1
echo $$ > repoint.pid
while [ ! -f stop-repoint ]; do
  echo "=== $(date -u +%T)"
  timeout 600 python -X utf8 repoint_fast.py --push 2>&1 | tail -1
  sleep 20
done >> repoint_loop.log 2>&1
rm -f repoint.pid
