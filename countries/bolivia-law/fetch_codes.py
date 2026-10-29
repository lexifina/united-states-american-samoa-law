"""Fetch (or reuse) the pinned SILEP captures that parse_codes.py reads.

silep.gob.bo does not resolve from here, so every page comes from the Internet Archive (id_ raw form) through the
shared client scripts/gitlaw_common/wayback.py (one machine-wide adaptive rate, cache under .cache/, every
request logged to .cache/requests.jsonl).

    python -X utf8 fetch_codes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'gitlaw_common'))
import wayback  # noqa: E402

CACHE = HERE / '.cache'
PINS = [
    (4451, '20240224013706'),   # Código Civil (built)
    (4368, '20200907201025'), (4368, '20210510203809'), (4368, '20211107212007'),
    (4368, '20220610234911'), (4368, '20230825213055'), (4368, '20240124074843'),  # Código Penal (report only)
    (15931, '20231004042425'),  # Ley 1390 de 27/08/2021 (report only)
]

if __name__ == '__main__':
    for norma, ts in PINS:
        body = wayback.get(f'http://www.silep.gob.bo/norma/{norma}/ley_actualizada', ts=ts, cache=CACHE)
        print(norma, ts, len(body) if body else 'MISSING')
