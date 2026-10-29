"""Fetch the legalize-be versions of the acts we build (text source for Belgium).

legalize-be (github.com/legalize-dev/legalize-be; pipeline MIT, data "Licence ouverte / open data federal belge,
CC0 par defaut") reconstructs Justel's archived consolidated versions, one file per act (be/<NUMAC>.md) and one
commit per archived version. Justel's own robots.txt disallows /cgi_loi/, /eli/ and /mopdf/, so we read those
versions from legalize-be instead of crawling Justel.

Steps (resumable, everything cached under .cache/):
1. a treeless bare clone (commits only, ~22 MB) of legalize-be, pinned at PIN;
2. an index of every commit whose `Norm-Id:` trailer is one of our NUMACs (.cache/legalize/index.json);
3. each version's file from raw.githubusercontent.com/<repo>/<commit>/be/<NUMAC>.md, through the shared
   adaptive host client (wayback.host_get), 8 threads, cached by sha256 of the URL and logged to requests.jsonl.

    python -X utf8 scripts/belgium-law/fetch_legalize.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

REPO = 'legalize-dev/legalize-be'
PIN = 'da37dfb18b17b06f8f8dc74c0d724cca22292bee'   # main on 2026-10-29 (last commit dated 2026-10-28)
CLONE = CACHE / 'legalize-be.git'
OUT = CACHE / 'legalize'

NUMACS = {
    '1994021048': 'Constitution coordonnee (17 fevrier 1994)',
    '1867060850': 'Code penal (8 juin 1867)',
    '2024002052': 'Loi introduisant le livre Ier du Code penal (29 fevrier 2024)',
    '2024002088': 'Loi introduisant le livre II du Code penal (29 fevrier 2024)',
    '2019012168': 'Loi portant creation d\'un Code civil et y inserant un livre 8 (13 avril 2019)',
    '2020020347': 'Loi portant le livre 3 du Code civil (4 fevrier 2020)',
    '2022030600': 'Loi portant le livre 2, titre 3 et le livre 4 du Code civil (19 janvier 2022)',
    '2022032057': 'Loi portant le livre 1er du Code civil (28 avril 2022)',
    '2022032058': 'Loi portant le livre 5 du Code civil (28 avril 2022)',
    '2024001600': 'Loi portant le livre 6 du Code civil (7 fevrier 2024)',
    '2025005089': 'Loi portant le titre 1er du livre 9 du Code civil (5 juin 2025)',
}


def git(*args: str) -> str:
    return subprocess.run(['git', '-C', str(CLONE), *args], check=True, capture_output=True,
                          text=True, encoding='utf-8').stdout


def ensure_clone() -> None:
    if not (CLONE / 'HEAD').exists():
        subprocess.run(['git', 'clone', '--bare', '--filter=tree:0', f'https://github.com/{REPO}.git', str(CLONE)],
                       check=True)
    try:
        git('cat-file', '-e', PIN + '^{commit}')
    except subprocess.CalledProcessError:
        subprocess.run(['git', '-C', str(CLONE), 'fetch', '--filter=tree:0', 'origin', 'main'], check=True)


def index() -> list[dict]:
    raw = git('log', PIN, '--format=%H%x1f%ad%x1f%B%x1e', '--date=short')
    rows = []
    for rec in raw.split('\x1e'):
        rec = rec.strip('\n')
        if not rec:
            continue
        sha, date, body = rec.split('\x1f', 2)
        m = re.search(r'^Norm-Id: (\S+)\s*$', body, re.M)
        if not m or m.group(1) not in NUMACS:
            continue
        rows.append({'commit': sha, 'date': date, 'numac': m.group(1), 'message': body.strip()})
    rows.reverse()   # oldest first, in legalize-be's own commit order
    return rows


def raw_url(sha: str, numac: str) -> str:
    return f'https://raw.githubusercontent.com/{REPO}/{sha}/be/{numac}.md'


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    OUT.mkdir(exist_ok=True)
    ensure_clone()
    rows = index()
    (OUT / 'index.json').write_text(json.dumps({'repo': REPO, 'pin': PIN, 'commits': rows}, ensure_ascii=False,
                                               indent=1), encoding='utf-8')
    print(len(rows), 'commits for', len(NUMACS), 'acts')

    def one(row: dict) -> tuple[str, int]:
        body = wayback.host_get(raw_url(row['commit'], row['numac']), cache=CACHE)
        return row['commit'], len(body or b'')

    with ThreadPoolExecutor(8) as pool:
        missing = [sha for sha, n in pool.map(one, rows) if not n]
    print('missing:', missing)


if __name__ == '__main__':
    main()
