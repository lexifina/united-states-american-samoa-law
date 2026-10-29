"""gitlaw-LV fetch: likumi.lv consolidated versions ("redakcijas") through Internet Archive `id_` captures.

likumi.lv does not answer HTTPS from this machine (TCP timeout on 443; port 80 only redirects to HTTPS), and
Common Crawl's index server is unreachable from here, so every likumi.lv page is read from archive.org through the
shared client scripts/gitlaw_common/wayback.py (one machine-wide adaptive rate). Amending laws' official
publications are read directly from www.vestnesis.lv (robots.txt allows /ta/, Crawl-delay 1).

    python -X utf8 fetch.py <act-slug> [--cached-only]

Writes captures.json: for each act, the version list (from the newest archived page) and the pinned capture
(timestamp + URL) used for each version. Everything is cached in .cache/ by sha256 of the URL.
"""
import json
import re
import subprocess
import sys
import time
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = HERE / '.cache'
ACTS = json.loads((HERE / 'acts.json').read_text(encoding='utf-8'))
CAPS = HERE / 'captures.json'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'


def version_list(html: str) -> list[dict]:
    m = re.search(r'\{"selected":.*?\]\}', html)
    if not m:
        return []
    d = json.loads(m.group(0))
    out = []
    for x in d['data']:
        txt = re.sub(r'<[^>]+>', '', x['content'])
        rng = re.match(r'(\d\d)\.(\d\d)\.(\d{4})\.-(?:(\d\d)\.(\d\d)\.(\d{4})\.|\.\.\.)', txt)
        frm = x['iso_value'].replace('/', '-')
        until = f'{rng.group(6)}-{rng.group(5)}-{rng.group(4)}' if rng and rng.group(6) else None
        out.append({'from': frm, 'until': until, 'status': txt.split()[-1] if txt.split() else ''})
    return sorted(out, key=lambda v: v['from'])


def page_version(html: str) -> str | None:
    """The version (YYYY-MM-DD) a page displays, from its version selector."""
    d = re.search(r'\{"selected":\{"value":"(\d\d)\.(\d\d)\.(\d{4})"', html)
    return f'{d.group(3)}-{d.group(2)}-{d.group(1)}' if d else None


def complete(html: str) -> bool:
    return '</html>' in html[-2000:].lower() and 'doc-body' in html


def direct(url: str) -> bytes | None:
    """www.vestnesis.lv, at most 1 request a second, cached and logged."""
    CACHE.mkdir(exist_ok=True)
    hit = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if hit.exists():
        return hit.read_bytes()
    time.sleep(1.0)
    tmp = hit.with_suffix('.part')
    out = subprocess.run(['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', '90', '-o', str(tmp),
                          '-w', '%{http_code}', url], capture_output=True, text=True)
    code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'bytes': tmp.stat().st_size if tmp.exists() else 0,
                            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'via': 'latvia-law/fetch.py'}) + '\n')
    if code != 200:
        tmp.unlink(missing_ok=True)
        return None
    for _ in range(6):  # Windows may hold the fresh file briefly (indexer, antivirus)
        try:
            tmp.replace(hit)
            break
        except PermissionError:
            time.sleep(0.5)
    else:
        body = tmp.read_bytes()  # still held: copy the bytes instead of renaming
        hit.write_bytes(body)
        try:
            tmp.unlink()
        except PermissionError:
            pass
    return hit.read_bytes()


def fetch_laws(slug: str) -> None:
    """Each amending law named in the act's notes: its official publication on www.vestnesis.lv/ta/id/<id>."""
    import likumi
    caps = json.loads(CAPS.read_text(encoding='utf-8'))[slug]
    lid = caps['likumi_id']
    ids = set()
    for v, c in caps['chosen'].items():
        b = wayback.get(c['url'], ts=c['ts'], cache=CACHE)
        p = likumi.parse_page(b, lid)
        for u in list(p['units'].values()) + list(p['removed'].values()):
            ids.update(e['law_id'] for e in u['events'])
    print(f'{slug}: {len(ids)} amending laws/rulings named')
    ids.discard(None)
    miss = [i for i in sorted(ids) if not direct(f'https://www.vestnesis.lv/ta/id/{i}')]
    print(f'{slug}: vestnesis pages missing for {miss}')


