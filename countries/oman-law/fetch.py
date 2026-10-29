"""Fetch Oman sources into .cache/ (sha256 of the URL) with curl; resumable; logs .cache/requests.jsonl.

Sources: Qanoon.om (WordPress pages transcribing the Official Gazette: each royal decree as issued, and a consolidated
"(معدل)" page per law with footnotes naming the amending decree) and the Ministry of Justice and Legal Affairs
(mjla.gov.om) laws section, whose PDFs are the official current texts. At most 3 requests a second.
Usage: python -X utf8 fetch.py
"""
import hashlib, json, os, re, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache')
UA = 'lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)'
_last = [0.0]

QANOON = ['1996/rd1996101', '2011/rd2011099', '2021/rd2021006', '2021/l2021006', '2026/rd2026079',
          '2018/rd2018007', '2018/l2018007', '2022/rd2022068', '2025/rd2025011', '2026/rd2026066',
          '2022/rd2022006', '2022/l2022006', '2026/rd2026068']
MJLA_PAGES = ['https://mjla.gov.om/laws/1'] + ['https://mjla.gov.om/laws/1/page/%d' % i for i in range(1, 9)]


def qurl(p):
    return 'https://qanoon.om/p/%s/' % p


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())


def get(url, offline=False):
    p = path_for(url)
    if os.path.exists(p):
        return open(p, 'rb').read()
    if offline:
        raise FileNotFoundError(url)
    os.makedirs(CACHE, exist_ok=True)
    wait = _last[0] + 0.34 - time.time()
    if wait > 0:
        time.sleep(wait)
    _last[0] = time.time()
    code = ''
    for attempt in range(4):
        r = subprocess.run(['curl', '-sS', '--compressed', '-f', '-L', '-m', '120', '-A', UA, '-o', p + '.part',
                            '-w', '%{http_code}', url], capture_output=True, text=True)
        code = r.stdout.strip()
        if r.returncode == 0:
            break
        time.sleep(60 if code in ('429', '503') else 3)
    with open(os.path.join(CACHE, 'requests.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'url': url, 'status': code, 'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}) + '\n')
    if r.returncode != 0:
        raise RuntimeError('%s: %s %s' % (url, code, r.stderr.strip()))
    os.replace(p + '.part', p)
    return open(p, 'rb').read()


def mjla_laws(offline=False):
    """{title: show-page url} from the MJLA laws listing."""
    out = {}
    for u in MJLA_PAGES:
        try:
            s = get(u, offline).decode('utf-8')
        except Exception as e:
            print('warn', u, e)
            continue
        for href, title in re.findall(r'''<a\s+href=["'](laws/ar/1/show/\d+)/?["']>([^<]+)''', s):
            out[re.sub(r'\s+', ' ', title).strip()] = 'https://mjla.gov.om/' + href + '/'
    return out


def mjla_pdf(show_url, offline=False):
    s = get(show_url, offline).decode('utf-8')
    m = re.search(r'source="(https://www\.mjla\.gov\.om/images/laws/file/[^"]+\.pdf)"', s)
    return m.group(1) if m else None


WANT = {'basic': 'النظام الأساسي للدولة', 'penal': 'قانون الجزاء', 'pdpl': 'حماية البيانات الشخصية'}


def main():
    for p in QANOON:
        get(qurl(p))
    laws = mjla_laws()
    print(len(laws), 'MJLA laws listed')
    for k, needle in WANT.items():
        hits = [(t, u) for t, u in laws.items() if needle in re.sub('ـ', '', t)]
        for t, u in hits:
            pdf = mjla_pdf(u)
            print(k, t, u, pdf)
            if pdf:
                get(pdf)


if __name__ == '__main__':
    main()
