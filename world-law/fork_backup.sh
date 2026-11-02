#!/bin/bash
# Pushes the speed-up material (benchmarks, speed rules, code snapshots) to the PRIVATE repo lexifina/world-law-max-speed,
# branch main. Never to global-law or the country repos (user's rule, 2026-10-29). Run once, or every 5 min: --loop
L=/c/Users/alany/Documents/lexifina/scripts; R=$HOME/world-law-max-speed; J=/c/Users/alany/.claude/jobs/bf2c37ff/tmp
once() {
  [ -d $R/.git ] || git clone -q https://github.com/lexifina/world-law-max-speed.git $R
  git -C $R pull -q --ff-only origin main 2>/dev/null
  rm -rf $R/bench; mkdir -p $R/bench $R/rules $R/code $R/tools
  cp -r $L/world-law/bench/. $R/bench/; find $R -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null
  cp $L/world-law/FORK.md $L/world-law/ALT-SOURCES.md $R/rules/ 2>/dev/null; cp $L/africa-law/PEACHJAM.md $R/rules/ 2>/dev/null
  cp $L/gitlaw_common/wayback.py $L/south-america-law/autopush.py $R/code/ 2>/dev/null
  for f in unpushed.py push_now.py gate_scan.py; do cp $J/$f $R/tools/ 2>/dev/null; done
  git -C $R add -A
  if git -C $R -c user.name=Lexifina -c user.email=world-law@lexifina.com commit -q -m "Speed-ups and benchmarks ($(date -u +%FT%TZ))" 2>/dev/null; then
    git -C $R push -q origin main && echo "$(date -u +%FT%TZ) pushed $(git -C $R rev-parse --short HEAD) to lexifina/world-law-max-speed main" || echo "$(date -u +%FT%TZ) PUSH FAILED"
  else echo "$(date -u +%FT%TZ) unchanged"; fi
}
if [ "$1" = "--loop" ]; then while true; do once; sleep 300; done; else once; fi
