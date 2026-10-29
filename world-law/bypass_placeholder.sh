#!/usr/bin/env bash
# Upload a locally built law repo whose history is unrelated to what GitHub holds
# (usually the one-commit "<Name>: sources, before any law" placeholder).
#
# No force-push: it adds one merge commit whose first parent is the local build and
# whose second parent is GitHub's current head, so nothing on GitHub is lost. The
# merge keeps the local build's tree exactly and its message carries the bypass notice.
#
# usage: scripts/world-law/bypass_placeholder.sh REPO_DIR OWNER/REPO [BRANCH]
#   REPO_DIR may be a bare repo or a checkout. BRANCH defaults to main.
#   If OWNER/REPO doesn't exist yet it is created private; the branch is pushed as is.
set -euo pipefail

dir=$1
slug=$2
br=${3:-main}
url="https://github.com/$slug.git"

local_head=$(git -C "$dir" rev-parse --verify "refs/heads/$br")

if ! gh repo view "$slug" >/dev/null 2>&1; then
  gh repo create "$slug" --private >/dev/null
  echo "$slug: created (private)"
fi

remote_head=$(git ls-remote "$url" "refs/heads/$br" | cut -f1)

if [ -z "$remote_head" ]; then
  echo "$slug: GitHub has no $br; pushing the local build as is"
elif git -C "$dir" fetch -q "$url" "$br" && git -C "$dir" merge-base --is-ancestor "$remote_head" "$local_head"; then
  echo "$slug: local $br already contains GitHub's head; plain push"
else
  remote_subject=$(git -C "$dir" log -1 --format=%s "$remote_head")
  remote_count=$(git -C "$dir" rev-list --count "$remote_head")
  local_count=$(git -C "$dir" rev-list --count "$local_head")
  only_remote=$(comm -13 \
    <(git -C "$dir" ls-tree -r --name-only "$local_head" | sort) \
    <(git -C "$dir" ls-tree -r --name-only "$remote_head" | sort))
  only_remote_n=$(printf '%s' "$only_remote" | grep -c . || true)
  msg=$(cat <<EOF
SOURCES, BEFORE ANY LAW, BYPASSED TEMPORARILY TO UPLOAD THESE LAWS.

URGENT TO-DO: RELATE this build to what GitHub held before it. Rebuild on top of
(or properly replace) the second parent, carry over anything of it that should stay
(SOURCES.md, jurisdiction.json, ...), then drop this merge commit. Builders that
check the root commit, and global-law, should treat this repo as provisional until then.

First parent:  the local build, $local_count commits, ${local_head:0:12}
Second parent: what GitHub held, $remote_count commits, ${remote_head:0:12} "$remote_subject"

This commit's tree is the local build's tree, unchanged. $only_remote_n file(s) exist only
in the second parent and were not carried over:
$(printf '%s\n' "$only_remote" | head -25 | sed 's/^/  /')
$( [ "$only_remote_n" -gt 25 ] && echo "  ... and $((only_remote_n - 25)) more" )

Uploaded from $(hostname) on $(date -u +%Y-%m-%dT%H:%MZ) with scripts/world-law/bypass_placeholder.sh.
EOF
)
  merge=$(git -C "$dir" commit-tree "$local_head^{tree}" -p "$local_head" -p "$remote_head" -m "$msg")
  git -C "$dir" update-ref "refs/heads/$br" "$merge" "$local_head"
  echo "$slug: merge ${merge:0:12} (local ${local_head:0:9} + GitHub ${remote_head:0:9})"
fi

git -C "$dir" push -q "$url" "refs/heads/$br:refs/heads/$br"
echo "$slug: pushed $br"
