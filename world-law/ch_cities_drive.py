"""Parse and publish one Swiss city's corpus.d parts as its fetch completes them (gitlaw-scraper-dell, 2026-10-31).

    python -X utf8 scripts/world-law/ch_cities_drive.py winterthur 2026-10-31

Every 60 s: wait while cpu5 > 90 or RAM > 85 (last line of %LOCALAPPDATA%/gitlaw-cpu.log); parse new parts; verify
and PUBLISH each unpublished part (letters check + check.py on a scratch build). Stops once the fetch is done and
every part is published (or a part fails verification, which is reported and left unpublished). Private.
"""
from __future__ import annotations

import calendar
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cities as K  # noqa: E402

C = K.C


def busy() -> bool:
    try:
        line = (Path(os.environ['LOCALAPPDATA']) / 'gitlaw-cpu.log').read_text().strip().splitlines()[-1]
        cpu5 = int(re.search(r'cpu5=(\d+)', line).group(1))
        ram = int(re.search(r'ram=(\d+)', line).group(1))
        return cpu5 > 90 or ram > 85
    except Exception:
        return False


def main(city: str, docs_date: str):
    slug = K.key(city)
    d = C.folder(slug) / 'corpus.d'
    failed: set[str] = set()
    later: dict[str, float] = {}   # part -> retry time: a version in force today is dated noon Zurich (11:00Z)
    while True:
        if (C.folder(slug) / 'STOP').exists():
            print('drive: STOPPED by the stop file', flush=True)
            return
        if busy():
            time.sleep(60)
            continue
        import io
        import contextlib
        with contextlib.redirect_stdout(io.StringIO()):
            C.parse_canton(slug, docs_date)
        todo = [p.stem for p in sorted(d.glob('*.json'))
                if not p.with_suffix('.PUBLISH').exists() and p.stem not in failed
                and later.get(p.stem, 0) <= time.time()]
        for part in todo:
            while busy():
                time.sleep(60)
            r = C.publish(slug, part, docs_date)
            print(time.strftime('%H:%M:%SZ', time.gmtime()), part, r[:300], flush=True)
            if not r.startswith('PUBLISH'):
                noon = calendar.timegm(time.gmtime()[:3] + (11, 5, 0, 0, 0, 0))   # 11:05Z today
                fd = re.search(r'"future_dated": (\d+)', r)
                if (fd and int(fd.group(1)) > 0 and '"mismatches": 0' in r and '"trailer_errors": 0' in r
                        and time.time() < noon):
                    later[part] = noon
                    print(f'{part}: deferred to 11:05Z (a version in force today, dated at noon Zurich)', flush=True)
                else:
                    failed.add(part)
        done = (C.folder(slug) / '.cache' / 'fetch-ord-done.txt').exists()
        stopped = 'STOPPED' in (C.folder(slug) / 'fetch.log').read_text(encoding='utf-8', errors='replace')
        if (done or stopped) and not todo and not any(t > time.time() for t in later.values()):
            print('drive: finished', 'fetch stopped' if stopped else 'fetch done', 'failed:', sorted(failed), flush=True)
            return
        time.sleep(60)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
