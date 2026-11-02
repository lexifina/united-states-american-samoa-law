"""Private (never published). One build pass over the SAPL wave cities (gitlaw-scraper-dell, 2026-11-01): no network
except the one repo-creation API call (br_sapl_open.sh) per city.

    python -X utf8 scripts/world-law/br_sapl_cycle.py [--loop SECONDS]

Per city (world-law/.br-cities/sapl-wave-data.txt), one at a time:
1. Lei Orgânica: when sapl-spec.json names a Texto Articulado (ta) and every vigência view is cached, write parse.py
   (br_sapl_ta_make.py) once.
2. br_sapl_verify.sh (at most 4 new parts per run: parse, letters check with a second reader, build, check.py, audit;
   writes <part>.PUBLISH).
3. When a part has .PUBLISH: br_sapl_open.sh once (repo + docs + PROGRESS.md), afterwards docs again when the
   published parts change.
Stop: world-law/.br-cities/STOP-cycle.
"""
import hashlib, json, re, subprocess, sys, time
from pathlib import Path

W = Path(__file__).resolve().parent
S = W.parent
STOPF = W / '.br-cities' / 'STOP-cycle'
LOG = W / '.br-cities' / 'cycle.log'
BASH = r'C:\Program Files\Git\bin\bash.exe'  # not WSL's bash.exe


def log(*a):
    line = time.strftime('%Y-%m-%dT%H:%M:%SZ ', time.gmtime()) + ' '.join(str(x) for x in a)
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def views_ready(F, s):
    pr = F / '.cache' / 'sapl' / 'probe.json'
    if not pr.exists():
        return False
    d = json.loads(pr.read_text(encoding='utf-8'))
    rec = [r for r in d['lom'] if r['id'] == s['norma']]
    if not rec:
        return False
    raw = F / '.cache' / 'sapl' / 'raw'
    urls = [f"https://{s['host']}{v}" for v in rec[0]['vigencias']] + [f"https://{s['host']}/norma/{s['norma']}"]
    return all((raw / hashlib.sha256(u.encode()).hexdigest()).exists() for u in urls)


def run(cmd, timeout=3600):
    r = subprocess.run(cmd, cwd=S, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout)
    return r.returncode, (r.stdout or '') + (r.stderr or '')


MONTHS = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro',
          'novembro', 'dezembro']


def fill_ta(F, s):
    """Wave 2: when the probe found exactly one Lei Orgânica record whose vigência views all belong to one Texto
    Articulado and the first view starts on the record's own date (the text as promulgated), record it in
    sapl-spec.json so br_sapl_ta_make.py can run. A history that starts later is not used (it would credit the
    amended text to the Lei Orgânica itself)."""
    pr = F / '.cache' / 'sapl' / 'probe.json'
    if s.get('ta') or s.get('lom_pdf') or s.get('no_ta') or not pr.exists():
        return s
    d = json.loads(pr.read_text(encoding='utf-8'))
    recs = [r for r in d.get('lom', []) if r.get('vigencias')]
    if len(recs) != 1:
        return s
    r = recs[0]
    tas = {re.match(r'/ta/(\d+)/', v).group(1) for v in r['vigencias']}
    first = min(v.split(',')[1] for v in r['vigencias'])
    if len(tas) != 1 or first != r['data']:
        s['no_ta'] = f'TA views: {len(tas)} texts, first view from {first}, record date {r["data"]}'
    else:
        y, m, dd = r['data'].split('-')
        s.update({'norma': r['id'], 'ta': int(tas.pop()), 'lom_date': r['data'], 'lom_year': int(y),
                  'lom_label': f"Lei Orgânica do Município de {s['city']}, de {int(dd)} de {MONTHS[int(m) - 1]} de {y}",
                  'lom_title': f"Lei Orgânica do Município de {s['city']}"})
    (F / 'sapl-spec.json').write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    log(F.name, 'fill_ta', s.get('ta') or s.get('no_ta'))
    return s


def one(folder):
    F = S / folder
    s = json.loads((F / 'sapl-spec.json').read_text(encoding='utf-8'))
    s = fill_ta(F, s)
    if s.get('ta') and not (F / 'parse.py').exists() and views_ready(F, s):
        rc, out = run([sys.executable, '-X', 'utf8', str(W / 'br_sapl_ta_make.py'), str(F / 'sapl-spec.json')])
        log(folder, 'ta_make', rc, out.strip()[-200:])
    before = sorted(p.name for p in (F / 'corpus.d').glob('*.PUBLISH')) if (F / 'corpus.d').exists() else []
    rc, out = run([BASH, str(W / 'br_sapl_verify.sh'), str(F), time.strftime('%Y-%m-%d', time.gmtime())])
    tail = [l for l in out.splitlines() if any(k in l for k in ('PUBLISHED', 'FAIL', 'nothing new', 'versions checked',
                                                                'acts', 'Traceback', 'Error', "{'"))]
    log(folder, 'verify', rc, ' | '.join(tail)[-600:])
    after = sorted(p.name for p in (F / 'corpus.d').glob('*.PUBLISH')) if (F / 'corpus.d').exists() else []
    if after and (after != before or not (F / 'PROGRESS.md').exists()):
        rc, out = run([BASH, str(W / 'br_sapl_open.sh'), folder], timeout=600)
        log(folder, 'open/docs', rc, out.strip().splitlines()[-1][:300] if out.strip() else '')


def main():
    loop = int(sys.argv[2]) if sys.argv[1:2] == ['--loop'] else 0
    while True:
        for line in (W / '.br-cities' / 'sapl-wave-data.txt').read_text(encoding='utf-8').splitlines():
            if STOPF.exists():
                log('STOP-cycle found: exiting')
                return
            if line.strip():
                try:
                    one(line.split()[1])
                except Exception as e:
                    log(line.split()[1], 'ERROR', type(e).__name__, str(e)[:300])
        if not loop:
            return
        time.sleep(loop)


if __name__ == '__main__':
    main()
