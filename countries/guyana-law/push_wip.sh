#!/bin/sh
# Push scripts/guyana-law/ (minus .cache) to the `wip` branch of lexifina/guyana-law under wip/,
# using git plumbing in a temporary index so the clone's main and working tree are untouched.
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
CLONE="C:/Users/alany/Documents/guyana-law"
export GIT_INDEX_FILE="$CLONE/.git/wip-index"
rm -f "$GIT_INDEX_FILE"
cd "$SRC"
for f in $(git ls-files --others --cached --exclude-standard . 2>/dev/null; ls *.py *.md *.sh corpus.json 2>/dev/null; find repo -type f 2>/dev/null); do
  [ -f "$f" ] || continue
  case "$f" in .cache/*) continue;; esac
  sz=$(wc -c < "$f")
  [ "$sz" -gt 50000000 ] && continue
  h=$(git -C "$CLONE" hash-object -w "$SRC/$f")
  git -C "$CLONE" update-index --add --cacheinfo 100644 "$h" "wip/$f"
done
T=$(git -C "$CLONE" write-tree)
C=$(echo "wip: gitlaw-GY working files $(date -u +%Y-%m-%dT%H:%MZ)" | GIT_AUTHOR_NAME=Lexifina GIT_AUTHOR_EMAIL=guyana-law@lexifina.com GIT_COMMITTER_NAME=Lexifina GIT_COMMITTER_EMAIL=guyana-law@lexifina.com git -C "$CLONE" commit-tree "$T")
rm -f "$GIT_INDEX_FILE"
git -C "$CLONE" push -f origin "$C:refs/heads/wip"
echo "wip -> $C"
