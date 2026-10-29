#!/bin/sh
# Push scripts/ecuador-law (without .cache) to the `wip` branch of lexifina/ecuador-law, using git plumbing only,
# so the clone's main branch and working tree are untouched.
set -e
SRC=C:/Users/alany/Documents/lexifina/scripts/ecuador-law
CLONE=C:/Users/alany/Documents/ecuador-law
TMPIDX=$(mktemp)
export GIT_INDEX_FILE="$TMPIDX"
rm -f "$GIT_INDEX_FILE"
cd "$SRC"
for f in $(find . -path ./.cache -prune -o -type f -print | sed 's#^\./##' | grep -v '__pycache__' | sort); do
  size=$(stat -c %s "$f")
  if [ "$size" -gt 50000000 ]; then continue; fi
  blob=$(git -C "$CLONE" hash-object -w --path="$f" -- "$SRC/$f")
  git -C "$CLONE" update-index --add --cacheinfo 100644 "$blob" "wip/$f"
done
tree=$(git -C "$CLONE" write-tree)
commit=$(GIT_AUTHOR_NAME=gitlaw-EC GIT_AUTHOR_EMAIL=corpus@lexifina.com GIT_COMMITTER_NAME=gitlaw-EC GIT_COMMITTER_EMAIL=corpus@lexifina.com \
  git -C "$CLONE" commit-tree "$tree" -m "wip: scripts/ecuador-law snapshot")
rm -f "$TMPIDX"
git -C "$CLONE" push -f origin "$commit:refs/heads/wip"
echo "wip -> $commit"
