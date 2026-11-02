#!/usr/bin/env bash
# Runs build.py / check.py / push_clean.py inside WSL, with the output repository on ext4 (~/gitlaw-builds/<slug>)
# instead of NTFS. Inputs (corpus.json, corpus.d/, repo/, the builder itself) are read from /mnt/c. Normally started by
# wsl_run.py on the Windows side; see README-wsl.md.
#
#   wsl_build.sh setup
#   wsl_build.sh build <slug|folder> --docs-date D [--repo DIR] [--compare DIR] [--site-data FILE]
#   wsl_build.sh check <slug|folder> [--repo DIR] [--write]
#   wsl_build.sh push  <slug|folder> [--repo DIR] [--main] [--branch B]
#   wsl_build.sh git   <slug|folder> [--repo DIR] <git args...>
#   wsl_build.sh path  <slug|folder> [--repo DIR]
#
# Environment (wsl_run.py sets these): GITLAW_COMMON (this folder on /mnt/c), GITLAW_SCRIPTS (the scripts folder),
# GITLAW_WIN_HOME (the Windows home on /mnt/c), GITLAW_WSL_TIME=1 to print wall and CPU time to stderr.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON="${GITLAW_COMMON:-$HERE}"
SCRIPTS="${GITLAW_SCRIPTS:-$(dirname "$COMMON")}"
ROOT="${GITLAW_WSL_ROOT:-$HOME/gitlaw-builds}"
VENV="$ROOT/.venv"
PY="$VENV/bin/python"
GCM='/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe'
TZDATA_VERSION="${GITLAW_TZDATA_VERSION:-2026.6}"   # the tzdata the Windows builders use: same offsets, same hashes

# git reads this file as its "global" config for everything started here; ~/.gitconfig is never touched. It carries
# the Windows user.name/user.email (so `git config --global user.email`, which private.audit_push reads, answers as
# on Windows) and sends credentials to the Windows Git Credential Manager, so no token is ever copied into WSL.
export GIT_CONFIG_GLOBAL="$ROOT/gitconfig"
# zoneinfo reads the tzdata package (as on Windows, which has no system zone files), not /usr/share/zoneinfo.
export PYTHONTZPATH=''
export PYTHONUTF8=1
export PYTHONDONTWRITEBYTECODE=1   # no __pycache__ written into the Windows folders
export LC_ALL=C.UTF-8

die() { echo "wsl_build: $*" >&2; exit 2; }

setup() {
  mkdir -p "$ROOT"
  if [ ! -x "$PY" ]; then
    # Ubuntu's python3 has no ensurepip: make the venv without pip, then run pip from its wheel to install itself.
    python3 -m venv --without-pip "$VENV"
  fi
  if ! "$PY" -m pip --version >/dev/null 2>&1; then
    local whl="${GITLAW_PIP_WHEEL:-}"
    [ -n "$whl" ] && [ -f "$whl" ] || die "pip is missing from $VENV: pass GITLAW_PIP_WHEEL=<pip-*.whl> (wsl_run.py setup downloads one)"
    "$PY" -I "$whl/pip" install -q --no-index "$whl"
  fi
  # build.py, check.py, push_clean.py and private.py are standard library only; tzdata is the one package they need.
  if ! "$PY" -c "import tzdata, sys; sys.exit(tzdata.__version__ != '$TZDATA_VERSION')" 2>/dev/null; then
    if [ -n "${GITLAW_WHEEL_DIR:-}" ] && ls "$GITLAW_WHEEL_DIR"/tzdata-"$TZDATA_VERSION"-*.whl >/dev/null 2>&1; then
      "$PY" -m pip install -q --no-index --find-links "$GITLAW_WHEEL_DIR" "tzdata==$TZDATA_VERSION"
    else
      "$PY" -m pip install -q "tzdata==$TZDATA_VERSION"
    fi
  fi
  [ -f "$GCM" ] || die "Git Credential Manager not found at $GCM"
  local cfg="$GIT_CONFIG_GLOBAL.tmp"
  rm -f "$cfg"; : > "$cfg"
  # user.name/user.email as in the Windows global config: private.audit_push asks `git config --global user.email`
  # for the personal address it must keep out of pushes (an include would not do: --global lookups skip includes).
  if [ -n "${GITLAW_WIN_HOME:-}" ] && [ -f "$GITLAW_WIN_HOME/.gitconfig" ]; then
    local k v
    for k in user.name user.email; do
      v="$(git config -f "$GITLAW_WIN_HOME/.gitconfig" "$k" || true)"
      [ -n "$v" ] && git config -f "$cfg" "$k" "$v"
    done
  fi
  # An empty helper first clears any helper named earlier; then the Windows Git Credential Manager.
  git config -f "$cfg" credential.helper ''
  git config -f "$cfg" --add credential.helper "${GCM// /\\ }"
  git config -f "$cfg" core.autocrlf false
  mv "$cfg" "$GIT_CONFIG_GLOBAL"
  echo "python: $("$PY" --version) tzdata $("$PY" -c 'import tzdata; print(tzdata.__version__)')"
  echo "git: $(git --version)"
  echo "root: $ROOT ($(df -h --output=avail "$ROOT" | tail -1 | tr -d ' ') free)"
  # A read against the private ops repo proves the credential path without printing anything secret.
  if GIT_TERMINAL_PROMPT=0 git ls-remote -q https://github.com/lexifina/world-law-ops.git HEAD >/dev/null 2>&1; then
    echo "credentials: ok (Git Credential Manager)"
  else
    echo "credentials: FAILED (run 'git ls-remote https://github.com/lexifina/world-law-ops.git' once to sign in)" >&2
    return 1
  fi
}

