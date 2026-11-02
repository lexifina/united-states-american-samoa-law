"""Fetch every source text for the Vanuatu build into .cache/ (resumable; cached by sha256 of the URL).

PacLII pages are read only from Internet Archive `id_` captures, pinned by timestamp, through the shared
gitlaw_common/wayback.py client (one machine-wide adaptive rate). The 2020 consolidated Constitution comes directly
from parliament.gov.vu (one request). The list of sources is sources.json.

    python -X utf8 scripts/vanuatu-law/fetch.py
"""
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'


def wb_url(src: dict) -> str:
    return f'https://web.archive.org/web/{src["ts"]}id_/{src["url"]}'


def cache_path(url: str) -> Path:
    return CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()


def direct(url: str) -> bytes | None:
    hit = cache_path(url)
    if hit.exists():
        return hit.read_bytes()
    tmp = hit.with_suffix('.part')
    out = subprocess.run(['curl', '-sS', '-L', '--compressed', '-A', UA, '--max-time', '180', '-o', str(tmp),
                          '-w', '%{http_code}', url], capture_output=True, text=True)
    code = int(out.stdout.strip() or 0)
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'bytes': tmp.stat().st_size if tmp.exists() else 0,
                            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'via': 'fetch.py'}) + '\n')
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    tmp.replace(hit)
    time.sleep(1)
    return hit.read_bytes()


def get(src: dict) -> bytes | None:
    if src.get('ts'):
        return wayback.fetch(wb_url(src), CACHE)
    return direct(src['url'])


def raw(src: dict) -> bytes:
    """Read a source from the cache only (used by parse.py)."""
    p = cache_path(wb_url(src) if src.get('ts') else src['url'])
    return p.read_bytes()


def main():
    CACHE.mkdir(exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    srcs = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    todo = [s for s in srcs.values()]
    with ThreadPoolExecutor(4) as ex:
        for s, b in zip(todo, ex.map(get, todo)):
            print('ok ' if b else 'MISSING', len(b or b''), s['url'], s.get('ts', ''))


if __name__ == '__main__':
    main()
