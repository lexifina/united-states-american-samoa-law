"""Cyprus fetch: CyLaw consolidated pages and numbered-law PDFs, read ONLY through Internet Archive captures.

CyLaw's terms (cylaw.org/terms.html) allow free copying with CyLaw named as the source, but bulk or automated
downloading needs its prior written consent. So this script never requests cylaw.org: every page comes from
web.archive.org (`id_` raw captures) through the shared machine-wide client scripts/gitlaw_common/wayback.py,
cached under .cache/ by the sha256 of the URL and logged to .cache/requests.jsonl.

    python -X utf8 scripts/cyprus-law/fetch.py [act ...]      # acts: 2018_1_125 syntagma 0_154 (default: all)

What it gets, per act:
1. the CDX capture lists of /nomoi/enop/non-ind/<act>/ and /nomoi/enop/ind/<act>/ (one request each);
2. every archived copy of the consolidated full text (full.html), one per distinct content digest;
3. every per-section old-wording page (`section-<sc>-ln<ln>.html`) that any full.html copy links to and the
   archive holds (its newest capture);
4. the Official Gazette extract PDF (/nomoi/arith/<yyyy>_1_<nnn>.pdf) of every instrument in the amendment list,
   for its Gazette issue number and publication date (text layer only, no OCR).
Plus the Interpretation Law, Cap. 1 (non-ind/0_1/full.html), for the default commencement rule.
The pins (capture timestamps) are written to sources.json, which parse.py reads.
"""
from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = HERE / '.cache'
ACTS = ['2018_1_125', 'syntagma', '0_154']
HOST = re.compile(r'^https?://(www\.)?cylaw\.org(:80)?')


def path_of(original: str) -> str:
    return HOST.sub('', original).split('?')[0]


def caps(prefix: str) -> list[dict]:
    return wayback.captures(f'cylaw.org{prefix}', match='prefix', cache=CACHE, collapse=None)


def full_copies(act: str) -> list[dict]:
    """One capture per distinct digest of /nomoi/enop/non-ind/<act>/full.html, oldest first."""
    seen, out = set(), []
    for c in sorted(caps(f'/nomoi/enop/non-ind/{act}/'), key=lambda c: c['timestamp']):
        if path_of(c['original']) == f'/nomoi/enop/non-ind/{act}/full.html' and c['digest'] not in seen:
            seen.add(c['digest'])
            out.append(c)
    return out


def sidebar(html: str) -> list[str]:
    sb = html[html.find('sidebar-history-header'):html.find('main-content')]
    return [x.strip() for x in re.findall(
        r'<li[^>]*>\s*(?:<span class="toc-instrument-enum">)?([^<]+?)\s*(?:</span>)?\s*</li>', sb)]


def pdf_name(label: str) -> str | None:
    """'26(I)/2022' -> '2022_1_026.pdf'; '3/1962' -> '1962_1_003.pdf'; base acts and notices -> None."""
    m = re.fullmatch(r'(\d+)(?:\([IΙ]+\))?/(\d{4})', label.replace('Ι', 'I'))
    return f'{m.group(2)}_1_{int(m.group(1)):03d}.pdf' if m else None


# ---------------------------------------------------------------- the Official Gazette (Government Printing Office)
# For laws whose CyLaw Gazette extract is not archived or carries no Gazette header, the issue itself is read from
# the Printing Office's own archive (www.mof.gov.cy/mof/gpo/gazette.nsf, issues from 2004): an official source,
# requested directly, at most one request a second, cached and logged like everything else.

GPO = 'https://www.mof.gov.cy/mof/gpo/gazette.nsf'
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = [0.0]


