"""Cached, polite fetcher for direct (non-archive) Moldovan official sources (curl subprocess).

Cache: .cache/<sha256(url)> plus .cache/requests.jsonl (one line per network request).
Archive.org and Common Crawl go through scripts/gitlaw_common/wayback.py (same cache, same log).
Usage:  python -X utf8 fetch.py URL [URL ...]      (prints cache paths)
"""
import hashlib, json, os, subprocess, sys, time, threading

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
UA = "lexifina-watch/1.0 (+https://lexifina.com/watch; corpus@lexifina.com)"
MIN_GAP = 0.34  # at most 3 requests a second per host (SPEED RULE)
_last = {}
_lock = threading.Lock()


def path_for(url):
    return os.path.join(CACHE, hashlib.sha256(url.encode("utf-8")).hexdigest())


def get(url, force=False, timeout=180):
    os.makedirs(CACHE, exist_ok=True)
    p = path_for(url)
    if os.path.exists(p) and not force:
        return p
    host = url.split("/")[2]
    if host.endswith("legis.md") or host.endswith("parlament.md"):
        raise RuntimeError("bot-challenged site: read it through the archives only")
    with _lock:
        wait = _last.get(host, 0) + MIN_GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.time()
    tmp = p + ".part"
    r = subprocess.run(["curl", "-s", "-L", "--compressed", "-m", str(timeout), "-A", UA,
                        "-o", tmp, "-w", "%{http_code} %{content_type}", url], capture_output=True, text=True)
    code, _, ctype = (r.stdout or "000 ").partition(" ")
    size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
    sha = hashlib.sha256(open(tmp, "rb").read()).hexdigest() if size else None
    with open(os.path.join(CACHE, "requests.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "url": url,
                            "status": int(code or 0), "type": ctype, "bytes": size, "sha256": sha}) + "\n")
    if code != "200" or not size:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise RuntimeError(f"fetch failed {code} {url}")
    os.replace(tmp, p)
    return p


if __name__ == "__main__":
    for u in sys.argv[1:]:
        try:
            print(get(u), u)
        except Exception as e:
            print("ERR", e)
