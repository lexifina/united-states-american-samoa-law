"""gitlaw-scraper-dell (2026-10-31): catalogue + English statute PDFs of the Sri Lanka Provincial Councils that publish
them (Uva, Northern, Central). Private. One request at a time per host via pkmy_fetch (>= 3.2 s).

    python -X utf8 lk_prov_fetch.py uva|northern|central
Writes scripts/sri-lanka-<p>-law/.cache/catalogue.json.
"""
import html, json, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pkmy_fetch as F

def clean(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()

def uva():
    url = 'https://www.up.gov.lk/publications/statutes/'
    b = F.get(url).decode('utf-8', 'replace')
    out = []
    for r in re.findall(r'<tr.*?</tr>', b, re.S):
        cells = [clean(c) for c in re.findall(r'<td.*?</td>', r, re.S)]
        en = re.findall(r'href="([^"]+)"[^>]*>\s*En', r)
        if len(cells) >= 4 and en:
            out.append({'number': cells[0], 'title': cells[1], 'gazette': cells[2], 'date': cells[3],
                        'url': en[0].replace('http://', 'https://'), 'listing': url})
    return out

NP_PAGES = ['https://np.gov.lk/statutes-ministry-of-education-cultural-affairs-spots-and-youth-affairs/',
            'https://np.gov.lk/statutes-ministry-of-finance-planning-law-order-lands-electricity-housing-construction-tourism-local-government-provincial-administration-rural-development-road-development-m/',
            'https://np.gov.lk/statutes-ministry-of-health-indigenous-medicine-and-probation-childcare-services/',
            'https://np.gov.lk/statutes-provincial-revenue-department/']

def northern():
    out = []
    for page in NP_PAGES:
        b = F.get(page).decode('utf-8', 'replace')
        body = b[b.find('entry-content'):]
        for m in re.finditer(r'<a href="([^"]+?(?:_E|English|-English)[^"]*?\.pdf)"[^>]*>(.*?)</a>(.{0,400})', body, re.S | re.I):
            u, t, after = m.group(1), clean(m.group(2)), clean(m.group(3))
            g = re.search(r'Gazette\s*No\.?\s*([\d/]+)\s*[–-]?\s*([^)]*)\)', after, re.I)
            out.append({'title': t, 'gazette': g.group(1) if g else None, 'date': g.group(2).strip() if g else None,
                        'url': u.replace(' ', '%20'), 'listing': page})
    return out

def central():
    api = 'https://www.cp.gov.lk/api/statutes.php'
    d = json.loads(F.get(api))['data']
    return [{'number': x['number'], 'title': x['name'].strip(), 'enacted': x.get('inacted'), 'published': x.get('published'),
             'url': f'https://www.cp.gov.lk/web/statutes/files/statute-{x["number"]}-en.pdf',
             'listing': f'https://www.cp.gov.lk/web/statutes/view?id={x["id"]}&la=en'} for x in d if x.get('file-en')]

if __name__ == '__main__':
    p = sys.argv[1]
    cat = {'uva': uva, 'northern': northern, 'central': central}[p]()
    folder = HERE.parent / f'sri-lanka-{p}-law' / '.cache'
    folder.mkdir(parents=True, exist_ok=True)
    seen = set()
    for it in cat:
        if it['url'] in seen:
            it['pdf'] = str(F.path_for(it['url'])); continue
        seen.add(it['url'])
        try:
            b = F.get(it['url'], timeout=180)
        except F.Stopped as e:
            print('STOPPED', e); break
        it['ok'] = bool(b and b.startswith(b'%PDF'))
        it['pdf'] = str(F.path_for(it['url']))
        print(p, it['ok'], it['url'][-60:], flush=True)
    (folder / 'catalogue.json').write_text(json.dumps(cat, indent=1, ensure_ascii=False), encoding='utf-8')
    print(p, len(cat), 'entries,', len(seen), 'files')
