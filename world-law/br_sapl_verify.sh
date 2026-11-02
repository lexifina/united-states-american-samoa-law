#!/bin/bash
# Private (never published). SAPL municipal wave (gitlaw-scraper-dell, 2026-11-01): parse (parse.py for the Lei
# Orgânica if present, laws.py), then for every corpus.d part without .PUBLISH: letters check with a second reader
# (check_letters.py for 10-*, check_laws.py for 30-*; laws the second reader disagrees on are left out and re-parsed),
# build + check.py + audit_push; writes .PUBLISH only when all pass. At most $MAXNEW parts are verified per run.
# Usage: bash world-law/br_sapl_verify.sh <scripts/brazil-...-city-law> [today]
set -u
F=$(cd "$1" && pwd -W)
TODAY=${2:-$(date -u +%F)}
MAXNEW=${MAXNEW:-4}
S=C:/Users/alany/Documents/lexifina/scripts
cd "$F"
while :; do
  l=$(tail -1 "$LOCALAPPDATA/gitlaw-cpu.log"); c=$(sed -n 's/.*cpu5=\([0-9]*\).*/\1/p' <<<"$l"); r=$(sed -n 's/.*ram=\([0-9]*\).*/\1/p' <<<"$l")
  [ "${c:-0}" -le 90 ] && [ "${r:-0}" -le 85 ] && break; echo "waiting: $l"; sleep 60
done
parse() {
  if [ -f parse.py ]; then python -X utf8 parse.py --today "$TODAY" || return 1; fi
  if [ -f laws.py ]; then python -X utf8 laws.py --today "$TODAY" || return 1; fi
}
# The Lei Orgânica (10-*) is always published on its own, before any law part.
newparts() {
  local all; all=$(for p in corpus.d/*.json; do [ -e "$p" ] && { [ -e "${p%.json}.PUBLISH" ] || echo "$p"; }; done)
  if grep -q '/10-' <<<"$all"; then grep '/10-' <<<"$all" | head -n 1; else echo "$all" | grep . | head -n "$MAXNEW"; fi
}
letters() {
  : > letters.out; rc=0
  for p in $NEW; do
    case "$(basename "$p")" in
      10-*) python -X utf8 check_letters.py "$p" >> letters.out || rc=1 ;;
      *) python -X utf8 check_laws.py "$p" >> letters.out || rc=1 ;;
    esac
  done
  return $rc
}
parse || { echo PARSE FAIL; exit 1; }
NEW=$(newparts)
[ -z "$NEW" ] && { echo "nothing new"; exit 0; }
echo "new parts: $NEW"
for round in 1 2 3; do
  letters && break
  grep -q '^MISMATCH lei-organica\|^MISMATCH [^lL]' letters.out && { cat letters.out; echo LETTERS FAIL; exit 1; }
  [ $round = 3 ] && { cat letters.out; echo LETTERS FAIL; exit 1; }
  python -X utf8 -c "import json,re,os;p='letters-excluded.json';x=set(json.load(open(p,encoding='utf-8'))) if os.path.exists(p) else set();x|=set(re.findall(r'^MISMATCH ((?:lei|lc)-\S+)',open('letters.out',encoding='utf-8').read(),re.M));json.dump(sorted(x),open(p,'w',encoding='utf-8'),indent=0)"
  parse || { echo PARSE FAIL; exit 1; }
  NEW=$(newparts)
  [ -z "$NEW" ] && { echo "nothing new after exclusions"; exit 0; }
done
grep 'versions checked' letters.out
rm -rf .tmp-build
GITLAW_VERIFIED_PARTS_ONLY=0 python -X utf8 $S/gitlaw_common/build.py "$F" --repo "$F/.tmp-build" --docs-date "$TODAY" >build.out 2>&1 || { tail build.out; echo BUILD FAIL; exit 1; }
python -X utf8 $S/gitlaw_common/check.py "$F/.tmp-build" --corpus "$F/corpus.json" >check.out 2>&1
CK=$?
python -X utf8 -c "import json;d=json.load(open('check.out',encoding='utf-8'));print({k:v for k,v in d.items() if k!='details'})" 2>/dev/null || tail -5 check.out
[ $CK -eq 0 ] || { echo CHECK FAIL; exit 1; }
AUD=$(python -X utf8 -c "import sys; sys.path.insert(0, r'$S/gitlaw_common'); import private; from pathlib import Path; print(private.audit_push(Path(r'$F/.tmp-build'), 'HEAD'))")
echo "audit: $AUD"
[ "$AUD" = "[]" ] || { echo AUDIT FAIL; exit 1; }
N=$(python -X utf8 -c "import json;print(json.load(open('check.out',encoding='utf-8')).get('acts','?'))")
T=$(date -u +%Y-%m-%dT%H:%M:%SZ)
for p in $NEW; do echo "Verified $T gitlaw-scraper-dell: check.py 0 mismatches 0 trailer errors ($N acts); letters-and-digits check with a second reader 0 mismatches; audit_push []." > "${p%.json}.PUBLISH"; done
echo "PUBLISHED $T: $NEW"
rm -rf .tmp-build
