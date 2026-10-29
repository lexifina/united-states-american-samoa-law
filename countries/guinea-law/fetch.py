"""Downloads every source in sources.json into .cache/ through gncache (curl, sha256 names, requests.jsonl, resumable).

    python -X utf8 scripts/guinea-law/fetch.py

Direct official host only (journal-officiel.sgg.gov.gn, robots.txt allows all), at most 3 requests a second.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor

import gncache as c

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with open(os.path.join(HERE, 'sources.json'), encoding='utf-8') as f:
        urls = [s['url'] for s in json.load(f)['files']]

    def one(u):
        try:
            return f'{os.path.getsize(c.get(u, timeout=300))} {u}'
        except Exception as e:  # noqa: BLE001
            return f'FAIL {u} {e}'
    with ThreadPoolExecutor(3) as ex:
        for line in ex.map(one, urls):
            print(line)


if __name__ == '__main__':
    main()
