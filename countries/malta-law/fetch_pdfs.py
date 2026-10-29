"""Download the PDF of every English consolidated version listed in .cache/laws/*.json.

Each version's PDF is at https://legislation.mt/getpdf/<snapshot id>. Saved to .cache/pdf/<snapshot>.pdf with its
sha256 in .cache/pdf-sha256.tsv; resumes, and rescans the catalogue so it can run while the catalogue is fetched.

    python scripts/malta-law/fetch_pdfs.py [--workers 12]
"""
import argparse
import hashlib
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from fetch_catalogue import BASE, CACHE, LAWS, curl

PDF = CACHE / 'pdf'
LOCK = threading.Lock()


def wanted() -> list[str]:
    snaps = []
    for f in sorted(LAWS.glob('*.json')):
        d = json.loads(f.read_text('utf-8'))
        for v in d['versions']:
            if v.get('snapshot') and (v.get('uri') or '').endswith('/eng'):
                snaps.append(v['snapshot'])
    return sorted(set(snaps))


def fetch(snap: str) -> int:
    body = curl(f'{BASE}/getpdf/{snap}', timeout=300)
    if not body.startswith(b'%PDF'):
        raise RuntimeError(f'not a PDF ({body[:60]!r})')
    tmp = PDF / f'{snap}.part'
    tmp.write_bytes(body)
    tmp.replace(PDF / f'{snap}.pdf')
    with LOCK, open(CACHE / 'pdf-sha256.tsv', 'a', encoding='utf-8') as fh:
        fh.write(f'{snap}\t{hashlib.sha256(body).hexdigest()}\t{len(body)}\n')
    return len(body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=12)
    args = ap.parse_args()
    PDF.mkdir(parents=True, exist_ok=True)
    todo = [s for s in wanted() if not (PDF / f'{s}.pdf').exists()]
    print(f'{len(todo)} PDFs to fetch', flush=True)
    done = failed = 0
    total = 0
    with ThreadPoolExecutor(args.workers) as pool:
        futs = {pool.submit(fetch, s): s for s in todo}
        for fut in as_completed(futs):
            try:
                total += fut.result()
                done += 1
            except Exception as e:  # noqa: BLE001
                failed += 1
                print(f'FAIL {futs[fut]}: {e}', file=sys.stderr, flush=True)
            if (done + failed) % 200 == 0:
                print(f'{done} done ({total / 1e9:.2f} GB), {failed} failed of {len(todo)}', flush=True)
    print(f'finished: {done} done ({total / 1e9:.2f} GB), {failed} failed', flush=True)


if __name__ == '__main__':
    main()
