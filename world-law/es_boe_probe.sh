#!/bin/bash
# BOE open-data outage probe (gitlaw-scraper-dell): one request every 30 min to an in-force norm until it answers
# 200; gives up at 06:00 UTC. Every request logged in logs/es-boe-requests.jsonl.
LOG=/c/Users/alany/Documents/lexifina/scripts/world-law/logs/es-boe-requests.jsonl
URL=https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2026-17836
STOP=$(date -u -d '2026-10-31 06:00:00' +%s)
while true; do
  sleep 1800
  [ $(date -u +%s) -ge $STOP ] && { echo "gave up $(date -u +%FT%TZ)"; exit 1; }
  at=$(date -u +%FT%TZ)
  out=$(curl -s -m 60 -A 'lexifina-git-for-law/1.0 (world-law@lexifina.com)' -H 'Accept: application/xml' -o /dev/null -w '%{http_code} %{size_download} %{time_total}' "$URL")
  set -- $out
  echo "{\"at\": \"$at\", \"status\": $1, \"bytes\": $2, \"secs\": $3, \"url\": \"$URL\", \"note\": \"outage probe (30 min)\"}" >> $LOG
  echo "$at $1"
  [ "$1" = "200" ] && exit 0
done
