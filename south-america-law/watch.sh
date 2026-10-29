#!/bin/bash
# Exits (waking the coordinator) when any country's corpus.json, ISSUES.md or built main changes, or after 30 min.
cd /c/Users/alany/Documents/lexifina/scripts
snap() { for s in chile uruguay brazil colombia argentina peru paraguay ecuador bolivia venezuela guyana suriname; do f=$s-law; echo "$s corpus=$( [ -f $f/corpus.json ] && stat -c %Y $f/corpus.json ) issues=$( [ -f $f/ISSUES.md ] && stat -c %Y $f/ISSUES.md ) main=$(git -C /c/Users/alany/Documents/$f rev-parse -q --verify main 2>/dev/null | cut -c1-7)"; done; }
a=$(snap); for i in $(seq 1 60); do sleep 30; b=$(snap); if [ "$a" != "$b" ]; then diff <(echo "$a") <(echo "$b") | grep '^>'; exit 0; fi; done; echo "no change in 30 min"
