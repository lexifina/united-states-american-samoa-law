"""Private. Terms gate for SAPL Câmaras (gitlaw-scraper-dell, municipal SAPL wave, 2026-11-01).

    python -X utf8 scripts/world-law/br_sapl_gate.py <sapl host>=<folder>[=<câmara site>] ...

Per city, in sequence, one request at a time and >= 3 s apart across all hosts (the SAPL host itself >= 61 s after its
robots.txt read, Crawl-delay 60): the SAPL home page (cached in <folder>/.cache/sapl); the Câmara site it links
(www.<city>.<uf>.leg.br or similar): that site's robots.txt ALONE first, then its home page only if robots allows /,
then any page it links named like terms of use / copyright / reproduction (robots permitting). Prints what it finds
and writes world-law/.br-cities/gate/<host>.json.
"""
import json, re, sys, time
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from br_city_get import Host, Stop  # noqa: E402

SCRIPTS = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent / '.br-cities' / 'gate'
TERMS = re.compile(r'(?i)termos?\s+de\s+uso|pol[ií]tica\s+de\s+(?:uso|privacidade)|direitos\s+autorais|'
                   r'reprodu[çc][ãa]o|aviso\s+legal|copyright|cr[ée]ditos')
FLAGS = re.compile(r'(?i)(?:pr[ée]via|expressa)\s+autoriza[çc][ãa]o|autoriza[çc][ãa]o\s+(?:pr[ée]via|expressa|por escrito)|'
                   r'uso\s+(?:pessoal|particular|n[ãa]o[- ]comercial)|proibida\s+a\s+reprodu|vedad[ao]\s+a\s+reprodu|'
                   r'todos\s+os\s+direitos\s+reservados|permitida\s+a\s+reprodu[^.]{0,120}|desde\s+que\s+citada\s+a\s+fonte')
LAST = [0.0]


def pace():
    w = 3.2 - (time.time() - LAST[0])
    if w > 0:
        time.sleep(w)
    LAST[0] = time.time()


def robots_allows(txt, path='/'):
    """Rules for '*' (and any AI-agent group); True when path is allowed."""
    groups, cur = [], None
    for line in txt.splitlines():
        line = line.split('#')[0].strip()
        if ':' not in line:
            continue
        k, v = (x.strip() for x in line.split(':', 1))
        k = k.lower()
        if k == 'user-agent':
            if cur is None or cur[1]:
                cur = ([], [])
                groups.append(cur)
            cur[0].append(v.lower())
        elif cur is not None:
            cur[1].append((k, v))
    ai = [g for g in groups if any(re.search(r'claude|anthropic|gptbot', u) for u in g[0])]
    use = ai or [g for g in groups if '*' in g[0]]
    best = (0, True)
    for g in use:
        for k, v in g[1]:
            if k in ('allow', 'disallow') and v and path.startswith(v.rstrip('*')):
                if len(v) >= best[0]:
                    best = (len(v), k == 'allow')
    return best[1], [(g[0], g[1]) for g in ai]


def gate(sapl, folder, force_site=None):
    rec = {'sapl': sapl, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    H = Host(SCRIPTS / folder / '.cache' / 'sapl', sapl, delay=61)
    pace()
    b = H.get(f'https://{sapl}/')
    home = b.decode('utf-8', 'replace') if b else ''
    rec['sapl_home_bytes'] = len(home)
    m = re.search(r'<title>([^<]*)</title>', home)
    rec['sapl_title'] = m.group(1).strip() if m else None
    links = set()
    for h in re.findall(r'href="(https?://[^"]+)"', home):
        n = urlparse(h).netloc.lower()
        if n and n != sapl and not re.search(r'interlegis|github|google|facebook|twitter|instagram|youtube|gov\.br/lexml|'
                                             r'lexml|senado|camara\.leg\.br$|whatsapp|linkedin|w3\.org', n):
            links.add(n)
    rec['links'] = sorted(links)
    city = sapl.split('.', 1)[1]
    site = f'www.{city}' if f'www.{city}' in links or not links else None
    if not site:
        cand = [n for n in links if 'camara' in n or n.endswith('.leg.br')]
        site = cand[0] if cand else f'www.{city}'
    site = force_site or site
    rec['site'] = site
    S = Host(OUT / 'cache' / site, site, delay=3.2, timeout=30)
    try:
        pace()
        r = S.get(f'https://{site}/robots.txt')
        rtxt = r.decode('utf-8', 'replace') if r else ''
        if rtxt.lstrip().lower().startswith(('<!doctype', '<html')):
            rtxt = ''
        rec['site_robots'] = rtxt[:3000] if r is not None else '(404)'
        ok, ai = robots_allows(rtxt)
        rec['site_robots_allows_root'], rec['site_robots_ai'] = ok, ai
        cd = re.findall(r'(?im)^crawl-delay:\s*(\d+)', rtxt)
        if cd:
            S.delay = max(S.delay, float(cd[0]) + 1)
        if not ok:
            rec['verdict_terms'] = 'site robots disallows /: terms page not read'
            return rec
        pace()
        b = S.get(f'https://{site}/')
        sh = b.decode('utf-8', 'replace') if b else ''
        rec['site_home_bytes'] = len(sh)
        txt = re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<script.*?</script>|<style.*?</style>', ' ', sh))
        rec['site_flags'] = sorted(set(m.group(0) for m in FLAGS.finditer(txt)))[:10]
        pages = []
        for href, label in re.findall(r'(?is)<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', sh):
            lab = re.sub(r'<[^>]+>|\s+', ' ', label).strip()
            if TERMS.search(lab) or TERMS.search(href.replace('-', ' ')):
                u = urljoin(f'https://{site}/', href)
                if urlparse(u).netloc == site and u not in pages:
                    pages.append(u)
        rec['terms_pages'] = pages[:3]
        rec['terms_flags'] = {}
        for u in pages[:3]:
            if not robots_allows(rtxt, urlparse(u).path or '/')[0]:
                rec['terms_flags'][u] = 'robots disallows'
                continue
            pace()
            b = S.get(u)
            t = re.sub(r'<[^>]+>', ' ', re.sub(r'(?is)<script.*?</script>|<style.*?</style>', ' ',
                                                 b.decode('utf-8', 'replace') if b else ''))
            t = re.sub(r'\s+', ' ', t)
            rec['terms_flags'][u] = sorted(set(m.group(0) for m in FLAGS.finditer(t)))[:10]
            hits = [t[max(0, m.start() - 200):m.end() + 200] for m in re.finditer(r'(?i)reprodu|autoriza', t)][:4]
            rec.setdefault('terms_context', {})[u] = hits
    except Stop as e:
        rec['site_error'] = str(e)[:300]
    return rec


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for a in sys.argv[1:]:
        sapl, folder, *fs = a.split('=')
        try:
            rec = gate(sapl, folder, fs[0] if fs else None)
        except Stop as e:
            rec = {'sapl': sapl, 'sapl_error': str(e)[:300]}
        (OUT / f'{sapl}.json').write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding='utf-8')
        print(json.dumps({k: rec.get(k) for k in ('sapl', 'sapl_title', 'site', 'site_robots_allows_root',
                                                    'site_robots_ai', 'site_flags', 'terms_pages', 'terms_flags',
                                                    'site_error', 'sapl_error', 'verdict_terms')},
                         ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
