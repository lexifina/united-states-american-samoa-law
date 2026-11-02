#!/bin/bash
# Private (never published). Parse, then letters check + build/check/audit of every corpus.d part without .PUBLISH;
# writes .PUBLISH for them only when all pass.
#   bash world-law/br_city_verify.sh <scripts/brazil-...-city-law> [<year>]
# With <year>, only that year is parsed (small PUBLISH batches) and, on success, it is added to .verified-years.
# One run per folder at a time (lock dir .verify.lock); each run builds in its own folder outside scripts/ (2026-11-01:
# two runs sharing .tmp-build corrupted each other's builds and failed).
set -u
F=$(cd "$1" && pwd -W)
Y=${2:-}
S=C:/Users/alany/Documents/lexifina/scripts
TODAY=$(date -u +%F)
cd "$F"
if ! mkdir .verify.lock 2>/dev/null; then
  # a lock older than 3 h is from a run that died (machine sleep, killed shell)
  if [ -n "$(find .verify.lock -maxdepth 0 -mmin +180)" ]; then rm -rf .verify.lock && mkdir .verify.lock || exit 1
  else echo "LOCKED (another verify runs in $F)"; exit 3; fi
fi
B="$(cygpath -m "$LOCALAPPDATA")/gitlaw-br-city/$(basename "$F")-$$"
trap 'rm -rf "$B"; rmdir .verify.lock 2>/dev/null' EXIT
PARSE="python -X utf8 parse.py --today $TODAY${Y:+ --only-year $Y}"
while :; do
  l=$(tail -1 "$LOCALAPPDATA/gitlaw-cpu.log"); c=$(sed -n 's/.*cpu5=\([0-9]*\).*/\1/p' <<<"$l"); r=$(sed -n 's/.*ram=\([0-9]*\).*/\1/p' <<<"$l")
  [ "${c:-0}" -le 90 ] && [ "${r:-0}" -le 85 ] && break; echo "waiting: $l"; sleep 60
done
$PARSE || exit 1
NEW=$(for p in corpus.d/*.json; do [ -e "${p%.json}.PUBLISH" ] || echo "$p"; done)
[ -z "$NEW" ] && { echo "nothing new"; [ -n "$Y" ] && echo "$Y" >> .verified-years; exit 0; }
echo "new parts: $NEW"
if ! python -X utf8 check_letters.py $NEW > letters.out; then
  # Opt-in (a folder with letters-excluded.json): leave out the acts the second reader disagrees on, re-parse, re-check.
  [ -f letters-excluded.json ] || { cat letters.out; echo LETTERS FAIL; exit 1; }
  python -X utf8 -c "import json,re,sys;p='letters-excluded.json';x=set(json.load(open(p,encoding='utf-8')));x|=set(re.findall(r'^MISMATCH (\S+)',open('letters.out',encoding='utf-8').read(),re.M));json.dump(sorted(x),open(p,'w',encoding='utf-8'),indent=0)"
  for p in $NEW; do rm -f "$p"; done
  $PARSE || exit 1
  NEW=$(for p in corpus.d/*.json; do [ -e "${p%.json}.PUBLISH" ] || echo "$p"; done)
  [ -z "$NEW" ] && { echo "nothing new after exclusions"; [ -n "$Y" ] && echo "$Y" >> .verified-years; exit 0; }
  python -X utf8 check_letters.py $NEW > letters.out || { cat letters.out; echo LETTERS FAIL; exit 1; }
fi
tail -1 letters.out
mkdir -p "$(dirname "$B")"
GITLAW_VERIFIED_PARTS_ONLY=0 python -X utf8 $S/gitlaw_common/build.py "$F" --repo "$B" --docs-date $TODAY >build.out 2>&1 || { tail build.out; echo BUILD FAIL; exit 1; }
python -X utf8 $S/gitlaw_common/check.py "$B" --corpus "$F/corpus.json" >check.out 2>&1
CK=$?
python -X utf8 -c "import json;d=json.load(open('check.out',encoding='utf-8'));print({k:v for k,v in d.items() if k!='details'})" 2>/dev/null || tail -5 check.out
[ $CK -eq 0 ] || { echo CHECK FAIL; exit 1; }
AUD=$(python -X utf8 -c "import sys; sys.path.insert(0, r'$S/gitlaw_common'); import private; from pathlib import Path; print(private.audit_push(Path(r'$B'), 'HEAD'))")
echo "audit: $AUD"
[ "$AUD" = "[]" ] || { echo AUDIT FAIL; exit 1; }
N=$(python -X utf8 -c "import json;print(json.load(open('check.out',encoding='utf-8')).get('acts','?'))")
T=$(date -u +%Y-%m-%dT%H:%M:%SZ)
for p in $NEW; do echo "Verified $T gitlaw-scraper-dell: check.py 0 mismatches 0 trailer errors ($N acts); check_letters 0 mismatches; audit_push []." > "${p%.json}.PUBLISH"; done
echo "PUBLISHED $T:" $NEW
[ -n "$Y" ] && echo "$Y" >> .verified-years
exit 0
