"""Writes the data for the South American reader at lexifina.com/watch/south-america.

    python -X utf8 scripts/south-america-law/site_data.py [--site saas-webpage] [--only chile peru]

For each country with scripts/<slug>-law/PUBLISH, it loads the corpus exactly as main builds it (verified parts only,
GITLAW_VERIFIED_PARTS_ONLY=1, through gitlaw_common/build.load), with the same --docs-date autopush uses, and calls
gitlaw_common/build.site_data. It writes:

    app/watch/south-america/_data/<slug>.json          the country: laws, sources, each act's versions (no texts)
    app/watch/south-america/_data/<slug>/<act>.json    one act's provisions, every version of each

Acts are split out so no file is large (Chile's whole record is about 13 MB) and the page fetches only the act read.
A country without PUBLISH has its files removed, so the site never shows what main does not hold.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

os.environ['GITLAW_VERIFIED_PARTS_ONLY'] = '1'  # before build is imported: main holds verified parts only
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'gitlaw_common'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402
from autopush import SOUTH_AMERICA as COUNTRIES, docs_date  # noqa: E402  (the reader is South America only)


def dump(path: Path, data) -> int:
    b = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8') + b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_bytes() != b:
        path.write_bytes(b)
    return len(b)


def one(slug: str, out: Path) -> str:
    folder = ROOT / 'scripts' / f'{slug}-law'
    index, acts_dir = out / f'{slug}.json', out / slug
    if not (folder / 'PUBLISH').exists():
        index.unlink(missing_ok=True)
        shutil.rmtree(acts_dir, ignore_errors=True)
        return f'{slug:10} not published, no data'
    c, _ = build.load(folder)
    errs = build.validate(c)
    if errs:
        return f'{slug:10} corpus has {len(errs)} problems, left as it was: {errs[0]}'
    d = build.site_data(c, docs_date(c))
    sizes = {}
    keep = set()
    for a in d['acts']:
        units = a.pop('units')
        a['provisions'] = len(units)
        a['changed'] = sum(1 for u in units if len(u['versions']) > 1)
        keep.add(f'{a["slug"]}.json')
        sizes[a['slug']] = dump(acts_dir / f'{a["slug"]}.json', {'act': a['slug'], 'units': units})
    for p in acts_dir.glob('*.json'):
        if p.name not in keep:
            p.unlink()
    n = dump(index, d)
    big = max(sizes.items(), key=lambda kv: kv[1])
    return (f'{slug:10} {len(d["acts"])} acts, {sum(len(a["versions"]) for a in d["acts"])} versions, {len(d["laws"])} laws; '
            f'index {n / 1e3:.0f} kB, acts {sum(sizes.values()) / 1e6:.1f} MB (largest {big[0]} {big[1] / 1e6:.2f} MB)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--site', default=str(ROOT / 'saas-webpage'))
    ap.add_argument('--only', nargs='*', default=None)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    out = Path(args.site) / 'app' / 'watch' / 'south-america' / '_data'
    for slug in args.only or COUNTRIES:
        print(one(slug, out), flush=True)


if __name__ == '__main__':
    main()
