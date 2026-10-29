"""Fetch (or reuse from the cache) every source the codes/ parts need (Código de Comercio).

Gazette editions go through the country's fetch.py (curl --compressed, sha256-named cache, polite, logged to
.cache/requests.jsonl); the archived Lexis index through gitlaw_common/wayback.py (shared archive.org rate).
The Asamblea's law list and PDFs screened for amendments are fetched by codes/screen.py.

    python -X utf8 codes/fetch_codes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, r"C:/Users/alany/Documents/lexifina/scripts/gitlaw_common")
import fetch  # noqa: E402
import wayback  # noqa: E402
import comercio  # noqa: E402

GAZETTE = [comercio.S497_2019, comercio.S347_2020, comercio.S245_2023]


def main() -> int:
    bad = 0
    for u in GAZETTE:
        p = fetch.get(u, timeout=900)
        print("ok " if p else "FAILED", u)
        bad += p is None
    b = wayback.get(comercio.LEXIS_2020.split("id_/", 1)[1], ts="20240527012147", cache=HERE.parent / ".cache")
    print("ok " if b else "FAILED", comercio.LEXIS_2020)
    return 1 if bad or not b else 0


if __name__ == "__main__":
    sys.exit(main())
