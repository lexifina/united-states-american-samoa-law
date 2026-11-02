"""Second pass for REVIEW units (gitlaw-scraper-dell, 2026-10-31). Private.

From each unit's cached home page: every URL mentioning a privacy / terms / copyright policy (anywhere in the HTML) is
read and scanned for HOLD wording; then up to two ordinance / gazette / normatividad pages are read and one document
link on them is fetched and classified (PDF with a text layer, scan, captcha form, HTML). Robots rules already read in
the gate pass are re-applied to every URL. One request at a time per host (sa_probe).

    python -X utf8 scripts/world-law/sa_review.py <batch-jsonl> [<repo> ...]
"""
from __future__ import annotations

import html
import json
import re
import sys
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import sa_probe
from sa_gate_batch import HOLD, plain

HERE = Path(__file__).resolve().parent
POLICY = re.compile(r'pol[ií]tica|privacidad|condiciones|t[eé]rminos|derechos[-_ ]de[-_ ]autor|aviso[-_ ]legal', re.I)
LAWPAGE = re.compile(r'ordenanz|gaceta|normatividad|normativa', re.I)
DOC = re.compile(r'\.pdf\b|descargar|visorpdf|download|/documentos?/', re.I)


def urls(s: str, base: str) -> list[tuple[str, str]]:
    out = {}
    for m in re.finditer(r'href=["\']([^"\'#]+)["\'][^>]*>(.{0,200}?)</a', s, re.S | re.I):
        t = html.unescape(re.sub(r'<[^>]+>|\s+', ' ', m.group(2))).strip()
        u = urljoin(base, html.unescape(m.group(1).strip()))
        if u.startswith('http'):
            out.setdefault(u, t[:90])
    return list(out.items())


def same_site(u: str, base: str) -> bool:
    a = urlparse(u).netloc.lower().removeprefix('www.')
    b = urlparse(base).netloc.lower().removeprefix('www.')
    return a == b or a.endswith('.' + b)


def classify(b: bytes) -> str:
    if b[:4] == b'%PDF':
        try:
            import pymupdf
            with pymupdf.open(stream=b, filetype='pdf') as d:
                n = sum(len(p.get_text().strip()) for p in d)
                return f'PDF {d.page_count} pages, {n} text chars' + (' (SCAN: no text layer)' if n < 200 else '')
        except Exception as e:  # noqa: BLE001
            return f'PDF unreadable {e}'
    s = sa_probe.text(b[:200000]).lower()
    if 'g-recaptcha' in s or 'no eres un robot' in s or 'h-captcha' in s:
        return 'CAPTCHA FORM (document behind a captcha)'
    if b[:2] == b'PK':
        return 'DOCX/ZIP'
    return 'HTML'


def review(rec: dict) -> dict:
    host = next((h for h in rec['hosts'] if h['verdict'] == 'REVIEW'), None)
    if not host:
        return {'repo': rec['repo'], 'skip': 'no REVIEW host'}
    base = host['host']
    rb = sa_probe.fetch(base + 'robots.txt')
    rp = urllib.robotparser.RobotFileParser()
    body = sa_probe.text(rb.get('body') or b'')
    if rb['status'] == 200 and '<html' not in body[:500].lower():
        rp.parse(body.splitlines())
    else:
        rp.parse([])
    delay = host.get('crawl_delay') or 0
    home = sa_probe.fetch(base, delay=delay)
    fin = home.get('final') or base
    s = sa_probe.text(home['body'])
    out = {'repo': rec['repo'], 'host': base, 'policies': [], 'lawpages': [], 'docs': []}
    allu = urls(s, fin)
    pol = [(u, t) for u, t in allu if same_site(u, base) and (POLICY.search(t) or POLICY.search(u))
           and not re.search(r'tratamiento|datos[-_ ]personales|cookies|seguridad[-_ ]digital|antisoborno|riesgo', u + t, re.I)][:3]
    for u, t in pol:
        if not rp.can_fetch('*', u):
            out['policies'].append({'url': u, 'skipped': 'robots'})
            continue
        m = sa_probe.fetch(u, delay=delay)
        txt = plain(m['body'], u, '') if m['status'] == 200 else ''
        hits = [txt[max(0, x.start() - 200):x.end() + 200] for x in HOLD.finditer(txt)][:3]
        cls = classify(m['body']) if m['status'] == 200 else str(m['status'])
        out['policies'].append({'url': u, 'label': t, 'status': m['status'], 'class': cls, 'hold': hits})
        if 'CAPTCHA' in cls:
            out['captcha'] = u
    law = [(u, t) for u, t in allu if same_site(u, base) and (LAWPAGE.search(t) or LAWPAGE.search(u))][:2]
    for u, t in law:
        if not rp.can_fetch('*', u):
            continue
        m = sa_probe.fetch(u, delay=delay)
        if m['status'] != 200:
            out['lawpages'].append({'url': u, 'status': m['status']})
            continue
        ls = urls(sa_probe.text(m['body']), m.get('final') or u)
        docs = [(d, dt) for d, dt in ls if same_site(d, base) and DOC.search(d)]
        out['lawpages'].append({'url': u, 'label': t, 'docs': len(docs), 'sample': docs[:4]})
        if docs and not out['docs']:
            d, dt = docs[0]
            if rp.can_fetch('*', d):
                md = sa_probe.fetch(d, delay=delay)
                cls = classify(md['body']) if md['status'] == 200 else str(md['status'])
                out['docs'].append({'url': d, 'label': dt, 'status': md['status'], 'class': cls})
                if 'CAPTCHA' in cls:
                    out['captcha'] = d
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    want = set(sys.argv[2:])
    recs = {}
    for f in sys.argv[1].split(','):
        for l in open(f, encoding='utf-8'):
            r = json.loads(l)
            if r.get('verdict') == 'REVIEW' and (not want or r['repo'] in want):
                recs[r['repo']] = r
    outp = HERE / '.sa-regions' / 'review.jsonl'
    for repo, r in recs.items():
        try:
            o = review(r)
        except Exception as e:  # noqa: BLE001
            o = {'repo': repo, 'error': str(e)[:300]}
        with open(outp, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(o, ensure_ascii=False) + '\n')
        pol = '; '.join(f"{p.get('class', p.get('skipped'))}{' HOLD' if p.get('hold') else ''} {p['url'][-60:]}" for p in o.get('policies', []))
        docs = '; '.join(f"{d['class']} {d['url'][-70:]}" for d in o.get('docs', []))
        print(repo, '| policy:', pol or '-', '| doc:', docs or '-', '| lawpages:',
              [(p['url'][-50:], p.get('docs')) for p in o.get('lawpages', [])], flush=True)
