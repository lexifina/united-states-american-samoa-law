"""Build Tanzania's corpus from the cache only.

    python -X utf8 scripts/tanzania-law/parse.py

- corpus.json: the TanzLII acts (acts.json), through the shared Peachjam adapter (scripts/africa-law/peachjam.py,
  read-only; a byte-identical copy is kept in this folder so the repository ships the exact adapter it was built with),
  except the acts in UNVERIFIED below;
- corpus.d/50-unverified.json: those acts, whose newest archived version is not TanzLII's current expression (no
  .PUBLISH, so they reach the preview branch only).
- corpus.d/10-constitution.json is written by constitution.py, not here: the Constitution in English, from the
  official revised English version published by the Ministry of Constitutional and Legal Affairs (TanzLII has only the
  Kiswahili text). It has no .PUBLISH (see PROGRESS.md), so it reaches the preview branch only.
Also writes verification.json (the checks) and repo/README.md, repo/LICENSE. Deterministic: same cache, same bytes.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "africa-law"
sys.path.insert(0, str(HERE))
if (SHARED / "peachjam.py").exists():
    sys.path.insert(0, str(SHARED))
import peachjam  # noqa: E402

# Acts whose newest archived version is not the expression TanzLII's own listing names as current (2026-10-28).
# They go to corpus.d/50-unverified.json, which has no .PUBLISH: they stream to the preview branch only, and main
# (corpus.json) holds only acts verified against TanzLII's current expression.
UNVERIFIED = {
    "employment-labour-relations": "TanzLII's listing names 2025-03-14 as current, an expression the Internet Archive "
                                   "does not hold; the newest archived one is 2023-12-31.",
    "civil-procedure-code": "TanzLII's listing names 2021-10-22 as current, older than the newest archived expression "
                            "(2024-10-04), so which text is current cannot be confirmed.",
    "basic-rights-duties-enforcement": "TanzLII's listing names 2023-12-31 as current, older than the newest archived "
                                       "expression (2025-03-14), and 2023-12-31 is not archived.",
}


def laws_used(acts: list) -> set:
    used = set()
    for a in acts:
        used.update([a["first_law"]] if a.get("first_law") else [])
        used.update(a.get("earlier_laws", []))
        for v in a["versions"]:
            for ks in v.get("credits", {}).values():
                used.update(ks)
    return used


def split(corpus: dict) -> tuple[dict, dict]:
    keep = [a for a in corpus["acts"] if a["slug"] not in UNVERIFIED]
    held = [a for a in corpus["acts"] if a["slug"] in UNVERIFIED]
    held_short = tuple(f"{a['short']}:" for a in held)
    main = dict(corpus)
    main["acts"] = keep
    only_held = laws_used(held) - laws_used(keep)
    main["laws"] = {k: v for k, v in corpus["laws"].items() if k not in only_held}
    main["applies"] = [x for x in corpus["applies"] if x["law"] in main["laws"]]
    main["decisions"] = [d for d in corpus["decisions"] if not d.startswith(held_short)] + [
        "Held back from this history (kept on the preview branch only, in corpus.d/50-unverified.json, until each can be "
        "verified): " + " ".join(f"{a['title']}: {UNVERIFIED[a['slug']]}" for a in held)]
    part = {"acts": held,
            "laws": {k: v for k, v in corpus["laws"].items() if k in laws_used(held)},
            "applies": [x for x in corpus["applies"] if x["law"] not in main["laws"]],
            "decisions": [d for d in corpus["decisions"] if d.startswith(held_short)] + [
                f"{a['short']}: not verified against TanzLII's current text: {UNVERIFIED[a['slug']]}" for a in held]}
    return main, part


peachjam.vendor(HERE)
corpus, report = peachjam.parse(HERE)
corpus, unverified = split(corpus)
peachjam.write_corpus(HERE, corpus)
(HERE / "corpus.d").mkdir(exist_ok=True)
tmp = HERE / "corpus.d" / "50-unverified.json.tmp"
tmp.write_text(json.dumps(unverified, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
tmp.replace(HERE / "corpus.d" / "50-unverified.json")
peachjam.write_docs(HERE, corpus)
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                        newline="\n")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
