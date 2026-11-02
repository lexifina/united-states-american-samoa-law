#!/bin/bash
# Runs goal_tracker.py every 20 minutes; stops when the file "stop-goaltrack" exists.
cd "$(dirname "$0")" || exit 1
while [ ! -f stop-goaltrack ]; do
  sleep 1200
  [ -f stop-goaltrack ] && break
  timeout 600 python -X utf8 goal_tracker.py >> goaltrack.log 2>&1
done
