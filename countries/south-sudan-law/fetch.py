"""Fetch South Sudan's sources into .cache/ (sha256 of the URL; every request logged in .cache/requests.jsonl).

    python -X utf8 scripts/south-sudan-law/fetch.py            # every document in sources.json
    python -X utf8 scripts/south-sudan-law/fetch.py URL ...    # fetch (or re-read from cache) the given URLs

Network:
- mojca.gov.ss (Ministry of Justice and Constitutional Affairs): the "Laws of the Republic" page and its PDFs.
  At most 1 request per second.
- www.wipo.int (WIPO Lex): a details page per text, whose PDF link is a signed, expiring CDN URL. The PDF is
  stored in the cache under its stable URL (https://www.wipo.int/wipolex/edocs/lexdocs/laws/en/ss/<id>.pdf); the
  signed URL actually requested is logged in requests.jsonl. At most 1 request per second.
- web.archive.org: raw `id_` captures only (pinned in sources.json), through the shared adaptive client
  scripts/gitlaw_common/wayback.py (one machine-wide rate that backs off on 429). Common Crawl first where it
  holds the file (wayback.cc_captures / cc_get).

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

sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import wayback  # noqa: E402

for host in ("mojca.gov.ss", "www.mojca.gov.ss", "www.wipo.int", "wipolex-res.wipo.int"):
    peachjam.CRAWL_DELAY.setdefault(host, 1.0)


def cache() -> "peachjam.Cache":
    return peachjam.Cache(HERE)


def get(c: "peachjam.Cache", url: str) -> bytes:
    if url.startswith("https://web.archive.org/"):
        b = wayback.fetch(url, c.dir)
        if b is None:
            raise RuntimeError(f"not archived: {url}")
        return b
    return c.get(url)


def get_wipo(c: "peachjam.Cache", stable: str, details: str) -> bytes:
    """The WIPO Lex PDF `stable`, downloaded through the signed link on its details page."""
    import html
    import re
    if c.has(stable):
        return c.get(stable)
    c.path(details).unlink(missing_ok=True)  # its signed links expire within minutes: always read it fresh
    page = get(c, details).decode("utf-8", "replace")
    name = stable.rsplit("/", 1)[1]
    links = [html.unescape(m) for m in re.findall(r'href="(https://wipolex-res[^"]+)"', page)
             if html.unescape(m).split("?")[0].endswith("/" + name)]
    if not links:
        raise RuntimeError(f"no link to {name} on {details}")
    b = c.get(links[0])
    c.path(stable).write_bytes(b)
    if not b.startswith(b"%PDF"):
        raise RuntimeError(f"not a PDF: {stable}")
    return b


def main(argv: list[str]) -> None:
    c = cache()
    if argv:
        for u in argv:
            b = get(c, u)
            print(len(b), c.path(u).name, u)
        return
    src = HERE / "sources.json"
    if src.exists():
        for d in json.loads(src.read_text(encoding="utf-8"))["documents"]:
            if d.get("details"):
                get_wipo(c, d["url"], d["details"])
            else:
                get(c, d["url"])


if __name__ == "__main__":
    main(sys.argv[1:])
