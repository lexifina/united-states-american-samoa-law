"""Current-expression check for Malawi from archived MalawiLII listing pages (no MalawiLII page is fetched).

    python -X utf8 scripts/malawi-law/listing.py

MalawiLII's legislation listing (/legislation/, /legislation/?page=N, /legislation/all) names each work's current
expression date. This reads the newest Internet Archive capture of each listing URL (through gitlaw_common/wayback.py),
takes for each configured act the date given by the newest capture that names it, and writes listing_check.json:
{work: {"lii_current", "listing", "capture", "ours", "ok"}}. parse.py copies it into verification.json.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import peachjam  # noqa: E402
import wayback  # noqa: E402

CACHE = HERE / ".cache"
NEWEST = 2  # captures per listing URL, newest first


def entries(t: str, uri: str) -> list[str]:
    """Expression dates a listing page gives for the work uri (JSON rows, or links to the expression)."""
    out = re.findall(rf'"date":\s*"(\d{{4}}-\d{{2}}-\d{{2}})",\s*"work_frbr_uri":\s*"{re.escape(uri)}"', t)
    out += re.findall(rf'href="(?:/[a-z]{{2}})?{re.escape(uri)}/eng@(\d{{4}}-\d{{2}}-\d{{2}})"', t)
    return out


def main() -> dict:
    cfg = peachjam.load_config(HERE)
    host = cfg["lii"]["hosts"][0]
    rows = wayback.captures(f"{host}/legislation", match="prefix", cache=CACHE, collapse=None)
    by_url: dict[str, list[str]] = {}
    for r in rows:
        u = re.sub(r"^https?://(www\.)?", "https://", r["original"])
        if "html" in r["mimetype"] and re.search(r"/legislation/?(all)?/?(\?page=\d+)?$", u):
            by_url.setdefault(u, []).append(r["timestamp"])
    pages = sorted(((ts, u) for u, tss in by_url.items() for ts in sorted(tss)[-NEWEST:]), reverse=True)
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    want = {a["work"]: peachjam.work_uri(cfg, a["work"]) for a in cfg["acts"]}
    found: dict[str, dict] = {}
    for ts, u in pages:
        if len(found) == len(want):
            break
        b = wayback.get(u, ts=ts, cache=CACHE)
        if not b:
            continue
        t = b.decode("utf-8", "replace")
        for work, uri in want.items():
            ds = entries(t, uri)
            if work not in found and ds:
                found[work] = {"lii_current": max(ds), "listing": u, "capture": ts}
    out = {}
    for work in want:
        ex = sources["acts"].get(work, {}).get("expressions", {})
        ours = max(ex) if ex else None
        f = found.get(work, {"lii_current": None, "listing": None, "capture": None})
        out[work] = {**f, "ours": ours, "ok": bool(f["lii_current"] and f["lii_current"] == ours)}
    tmp = HERE / "listing_check.json.tmp"
    tmp.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    tmp.replace(HERE / "listing_check.json")
    return out


if __name__ == "__main__":
    print(json.dumps(main(), indent=1))
