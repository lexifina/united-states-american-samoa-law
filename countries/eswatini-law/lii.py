"""Eswatini's local extension of the shared Peachjam adapter (scripts/africa-law/peachjam.py, which is not edited).

Amending Acts on EswatiniLII are PDF-only pages: their archived pages carry no Akoma Ntoso text, so the adapter's
good_expression_page() rejects them and the laws get no dates. Their History tab is still on the page, and it gives
the dates the corpus needs: "Assented to" (enacted), "Published in ... Gazette ..." (published) and "Commenced".

    law_pages.json   written by fetch.py: {law uri: {"url", "capture", "sha256"}} for each pinned capture
    enrich(...)      used by parse.py: fills enacted/published from those pages and checks each law's commencement
                     against the version dates it is credited on

The adapter could adopt this: accept a law page without akn text for law_meta when the History tab is present.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def fetch_law_pages(cfg: dict) -> dict:
    sys.path.insert(0, str(HERE.parent / "gitlaw_common"))
    import wayback  # noqa: PLC0415
    out = {}
    for uri, pin in sorted(cfg.get("law_pages_pinned", {}).items()):
        url = f"https://web.archive.org/web/{pin['capture']}id_/https://eswatinilii.org{uri}/eng@{pin['expression']}"
        b = wayback.fetch(url, HERE / ".cache")
        if not b:
            print("law page not fetched:", url)
            continue
        out[uri] = {"url": url, "capture": pin["capture"], "expression": pin["expression"],
                    "sha256": hashlib.sha256(b).hexdigest()}
    tmp = HERE / "law_pages.json.tmp"
    tmp.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    tmp.replace(HERE / "law_pages.json")
    return out


def law_dates(peachjam, b: bytes) -> dict:
    """{enacted, published, published_text, commenced} from a law page's History tab."""
    pi = peachjam.page_info(b)
    out: dict = {"expression": pi.get("expression")}
    for t in pi["timeline"]:
        for e in t["events"]:
            if e["text"].startswith("Assented to"):
                out["enacted"] = t["date"]
            elif e["text"].startswith("Published in"):
                out["published"] = t["date"]
                out["published_text"] = e["text"]
            elif e["kind"] == "commenced" and e["text"] == "Commenced":
                out["commenced"] = t["date"]
    return out


def enrich(peachjam, corpus: dict, report: dict) -> None:
    pins = json.loads((HERE / "law_pages.json").read_text(encoding="utf-8"))
    cache = peachjam.Cache(HERE, offline=True)
    used: dict[str, set] = {}
    for a in corpus["acts"]:
        for v in a["versions"]:
            for ks in v.get("credits", {}).values():
                for k in ks:
                    used.setdefault(k, set()).add(v["from"])
    for uri, pin in sorted(pins.items()):
        b = cache.get(pin["url"])
        if hashlib.sha256(b).hexdigest() != pin["sha256"]:
            raise SystemExit(f"law page changed in cache: {pin['url']}")
        key = peachjam.law_key(uri)
        d = law_dates(peachjam, b)
        if d.get("expression") != f"{uri}/eng@{pin['expression']}":
            raise SystemExit(f"not the expected law page: {pin['url']}")
        law = corpus["laws"].get(key)
        if law is None:
            continue
        law["enacted"] = d.get("enacted") or law["enacted"]
        law["published"] = d.get("published") or law["published"]
        ok = sorted(used.get(key, [])) == ([d["commenced"]] if d.get("commenced") else [])
        report.setdefault("law_dates", {})[key] = {"commenced": d.get("commenced"), "dated": sorted(used.get(key, [])),
                                                    "ok": ok, "page": pin["url"]}
        corpus["decisions"].append(
            f"{law['label']} ({law['title']}): its EswatiniLII page has no text (PDF only), so its dates come from the "
            f"page's History tab ({pin['url']}): assented to {d.get('enacted')}, "
            f"\"{d.get('published_text')}\" on {d.get('published')}, commenced {d.get('commenced')}; its changes are "
            f"dated {', '.join(sorted(used.get(key, []))) or 'nowhere'}"
            + (", the same day." if ok else ", which differs: see verification.json."))
