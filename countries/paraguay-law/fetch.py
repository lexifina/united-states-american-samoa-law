"""Polite, resumable, cached fetcher for the Paraguay git-for-law build.

Every download goes through curl (Python TLS fails on this machine), is
cached under .cache/<sha256(url)>.<ext>, rate-limited to 1 request per
second per host, and logged to .cache/requests.jsonl.

Usage:
    python -X utf8 fetch.py URL [URL ...]      fetch (or reuse) each URL
    python -X utf8 fetch.py --plan             fetch everything parse.py needs
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
LOG = CACHE / "requests.jsonl"
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
_last: dict[str, float] = {}


def cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode("utf-8")).hexdigest()
    ext = ".pdf" if url.lower().split("?")[0].endswith(".pdf") else ".html"
    if url.endswith(".xml"):
        ext = ".xml"
    return CACHE / f"{h}{ext}"


def log_append(line: str) -> None:
    """Append one record; a lock file keeps parallel fetchers from interleaving lines."""
    lock = CACHE / "requests.lock"
    for _ in range(600):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        fd = None                  # a stale lock: write anyway rather than lose the record
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    finally:
        if fd is not None:
            os.close(fd)
            os.unlink(lock)


def fetch(url: str, *, force: bool = False, timeout: int = 300) -> Path | None:
    CACHE.mkdir(exist_ok=True)
    gi = CACHE / ".gitignore"
    if not gi.exists():
        gi.write_text("*\n", encoding="utf-8")
    p = cache_path(url)
    if p.exists() and p.stat().st_size > 0 and not force:
        return p
    host = urlparse(url).netloc
    wait = 1.0 - (time.time() - _last.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    tmp = p.with_suffix(p.suffix + ".part")
    t0 = time.time()
    r = subprocess.run(
        ["curl", "-sS", "-L", "--compressed", "-m", str(timeout), "-A", UA,
         "-o", str(tmp), "-w", "%{http_code} %{content_type} %{size_download}", url],
        capture_output=True, text=True)
    _last[host] = time.time()
    parts = (r.stdout or "").split(" ")
    status = parts[0] if parts else ""
    rec = {"url": url, "status": status, "content_type": parts[1] if len(parts) > 1 else "",
           "bytes": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0,
           "file": p.name, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)),
           "error": r.stderr.strip()[:300], "exit": r.returncode}
    log_append(json.dumps(rec, ensure_ascii=False) + "\n")
    rec_ok = r.returncode == 0      # curl exits non-zero on a timeout even after a 200 header: never cache a cut file
    if status == "200" and rec_ok and tmp.exists() and tmp.stat().st_size > 0:
        os.replace(tmp, p)
        return p
    if tmp.exists():
        tmp.unlink()
    print(f"FAILED {status} {url} {rec['error']}", file=sys.stderr)
    return None


def plan() -> list[str]:
    """Every URL parse.py reads; kept in sources.json next to this file."""
    src = next(p for p in (HERE / "sources.json", HERE / "repo" / "tools" / "sources.json") if p.exists())
    data = json.loads(src.read_text(encoding="utf-8"))
    return [u for u in data["urls"]]


def main(argv: list[str]) -> int:
    urls = plan() if argv[:1] == ["--plan"] else argv
    bad = 0
    for u in urls:
        p = fetch(u)
        print(("ok   " if p else "FAIL ") + u + (f" -> {p.name}" if p else ""))
        bad += p is None
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
