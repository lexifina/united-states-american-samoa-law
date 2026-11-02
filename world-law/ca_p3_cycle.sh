#!/usr/bin/env bash
# Private: parse -> build -> check --write -> rebuild -> check -> check_corpus -> check_facts -> audit_push, BelowNormal.
#   bash scripts/world-law/ca_p3_cycle.sh <unit-slug>
set -euo pipefail
U=$1
S=C:/Users/alany/Documents/lexifina/scripts
F=$S/canada-$U-law
B=C:/Users/alany/Documents/canada-$U-law-build
export GITLAW_NO_CHECKOUT=1
low() { python -X utf8 -c "import psutil,subprocess,sys;p=psutil.Process();p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);sys.exit(subprocess.call(sys.argv[1:]))" "$@"; }
low python -X utf8 "$F/parse.py"
rm -rf "$B"; mkdir -p "$B"; git -C "$B" init -q -b main
low python -X utf8 "$S/gitlaw_common/build.py" "$F" --repo "$B" --docs-date 2026-10-30 | tail -3
low python -X utf8 "$S/gitlaw_common/check.py" "$B" --corpus "$F/corpus.json" --write | grep -E '"(mismatches|trailer_errors|merges|backwards|future_dated|missing_in_force|versions)"' | tr -d "
"; echo
low python -X utf8 "$S/gitlaw_common/build.py" "$F" --repo "$B" --docs-date 2026-10-30 | tail -3
low python -X utf8 "$S/gitlaw_common/check.py" "$B" --corpus "$F/corpus.json" | tail -3
low python -X utf8 "$S/global-law/check_corpus.py" "$B" | tail -4
low python -X utf8 "$F/check_facts.py" "$B"
python -X utf8 -c "import sys; sys.path.insert(0, r'$S/gitlaw_common'); import private; from pathlib import Path; print('audit', private.audit_push(Path(r'$B'), 'HEAD'))"
git -C "$B" log --oneline | wc -l; git -C "$B" grep -I -n $'\r' HEAD | head -2 || true
