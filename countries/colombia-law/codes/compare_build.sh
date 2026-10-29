#!/bin/sh
# Build the part in the old full-units layout and in the `changes` layout, and compare the two repositories.
# Usage: sh codes/compare_build.sh   (from scripts/colombia-law)
set -e
D=C:/Users/alany/Documents/lexifina/scripts/colombia-law
T=$D/.tmp-build-codes
rm -rf $T/src $T/src2 $T/repo $T/repo2 && mkdir -p $T/src/corpus.d $T/src2/corpus.d
python -X utf8 -c "import json;c=json.load(open('$D/corpus.json',encoding='utf-8'));json.dump({'country':c['country'],'sources':[],'laws':{},'acts':[],'applies':[],'decisions':[],'ai_use':[]},open('$T/src/corpus.json','w',encoding='utf-8'),ensure_ascii=False)"
cp $T/src/corpus.json $T/src2/corpus.json
python -X utf8 $D/codes/parse_codes.py --full-units --out $T/src/corpus.d/50-codes.json | head -1
python -X utf8 $D/codes/parse_codes.py --out $T/src2/corpus.d/50-codes.json | head -1
python -c "import json;a=json.load(open('$T/src/corpus.d/50-codes.json',encoding='utf-8'));b=json.load(open('$T/src2/corpus.d/50-codes.json',encoding='utf-8'));a['sources'][0]['requests']=b['sources'][0]['requests'];json.dump(a,open('$T/src/corpus.d/50-codes.json','w',encoding='utf-8'),ensure_ascii=False,separators=(',',':'))"
python -X utf8 $D/../gitlaw_common/build.py $T/src --repo $T/repo --docs-date 2026-10-28 2>&1 | tail -3
python -X utf8 $D/../gitlaw_common/build.py $T/src2 --repo $T/repo2 --docs-date 2026-10-28 --compare $T/repo 2>&1 | tail -12
python -X utf8 $D/../gitlaw_common/check.py $T/repo2 --corpus $T/src2/corpus.json 2>&1 | grep -E "mismatches|unexplained|trailer"
