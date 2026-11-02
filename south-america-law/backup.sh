#!/bin/bash
# Backs up the git-for-law COORDINATOR files, for every region, to branch coordinator of the PRIVATE repo lexifina/world-law-ops
# (never to global-law or the country repos: user rule 2026-10-29). Country work is not copied here: each country folder already goes to its own repo's `wip`
# branch through autopush. Covers the shared builder, the briefs, plans, queues, adapters, scripts and the memory notes.
set -e
S=${GITLAW_BACKUP_DIR:-$HOME/.gitlaw-ops-backup}
L=/c/Users/alany/Documents/lexifina
if [ ! -d $S/.git ]; then rm -rf $S; git init -q -b coordinator $S; git -C $S remote add origin https://github.com/lexifina/world-law-ops.git; git -C $S config core.autocrlf false; fi
rm -rf $S/gitlaw_common $S/south-america-law $S/africa-law $S/world-law $S/memory
mkdir -p $S/memory $S/world-law
cp -r $L/scripts/gitlaw_common $S/
cp -r $L/scripts/africa-law $S/ 2>/dev/null || true
# south-america-law holds autopush, the watchdog, status and site_data: everything but its logs.
mkdir -p $S/south-america-law && (cd $L/scripts/south-america-law && find . -path ./logs -prune -o -path ./.bk -prune -o -type f -print | while read f; do mkdir -p "$S/south-america-law/$(dirname "$f")"; cp "$f" "$S/south-america-law/$f"; done)
for f in WAVE.md build_countries.py countries.json register.json; do cp $L/scripts/world-law/$f $S/world-law/ 2>/dev/null || true; done
# Every country's handoff and code (no caches, no corpora), so work whose wip push is refused still leaves this machine.
rm -rf $S/countries; (cd $L/scripts && for d in *-law; do find "$d" -maxdepth 2 \( -name .cache -o -name '.tmp*' -o -name repo -o -name corpus.d -o -name __pycache__ \) -prune -o -type f \( -name '*.md' -o -name '*.py' -o -name '*.sh' \) -size -2M -print; done | while read f; do mkdir -p "$S/countries/$(dirname "$f")"; cp "$f" "$S/countries/$f"; done)
find $S -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
# Never back up a credential an agent noted down (API keys in query strings), even one a public site embeds.
grep -rlE '(code|key|token|sig|apikey)=[A-Za-z0-9_%=-]{20,}' $S/countries 2>/dev/null | while read f; do sed -i -E 's/(code|key|token|sig|apikey)=[A-Za-z0-9_%=-]{20,}/\1=<redacted>/g' "$f"; done
cp $L/memory/south_america_git_law.md $L/memory/git_for_law.md $S/memory/
# Build each backup on what the remote holds, so a commit GitHub refused (secret scanning) never stays in the history.
git -C $S fetch -q origin coordinator 2>/dev/null && git -C $S reset -q --soft FETCH_HEAD
git -C $S add -A
git -C $S -c user.name=Lexifina -c user.email=world-law@lexifina.com commit -q -m "Git for law: coordinator files, all regions ($(date -u +%FT%TZ))" || true
# Never forced (no rewrite without the user's yes): the commit sits on the remote tip fetched above, so this
# fast-forwards; if the remote moved meanwhile the push fails and the next run builds on the new tip.
git -C $S push -q origin HEAD:refs/heads/coordinator
git -C $S log --oneline -1
