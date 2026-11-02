"""Gate a list of regional units in sequence (gitlaw-scraper-dell, 2026-10-31). Private.

For each unit: claim (exclusive create), then for each candidate host in order: robots.txt alone, the home page only
if robots allows it, then the site's terms / copyright pages (HTML, PDF or DOCX) scanned for HOLD wording ("autorización
previa", "uso personal", "no comercial", "prohibida su reproducción"). Records a verdict with quoted evidence in
.sa-regions/gates-<batch>.jsonl. A FAIL or HOLD releases the claim; a PASS-candidate keeps it for review.

    python -X utf8 scripts/world-law/sa_gate_batch.py <batch> <repo>=<host>[,<host>...] ...
"""
from __future__ import annotations

import html
import io
import json
import re
import sys
import time
import urllib.robotparser
import zipfile
from pathlib import Path
from urllib.parse import urljoin, urlparse

import sa_probe

HERE = Path(__file__).resolve().parent
CLAIMS = HERE / 'claims'
TERMS = re.compile(r't[eé]rminos|condiciones|derechos[-_ ]de[-_ ]autor|propiedad[-_ ]intelectual|aviso[-_ ]legal|'
                   r'pol[ií]tica[-_ ]de[-_ ](?:privacidad|derechos|uso)|copyright', re.I)
LAWS = re.compile(r'ordenanz|gaceta|normativ|normograma|leyes|constituci[oó]n|acuerdos', re.I)
HOLD = re.compile(r'autorizaci[oó]n\s+(?:previa|expresa|escrita)|previa\s+(?:y\s+)?(?:expresa\s+)?autorizaci[oó]n|'
                  r'uso\s+(?:exclusivamente\s+)?personal|(?:fines|uso|usos)\s+no\s+comercial|prohibida\s+su\s+reproducci[oó]n|'
                  r'se\s+proh[ií]be\s+(?:expresamente\s+)?(?:la|su|cualquier)\s+(?:reproducci[oó]n|uso)|'
                  r'sin\s+(?:la\s+)?(?:previa\s+)?autorizaci[oó]n', re.I)


def claim(repo: str, note: str) -> str:
    p = CLAIMS / f'{repo}.txt'
    try:
        with open(p, 'x', encoding='utf-8', newline='\n') as f:
            f.write(f'gitlaw-scraper-dell {time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())} (South American regional units: {note})\n')
        return 'claimed'
    except FileExistsError:
        t = p.read_text(encoding='utf-8', errors='replace')
        return 'mine' if t.startswith('gitlaw-scraper-dell') else 'HELD ' + t.strip()[:100]


def plain(b: bytes, url: str, ctype: str) -> str:
    try:
        if b[:4] == b'%PDF':
            import pymupdf
            with pymupdf.open(stream=b, filetype='pdf') as d:
                return re.sub(r'\s+', ' ', ' '.join(p.get_text() for p in d))
        if b[:2] == b'PK':
            x = zipfile.ZipFile(io.BytesIO(b)).read('word/document.xml').decode('utf-8', 'replace')
            return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x))
    except Exception as e:  # noqa: BLE001
        return f'[unreadable: {e}]'
    s = sa_probe.text(b)
    s = re.sub(r'(?s)<(script|style).*?</\1>', ' ', s)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s))


def links(s: str, base: str, rx) -> list[tuple[str, str]]:
    out = {}
    for m in re.finditer(r'href=["\']([^"\'#]+)["\'][^>]*>(.{0,160}?)</a', s, re.S | re.I):
        t = re.sub(r'<[^>]+>|\s+', ' ', m.group(2)).strip()
        if rx.search(m.group(1)) or rx.search(t):
            u = urljoin(base, html.unescape(m.group(1).strip()))
            if u.startswith('http'):
                out.setdefault(u, t[:80])
    return list(out.items())