def direct(url: str) -> bytes | None:
    import hashlib
    import subprocess
    import tempfile
    import time
    p = CACHE / hashlib.sha256(url.encode('utf-8')).hexdigest()
    if p.exists():
        return p.read_bytes()
    wait = 1.0 - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    with tempfile.NamedTemporaryFile(delete=False) as f:
        tmp = f.name
    out = subprocess.run(['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', '180', '-o', tmp,
                          '-w', '%{http_code}', url], capture_output=True, text=True)
    code = int(out.stdout.strip() or 0) if out.returncode == 0 else 0
    body = Path(tmp).read_bytes() if code == 200 else b''
    Path(tmp).unlink(missing_ok=True)
    with open(CACHE / 'requests.jsonl', 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'bytes': len(body),
                            'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'via': 'fetch.py direct'}) + '\n')
    if code != 200:
        return None
    p.write_bytes(body)
    return body


def gpo_year_index(year: int) -> int:
    """The archive view numbers years newest first: 2026 is 1, 2025 is 2, ..."""
    return 2026 - year + 1


def gpo_issues(year: int, month: int) -> list[dict]:
    """The First Annex Part I issues (laws) of one month: [{'id','date','issue','title','page'}]."""
    import html as h
    url = (f'{GPO}/dmlgazette_archive_gr/dmlgazette_archive_gr?OpenForm&Start=1&Count=9999'
           f'&Expand={gpo_year_index(year)}.{month}.2&Seq=1')
    raw = direct(url)
    if not raw:
        return []
    t = raw.decode('utf-8', 'replace')
    out = []
    for href, label in re.findall(r'<a[^>]+href="(/mof/gpo/gazette.nsf/All/[0-9A-F]{32}\?OpenDocument)"[^>]*>(.*?)</a>',
                                  t, re.S):
        lab = re.sub(r'\s+', ' ', h.unescape(re.sub(r'<[^>]+>', '', label))).strip()
        m = re.search(r'(\d{2})/(\d{2})/(\d{4}) - ΠΑΡΑΡΤΗΜΑ ΠΡΩΤΟ - ΜΕΡΟΣ \(Ι\) - Αρ\. (\w+)', lab)
        if m:
            out.append({'page': 'https://www.mof.gov.cy' + href, 'title': lab, 'issue': m.group(4),
                        'date': f'{m.group(3)}-{m.group(2)}-{m.group(1)}'})
    return out


def gpo_pdf(issue: dict) -> tuple[str, bytes] | None:
    raw = direct(issue['page'])
    if not raw:
        return None
    m = re.search(r'href="\.\./([0-9A-F]{32}/\$file/[^"]+\.pdf)"', raw.decode('utf-8', 'replace'))
    if not m:
        return None
    url = f'{GPO}/' + m.group(1).replace(' ', '%20')
    body = direct(url)
    return (url, body) if body else None


def pdf_text(raw: bytes, pages: int | None = None) -> str:
    import fitz  # the PDF's own text layer; no OCR
    doc = fitz.open(stream=raw, filetype='pdf')
    return '\n'.join(doc[i].get_text() for i in range(doc.page_count if pages is None else min(pages, doc.page_count)))


def heading_re(n: int, year: int) -> re.Pattern:
    return re.compile(rf'Αριθμός\s+{n}\s*\(\s*[ΙI1]\s*\)\s+του\s+{year}')


def first_law(raw: bytes) -> int | None:
    m = re.search(r'Αριθμός\s+(\d+)\s*\(\s*[ΙI1]\s*\)\s+του\s+\d{4}', pdf_text(raw, 3))
    return int(m.group(1)) if m else None


def gpo_find(n: int, year: int) -> dict | None:
    """The First Annex Part I issue that publishes law n(I)/year, found by binary search on each issue's first law."""
    issues = []
    for month in range(1, 13):
        issues += gpo_issues(year, month)
    issues.sort(key=lambda i: (i['date'], i['issue']))
    lo, hi = 0, len(issues) - 1
    firsts = {}

    def first(i):
        if i not in firsts:
            got = gpo_pdf(issues[i])
            firsts[i] = (first_law(got[1]) if got else None, got)
        return firsts[i]

    while lo < hi:  # the last issue whose first law is <= n
        mid = (lo + hi + 1) // 2
        f, _ = first(mid)
        if f is None:  # an issue without a numbered law: look at its neighbour instead
            issues.pop(mid)
            firsts.clear()
            hi -= 1
            continue
        if f <= n:
            lo = mid
        else:
            hi = mid - 1
    for i in (lo, lo - 1, lo + 1):
        if 0 <= i < len(issues):
            f, got = first(i)
            if got and heading_re(n, year).search(pdf_text(got[1])):
                return {'page': issues[i]['page'], 'pdf': got[0], 'issue': issues[i]['issue'],
                        'date': issues[i]['date'], 'title': issues[i]['title']}
    return None


# Laws whose CyLaw extract gives no Gazette date (retyped text, or not archived), looked up in the Gazette itself
# (the Printing Office's archive starts in 2004).
GPO_LOOKUP = {
    'syntagma': ['127(I)/2006', '51(I)/2010', '186(I)/2025'],
    '0_154': ['124(I)/2004', '31(I)/2005', '18(I)/2006', '130(I)/2006', '126(I)/2007', '127(I)/2007', '70(I)/2008',
              '83(I)/2008', '64(I)/2009', '56(I)/2011', '72(I)/2011', '163(I)/2011', '167(I)/2011', '84(I)/2012',
              '43(I)/2016', '212(I)/2025'],
}


def gpo_main(acts: list[str]) -> None:
    pins = json.loads((HERE / 'sources.json').read_text(encoding='utf-8'))
    for act in acts:
        found = pins.setdefault(act, {}).setdefault('gpo', {})
        for lab in GPO_LOOKUP.get(act, []):
            if lab in found:
                continue
            m = re.fullmatch(r'(\d+)\(I\)/(\d{4})', lab)
            hit = gpo_find(int(m.group(1)), int(m.group(2)))
            print(act, lab, hit and (hit['issue'], hit['date']), flush=True)
            if hit:
                found[lab] = hit
                tmp = HERE / 'sources.json.tmp'
                tmp.write_text(json.dumps(pins, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
                tmp.replace(HERE / 'sources.json')


def main(acts: list[str]) -> None:
    pins = json.loads((HERE / 'sources.json').read_text(encoding='utf-8')) if (HERE / 'sources.json').exists() else {}
    arith = {path_of(c['original']): c for c in wayback.captures('cylaw.org/nomoi/arith/', match='prefix', cache=CACHE,
                                                                 collapse='urlkey')}
    for act in acts:
        full = full_copies(act)
        ind = {}
        for c in caps(f'/nomoi/enop/ind/{act}/'):
            ind.setdefault(path_of(c['original']), []).append(c)
        print(act, 'full.html copies', len(full), flush=True)
        with ThreadPoolExecutor(6) as ex:
            bodies = list(ex.map(lambda c: wayback.get(c['original'], ts=c['timestamp'], cache=CACHE), full))
        links, labels = set(), []
        for c, b in zip(full, bodies):
            if not b:
                print('  missing full', c['timestamp'])
                continue
            h = b.decode('cp1253', 'replace')
            # Old wordings are linked as section-<sc>-ln<id>.html or section-<sc>-ai<id>.html.
            links |= set(re.findall(r'href="(/nomoi/enop/ind/[^"]+/section-sc[0-9a-f-]{36}-[^"]+\.html)"', h))
            for lab in sidebar(h):
                if lab not in labels:
                    labels.append(lab)
        old = {}
        for link in sorted(links):
            got = sorted(ind.get(link, []), key=lambda c: c['timestamp'])
            if got:
                old[link] = got[-1]
        print(f'  -ln pages linked {len(links)}, archived {len(old)}', flush=True)
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(lambda c: wayback.get(c['original'], ts=c['timestamp'], cache=CACHE), old.values()))
        gaz = {}
        for lab in labels:
            name = pdf_name(lab)
            if not name:
                continue
            # Older laws are also filed as <yyyy>_<nnn>.pdf.
            for alt in (name, name.replace('_1_', '_', 1)):
                c = arith.get(f'/nomoi/arith/{alt}')
                if c:
                    gaz[lab] = c
                    break
        print(f'  instruments {len(labels)}, gazette PDFs archived {len(gaz)}', flush=True)
        with ThreadPoolExecutor(6) as ex:
            list(ex.map(lambda c: wayback.get(c['original'], ts=c['timestamp'], cache=CACHE), gaz.values()))
        pins[act] = {
            'full': [{'ts': c['timestamp'], 'url': c['original'], 'digest': c['digest']} for c in full],
            'old': {k: {'ts': c['timestamp'], 'url': c['original']} for k, c in sorted(old.items())},
            'missing_old': sorted(links - set(old)),
            'gazette': {k: {'ts': c['timestamp'], 'url': c['original']} for k, c in gaz.items()},
            'instruments': labels,
            'gpo': pins.get(act, {}).get('gpo', {}),
        }
    cap1 = sorted((c for c in caps('/nomoi/enop/non-ind/0_1/')
                   if path_of(c['original']) == '/nomoi/enop/non-ind/0_1/full.html'), key=lambda c: c['timestamp'])
    if cap1:
        c = cap1[-1]
        wayback.get(c['original'], ts=c['timestamp'], cache=CACHE)
        pins['cap1'] = {'ts': c['timestamp'], 'url': c['original']}
    tmp = HERE / 'sources.json.tmp'
    tmp.write_text(json.dumps(pins, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(HERE / 'sources.json')


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--gpo' in sys.argv:
        gpo_main(args or ACTS)
    else:
        main(args or ACTS)