def main() -> None:
    slug = sys.argv[1]
    if '--laws' in sys.argv:
        return fetch_laws(slug)
    cached_only = '--cached-only' in sys.argv
    act = ACTS[slug]
    lid = act['likumi_id']
    caps_all = json.loads(CAPS.read_text(encoding='utf-8')) if CAPS.exists() else {}
    rows = wayback.captures(f'likumi.lv/ta/id/{lid}', match='prefix', cache=CACHE)
    rows = [r for r in rows if r.get('mimetype', '').startswith('text/html')]
    # every URL that names a version date: /ta/id/<id>[-slug]/redakcijas-datums/YYYY/MM/DD
    pat = re.compile(rf'likumi\.lv(?::80)?/ta/id/{lid}(?:-[a-z0-9-]+)?/redakcijas-datums/(\d{{4}})/(\d\d)/(\d\d)$')
    main_pat = re.compile(rf'likumi\.lv(?::80)?/ta/id/{lid}(?:-{re.escape(act["likumi_slug"])})?/?$')
    dated, mains = [], []
    for r in rows:
        u = r['original']
        m = pat.search(u)
        if m:
            dated.append((f'{m.group(1)}-{m.group(2)}-{m.group(3)}', r))
        elif main_pat.search(u):
            mains.append(r)
    mains.sort(key=lambda r: r['timestamp'], reverse=True)
    # newest complete main page gives the version list and today's text
    newest = None
    for r in mains[:6]:
        if cached_only and not (CACHE / hashlib.sha256(f"https://web.archive.org/web/{r['timestamp']}id_/{r['original']}".encode()).hexdigest()).exists():
            continue
        b = wayback.get(r['original'], ts=r['timestamp'], cache=CACHE)
        if b and complete(b.decode('utf-8', 'replace')):
            newest = (r, b.decode('utf-8', 'replace'))
            break
    if not newest:
        sys.exit(f'no complete main page for {slug}')
    versions = version_list(newest[1])
    print(f'{slug}: {len(versions)} versions listed; newest page {newest[0]["timestamp"]} shows {page_version(newest[1])}')
    chosen = {}
    cur = page_version(newest[1])
    if cur:
        chosen[cur] = {'ts': newest[0]['timestamp'], 'url': newest[0]['original']}
    # map each dated capture to the version in force on that date
    def version_on(day: str) -> str | None:
        best = None
        for v in versions:
            if v['from'] <= day:
                best = v['from']
        return best
    by_version: dict[str, list] = {}
    for day, r in dated:
        v = version_on(day)
        if v:
            by_version.setdefault(v, []).append((day == v, r['timestamp'], day, r))
    for v in versions:
        if v['from'] in chosen and v['from'] != cur:
            continue
        cands = sorted(by_version.get(v['from'], []), key=lambda c: (c[0], c[1]), reverse=True)
        for exact, ts, day, r in cands[:6]:
            url = f"https://web.archive.org/web/{ts}id_/{r['original']}"
            if cached_only and not (CACHE / hashlib.sha256(url.encode()).hexdigest()).exists():
                continue
            b = wayback.get(r['original'], ts=ts, cache=CACHE)
            if not b:
                continue
            h = b.decode('utf-8', 'replace')
            pv = page_version(h)
            if complete(h) and pv:
                if pv == v['from']:
                    chosen[v['from']] = {'ts': ts, 'url': r['original']}
                    break
                print(f'  {v["from"]}: capture {ts} {r["original"]} shows {pv}, skipped')
        print(f'  {v["from"]}: {chosen.get(v["from"], "MISSING")}')
    caps_all[slug] = {'likumi_id': lid, 'newest': {'ts': newest[0]['timestamp'], 'url': newest[0]['original']},
                      'versions': versions, 'chosen': dict(sorted(chosen.items()))}
    tmp = CAPS.with_suffix('.tmp')
    tmp.write_text(json.dumps(caps_all, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    tmp.replace(CAPS)
    print(f'{slug}: {len(chosen)}/{len(versions)} versions pinned')


if __name__ == '__main__':
    main()
