#!/bin/sh
# Test build of the codes part alone into ../.tmp-build-codes (autopush owns the clone).
# Usage: sh codes/test_build.sh   (from scripts/colombia-law)
set -e
D=C:/Users/alany/Documents/lexifina/scripts/colombia-law
T=$D/.tmp-build-codes
rm -rf $T/src && mkdir -p $T/src/corpus.d
python -X utf8 -c "import json,sys;c=json.load(open('$D/corpus.json',encoding='utf-8'));json.dump({'country':c['country'],'sources':[],'laws':{},'acts':[],'applies':[],'decisions':[],'ai_use':[]},open('$T/src/corpus.json','w',encoding='utf-8'),ensure_ascii=False)"
python -X utf8 $D/codes/parse_codes.py --out $T/src/corpus.d/50-codes.json
cp -r $D/repo $T/src/repo 2>/dev/null || true
python -X utf8 $D/../gitlaw_common/build.py $T/src --repo $T/repo --docs-date 2026-10-28 2>&1 | tail -8
python -X utf8 $D/../gitlaw_common/check.py $T/repo --corpus $T/src/corpus.json 2>&1 | tail -8
