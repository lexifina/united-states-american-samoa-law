#!/bin/bash
# Private (never published). São Paulo city: `bash br_city_sp.sh done` exits 0 when the fetch list is done (1892 in
# years-done.json); `bash br_city_sp.sh loop` runs the verify/publish loop (appends to loop.log).
F=/c/Users/alany/Documents/lexifina/scripts/brazil-sao-paulo-city-law
YEARS='cat .cache/years-done.json'
DONE="python -X utf8 -c \"import json,sys;sys.exit(1892 not in json.load(open('.cache/years-done.json')))\""
export PATH="/usr/bin:/mingw64/bin:$PATH"
cd "$F" || exit 1
case "$1" in
  done) eval "$DONE" ;;
  loop) exec bash "$(dirname "$0")/br_city_loop.sh" "$F" "$YEARS" "$DONE" \
          /c/Users/alany/Documents/lexifina/scripts/world-law/claims/brazil-sao-paulo-city-law.txt >> loop.log 2>&1 ;;
esac
