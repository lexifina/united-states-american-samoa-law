"""README, REPRODUCE.md, LICENSE, laws.csv and tools for the Malta law repository (called by build.py)."""
import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
REPO_FILES = HERE / 'repo'


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(laws: list[dict], commits: list[dict], issues: list[dict], related: dict, today: str) -> dict[str, bytes]:
    kinds = Counter(c['kind'] for c in commits)
    caps = sum(1 for l in laws if l['kind'] == 'cap')
    sls = len(laws) - caps
    versions = sum(len(l['eng']) for l in laws)
    first = min(c['date'] for c in commits) if commits else ''
    last = max(c['date'] for c in commits) if commits else ''
    authors = {c['author'] for c in commits if c['kind'] == 'amendment'}
    ev = Counter(e for c in commits if c['kind'] == 'amendment' for p in c['parts'] for e in p['evidence'].values())

    out = io.StringIO()
    w = csv.writer(out, lineterminator='\n')
    w.writerow(['law', 'kind', 'id', 'title', 'legal_force', 'repealed_by', 'versions', 'first_version', 'last_version', 'path'])
    for l in laws:
        lab = f"Cap. {l['id']}" if l['kind'] == 'cap' else f"S.L. {l['id']}"
        w.writerow([lab, l['kind'], l['id'], l['title'] or '', l.get('legal_force') or '', l.get('repealed_by') or '', len(l['eng']),
                    l['eng'][0]['date'], l['eng'][-1]['date'], f"{l['kind']}/{l['id']}/"])
    laws_csv = out.getvalue()

    iss = io.StringIO()
    w = csv.writer(iss, lineterminator='\n')
    w.writerow(['law', 'version', 'snapshot', 'issue'])
    for i in issues:
        w.writerow([i['law'], i['version'], i.get('snapshot', ''), i['issue']])

    stats = {
        'today': today, 'laws': len(laws), 'chapters': caps, 'subsidiary': sls, 'versions': versions,
        'commits': len(commits) + 1, 'consolidated': kinds['consolidated'], 'amendment': kinds['amendment'],
        'unexplained': kinds['unexplained'], 'amending_laws': len(authors), 'first': first, 'last': last,
        'unreadable': len(issues), 'evidence': dict(ev),
        'evidence_margin': ev['margin note'], 'evidence_law': ev['law'], 'evidence_date': ev['date'],
        'evidence_none': ev['none'],
    }
    readme = (REPO_FILES / 'README.md').read_text('utf-8')
    reproduce = (REPO_FILES / 'REPRODUCE.md').read_text('utf-8')
    for k, v in stats.items():
        readme = readme.replace('{{' + k.upper() + '}}', str(v))
        reproduce = reproduce.replace('{{' + k.upper() + '}}', str(v))
    for name in ('build.py', 'parse_pdf.py', 'fetch_catalogue.py', 'fetch_pdfs.py', 'docs.py'):
        reproduce = reproduce.replace('{{SHA_' + name.upper().replace('.', '_') + '}}', _sha(HERE / name))
    sums = ''.join(sorted(f"{l}\n" for l in (CACHE_SUMS.read_text('utf-8').splitlines() if CACHE_SUMS.exists() else [])))

    files = {
        'README.md': readme.encode('utf-8'),
        'REPRODUCE.md': reproduce.encode('utf-8'),
        'LICENSE': (REPO_FILES / 'LICENSE').read_bytes(),
        'laws.csv': laws_csv.encode('utf-8'),
        'data/unreadable.csv': iss.getvalue().encode('utf-8'),
        'data/stats.json': (json.dumps(stats, indent=1, sort_keys=True) + '\n').encode('utf-8'),
        'data/pdf-sha256.tsv': sums.encode('utf-8'),
        'tools/in_force_on.py': (REPO_FILES / 'tools' / 'in_force_on.py').read_bytes(),
    }
    for name in ('build.py', 'parse_pdf.py', 'fetch_catalogue.py', 'fetch_pdfs.py', 'docs.py'):
        files[f'tools/build/{name}'] = (HERE / name).read_bytes()
    for name in ('README.md', 'REPRODUCE.md', 'LICENSE'):
        files[f'tools/build/repo/{name}'] = (REPO_FILES / name).read_bytes()
    return files


CACHE_SUMS = HERE / '.cache' / 'pdf-sha256.tsv'
