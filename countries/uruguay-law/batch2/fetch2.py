"""Fetches the batch-2 codes (scripts/uruguay-law/corpus.d/50-batch2.json) into the shared scripts/uruguay-law/.cache.

    python -X utf8 scripts/uruguay-law/batch2/fetch2.py [slugs...]      # default: every act in batch2.ACTS
    python -X utf8 scripts/uruguay-law/batch2/fetch2.py --path P ...    # extra IMPO paths (e.g. vigencia articles)

Uses the main fetcher (fetch.py: curl, --compressed, the lexifina User-Agent, IMPO's Crawl-Delay 10 kept as 10.5 s,
requests.jsonl) and impo_history.needed_paths, in one process so the crawl delay holds. A failed URL is logged and
skipped; re-running fetches only what is missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import impo_history  # noqa: E402
import batch2  # noqa: E402


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
    for slug in argv or list(batch2.ACTS):
        cfg = batch2.ACTS[slug]
        if not get(cfg['path']):
            continue
        main_json = fetch.impo_json(fetch.impo(cfg['path']), True)
        extra = [cfg['base_in_force'][0]] if cfg.get('base_in_force') else []
        extra += cfg.get('extra', []) + batch2.sample_paths(cfg)
        paths = extra + impo_history.needed_paths(main_json, cfg['base'], cfg['vigencia'])
        todo = [p for p in paths if not fetch.cache_path(fetch.impo(p)).exists()]
        print(slug, len(paths), 'paths,', len(todo), 'to fetch', flush=True)
        for p in todo:
            get(p)
        print(slug, 'done', flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