# <slug|folder> -> FOLDER, SLUG, REPO (REPO may be overridden with --repo in the remaining args)
resolve() {
  local x="$1"
  if [ -d "$x" ]; then FOLDER="$(cd "$x" && pwd)"; else FOLDER="$SCRIPTS/$x"; fi
  [ -d "$FOLDER" ] || die "no corpus folder $FOLDER"
  SLUG="$(basename "$FOLDER")"
  REPO="$ROOT/$SLUG"
}

timed() {
  if [ "${GITLAW_WSL_TIME:-}" = 1 ]; then
    local TIMEFORMAT="wsl_build: wall %3R s, cpu %3U s user + %3S s sys"
    time "$@"
  else
    "$@"
  fi
}

[ $# -ge 1 ] || die "usage: wsl_build.sh setup|build|check|push|git|path ..."
cmd="$1"; shift
if [ "$cmd" = setup ]; then setup; exit; fi
[ -x "$PY" ] && [ -f "$GIT_CONFIG_GLOBAL" ] || die "not set up: run 'python wsl_run.py setup' first"
[ $# -ge 1 ] || die "$cmd needs a slug or corpus folder"
resolve "$1"; shift
args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --repo=*) REPO="${1#--repo=}"; shift ;;
    *) args+=("$1"); shift ;;
  esac
done
REPO="${REPO/#\~/$HOME}"
case "$REPO" in /mnt/*) echo "wsl_build: warning: $REPO is on a Windows drive, not ext4" >&2 ;; esac

case "$cmd" in
  build)
    mkdir -p "$(dirname "$REPO")"
    # nice 10 ~ BelowNormal. build.py streams every commit into one `git fast-import` (no change needed here).
    rc=0
    timed nice -n 10 "$PY" "$COMMON/build.py" "$FOLDER" --repo "$REPO" "${args[@]}" || rc=$?
    # build.py re-inits the repo, so its repo-local config is set again after each build. Repo-local only.
    if [ -d "$REPO/.git" ]; then
      git -C "$REPO" config gc.auto 0
      git -C "$REPO" config core.autocrlf false
    fi
    exit $rc
    ;;
  check)
    corpus="$FOLDER/corpus.json"
    timed nice -n 10 "$PY" "$COMMON/check.py" "$REPO" --corpus "$corpus" "${args[@]}"
    ;;
  push)
    # push_clean.py: audit_push, private wip snapshot, and plain (fast-forward-only) pushes to lexifina/<slug>.
    cd "$REPO"
    timed nice -n 10 "$PY" "$COMMON/push_clean.py" "$REPO" "$SLUG" "${args[@]}"
    ;;
  git)
    exec git -C "$REPO" "${args[@]}"
    ;;
  path)
    echo "folder=$FOLDER"
    echo "repo=$REPO"
    echo "windows_repo=\\\\wsl.localhost\\${WSL_DISTRO_NAME:-Ubuntu}${REPO//\//\\}"
    ;;
  *) die "unknown command $cmd" ;;
esac
