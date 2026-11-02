"""Final privacy audit of every lexifina repo on GitHub (read-only).

    python -X utf8 audit.py <out.json> [repo ...]     (no repos: every repo in the lexifina org except the two private stores)

For each repo, a full mirror clone (every branch and tag, all history) is scanned; the clone is deleted afterwards:
- **visibility** (public or private) and star count;
- **private files by name** anywhere in history: handoffs, issue lists, correspondence, logs, fetch helpers, the shared
  fetch client, the push tooling, the playbook and the source research;
- **content markers** in every .py/.sh/.md/.json/.txt blob in history:
  - speed tooling: host_get, cc_get, cc_captures, wayback, Common Crawl, thread pools, rates, Crawl-delay;
  - this machine's home path;
  - the personal email;
  - bot-challenge notes;
- **commit authors and committers** that aren't lexifina.com or a .invalid placeholder.

Each finding records whether it's at a branch tip (current) or only in history. Writes one JSON entry per repo.
"""
import json, re, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NAMES = re.compile(r'(^|/)(PROGRESS\.md|ISSUES\.md|PERMISSION[^/]*|NOTES\.md|[^/]*\.log|wayback[^/]*\.py|fetch[^/]*\.(py|sh)|'
                   r'crawl[^/]*\.py|grab[^/]*\.py|probe[^/]*\.py|discover[^/]*\.py|ia\.py|cc_[^/]*\.py|download[^/]*\.py|'
                   r'harvest[^/]*\.py|autopush\.py|watchdog\.sh|backup\.sh|BRIEF\.md|FANOUT\.md|WAVE\.md|FORK\.md|'
                   r'ALT-SOURCES\.md|PEACHJAM\.md|register\.json|QUEUE[^/]*\.md|BENCHMARKS\.md|SCRAPING-LOG\.md)$', re.I)
MARKS = {
    'speed tooling': re.compile(rb'host_get|cc_get\b|cc_captures|import wayback|wayback\.(get|captures|fetch)|ThreadPoolExecutor|requests a second|adaptive rate', re.I),
    'common crawl / archive tactics': re.compile(rb'data\.commoncrawl\.org|index\.commoncrawl\.org|cluster\.idx', re.I),
    'home path': re.compile(rb'(?i)(?:[A-Z]:(?:\\\\|\\|/)+Users(?:\\\\|\\|/)+alany|/c/Users/alany)'),
    'personal email': re.compile(rb'alanyahya@outlook', re.I),
    'bot-challenge notes': re.compile(rb'(?i)cloudflare|bot challenge|captcha|firewall page'),
}
TEXT = ('.py', '.sh', '.md', '.json', '.txt', '.csv', '.toml', '.yml', '.yaml')
TMP = Path(r'C:\Users\alany\audit-tmp')


def git(cwd, *a):
    return subprocess.run(['git', *a], cwd=cwd, capture_output=True).stdout.decode('utf-8', 'replace')


def one(repo):
    t0 = time.time()
    m = Path(tempfile.mkdtemp(prefix=f'{repo}-', dir=TMP))
    try:
        r = m / 'r.git'
        if subprocess.run(['git', 'clone', '-q', '--mirror', f'https://github.com/lexifina/{repo}.git', str(r)], capture_output=True).returncode:
            return {'repo': repo, 'error': 'clone failed'}
        tips = set()
        for ref in git(r, 'for-each-ref', '--format=%(refname)', 'refs/heads').split():
            for line in git(r, 'ls-tree', '-r', ref).splitlines():
                meta, path = line.split('\t', 1)
                tips.add((path, meta.split()[2]))
        tip_paths = {p for p, _ in tips}
        tip_blobs = {b for _, b in tips}
        objs = [l.split(' ', 1) for l in git(r, 'rev-list', '--objects', '--all').splitlines() if ' ' in l]
        by_blob = {}
        for sha, path in objs:
            by_blob.setdefault(sha, path)
        names = sorted({p for _, p in objs if NAMES.search(p)})
        found = {k: {'tip': set(), 'history': set()} for k in MARKS}
        texts = [(s, p) for s, p in by_blob.items() if p.endswith(TEXT)]
        if texts:
            q = subprocess.run(['git', 'cat-file', '--batch'], cwd=r, input=''.join(f'{s}\n' for s, _ in texts).encode(), capture_output=True).stdout
            i = 0
            for s, p in texts:
                head_end = q.index(b'\n', i)
                parts = q[i:head_end].split()
                if len(parts) < 3:
                    i = head_end + 1
                    continue
                size = int(parts[2])
                body = q[head_end + 1: head_end + 1 + size]
                i = head_end + 1 + size + 1
                for k, rx in MARKS.items():
                    if rx.search(body):
                        found[k]['tip' if s in tip_blobs else 'history'].add(p)
        people = {l for l in git(r, 'log', '--all', '--format=%ae%n%ce').split() if l}
        odd = sorted(e for e in people if not (e.endswith('lexifina.com') or e.endswith('.invalid')))
        return {'repo': repo,
                'private_names_at_tip': sorted(n for n in names if n in tip_paths)[:20],
                'private_names_in_history_only': sorted(n for n in names if n not in tip_paths)[:20],
                'markers': {k: {'tip': sorted(v['tip'])[:10], 'history_only': len(v['history'] - v['tip'])} for k, v in found.items() if v['tip'] or v['history']},
                'other_author_emails': odd, 'commits': int(git(r, 'rev-list', '--count', '--all').strip() or 0),
                'seconds': round(time.time() - t0)}
    except Exception as e:
        return {'repo': repo, 'error': str(e)[:200]}
    finally:
        shutil.rmtree(m, ignore_errors=True)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    TMP.mkdir(exist_ok=True)
    out = Path(sys.argv[1])
    repos = sys.argv[2:]
    with ThreadPoolExecutor(10) as ex:
        res = list(ex.map(one, repos))
    out.write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding='utf-8')
    print('audited', len(res))
