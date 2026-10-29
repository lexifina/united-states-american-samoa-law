#!/bin/sh
# Test build of the CST part alone into cst/.tmp/build (autopush owns the clone), then check.py and a --compare rebuild.
# Usage: sh cst/test_build.sh   (from scripts/colombia-law)
set -e
D=C:/Users/alany/Documents/lexifina/scripts/colombia-law
T=$D/cst/.tmp/build
rm -rf $T && mkdir -p $T/src/corpus.d
python -X utf8 -c "import json,sys;c=json.load(open('$D/corpus.json',encoding='utf-8'));json.dump({'country':c['country'],'sources':[],'laws':{},'acts':[],'applies':[],'decisions':[],'ai_use':[]},open('$T/src/corpus.json','w',encoding='utf-8'),ensure_ascii=False)"
python -X utf8 $D/cst/parse_cst.py --out $T/src/corpus.d/70-cst.json
cp -r $D/repo $T/src/repo 2>/dev/null || true
python -X utf8 $D/../gitlaw_common/build.py $T/src --repo $T/repo --docs-date 2026-10-28 2>&1 | tail -8
python -X utf8 $D/../gitlaw_common/check.py $T/repo --corpus $T/src/corpus.json 2>&1 | tail -8
if [ "$1" = "--compare" ]; then
  python -X utf8 $D/../gitlaw_common/build.py $T/src --repo $T/repo2 --docs-date 2026-10-28 --compare $T/repo 2>&1 | tail -5
fi
