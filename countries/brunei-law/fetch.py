"""Fetch Brunei's Phase 1 sources from the Attorney General's Chambers (www.agc.gov.bn).

    python -X utf8 scripts/brunei-law/fetch.py

Everything goes through curl (Python TLS fails on this machine), cached under .cache/ by the sha256 of the URL,
resumable, at most 3 requests a second, every request logged in .cache/requests.jsonl.
The list of documents is sources.json: each act's AGC document page, its revised-edition PDFs and its amending Orders.
"""
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
MIN_GAP = 0.34  # seconds between requests: at most 3 a second (SPEED RULE)
_last = [0.0]


def cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    ext = ".pdf" if url.lower().endswith(".pdf") else ".html"
    return CACHE / (h + ext)


def get(url: str) -> Path:
    """Return the cached file for url, fetching it once if needed."""
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    p = cache_path(url)
    if p.exists() and p.stat().st_size > 0:
        return p
    wait = MIN_GAP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix(p.suffix + ".part")
    r = subprocess.run(["curl", "-s", "-L", "--compressed", "--max-time", "180", "-A", UA,
                        "-o", str(tmp), "-w", "%{http_code} %{content_type} %{size_download}", url],
                       capture_output=True, text=True)
    _last[0] = time.time()
    status, ctype, size = (r.stdout.split(" ") + ["", "", ""])[:3]
    with open(CACHE / "requests.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"url": url, "status": status, "type": ctype, "bytes": size,
                            "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}) + "\n")
    if status != "200" or (url.lower().endswith(".pdf") and "pdf" not in ctype.lower()):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{url}: HTTP {status} {ctype}")
    tmp.replace(p)
    return p


def main() -> None:
    src = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    urls = []
    for act in src["acts"]:
        urls.append(act["page"])
        urls += [e["url"] for e in act["editions"]]
        urls += [o["url"] for o in act.get("orders", [])]
    for u in urls:
        try:
            p = get(u)
            print("ok ", p.name[:16], u)
        except RuntimeError as e:
            print("ERR", e, file=sys.stderr)


if __name__ == "__main__":
    main()
