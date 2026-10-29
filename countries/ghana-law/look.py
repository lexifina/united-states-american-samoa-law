"""Probe helper: list the archived GhaLII expressions of some works and print each latest page's History and notices.

    python -X utf8 -I scripts/ghana-law/look.py 2012/843 2003/651 ...
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "africa-law"))
import peachjam  # noqa: E402

cfg = {"lii": {"name": "GhaLII", "hosts": ["ghalii.org"], "cc": "gh", "path_prefixes": [""]}}
cache = peachjam.Cache(HERE)
for work in sys.argv[1:]:
    caps = peachjam.captures(cfg, cache, work)
    print("==", work, {d: len(v) for d, v in caps.items()})
    for day in sorted(caps)[-1:]:
        for ts, orig in caps[day][:3]:
            u = peachjam.raw(ts, orig)
            b = cache.get(u)
            ok = peachjam.good_expression_page(b, f"/akn/gh/act/{work}/eng@{day}")
            print(" ", day, ts, "good" if ok else "BAD", len(b))
            if not ok:
                continue
            info = peachjam.page_info(b)
            print("  title:", info.get("title"))
            for n in info["notices"]:
                print("  notice:", n["text"][:300])
            for a in info["amendments"]:
                print("  amendment:", a["text"][:200])
            for t in info["timeline"]:
                print("  history:", t["date"], [(e["kind"], e["text"][:120], e["unapplied"]) for e in t["events"]],
                      "read" if t["read"] else "")
            print("  unapplied notice:", info["unapplied_notice"][:3])
            units, refs = peachjam.units_of(b)
            print("  units:", len(units), list(units)[:5], "...", list(units)[-3:])
            break