def gate_host(host: str) -> dict:
    base = host if host.startswith('http') else f'https://{host}'
    base = base.rstrip('/') + '/'
    r = {'host': base}
    rb = sa_probe.fetch(base + 'robots.txt')
    r['robots'] = {'status': rb['status'], 'final': rb.get('final'), 'err': rb.get('error', '')[:160],
                   'markers': rb.get('challenge_markers')}
    st = rb['status']
    if st in (0, -1):
        return {**r, 'verdict': 'FAIL', 'gate': 1, 'why': 'robots.txt: ' + (rb.get('error') or 'error')[:160]}
    if st in (403, 429) or (rb.get('challenge_markers') and st not in (404,)):
        if st != 200 or any(m in (rb.get('challenge_markers') or []) for m in
                            ('just a moment', 'cf-chl', 'incapsula incident', 'challenge-platform',
                             '_incapsula_resource', 'request unsuccessful')):
            return {**r, 'verdict': 'FAIL', 'gate': 4, 'why': f'challenge/{st} on robots.txt {rb.get("challenge_markers")}'}
    if st >= 500:
        return {**r, 'verdict': 'FAIL', 'gate': 2, 'why': f'robots.txt HTTP {st} (= disallow all)'}
    body = sa_probe.text(rb['body'])
    is_file = st == 200 and 'html' not in (rb.get('ctype') or '').lower() and '<html' not in body[:500].lower()
    rp = urllib.robotparser.RobotFileParser()
    if is_file:
        rp.parse(body.splitlines())
        r['robots']['text'] = ' | '.join(l.strip() for l in body.splitlines() if l.strip() and not l.startswith('#'))[:600]
        cd = re.search(r'crawl-delay\s*:\s*(\d+)', body, re.I)
        r['crawl_delay'] = int(cd.group(1)) if cd else None
        if re.search(r'^\s*user-agent\s*:\s*(claudebot|claude-web|anthropic-ai|gptbot)', body, re.I | re.M):
            r['robots']['ai_rule'] = True
        if not rp.can_fetch('*', base):
            return {**r, 'verdict': 'FAIL', 'gate': 2, 'why': 'robots.txt disallows /'}
    else:
        r['robots']['text'] = '(no robots.txt file)'
    delay = r.get('crawl_delay') or 0
    h = sa_probe.fetch(base, delay=delay)
    r['home'] = {'status': h['status'], 'final': h.get('final'), 'bytes': len(h['body']), 'markers': h.get('challenge_markers'),
                 'err': h.get('error', '')[:160]}
    if h['status'] in (0, -1):
        return {**r, 'verdict': 'FAIL', 'gate': 1, 'why': 'home: ' + (h.get('error') or 'error')[:160]}
    if h['status'] in (403, 429) or (h.get('challenge_markers') and any(
            m in h['challenge_markers'] for m in ('just a moment', 'cf-chl', 'incapsula incident', 'challenge-platform',
                                                  '_incapsula_resource', 'request unsuccessful'))):
        return {**r, 'verdict': 'FAIL', 'gate': 4, 'why': f'challenge/{h["status"]} on home {h.get("challenge_markers")}'}
    if h['status'] >= 400:
        return {**r, 'verdict': 'FAIL', 'gate': 1, 'why': f'home HTTP {h["status"]}'}
    s = sa_probe.text(h['body'])
    fin = h.get('final') or base
    r['law_links'] = links(s, fin, LAWS)[:25]
    tl = [(u, t) for u, t in links(s, fin, TERMS) if urlparse(u).netloc.split(':')[0].endswith(
        urlparse(base).netloc.replace('www.', ''))][:5]
    r['terms'] = []
    held = []
    for u, t in tl:
        if rp.default_entry is not None or rp.entries:
            if not rp.can_fetch('*', u):
                r['terms'].append({'url': u, 'skipped': 'robots disallows'})
                continue
        m = sa_probe.fetch(u, delay=delay)
        txt = plain(m['body'], u, m.get('ctype', '')) if m['status'] == 200 else ''
        hits = [txt[max(0, x.start() - 220):x.end() + 220] for x in HOLD.finditer(txt)][:3]
        r['terms'].append({'url': u, 'label': t, 'status': m['status'], 'chars': len(txt), 'hold': hits})
        if hits:
            held.append(u)
        # one level down: a terms page that links to its own PDF/DOCX
        if m['status'] == 200 and not held:
            for u2, t2 in links(sa_probe.text(m['body']), u, re.compile(r'\.(pdf|docx?)\b', re.I)):
                if TERMS.search(u2) or TERMS.search(t2):
                    m2 = sa_probe.fetch(u2, delay=delay)
                    txt2 = plain(m2['body'], u2, m2.get('ctype', '')) if m2['status'] == 200 else ''
                    hits2 = [txt2[max(0, x.start() - 220):x.end() + 220] for x in HOLD.finditer(txt2)][:3]
                    r['terms'].append({'url': u2, 'label': t2, 'status': m2['status'], 'chars': len(txt2), 'hold': hits2})
                    if hits2:
                        held.append(u2)
                    break
    if held:
        return {**r, 'verdict': 'HOLD', 'gate': 3, 'why': 'terms: ' + ', '.join(held)}
    return {**r, 'verdict': 'REVIEW', 'why': 'robots ok, no challenge, no HOLD wording found in ' +
            (', '.join(u for u, _ in tl) or 'any terms page (none linked from home)')}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    except Exception:
        pass
    batch = sys.argv[1]
    out = HERE / '.sa-regions' / f'gates-{batch}.jsonl'
    for spec in sys.argv[2:]:
        repo, _, hosts = spec.partition('=')
        c = claim(repo, repo)
        if c.startswith('HELD'):
            rec = {'repo': repo, 'verdict': 'SKIP', 'why': c}
        else:
            rec = {'repo': repo, 'hosts': []}
            final = None
            for host in hosts.split(','):
                g = gate_host(host)
                rec['hosts'].append(g)
                final = g
                if g['verdict'] in ('REVIEW', 'HOLD'):
                    break
            rec['verdict'] = final['verdict'] if final else 'FAIL'
            rec['why'] = final['why'] if final else 'no host'
            if rec['verdict'] in ('FAIL', 'HOLD'):
                (CLAIMS / f'{repo}.txt').unlink(missing_ok=True)
                rec['claim'] = 'released'
        rec['at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        with open(out, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print(repo, rec['verdict'], rec['why'][:200], flush=True)


if __name__ == '__main__':
    main()
