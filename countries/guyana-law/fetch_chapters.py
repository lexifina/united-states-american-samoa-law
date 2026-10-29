"""Fetch (or reuse from the cache) the editions of the further chapters in corpus.d/50-chapters.json.

L.R.O. 1/2022 PDFs come from mola.gov.gy through fetch.py (curl, cached, 1 request per second); the L.R.O. 1/2012
PDFs from Internet Archive captures through gitlaw_common/wayback.py (shared machine-wide archive.org rate). Both
caches are named by the sha256 of the URL, so parse reads them the same way.

    python -X utf8 fetch_chapters.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"C:/Users/alany/Documents/lexifina/scripts/gitlaw_common")
import fetch  # noqa: E402
import wayback  # noqa: E402
from chapters import CHAPTERS  # noqa: E402
import chapters_extra  # noqa: E402
import chapters_more  # noqa: E402
import companies  # noqa: E402


def main() -> int:
    bad = 0
    for ch in CHAPTERS + chapters_more.MORE + [companies.CH] + chapters_extra.ALL + chapters_extra.SKIPPED:
        urls = {ed: url for ed, (url, *_rest) in ch["editions"].items()}
        urls["current"] = ch["current"]
        urls.update({m[0]: m[4] for m in ch["missing"]})
        if ch.get("lro2012_lists"):   # the archived 2012 copy read only for its front page (chapters_extra)
            urls["e2012-front"] = ch["lro2012_lists"][1]
        if ch is companies.CH:   # the archived copy (dates the edition online) and the Acts searched for amendments
            urls["archived"] = companies.ARCHIVED
            urls.update({s: companies.PARL + s for s in companies.SEARCHED})
        for ed, url in urls.items():
            if url.startswith("https://web.archive.org/web/"):
                ts, orig = url[len("https://web.archive.org/web/"):].split("id_/", 1)
                ok = wayback.get(orig, ts=ts, cache=fetch.CACHE) is not None
            else:
                try:
                    fetch.get(url)
                    ok = True
                except RuntimeError:
                    ok = False
            print("ok " if ok else "FAILED", ch["slug"], ed, url)
            bad += not ok
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
