"""Fetch Seychelles' configured acts (acts.json): SeyLII Peachjam expression pages, read from the Internet Archive.

    python -X utf8 scripts/seychelles-law/fetch.py               # every act in acts.json, then the amending laws
    python -X utf8 scripts/seychelles-law/fetch.py --probe WORK  # list one work's archived expressions and its History

Why not the shared adapter's own fetch: peachjam.fetch() spaces archive.org requests with its own 3 s stamp file;
the coordinator (2026-10-28, 21:45 UTC) moved every agent to scripts/gitlaw_common/wayback.py, which keeps ONE
adaptive rate for the whole machine. This file does what peachjam.fetch() does (same sources.json layout, same cache
file names: sha256 of the URL), through wayback.captures / wayback.fetch. peachjam.parse() then reads the cache.

SeyLII (seylii.org) itself moved from Peachjam to Lexum's Decisia/Norma platform in 2026; its Peachjam pages survive
only in the Internet Archive. No SeyLII document page is fetched directly. Common Crawl's index
(index.commoncrawl.org) did not answer from this machine on 2026-10-28, so every page here is an archive.org capture.
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


def expressions(cfg: dict, work: str) -> dict[str, list[tuple[str, str]]]:
    """{expression date: [(timestamp, original), ...] newest first}, from one archive.org CDX request per host."""
    out: dict[str, list[tuple[str, str]]] = {}
    for host in cfg["lii"]["hosts"]:
        for r in wayback.captures(f"{host}{peachjam.work_uri(cfg, work)}/eng@", match="prefix", cache=CACHE,
                                  collapse=None):
            orig = r["original"]
            if "html" not in r["mimetype"] or "?" in orig:
                continue
            m = re.search(r"/eng@(\d{4}-\d{2}-\d{2})/?$", orig)
            if m:
                out.setdefault(m.group(1), []).append((r["timestamp"], orig))
    return {d: sorted(set(v), reverse=True) for d, v in sorted(out.items())}


def best(cfg: dict, work: str, day: str, lst: list, tries: int = 6) -> dict | None:
    """The newest capture of this expression that is the expression page with its text."""
    expr_uri = f"{peachjam.work_uri(cfg, work)}/eng@{day}"
    for ts, orig in lst[:tries]:
        u = peachjam.raw(ts, orig)
        b = wayback.fetch(u, CACHE)
        if b and peachjam.good_expression_page(b, expr_uri):
            return {"capture": ts, "original": orig, "url": u, "sha256": hashlib.sha256(b).hexdigest()}
        print("  not an expression page:", u, flush=True)
    return None


def _t(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"the", "", (s or "").lower())).strip()


def law_page(cfg: dict, work: str, title: str) -> dict | None:
    """The amending law's own page, for its assent, publication and commencement dates: its oldest archived expression
    whose page title is the title the act's History gives it. SeyLII renumbered works in 2024/25 (in 2023-24
    /akn/sc/act/1994/7 was the Constitution itself; in 2025 it is the First Amendment Act 1994), so a page is accepted
    only if its title matches. Its text is not needed: the dates are on the coverpage and in its History tab, which
    script-loaded 2025 pages still carry."""
    for day, lst in expressions(cfg, work).items():
        for ts, orig in lst[:4]:
            u = peachjam.raw(ts, orig)
            b = wayback.fetch(u, CACHE)
            if not b:
                continue
            info = peachjam.page_info(b)
            got = _t(info.get("title") or info.get("page_title", "").split(" – ")[0].split(" - SeyLII")[0])
            if title and got == _t(title):
                return {"expression": day, "capture": ts, "url": u, "sha256": hashlib.sha256(b).hexdigest(),
                        "title_checked": title}
            print(f"  {u}: page is {got!r}, not {title!r}", flush=True)
    return None


def probe(cfg: dict, work: str) -> None:
    caps = expressions(cfg, work)
    print(work, "archived:", list(caps))
    for day in reversed(list(caps)):
        got = best(cfg, work, day, caps[day], tries=3)
        if not got:
            continue
        info = peachjam.page_info(wayback.fetch(got["url"], CACHE))
        print(" title:", info.get("title"), "| latest good:", day)
        print(" notices:", [n["text"] for n in info["notices"]])
        for t in info["timeline"]:
            print("  ", t["date"], "read" if t["read"] else "    ", [(e["kind"], e["text"][:110], e["unapplied"]) for e in t["events"]])
        print(" unapplied:", info["unapplied_notice"])
        return


def main() -> None:
    cfg = peachjam.load_config(HERE)
    if sys.argv[1:2] == ["--probe"]:
        for w in sys.argv[2:]:
            probe(cfg, w)
        return
    prev = json.loads((HERE / "sources.json").read_text(encoding="utf-8")) if (HERE / "sources.json").exists() else {}
    pins: dict = {"lii": cfg["lii"]["name"], "acts": {}, "laws": {}, "listings": {}}
    law_uris: set[str] = set()
    law_titles: dict[str, str] = {}
    for act in cfg["acts"]:
        work = act["work"]
        caps = expressions(cfg, work)
        old = prev.get("acts", {}).get(work, {}).get("expressions", {})
        ex = {}
        skipped = act.get("skip", {})
        for day, lst in caps.items():
            if day in skipped:  # left out on purpose (acts.json "skip" gives the reason; parse.py prints it)
                continue
            if day in old and (CACHE / hashlib.sha256(old[day]["url"].encode()).hexdigest()).exists():
                ex[day] = old[day]  # keep the pinned capture
                continue
            got = best(cfg, work, day, lst, act.get("max_tries", 6))
            if got:
                ex[day] = got
        pins["acts"][work] = {"expressions": ex, "skipped": sorted(skipped)}
        print(f"{work}: {len(ex)}/{len(caps)} expressions archived and good: {sorted(ex)}", flush=True)
        info = peachjam.page_info(wayback.fetch(ex[max(ex)]["url"], CACHE))
        for item in info["timeline"]:
            for ev in item["events"]:
                for href, title in ev["links"]:
                    if href and "/akn/" in href and "@" not in href:
                        u = re.sub(r"^/[a-z]{2}(?=/akn/)", "", href)
                        law_uris.add(u)
                        law_titles.setdefault(u, title)
    for uri in sorted(law_uris):
        work = re.sub(rf"^/akn/{cfg['lii']['cc']}/act/", "", uri)
        if work in pins["acts"]:
            continue
        if uri in prev.get("laws", {}) and prev["laws"][uri] and prev["laws"][uri].get("title_checked"):
            pins["laws"][uri] = prev["laws"][uri]
            continue
        pins["laws"][uri] = law_page(cfg, work, law_titles.get(uri, ""))
        got = pins["laws"][uri]
        print(f"law {uri}: {'archived ' + got['expression'] if got else 'no archived page'}", flush=True)
    pins["retrieved"] = cfg["retrieved"]
    tmp = HERE / "sources.json.tmp"
    tmp.write_text(json.dumps(pins, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(HERE / "sources.json")


if __name__ == "__main__":
    main()
