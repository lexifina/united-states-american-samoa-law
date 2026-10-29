"""Fetch one URL into the cache (rate-limited, logged): python -X utf8 get.py URL [out] [--pdf].

Government hosts go through the shared adapter's curl cache (1 request per second per host); web.archive.org goes
through scripts/gitlaw_common/wayback.py (the machine-wide rate), both cached under .cache/ by the sha256 of the URL
and logged to .cache/requests.jsonl.

A URL that should give a PDF (its path ends in .pdf, or --pdf is passed) is kept only if the bytes are a whole PDF:
they start with "%PDF-" and end with "%%EOF". Anything else (an HTML error page served with status 200, an archive
capture truncated at 1 MiB) is removed from the cache and reported, so it is never reused as a source.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
import peachjam  # noqa: E402  (read-only shared adapter: only its Cache is used)

DELAYS = {h: 1.0 for h in (
    "justice.gov.ng", "www.justice.gov.ng", "pre.cac.gov.ng", "cac.gov.ng", "www.cac.gov.ng", "ncc.gov.ng",
    "www.ncc.gov.ng", "nass.gov.ng", "www.nass.gov.ng", "ndpc.gov.ng", "www.ndpc.gov.ng", "placng.org",
    "www.placng.org", "aserc.anambrastate.gov.ng")}
peachjam.CRAWL_DELAY.update(DELAYS)


def is_pdf(b: bytes) -> bool:
    """A whole PDF: the header at the start and an end-of-file marker in the last 2 KiB."""
    return b.startswith(b"%PDF-") and b"%%EOF" in b[-2048:]


def wants_pdf(url: str) -> bool:
    return url.split("?")[0].lower().endswith(".pdf")


def get(url: str, pdf: bool | None = None) -> bytes:
    """The bytes of `url`, from the cache or the network. Raises ValueError (and drops the cached file) if a PDF was
    expected and the bytes are not a whole PDF."""
    c = peachjam.Cache(HERE)
    p = c.path(url)
    b = c.get(url)
    if (wants_pdf(url) if pdf is None else pdf) and not is_pdf(b):
        p.unlink(missing_ok=True)
        raise ValueError(f"not a whole PDF ({len(b)} bytes, starts {b[:15]!r}); removed from the cache: {url}")
    return b


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--pdf"]
    try:
        data = get(args[0], True if "--pdf" in sys.argv else None)
    except ValueError as e:
        sys.exit(str(e))
    print(len(data), peachjam.Cache(HERE).path(args[0]).name)
    if len(args) > 1:
        Path(args[1]).write_bytes(data)
