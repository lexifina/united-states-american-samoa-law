"""Fetch Tanzania's configured TanzLII acts (acts.json) from the Internet Archive and write sources.json in the format
the shared Peachjam adapter's parse() reads.

    python -X utf8 scripts/tanzania-law/fetch.py

Why not peachjam.fetch(): the coordinator's FAST ARCHIVE ACCESS rule (2026-10-28) says every archive.org request goes
through scripts/gitlaw_common/wayback.py, whose one adaptive rate is shared by every process on the machine; peachjam's
own fetch keeps a fixed 3 s delay. Common Crawl (wayback.cc_*) would come first, but index.commoncrawl.org refused
connections from this machine on 2026-10-28, so discovery and pages come from archive.org.

Raw captures are cached under .cache/sha256(https://web.archive.org/web/<ts>id_/<original>), exactly the key
peachjam.Cache uses, so peachjam.parse() reads them offline. TanzLII serves pages under /akn/... and /en/akn/...; both
are searched. TanzLII's open listing page (/en/legislation/?years=Y, robots-allowed) is read once per act through
peachjam.Cache (5 s Crawl-delay) to name the current expression. TanzLII's own document pages are never fetched.

The official English Constitution is not on TanzLII (its Constitution is Kiswahili only); constitution.py handles it.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import peachjam  # noqa: E402
import wayback  # noqa: E402

CACHE = HERE / ".cache"


def expr_captures(cfg: dict, work: str) -> dict:
    """{expression date: [(timestamp, original), ...]}: newest first, captures at least half the largest size first
    (small 2025-26 captures are often script shells without the text)."""
    lii = cfg["lii"]
    out: dict = {}
    for host in lii["hosts"]:
        for pre in lii.get("path_prefixes", [""]):
            for r in wayback.captures(f"{host}{pre}/akn/{lii['cc']}/act/{work}/eng@", match="prefix", cache=CACHE,
                                      collapse=None):
                o = r["original"].replace("%40", "@")
                m = re.search(r"/eng@(\d{4}-\d{2}-\d{2})/?$", o)
                if m and "?" not in o and "html" in r["mimetype"]:
                    out.setdefault(m.group(1), []).append((r["timestamp"], r["original"], int(r["length"] or 0)))
    res = {}
    for d, lst in out.items():
        lst = sorted(set(lst), reverse=True)
        big = max(x[2] for x in lst)
        res[d] = [(t, o) for t, o, n in lst if n >= big / 2] + [(t, o) for t, o, n in lst if n < big / 2]
    return dict(sorted(res.items()))


def main():
    cfg = peachjam.load_config(HERE)
    lii = cfg["lii"]
    old = json.loads((HERE / "sources.json").read_text(encoding="utf-8")) if (HERE / "sources.json").exists() else {}
    pins = {"lii": lii["name"], "acts": {}, "laws": {}, "listings": {}}
    listing = peachjam.Cache(HERE)
    only = set(sys.argv[1:])
    for act in cfg["acts"]:
        work = act["work"]
        if only and work not in only and work in old.get("acts", {}):
            pins["acts"][work] = old["acts"][work]
            if work in old.get("listings", {}):
                pins["listings"][work] = old["listings"][work]
            continue
        caps = expr_captures(cfg, work)
        ex = {}
        for day, lst in caps.items():
            expr_uri = f"/akn/{lii['cc']}/act/{work}/eng@{day}"
            cached = [x for x in lst if (CACHE / hashlib.sha256(peachjam.raw(*x).encode()).hexdigest()).exists()]
            for ts, orig in cached + [x for x in lst if x not in cached][: act.get("max_tries", 6)]:
                b = wayback.get(orig, ts=ts, cache=CACHE)
                if b and peachjam.good_expression_page(b, expr_uri):
                    ex[day] = {"capture": ts, "original": orig, "url": peachjam.raw(ts, orig),
                               "sha256": hashlib.sha256(b).hexdigest()}
                    break
        pins["acts"][work] = {"expressions": ex}
        lst_url = f"https://{lii['hosts'][0]}{lii.get('listing_prefix', '')}/legislation/?years={work.split('/')[-2]}"
        try:
            listing.get(lst_url)
            pins["listings"][work] = lst_url
        except RuntimeError as e:
            print("  listing", e)
        print(f"{work}: {len(ex)}/{len(caps)} archived expressions good: {sorted(ex)}", flush=True)
    pins["retrieved"] = cfg["retrieved"]
    tmp = HERE / "sources.json.tmp"
    tmp.write_text(json.dumps(pins, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(HERE / "sources.json")


if __name__ == "__main__":
    main()
