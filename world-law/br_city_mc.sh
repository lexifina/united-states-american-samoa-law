#!/bin/bash
# Private (never published). Maceió: `bash br_city_mc.sh done` exits 0 when every listed law PDF has been fetched;
# `bash br_city_mc.sh loop` runs the verify/publish loop (appends to loop.log).
F=/c/Users/alany/Documents/lexifina/scripts/brazil-maceio-city-law
YEARS='python -X utf8 ../world-law/br_city_years.py .'
DONE='grep -qs "pdfs done" fetch*.log'
export PATH="/usr/bin:/mingw64/bin:$PATH"
cd "$F" || exit 1
case "$1" in
  done) eval "$DONE" ;;
  loop) exec bash "$(dirname "$0")/br_city_loop.sh" "$F" "$YEARS" "$DONE" \
          /c/Users/alany/Documents/lexifina/scripts/world-law/claims/brazil-maceio-city-law.txt >> loop.log 2>&1 ;;
esac
