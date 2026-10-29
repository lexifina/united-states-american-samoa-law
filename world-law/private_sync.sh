#!/bin/bash
# Copies the private git-for-law material into the two PRIVATE repos (user's rule, 2026-10-29), as readable trees on
# branch main. Nothing here ever goes to global-law or a country repo. Run once, or every 5 minutes with --loop.
#   lexifina/world-law-max-speed  speed-ups: bench/ (BENCHMARKS.md + raw results), experiments/, the speed rules,
#                                 snapshots of wayback.py and autopush.py, and the fork's push tools
#   lexifina/world-law-ops        operations: world-law/ (playbook, queues, register, countries, census), global-law/
#                                 (builder, bridges), gitlaw_common/, south-america-law/ and africa-law/ (briefs,
#                                 tooling), memory/ (git-for-law notes), countries/<slug>-law/ (every handoff, issue
#                                 list, correspondence draft, log and script; no caches, no corpora)
L=/c/Users/alany/Documents/lexifina; S=$L/scripts; J=/c/Users/alany/.claude/jobs/bf2c37ff/tmp
copy_tree() {  # copy_tree <src> <dst>: every file under 2 MB, skipping caches, scratch folders and builds
  (cd "$1" && find . \( -name .cache -o -name '.tmp*' -o -name __pycache__ -o -name .git -o -name corpus.d -o -name node_modules \) -prune -o -type f -size -2M -print) |
    while read -r f; do mkdir -p "$2/$(dirname "$f")"; cp "$1/$f" "$2/$f"; done
}
push() {  # push <repo dir> <label>
  git -C "$1" add -A
  if git -C "$1" -c user.name=Lexifina -c user.email=world-law@lexifina.com commit -q -m "$2 ($(date -u +%FT%TZ))" 2>/dev/null; then
    git -C "$1" push -q origin main && echo "$(date -u +%FT%TZ) pushed $(git -C "$1" rev-parse --short HEAD) to $(git -C "$1" remote get-url origin)" || echo "$(date -u +%FT%TZ) PUSH FAILED $1"
  else echo "$(date -u +%FT%TZ) unchanged $1"; fi
}
once() {
  M=$HOME/world-law-max-speed; O=$HOME/world-law-ops-main
  [ -d $M/.git ] || git clone -q https://github.com/lexifina/world-law-max-speed.git $M
  git -C $M pull -q --ff-only origin main 2>/dev/null
  rm -rf $M/bench $M/experiments; mkdir -p $M/bench $M/rules $M/code $M/tools
  copy_tree $S/world-law/bench $M/bench
  [ -d $S/world-law/experiments ] && copy_tree $S/world-law/experiments $M/experiments
  cp $S/world-law/FORK.md $S/world-law/ALT-SOURCES.md $M/rules/ 2>/dev/null; cp $S/africa-law/PEACHJAM.md $M/rules/ 2>/dev/null
  cp $S/gitlaw_common/wayback.py $S/gitlaw_common/private.py $S/south-america-law/autopush.py $M/code/ 2>/dev/null
  for f in unpushed.py push_now.py gate_scan.py archive_all.py purge/purge_rewrite.py purge/callback.py; do cp $J/$f $M/tools/ 2>/dev/null; done
  push $M "Speed-ups and benchmarks"
  if [ ! -d $O/.git ]; then git init -q -b main $O; git -C $O remote add origin https://github.com/lexifina/world-law-ops.git; git -C $O config core.autocrlf false; fi
  git -C $O fetch -q origin main 2>/dev/null && git -C $O reset -q --soft FETCH_HEAD 2>/dev/null
  rm -rf $O/world-law $O/global-law $O/gitlaw_common $O/south-america-law $O/africa-law $O/memory $O/countries
  for d in world-law global-law gitlaw_common south-america-law africa-law; do [ -d $S/$d ] && copy_tree $S/$d $O/$d; done
  rm -rf $O/world-law/bench $O/world-law/experiments   # speed material lives in world-law-max-speed
  mkdir -p $O/memory; cp $L/memory/*law*.md $L/memory/MEMORY.md $O/memory/ 2>/dev/null
  for d in $S/*-law; do n=$(basename $d); case $n in world-law|global-law|south-america-law|africa-law) continue;; esac
    mkdir -p $O/countries/$n; (cd $d && find . -maxdepth 3 \( -name .cache -o -name '.tmp*' -o -name __pycache__ -o -name repo -o -name corpus.d \) -prune -o -type f -size -2M \( -name '*.md' -o -name '*.py' -o -name '*.sh' -o -name '*.log' -o -name '*.txt' -o -name 'PUBLISH*' \) -print) |
      while read -r f; do mkdir -p "$O/countries/$n/$(dirname "$f")"; cp "$d/$f" "$O/countries/$n/$f"; done; done
  # Never store a credential an agent noted down (API keys in query strings), even one a public site embeds.
  grep -rlE '(code|key|token|sig|apikey)=[A-Za-z0-9_%=-]{20,}' $O 2>/dev/null | grep -v '/\.git/' | while read -r f; do sed -i -E 's/(code|key|token|sig|apikey)=[A-Za-z0-9_%=-]{20,}/\1=<redacted>/g' "$f"; done
  [ -f $O/README.md ] || printf '# world-law-ops (private)\n\nGit-for-law operations, private by the user'"'"'s rule (2026-10-29): the agent playbook and queues (world-law/), the source research (world-law/register.json, countries.json; global-law/ census and bridges), the shared builder and push tooling, the git-for-law memory notes, and every country'"'"'s handoffs, issue lists, correspondence drafts, licence notes and scripts (countries/). Speed-ups live in lexifina/world-law-max-speed.\n\nBranches: main (this readable tree, refreshed every 5 minutes), coordinator (the coordinator backup), archive/<repo>/<ref> (every original branch and tag of every country repo and of global-law, kept before the 2026-10-29 history rewrite so nothing was discarded).\n' > $O/README.md
  push $O "Operations"
}
if [ "$1" = "--loop" ]; then while true; do once; sleep 300; done; else once; fi
