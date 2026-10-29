"""Fetches the batch-4 acts (scripts/uruguay-law/corpus.d/70-batch4.json) into the shared scripts/uruguay-law/.cache.

    python -X utf8 scripts/uruguay-law/batch4/fetch4.py [slugs...]      # default: every act in batch4.ACTS
    python -X utf8 scripts/uruguay-law/batch4/fetch4.py --path P ...    # extra IMPO paths (e.g. vigencia articles)

The fetcher of batches 2 and 3: the main fetch.py (curl, --compressed, the lexifina User-Agent, IMPO's robots.txt
Crawl-Delay 10 kept as 10.5 s between requests, requests.jsonl) and impo_history.needed_paths, in one process so the
crawl delay holds. legalize-dev/legalize-uy and Common Crawl were checked first and hold none of what this needs
(batch4.DECISIONS_COMMON). A failed URL is logged and skipped; re-running fetches only what is missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import batch4  # noqa: E402

batch4.batch3.FETCHING = True


def get(path: str) -> bool:
    url = fetch.impo(path)
    if fetch.cache_path(url).exists():
        return True
    try:
        fetch.fetch(url)
        print('ok', path, flush=True)
        return True
    except Exception as e:  # noqa: BLE001
        print('FAIL', path, str(e)[:200], flush=True)
        return False


def main(argv: list[str]) -> None:
    if argv[:1] == ['--path']:
        for p in argv[1:]:
            get(p)
        return
    for slug in argv or list(batch4.ACTS):
        cfg = batch4.ACTS[slug]
        if not get(cfg['path']):
            continue
        paths = batch4.all_paths(cfg)
        todo = [p for p in paths if not fetch.cache_path(fetch.impo(p)).exists()]
        print(slug, len(paths), 'paths,', len(todo), 'to fetch', flush=True)
        for p in todo:
            get(p)
        print(slug, 'done', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
