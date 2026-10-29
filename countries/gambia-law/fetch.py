"""Fetch The Gambia's sources into .cache/ (sha256 of the URL; every request logged in .cache/requests.jsonl).

    python -X utf8 scripts/gambia-law/fetch.py            # the listing pages, then every document in sources.json
    python -X utf8 scripts/gambia-law/fetch.py URL ...    # fetch (or re-read from cache) the given URLs

Network:
- assembly.gm (National Assembly of The Gambia): the open document listing (/documents/type/acts?page=N), each
  document page (/documents/<id>) and its PDF (/documents/<id>/download). robots.txt: "User-agent: * / Disallow:".
  At most 1 request per second.
- web.archive.org: raw `id_` captures only (pinned in sources.json), at most 1 request per 3 s shared by every
  process on this machine (the stamp file of the shared Peachjam adapter).

The curl cache is the shared adapter's Cache class (scripts/africa-law/peachjam.py, imported read-only; this folder
carries the exact copy it was run with).
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "africa-law" / "peachjam.py"
if SHARED.exists() and (not (HERE / "peachjam.py").exists()
                        or SHARED.read_bytes() != (HERE / "peachjam.py").read_bytes()):
    shutil.copyfile(SHARED, HERE / "peachjam.py")
sys.path.insert(0, str(HERE))
import peachjam  # noqa: E402

peachjam.CRAWL_DELAY.setdefault("assembly.gm", 1.0)
LISTING = "https://assembly.gm/documents/type/acts?page={n}"
LISTING_PAGES = 9


def cache() -> "peachjam.Cache":
    return peachjam.Cache(HERE)


def main(argv: list[str]) -> None:
    c = cache()
    if argv:
        for u in argv:
            try:
                b = c.get(u, retries=2)
            except RuntimeError as e:
                print("FAILED", e)
                continue
            print(len(b), c.path(u).name, u)
        return
    for n in range(1, LISTING_PAGES + 1):
        c.get(LISTING.format(n=n))
    src = HERE / "sources.json"
    if src.exists():
        for d in json.loads(src.read_text(encoding="utf-8"))["documents"]:
            c.get(d["url"])


if __name__ == "__main__":
    main(sys.argv[1:])
