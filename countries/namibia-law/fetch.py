"""Fetch Namibia's configured acts (acts.json): NamibLII expression pages read from the Internet Archive.

    python -X utf8 scripts/namibia-law/fetch.py

Writes sources.json in the shape the shared Peachjam adapter's parse() reads (scripts/africa-law/peachjam.py), so
parse.py is the adapter's own. What differs from peachjam.fetch: every archive.org request goes through the shared,
machine-wide adaptive client scripts/gitlaw_common/wayback.py (coordinator, 2026-10-28: archive.org throttles this
machine; Common Crawl has no NamibLII pages, since NamibLII's robots.txt disallows CCBot), and discovery is one CDX
prefix listing of namiblii.org/akn/na/act/ instead of one per work. The cache layout is the adapter's: one file per
URL named by sha256(url), every request in .cache/requests.jsonl. NamibLII itself is asked only for its open listing
page (/legislation/?years=Y), one per act, at the adapter's 5 s crawl delay.
"""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "africa-law" / "peachjam.py"
if SHARED.exists() and (not (HERE / "peachjam.py").exists()
                        or SHARED.read_bytes() != (HERE / "peachjam.py").read_bytes()):
    shutil.copyfile(SHARED, HERE / "peachjam.py")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
import peachjam  # noqa: E402
import wayback  # noqa: E402

CACHE = HERE / ".cache"


def expr_of(orig: str) -> tuple[str, str] | None:
    """(work, expression date) of an archived NamibLII URL, any host form or %40 encoding."""
    o = orig.replace("%40", "@").split("?")[0].split("#")[0].rstrip("/")
    m = re.search(r"namiblii\.org(?::\d+)?(?:/en)?/akn/na/act/(.+?)/eng@(\d{4}-\d{2}-\d{2})$", o)
    return (m.group(1), m.group(2)) if m else None


def all_captures(prefix: str) -> dict[str, dict[str, list[tuple[str, str]]]]:
    """{work: {date: [(timestamp, original), newest first]}} from one CDX prefix listing (every distinct copy)."""
    out: dict = {}
    for c in wayback.captures(prefix, match="prefix", cache=CACHE, collapse="digest"):
        if "html" not in c["mimetype"]:
            continue
        we = expr_of(c["original"])
        if we:
            out.setdefault(we[0], {}).setdefault(we[1], []).append((c["timestamp"], c["original"]))
    for w in out:
        for d in out[w]:
            out[w][d] = sorted(set(out[w][d]), reverse=True)
    return out


def complete(b: bytes) -> bool:
    """A whole page: some archived copies are cut off at 1 MiB (the Criminal Procedure Act, 2023-07-25, capture
    20240617051143), and the adapter's good_expression_page() accepts them because the text starts early."""
    return b.rstrip().lower().endswith(b"</html>")


def get_good(work_uri: str, day: str, caps: list[tuple[str, str]], tries: int) -> dict | None:
    expr = f"{work_uri}/eng@{day}"
    for ts, orig in caps[:tries]:
        b = wayback.get(orig, ts=ts, cache=CACHE)
        if b and peachjam.good_expression_page(b, expr) and complete(b):
            return {"capture": ts, "original": orig, "url": peachjam.raw(ts, orig),
                    "sha256": hashlib.sha256(b).hexdigest()}
        print("  not a usable expression page:", ts, orig)
    return None


def main() -> None:
    cfg = peachjam.load_config(HERE)
    lii = cfg["lii"]
    pins: dict = {"lii": lii["name"], "acts": {}, "laws": {}, "listings": {}}
    caps_by_work: dict = {}
    for pre in cfg.get("cdx_prefixes", ["namiblii.org/akn/na/act/"]):
        for w, d in all_captures(pre).items():
            for day, lst in d.items():
                caps_by_work.setdefault(w, {}).setdefault(day, []).extend(lst)
    law_uris: set[str] = set()
    cache = peachjam.Cache(HERE)
    for act in cfg["acts"]:
        work = act["work"]
        caps = caps_by_work.get(work, {})
        ex = {}
        for day in sorted(caps):
            got = get_good(peachjam.work_uri(cfg, work), day, sorted(set(caps[day]), reverse=True),
                           act.get("max_tries", 4))
            if got:
                ex[day] = got
        pins["acts"][work] = {"expressions": ex}
        print(f"{work}: {len(ex)}/{len(caps)} archived expressions usable: {sorted(ex)}", flush=True)
        if not ex:
            continue
        info = peachjam.page_info(cache.get(ex[max(ex)]["url"]))
        for item in info["timeline"]:
            for ev in item["events"]:
                for href, _ in ev["links"]:
                    if href and "/akn/" in href and "@" not in href:
                        law_uris.add(re.sub(r"^/[a-z]{2}(?=/akn/)", "", href))
        if lii.get("listing", True):
            year = work.split("/")[-2]
            lst_url = f"https://{lii['hosts'][0]}{lii.get('listing_prefix', '')}/legislation/?years={year}"
            try:
                cache.get(lst_url)
                pins["listings"][work] = lst_url
            except RuntimeError as e:
                print("  listing", e)
    # The amending laws' own pages: on NamibLII most amending Acts are shown only as their Gazette PDF (no coverpage
    # notices, no Akoma Ntoso text), so their pages add no dates the adapter reads. Fetched only if configured.
    for uri in sorted(law_uris) if cfg.get("fetch_law_pages") else []:
        work = re.sub(rf"^/akn/{lii['cc']}/act/", "", uri)
        if work in pins["acts"]:
            continue
        got = None
        for day in sorted(caps_by_work.get(work, {})):  # oldest expression first: the law as enacted
            got = get_good(uri, day, caps_by_work[work][day], 2)
            if got:
                got = {"expression": day, **{k: got[k] for k in ("capture", "url", "sha256")}}
                break
        pins["laws"][uri] = got
        print(f"law {uri}: {'archived ' + got['expression'] if got else 'no usable archived page'}")
    for uri in sorted(law_uris):
        pins["laws"].setdefault(uri, None)
    pins["retrieved"] = cfg["retrieved"]
    tmp = HERE / "sources.json.tmp"
    tmp.write_text(json.dumps(pins, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(HERE / "sources.json")


if __name__ == "__main__":
    main()
