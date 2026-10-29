"""Check today's text (the last version of each act in corpus.json) against the LiberLII page it was parsed from.

Word multisets, both ways, after the same normalisation parse.py uses:
- added:       words in the repository's latest version that the source page does not print (must be 0, apart from
               the '#' heading marks and words of the version-specific marker lines listed in ALLOWED);
- unaccounted: words the source page prints that the latest version does not hold (the Contents list, the chapter
               lists of sections, the earlier § 14.70 text and the annotations parse.py moves to notes are expected).

    python -X utf8 verify.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import parse  # noqa: E402

WORD = re.compile(r"[A-Za-z]+|[0-9]+")  # "Article11" in the source reads as "Article 11"
# Headings parse.py names itself (the source prints the list with no heading of its own).
ALLOWED = Counter({"signatories": 1, "enactment": 1})


def words(s: str) -> Counter:
    return Counter(w.lower() for w in WORD.findall(s))


def latest(act: dict) -> dict:
    units: dict = {}
    for v in act["versions"]:
        if "units" in v:
            units = dict(v["units"])
        for k, u in (v.get("changes") or {}).items():
            if u is None:
                units.pop(k, None)
            else:
                units[k] = u
    return units


def main() -> int:
    c = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    src = {"constitution": "constitution", "penal-law": "penal-law", "freedom-of-information-act": "foi-act"}
    bad = 0
    for act in c["acts"]:
        units = latest(act)
        repo = Counter()
        for u in units.values():
            repo += words(u["text"])
        page = Counter()
        for _bold, line in parse.blocks(parse.raw(src[act["slug"]])):
            page += words(line)
        added = repo - page - ALLOWED
        unacc = page - repo
        print(f"{act['slug']}: {sum(repo.values())} words; added {sum(added.values())} {dict(added.most_common(12))}; "
              f"unaccounted {sum(unacc.values())} {dict(unacc.most_common(12))}")
        if added:
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
