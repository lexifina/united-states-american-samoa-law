"""Fetch the catalogue of Maltese law from legislation.mt.

Reads the ELI sitemap for every Chapter (eli/cap/N) and piece of subsidiary legislation (eli/sl/N.M), then each
law's English landing page, which embeds two timelines as JSON: `group1Data` (the consolidated versions, with the
snapshot id of each version's PDF) and `group2Data` (the Acts and Legal Notices related to the law). Writes one
JSON file per law to .cache/laws/ and resumes where it left off.

    python scripts/malta-law/fetch_catalogue.py [--workers 8] [--only cap|sl]
"""
import argparse
import html
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
CACHE = HERE / '.cache'
LAWS = CACHE / 'laws'
BASE = 'https://legislation.mt'
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
UA = 'Mozilla/5.0 (compatible; Lexifina law history; +https://lexifina.com)'


def curl(url: str, timeout: int = 90) -> bytes:
    # Python's urllib fails on this machine (self-signed proxy cert in the chain), so use curl.
    for attempt in range(4):
        r = subprocess.run(['curl', '-sL', '--compressed', '-m', str(timeout), '-A', UA, '-w', '\n%{http_code}', url],
                           capture_output=True)
        body, _, code = r.stdout.rpartition(b'\n')
        if r.returncode == 0 and code.strip() == b'200':
            return body
        time.sleep(2 + attempt * 5)
    raise RuntimeError(f'GET {url} failed: rc={r.returncode} code={code!r}')


def timeline(page: str, name: str) -> list:
    m = re.search(r'var %s = ' % name, page)
    if not m:
        return []
    arr, _ = json.JSONDecoder().raw_decode(page[m.end():])
    return arr


def tooltip(t: str | None) -> dict:
    """The related-act tooltip is HTML: publication date, force status, document type, promulgating notices."""
    if not t:
        return {}
    text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<!--.*?-->|<[^>]+>', ' ', t, flags=re.S))).strip()
    out = {'text': text}
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
    if m:
        out['published'] = f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    m = re.search(r'Promulgat\S* bl-Avvi\S* Legali\s+(.+)$', text)
    if m:
        out['promulgated_by'] = m.group(1).strip()
    return out


def ms_date(v: str | None) -> str | None:
    m = re.search(r'Date\((-?\d+)\)', v or '')
    if not m:
        return None
    # The timeline stores midnight Malta time as UTC milliseconds; adding 12 hours lands safely inside the day.
    # (time.gmtime rejects negative timestamps on Windows, and versions go back to 1855.)
    return (EPOCH + timedelta(milliseconds=int(m.group(1)), hours=12)).strftime('%Y-%m-%d')


def fetch_law(kind: str, ident: str) -> dict:
    page = curl(f'{BASE}/eli/{kind}/{ident}/eng').decode('utf-8', 'replace')
    ld = {}
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            d = json.loads(block)
        except json.JSONDecodeError:
            continue
        if d.get('@type') == 'Legislation':
            ld = d
            break
    versions, related = [], []
    for item in timeline(page, 'group1Data'):
        versions.append({'date': ms_date(item.get('start')), 'label': item.get('content'), 'uri': item.get('uri'),
                         'snapshot': item.get('snapshotID'), 'lang': item.get('lang'),
                         'repealed': item.get('isRepealed'), 'class': item.get('className')})
    for item in timeline(page, 'group2Data'):
        related.append({'name': item.get('content'), 'uri': item.get('uri'), 'date': ms_date(item.get('start')),
                        'indicative': item.get('isPublishDateIndicative'), 'force': item.get('legalForceEnum'),
                        'relation': item.get('legalRelationEnum'), **tooltip(item.get('title'))})
    force = (ld.get('legislationLegalForce') or {}).get('@id')
    return {'kind': kind, 'id': ident, 'title': ld.get('alternativeHeadline') or ld.get('name'),
            'legal_force': force, 'date_created': ld.get('legislationDate'),
            'version_shown': ld.get('legislationDateVersion'), 'versions': versions, 'related': related}


def catalogue(only: str | None) -> list[tuple[str, str]]:
    sm = CACHE / 'sitemap.xml'
    if not sm.exists():
        sm.write_bytes(curl(f'{BASE}/eli/sitemap.xml'))
    locs = re.findall(r'<loc>https://legislation\.mt/eli/(cap|sl)/([^<]+)</loc>', sm.read_text('utf-8'))
    out = sorted({(k, i) for k, i in locs if '/' not in i and (only is None or k == only)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--only', choices=['cap', 'sl'])
    args = ap.parse_args()
    LAWS.mkdir(parents=True, exist_ok=True)
    (CACHE / '.gitignore').write_text('*\n')
    todo = [(k, i) for k, i in catalogue(args.only) if not (LAWS / f'{k}-{i}.json').exists()]
    print(f'{len(todo)} laws to fetch', flush=True)
    done = failed = 0
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(fetch_law, k, i): (k, i) for k, i in todo}
        for fut in as_completed(futs):
            k, i = futs[fut]
            try:
                (LAWS / f'{k}-{i}.json').write_text(json.dumps(fut.result(), ensure_ascii=False, indent=1), 'utf-8')
                done += 1
            except Exception as e:  # noqa: BLE001 - keep going, report at the end
                failed += 1
                print(f'FAIL {k}/{i}: {e}', file=sys.stderr, flush=True)
            if (done + failed) % 100 == 0:
                print(f'{done} done, {failed} failed of {len(todo)}', flush=True)
    print(f'finished: {done} done, {failed} failed', flush=True)


if __name__ == '__main__':
    main()
