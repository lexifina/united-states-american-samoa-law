#!/bin/bash
# Private. SAPL municipal wave (gitlaw-scraper-dell, 2026-11-01): after the first part of a city has .PUBLISH, create
# lexifina/<slug>-law (one API call, br_scaffold.py; skipped when it exists), write the docs and PROGRESS.md so the
# autopush loop (claim + folder) publishes main. Usage: bash world-law/br_sapl_open.sh <folder>
set -eu
S=/c/Users/alany/Documents/lexifina/scripts
F=$1
cd $S
ls $F/corpus.d/*.PUBLISH >/dev/null 2>&1 || { echo "no PUBLISHed part in $F"; exit 1; }
read -r SLUG CITY HOST < <(python -X utf8 -c "import json;s=json.load(open('$F/sapl-spec.json',encoding='utf-8'));print(s['slug'][len('brazil-'):], s['city'].replace(' ','_'), s['host'])")
CITY=${CITY//_/ }
python -X utf8 world-law/br_scaffold.py "$SLUG" "$CITY (city)" "Câmara Municipal de $CITY, SAPL ($HOST)." "-0300"
python -X utf8 world-law/br_sapl_docs.py $F
[ -f $F/PUBLISH ] || echo "Verified $(date -u +%FT%TZ) (gitlaw-scraper-dell): $CITY city published part by part; only corpus.d parts with their own .PUBLISH go to main (each checked against the SAPL pages and PDFs: check.py clean, letters-and-digits check with a second reader clean)." > $F/PUBLISH
T=$(date -u +%FT%TZ)
if [ ! -f $F/PROGRESS.md ]; then
  printf '# %s (gitlaw-scraper-dell, 2026-11-01)\n\nPrivate. Municipal tier, SAPL wave via global-law-main-composer. Source: Câmara Municipal de %s SAPL (%s): Interlegis robots, `*` Crawl-delay 60 (61 s kept), no AI rule; SAPL footer CC BY-SA 4.0; Câmara site terms read (world-law/.br-cities/gate/%s.json); no challenge. Fetcher: world-law/br_sapl_wave.py (one process for the whole wave). Parts: parse.py (Lei Orgânica, Texto Articulado, if any), laws.py (laws newest first); verify world-law/br_sapl_verify.sh.\n' "$(basename $F)" "$CITY" "$HOST" "$HOST" > $F/PROGRESS.md
fi
echo "- $T: repo ready; PUBLISHed: $(cd $F/corpus.d && ls *.PUBLISH | tr '\n' ' ')" >> $F/PROGRESS.md
tail -2 $F/PROGRESS.md
