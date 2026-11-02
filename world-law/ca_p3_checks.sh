#!/bin/sh
# private: build + full checks for a phase-3 province. usage: ca_p3_checks.sh <slug> (e.g. new-brunswick)
set -e
S=$1; L=/c/Users/alany/Documents/lexifina/scripts; F=$L/canada-$S-law; B=/c/Users/alany/Documents/canada-$S-law-build; BW=$(cygpath -m "$B")
export GITLAW_NO_CHECKOUT=1
rm -rf "$B"; mkdir -p "$B"; git -C "$B" init -q
python -X utf8 -c "import psutil,os;psutil.Process(os.getpid()).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);import subprocess,sys;sys.exit(subprocess.call(sys.argv[1:]))" python -X utf8 $L/gitlaw_common/build.py $F --repo "$B" --docs-date 2026-10-30 | tail -5
python -X utf8 -c "import psutil,os;psutil.Process(os.getpid()).nice(psutil.BELOW_NORMAL_PRIORITY_CLASS);import subprocess,sys;sys.exit(subprocess.call(sys.argv[1:]))" python -X utf8 $L/gitlaw_common/check.py "$B" --corpus $F/corpus.json --write | tail -15
python -X utf8 $L/global-law/check_corpus.py "$B" 2>&1 | tail -6
[ -f $F/check_facts.py ] && python -X utf8 $F/check_facts.py "$B"
python -X utf8 -c "import sys; sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common'); import private; from pathlib import Path; print('audit', private.audit_push(Path(r'$BW'), 'HEAD'))"
python -X utf8 /c/Users/alany/Documents/lexifina/scripts/world-law/ca_cr_check.py "$BW"
