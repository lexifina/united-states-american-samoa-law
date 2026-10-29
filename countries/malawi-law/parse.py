"""Build Malawi's corpus.json from the cache only, through the shared Peachjam adapter.

    python -X utf8 scripts/malawi-law/parse.py

Reads acts.json (configuration), sources.json (pinned archive copies, written by fetch.py) and .cache/; writes
corpus.json (atomically), repo/README.md, repo/LICENSE and verification.json (the checks). Deterministic: the same
cache gives the same bytes.

Malawi-specific steps after peachjam.parse (lii.py explains why): a version read from Common Crawl gets a source_url
naming the WARC file and byte range, and the adapter's wording about where copies come from is corrected to name both
archives. The current-expression check reads archived MalawiLII listing pages (listing.py), not MalawiLII itself.
"""
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for src in (HERE.parent / "africa-law" / "peachjam.py", HERE.parent / "gitlaw_common" / "wayback.py"):
    if src.exists() and (not (HERE / src.name).exists() or src.read_bytes() != (HERE / src.name).read_bytes()):
        shutil.copyfile(src, HERE / src.name)
sys.path.insert(0, str(HERE))
import peachjam  # noqa: E402

IA_NO_COPY = "the Internet Archive holds no copy"
BOTH_NO_COPY = "neither Common Crawl nor the Internet Archive holds a copy with its text"
README_SUBS = [
    ("MalawiLII's document pages answer automated clients with a bot challenge, so `tools/fetch.py` reads each "
     "expression page from its latest Internet Archive capture (the raw `id_` form), found through the Wayback CDX "
     "index, with curl,",
     "MalawiLII's terms prohibit scraping and bulk downloading, so no MalawiLII page is fetched: `tools/fetch.py` "
     "(with `tools/lii.py`) reads each expression page from its newest archived copy that carries the text, Common "
     "Crawl first (found through its index, read by byte range from the WARC file), else the Internet Archive (the "
     "raw `id_` form, found through the Wayback CDX index), with curl,"),
    ("| [Internet Archive](https://web.archive.org/) | Archived copies of those expression pages | Reading them |",
     "| [Common Crawl](https://commoncrawl.org/) and the [Internet Archive](https://web.archive.org/) | Archived "
     "copies of those expression pages and of MalawiLII's listing pages | Reading them |"),
    ("its listing page names the current version |", "its listing pages name the current version |"),
]


def cc_url(key: str) -> str:
    _, warc, off, length = key.split(":", 3)
    return f"https://data.commoncrawl.org/{warc}#bytes={off}-{int(off) + int(length) - 1}"


def first_version_fix(corpus: dict) -> None:
    """Workaround for ISSUES-malawi.md #1. When the oldest archived expression is not the act's original expression
    but one made by an amendment on that day, peachjam.parse notes it as "the act as published" and names no earlier
    law. Name the amendment(s) of that day as earlier laws and say which original expression is missing."""
    cfg = peachjam.load_config(HERE)
    pins = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    cache = peachjam.Cache(HERE, offline=True)
    by_slug = {a["slug"]: a for a in cfg["acts"]}
    lii = cfg["lii"]["name"]
    for act in corpus["acts"]:
        if act["first_law"]:
            continue
        work = by_slug[act["slug"]]["work"]
        ex = pins["acts"][work]["expressions"]
        info = peachjam.page_info(cache.get(ex[max(ex)]["url"]))
        v0 = act["versions"][0]
        day = min(ex)
        same_day = [a for a in info["amendments"] if a["date"] == day and a["uri"]]
        if not same_day or v0["from"] != day:
            continue
        older = sorted(t["date"] for t in info["timeline"] if t["read"] and t["date"] < day)
        names = []
        for a in same_day:
            uri = re.sub(r"^/[a-z]{2}(?=/akn/)", "", a["uri"])
            key = peachjam.law_key(uri)
            title = re.sub(r"\s*\([^()]*\)\s+on\s+[^()]*$", "", a["text"].strip("[]").removeprefix("Amended by "))
            corpus["laws"].setdefault(key, {"label": peachjam.label_from(a["text"], uri), "title": title,
                                            "kind": peachjam.kind_of_law(uri), "enacted": None, "published": None,
                                            "url": f"https://{cfg['lii']['hosts'][0]}{uri}", "temporary_until": None,
                                            "restores": None, "note": None})
            if key not in act["earlier_laws"]:
                act["earlier_laws"].append(key)
            names.append(f"{corpus['laws'][key]['title']} ({corpus['laws'][key]['label']})")
        miss = (f"; {lii}'s earlier expression(s) {', '.join(older)} have no archived copy with their text"
                if older else "")
        v0["note"] = (f"The {lii} version of {day}, which takes in the {' and '.join(names)}: the oldest version "
                      f"archived{miss}.")
    corpus["laws"] = dict(sorted(corpus["laws"].items()))


corpus, report = peachjam.parse(HERE)
first_version_fix(corpus)
for act in corpus["acts"]:
    for v in act["versions"]:
        if v["source_url"].startswith("cc:"):
            v["source_url"] = cc_url(v["source_url"])
corpus["decisions"] = [d.replace(IA_NO_COPY, BOTH_NO_COPY) for d in corpus["decisions"]]
extra = HERE / "decisions.json"
if extra.exists():
    corpus["decisions"] += json.loads(extra.read_text(encoding="utf-8"))
check = HERE / "listing_check.json"
if check.exists():
    report["listing"] = json.loads(check.read_text(encoding="utf-8"))
peachjam.write_corpus(HERE, corpus)
peachjam.write_docs(HERE, corpus)
readme = HERE / "repo" / "README.md"
t = readme.read_text(encoding="utf-8")
for a, b in README_SUBS:
    t = t.replace(a, b)
if check.exists():
    lc = json.loads(check.read_text(encoding="utf-8"))
    caps = sorted(v["capture"][:8] for v in lc.values() if v.get("capture"))
    ok = all(v["ok"] for v in lc.values())
    t = re.sub(r"- \*\*Against MalawiLII today:\*\*[^\n]*",
               "- **Against MalawiLII's current text:** the last version of each act is the expression MalawiLII's own "
               "legislation listing names as current, in its newest archived copies (Internet Archive captures of "
               f"{caps[0][:4]}-{caps[0][4:6]}-{caps[0][6:]} to {caps[-1][:4]}-{caps[-1][4:6]}-{caps[-1][6:]}; "
               f"{'all match' if ok else 'see listing_check.json'}), and is the text of that expression page.", t)
readme.write_text(t, encoding="utf-8", newline="\n")
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                        newline="\n")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
