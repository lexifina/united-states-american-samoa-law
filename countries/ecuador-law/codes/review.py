"""Research helper: print each version's changes of one act in a corpus part as a line diff (reading the part only).

    python -X utf8 codes/review.py <part.json> [law-key-regex]
"""
from __future__ import annotations

import difflib
import json
import re
import sys


def main(path: str, pat: str = ".") -> None:
    part = json.loads(open(path, encoding="utf-8").read())
    for act in part["acts"]:
        units = dict(act["versions"][0]["units"])
        for v in act["versions"][1:]:
            laws = sorted({l for ls in v["credits"].values() for l in ls})
            show = any(re.search(pat, l) for l in laws)
            if show:
                print(f"=== {v['from']} {' '.join(laws)}")
            for k, new in (v.get("changes") or {}).items():
                old = units.get(k)
                if show:
                    a = old["text"].splitlines() if old else []
                    b = new["text"].splitlines() if new else []
                    print(f"--- {k}" + (" (removed)" if new is None else " (new)" if old is None else ""))
                    for line in difflib.unified_diff(a, b, lineterm="", n=0):
                        if not line.startswith(("---", "+++", "@@")):
                            print("   " + line)
                if new is None:
                    units.pop(k, None)
                else:
                    units[k] = new
            if show and not v.get("changes"):
                print("   (no change of words) " + ", ".join(v["credits"]))


if __name__ == "__main__":
    main(*sys.argv[1:])
