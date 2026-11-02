"""Local verification of a Land's corpus.d parts before <part>.PUBLISH (private, gitlaw-scraper-dell).

    python -X utf8 scripts/world-law/verify_parts_local.py <folder>

Builds every part (verified or not) into <folder>/.tmp-build/repo with gitlaw_common/build.py, runs check.py (no
--write) and audit_push(repo, 'HEAD'), and prints one JSON line. Exit 0 only when mismatches, trailer errors and
future-dated are all 0 and the audit is [].
"""
import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / 'gitlaw_common'
sys.path.append(str(COMMON))
import private  # noqa: E402
from build import load  # noqa: E402

folder = Path(sys.argv[1]).resolve()
repo = folder / '.tmp-build' / 'repo'
repo.mkdir(parents=True, exist_ok=True)
if not (repo / '.git').exists():
    subprocess.run(['git', 'init', '-q', '-b', 'main', str(repo)], check=True)
corpus, _ = load(folder)
days = sorted(s.get('retrieved', '') for s in corpus.get('sources', []) if s.get('retrieved'))
env = {**os.environ, 'GITLAW_VERIFIED_PARTS_ONLY': '0', 'GITLAW_NO_CHECKOUT': '1'}
low = {'creationflags': 0x00004000} if os.name == 'nt' else {}
py = [sys.executable, '-X', 'utf8']
b = subprocess.run(py + [str(COMMON / 'build.py'), str(folder), '--repo', str(repo), '--docs-date', days[-1]],
                   capture_output=True, text=True, encoding='utf-8', env=env, **low)
if b.returncode:
    print(json.dumps({'stage': 'build', 'error': (b.stderr or b.stdout)[-3000:]}))
    sys.exit(1)
c = subprocess.run(py + [str(COMMON / 'check.py'), str(repo), '--corpus', str(folder / 'corpus.json')],
                   capture_output=True, text=True, encoding='utf-8', env=env, **low)
try:
    chk = json.loads(c.stdout)
except ValueError:
    print(json.dumps({'stage': 'check', 'error': (c.stderr or c.stdout)[-3000:]}))
    sys.exit(1)
details = chk.pop('details', None)
audit = private.audit_push(repo, 'HEAD')
ok = c.returncode == 0 and not chk.get('mismatches') and not chk.get('trailer_errors') and not chk.get('future_dated') \
    and audit == []
print(json.dumps({'ok': ok, 'check': chk, 'audit': audit, 'details': details if not ok else None}, ensure_ascii=False)[:4000])
sys.exit(0 if ok else 1)
