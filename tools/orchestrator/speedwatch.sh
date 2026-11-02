#!/bin/bash
# Runs speedwatch.py every 5 minutes; stops when the file "stop-speedwatch" exists.
cd "$(dirname "$0")" || exit 1
while [ ! -f stop-speedwatch ]; do
  timeout 280 python -X utf8 speedwatch.py >> speedwatch.log 2>&1
  sleep 300
done
