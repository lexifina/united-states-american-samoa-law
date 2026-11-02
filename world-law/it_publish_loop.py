"""gitlaw-scraper-dell (2026-10-30): publish loop for Italian units whose fetch runs in the background. Every few
minutes: parse the parts whose sources are all cached, verify each unpublished part and write its PUBLISH. Ends once
the unit's fetch log says done/STOPPED and every part is published (or a part fails twice). Private.

    python -X utf8 scripts/world-law/it_publish_loop.py <module> [<module> ...]     # e.g. it_piedmont it_marche
"""
from __future__ import annotations

import importlib
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import it_regions as R  # noqa: E402


def main(mods: list[str]):
    R.below_normal()
    ms = [importlib.import_module(m) for m in mods]
    fails: dict[tuple, int] = {}
    active = set(mods)
    while active:
        for name, m in zip(mods, ms):
            if name not in active:
                continue
            R.wait_cpu()
            log = R.folder(m.SLUG) / 'fetch.log'
            fetch_done = log.exists() and any(x.startswith(('done', 'STOPPED'))
                                              for x in log.read_text(encoding='utf-8').splitlines())
            importlib.reload(m)
            m.parse()
            d = R.folder(m.SLUG) / 'corpus.d'
            pending = [p.stem for p in sorted(d.glob('*.json')) if not p.with_suffix('.PUBLISH').exists()]
            for part in pending:
                if fails.get((name, part), 0) >= 2:
                    continue
                out = R.publish(m.SLUG, m.SRC, part, m.DOCS_DATE, m.letters_check)
                print(time.strftime('%H:%M:%S'), name, part, out[:300], flush=True)
                if not out.startswith('PUBLISH'):
                    fails[(name, part)] = fails.get((name, part), 0) + 1
            left = [p for p in pending if not (d / f'{p}.PUBLISH').exists() and fails.get((name, p), 0) < 2]
            if fetch_done and not left:
                print(time.strftime('%H:%M:%S'), name, 'finished', flush=True)
                active.discard(name)
        if active:
            time.sleep(300)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1:])
