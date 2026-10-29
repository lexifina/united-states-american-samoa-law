"""Lithuania: fetch the archived official texts (Wayback id_ captures of e-tar.lt; e-tar.lt itself sits behind a
Cloudflare challenge that we never touch). Every byte goes through scripts/gitlaw_common/wayback.py, which caches by
sha256 of the URL under .cache/ and logs to .cache/requests.jsonl. Capture timestamps are pinned in sources.json."""
import json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402
CACHE = HERE / '.cache'
SRC = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))


def one(item):
    ts, url = item['ts'], item['url']
    b = wayback.get(url, ts=ts, cache=CACHE)
    return url, ts, len(b) if b else 0


UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'


def direct(item):
    """The Seimas page as served today (lrs.lt allows crawlers; one request, kept as .cache/direct/<role>.html)."""
    import subprocess, time
    out = CACHE / 'direct' / (item['role'].replace(':', '-') + '.html')
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['curl', '-s', '--compressed', '-A', UA, '--max-time', '60', '-o', str(out), '-w', '%{http_code}',
                        item['url']], capture_output=True, text=True)
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'t': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'url': item['url'],
                            'status': int(r.stdout or 0), 'bytes': out.stat().st_size if out.exists() else 0}) + '\n')
    print(r.stdout, item['url'])


def main():
    items = [it for act in SRC['acts'].values() for it in act['captures']]
    with ThreadPoolExecutor(4) as ex:
        for url, ts, n in ex.map(one, items):
            print(n, ts, url, flush=True)
    for it in SRC.get('direct', []):
        direct(it)


if __name__ == '__main__':
    main()
