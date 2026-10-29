#!/usr/bin/env bash
# Snapshot scripts/peru-law (minus .cache) to the `wip` branch of lexifina/peru-law
# using git plumbing in a throwaway index, so main and the working tree are untouched.
set -euo pipefail
SRC="$(cd "$(dirname "$0")" && pwd)"
CLONE="${1:-C:/Users/alany/Documents/peru-law}"
TMP="$(mktemp -d)"
mkdir -p "$TMP/wip"
( cd "$SRC" && tar --exclude=.cache --exclude=__pycache__ -cf - . ) | ( cd "$TMP/wip" && tar -xf - )
if [ -f "$TMP/wip/corpus.json" ] && [ "$(stat -c %s "$TMP/wip/corpus.json")" -gt 50000000 ]; then rm "$TMP/wip/corpus.json"; fi
export GIT_INDEX_FILE="$TMP/index"
export GIT_WORK_TREE="$TMP"
git -C "$CLONE" --work-tree="$TMP" add -A wip
TREE=$(git -C "$CLONE" write-tree)
PARENT=$(git -C "$CLONE" rev-parse -q --verify refs/remotes/origin/wip || true)
MSG="wip: scripts/peru-law snapshot $(date -u +%Y-%m-%dT%H:%MZ)"
if [ -n "$PARENT" ]; then C=$(echo "$MSG" | git -C "$CLONE" commit-tree "$TREE" -p "$PARENT"); else C=$(echo "$MSG" | git -C "$CLONE" commit-tree "$TREE"); fi
git -C "$CLONE" update-ref refs/heads/wip "$C"
git -C "$CLONE" push -q -f origin wip:wip
git -C "$CLONE" fetch -q origin wip:refs/remotes/origin/wip || true
rm -rf "$TMP"
echo "pushed wip $C"
