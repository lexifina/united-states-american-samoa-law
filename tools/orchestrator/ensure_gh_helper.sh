#!/bin/bash
# Give WSL law clones a per-repo gh credential helper, so a hidden git-credential-manager prompt can never hang a push
# (it did twice on 2026-11-03). Local config only; global config is never touched.
#   ensure_gh_helper.sh                 report every clone under ~/gitlaw-builds without the helper (changes nothing)
#   ensure_gh_helper.sh --apply DIR...  set it on these clones
#   ensure_gh_helper.sh --apply-all     set it on every clone under ~/gitlaw-builds (only with each owner's OK)
# Run inside WSL:  wsl.exe -d Ubuntu --cd /home/alany -- bash /mnt/c/Users/alany/AppData/Local/gitlaw-orchestrator/ensure_gh_helper.sh
GH='!gh.exe auth git-credential'
has() { git -C "$1" config --local --get-all credential.helper 2>/dev/null | grep -qF 'gh.exe auth git-credential'; }
set_one() {
  [ -d "$1/.git" ] || [ -f "$1/HEAD" ] || { echo "skip (not a repo): $1"; return; }
  if has "$1"; then echo "ok   $1"; return; fi
  git -C "$1" config --local --replace-all credential.helper "" && git -C "$1" config --local --add credential.helper "$GH" \
    && echo "set  $1"
}
command -v gh.exe >/dev/null || { echo "gh.exe not on PATH inside WSL"; exit 1; }
case "$1" in
  --apply) shift; for d in "$@"; do set_one "$d"; done ;;
  --apply-all) while IFS= read -r g; do set_one "$(dirname "$g")"; done < <(find "$HOME/gitlaw-builds" -maxdepth 4 -name .git -type d 2>/dev/null) ;;
  *) n=0; while IFS= read -r g; do d=$(dirname "$g"); has "$d" || { echo "missing $d"; n=$((n+1)); }; done \
       < <(find "$HOME/gitlaw-builds" -maxdepth 4 -name .git -type d 2>/dev/null); echo "$n clones without the gh helper" ;;
esac
