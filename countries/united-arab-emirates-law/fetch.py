"""Fetch the UAE Phase 1 acts from Internet Archive captures of uaelegislation.gov.ae (Arabic).

uaelegislation.gov.ae answers every direct request from this machine with a Cloudflare challenge (HTTP 403), so,
following the git-for-law rules, we never touch the live site and read only archive.org `id_` captures through the
shared client scripts/gitlaw_common/wayback.py (one adaptive machine-wide rate, cache by sha256 of URL, requests.jsonl).
Common Crawl's index was unreachable from this machine on 2026-10-28, so archive.org is the only archive used.

What is fetched, per act (legislation id on the site):
  1. the CDX list of captures under /ar/legislations/<id> (one request);
  2. the newest capture of the act page whose articles are inline (later pages load them by ajax);
  3. every "previous texts" popup (/ar/materials/<n>/previous) that page links to, at its newest capture;
  4. the act's related-legislations page (lists the amending laws with their links), newest capture;
  5. each amending law's own page (issue, in-force and gazette dates), newest capture.
Capture timestamps are written to .cache/pins.json so parse.py reads exactly the same bytes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, r'C:/Users/alany/Documents/lexifina/scripts/gitlaw_common')
import wayback  # noqa: E402

HERE = Path(__file__).resolve().parent
CACHE = HERE / '.cache'
SITE = 'https://uaelegislation.gov.ae'
ACTS = {'1000': 'constitution', '1529': 'penal-code', '1972': 'personal-data'}


def cdx(path: str, match: str = 'prefix') -> list[dict]:
    rows = wayback.captures('uaelegislation.gov.ae' + path, match=match, cache=CACHE, collapse=None)
    return sorted(rows, key=lambda r: r['timestamp'])


def norm(url: str) -> str:
    return re.sub(r'^https?://(www\.)?uaelegislation\.gov\.ae', '', url).split('?')[0].rstrip('/')


def newest(rows: list[dict], path: str, mime: str = 'text/html') -> list[dict]:
    return [r for r in reversed(rows) if norm(r['original']) == path and r['mimetype'] == mime]


def get(rec: dict) -> bytes | None:
    return wayback.get(rec['original'], rec['timestamp'], cache=CACHE)


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    pins: dict = json.loads((CACHE / 'pins.json').read_text('utf-8')) if (CACHE / 'pins.json').exists() else {}
    for lid in ACTS:
        rows = cdx(f'/ar/legislations/{lid}')
        act_pin = None
        for rec in newest(rows, f'/ar/legislations/{lid}'):
            body = get(rec)
            if body and body.count(b'id="item') > 20:
                act_pin = rec
                break
        if not act_pin:
            print('no inline capture for', lid)
            continue
        html = get(act_pin).decode('utf-8')
        pins[f'act:{lid}'] = {'url': act_pin['original'], 'ts': act_pin['timestamp']}
        rel = newest(rows, f'/ar/legislations/{lid}/related-legislations')
        if rel and get(rel[0]):
            pins[f'related:{lid}'] = {'url': rel[0]['original'], 'ts': rel[0]['timestamp']}
        mats = sorted(set(re.findall(r'/ar/materials/(\d+)/previous', html)), key=int)
        mrows = []
        for m in mats:
            mrows = cdx(f'/ar/materials/{m}/previous', match='prefix')
            got = None
            for rec in reversed(mrows):
                if rec['statuscode'] == '200' and get(rec):
                    got = rec
                    break
            pins[f'material:{m}'] = {'url': got['original'], 'ts': got['timestamp']} if got else None
            print(lid, 'material', m, got and got['timestamp'])
        (CACHE / 'pins.json').write_text(json.dumps(pins, ensure_ascii=False, indent=1, sort_keys=True), 'utf-8')
        print(lid, 'act', act_pin['timestamp'], len(mats), 'materials')
    if 'laws' not in sys.argv[1:]:
        return
    # amending laws named on the related-legislations pages
    for key, pin in list(pins.items()):
        if not key.startswith('related:') or not pin:
            continue
        body = wayback.get(pin['url'], pin['ts'], cache=CACHE).decode('utf-8')
        for lid in sorted(set(re.findall(r'/ar/legislations/(\d+)', body)), key=int):
            if f'law:{lid}' in pins or lid in ACTS:
                continue
            rows = newest(cdx(f'/ar/legislations/{lid}', match='exact'), f'/ar/legislations/{lid}')
            got = rows[0] if rows and get(rows[0]) else None
            pins[f'law:{lid}'] = {'url': got['original'], 'ts': got['timestamp']} if got else None
            print('law', lid, got and got['timestamp'])
        (CACHE / 'pins.json').write_text(json.dumps(pins, ensure_ascii=False, indent=1, sort_keys=True), 'utf-8')


if __name__ == '__main__':
    main()
