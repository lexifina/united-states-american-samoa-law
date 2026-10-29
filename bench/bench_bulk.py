"""Benchmark 2: live official HTML via host_get vs official bulk/open-data APIs vs hosted reconstructed archives.

Measures, per approach: wall time, requests, bytes, and versions (or acts) obtained per request.
Small samples; host_get keeps its shared per-host adaptive rate. Writes bench_bulk.json.
"""
import json, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'gitlaw_common'))
import wayback as w
sys.stdout.reconfigure(encoding='utf-8')
out = {'at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'runs': []}
UA = w.UA

def curl(url, accept=None, path=None, timeout=300):
    args = ['curl', '-gsS', '-L', '--compressed', '-A', UA, '--max-time', str(timeout), '-w', '%{http_code} %{size_download}']
    if accept: args += ['-H', f'Accept: {accept}']
    args += ['-o', path or 'NUL' if sys.platform == 'win32' and not path else (path or '/dev/null'), url]
    t = time.time(); r = subprocess.run(args, capture_output=True, text=True)
    code, size = (r.stdout.split() + ['0', '0'])[:2]
    return int(code or 0), int(float(size or 0)), time.time() - t

def rec(**k):
    out['runs'].append(k); print(json.dumps(k, ensure_ascii=False), flush=True)

tmp = Path(tempfile.mkdtemp(prefix='bench-bulk-'))
# 1. BOE open-data API: whole consolidated history of an act per request
code, size, dt = curl('https://www.boe.es/datosabiertos/api/legislacion-consolidada?limit=40', 'application/json', str(tmp / 'list.json'))
ids = [d['identificador'] for d in json.loads((tmp / 'list.json').read_text(encoding='utf-8'))['data']][:24]
def boe_api(i):
    p = tmp / f'{i}.xml'; c, s, d = curl(f'https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/{i}/texto', 'application/xml', str(p))
    return (c, s, len(re.findall(rb'<version ', p.read_bytes())) if c == 200 else 0)
for th in (1, 6):
    t = time.time()
    with ThreadPoolExecutor(th) as ex: res = list(ex.map(boe_api, ids[:12] if th == 1 else ids))
    dt = time.time() - t; ok = [r for r in res if r[0] == 200]
    rec(approach='official open-data API (Spain BOE, whole history per act)', threads=th, requests=len(res), ok=len(ok),
        seconds=round(dt, 2), versions=sum(r[2] for r in ok), versions_per_request=round(sum(r[2] for r in ok) / max(1, len(ok)), 1),
        versions_per_s=round(sum(r[2] for r in ok) / dt, 1), MB=round(sum(r[1] for r in ok) / 1e6, 2))
# 2. live HTML on the same host via host_get (one page = one current version)
pages = [f'https://www.boe.es/buscar/act.php?id={i}' for i in ids]
for th, n in ((1, 8), (4, 16), (12, 24)):
    d = Path(tempfile.mkdtemp(prefix='bench-host-'))
    t = time.time()
    with ThreadPoolExecutor(th) as ex: res = list(ex.map(lambda u: w.host_get(u, d), pages[:n]))
    dt = time.time() - t; ok = [r for r in res if r]
    rec(approach='live official HTML via host_get (BOE act pages)', threads=th, requests=n, ok=len(ok), seconds=round(dt, 2),
        pages_per_s=round(len(ok) / dt, 2), versions_per_request=1.0, MB=round(sum(map(len, ok)) / 1e6, 2))
# 3. Lovdata bulk dataset (Norway): every current law in one request
c, s, dt = curl('https://api.lovdata.no/v1/publicData/get/gjeldende-lover.tar.bz2', None, str(tmp / 'lov.tar.bz2'), 600)
n_files = 0
if c == 200:
    lst = subprocess.run(['tar', '-tjf', str(tmp / 'lov.tar.bz2')], capture_output=True, text=True).stdout.split()
    n_files = len([x for x in lst if not x.endswith('/')])
rec(approach='official bulk dump (Norway Lovdata, all current laws)', requests=1, http=c, seconds=round(dt, 2), MB=round(s / 1e6, 1),
    acts_in_one_request=n_files)
# 4. Estonia Riigi Teataja: one act's version list (each redaction is a separate XML)
c, s, dt = curl('https://www.riigiteataja.ee/akt/redaktsioonid/127042011002', None, str(tmp / 'rt.html'))
nred = len(re.findall(rb'/akt/\d{9,}', (tmp / 'rt.html').read_bytes())) if c == 200 else 0
rec(approach='official version list (Estonia Riigi Teataja, Constitution redactions page)', requests=1, http=c, seconds=round(dt, 2),
    version_links=nred)
# 5. Austria RIS OGD API: consolidated federal law search (JSON)
c, s, dt = curl('https://data.bka.gv.at/ris/api/v2.6/Bundesrecht?Applikation=BrKons&Titel=Bundes-Verfassungsgesetz&DokumenteProSeite=OneHundred',
                'application/json', str(tmp / 'ris.json'))
docs = 0
if c == 200:
    try: docs = len(json.loads((tmp / 'ris.json').read_text(encoding='utf-8'))['OgdSearchResult']['OgdDocumentResults']['OgdDocumentReference'])
    except Exception: pass
rec(approach='official open-data API (Austria RIS OGD, B-VG provisions)', requests=1, http=c, seconds=round(dt, 2), documents=docs, MB=round(s / 1e6, 2))
# 6. legalize.dev hosted reconstruction: one clone = a country's whole history
for repo in ('legalize-lt', 'legalize-lv'):
    dst = tmp / repo; t = time.time()
    r = subprocess.run(['git', 'clone', '-q', '--filter=blob:none', '--no-checkout', f'https://github.com/legalize-dev/{repo}.git', str(dst)], capture_output=True, text=True)
    dt_clone = time.time() - t
    commits = subprocess.run(['git', '-C', str(dst), 'rev-list', '--count', 'HEAD'], capture_output=True, text=True).stdout.strip() if r.returncode == 0 else '0'
    files = subprocess.run(['git', '-C', str(dst), 'ls-tree', '-r', '--name-only', 'HEAD'], capture_output=True, text=True).stdout.split() if r.returncode == 0 else []
    first = subprocess.run(['git', '-C', str(dst), 'log', '--reverse', '--format=%ad %s', '--date=short', '-3'], capture_output=True, text=True).stdout.strip().splitlines()[:3] if r.returncode == 0 else []
    t = time.time()
    full = subprocess.run(['git', 'clone', '-q', f'https://github.com/legalize-dev/{repo}.git', str(tmp / (repo + '-full'))], capture_output=True, text=True) if r.returncode == 0 else None
    rec(approach=f'hosted reconstructed archive ({repo})', ok=r.returncode == 0, clone_metadata_s=round(dt_clone, 1),
        full_clone_s=round(time.time() - t, 1) if full else None, commits=int(commits or 0), law_files=len(files),
        first_commits=first, err=r.stderr[-200:] if r.returncode else '')
(HERE / 'bench_bulk.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
print('saved', tmp)
