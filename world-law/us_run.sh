#!/bin/sh
# us_run.sh <state> : docs, build into empty folder, check. (BelowNormal via PowerShell Start)
S=$1
R=/c/Users/alany/Documents/lexifina
B=/c/Users/alany/Documents/united-states-$S-law-build
export GITLAW_NO_CHECKOUT=1
cd $R/scripts/united-states-$S-law && python -X utf8 docs.py || exit 1
rm -rf "$B"; mkdir -p "$B"; git -C "$B" init -q -b main
cd $R
python -X utf8 scripts/gitlaw_common/build.py scripts/united-states-$S-law --repo "$B" --docs-date 2026-10-30 > $B.log 2>&1 || { tail -20 $B.log; exit 1; }
tail -3 $B.log
python -X utf8 scripts/gitlaw_common/check.py "$B" --corpus scripts/united-states-$S-law/corpus.json 2>&1 | tail -15
