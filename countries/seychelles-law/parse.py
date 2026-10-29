"""Build Seychelles' corpus.json from the cache only, through the shared Peachjam adapter.

    python -X utf8 scripts/seychelles-law/parse.py

Reads acts.json (configuration), sources.json (pinned Wayback captures, written by fetch.py) and .cache/; writes
corpus.json (atomically) and verification.json (the checks). Deterministic: the same cache gives the same bytes.

After peachjam.parse() it applies three Seychelles-specific steps (candidates for the shared adapter):
1. expressions left out on purpose (acts.json "skip": {date: reason}) get their reason in `decisions` and in the next
   version's note, in place of the adapter's generic "the Internet Archive holds no copy";
2. an amending law whose archived page loads its text by script has no coverpage notices; its assent and publication
   dates are then read from the History tab of that same page ("Assented to", "Published in ...");
3. the Constitution of 1993 is SeyLII work si/1993/38 (S.I. series), which the adapter would call a decree; it is
   recorded as kind "law".
Then two text clean-ups (clean()) and one split (split_parts()):
4. a line that is only a paragraph number ("(8)", "14.") or only a quoted defined term ('"interment"') is what is left
   of a subprovision whose whole printed content was an editorial remark ("[clause (8) ... repealed by ...]"), which
   the adapter drops inside a provision; such lines are removed, so a repealed subprovision is simply absent;
5. an en dash that is not between two digits (the Licences Act's chapeaux, "In this Act–") becomes an em dash, the
   form every other act and later expression uses, so a change of typesetting is not a change of wording;
6. acts that acts.json gives a "part" (with a "held_back" reason) go to corpus.d/<part>.json instead of corpus.json:
   they stream to the preview branch but reach main only if their own corpus.d/<part>.PUBLISH is written.
repo/README.md describes only corpus.json (what main holds); README.extra.md adds the country notes.
"""
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
import peachjam  # noqa: E402


def post(corpus: dict, report: dict) -> None:
    cfg = peachjam.load_config(HERE)
    pins = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    cache = peachjam.Cache(HERE, offline=True)
    by_slug = {a["slug"]: a for a in corpus["acts"]}
    for act in cfg["acts"]:
        skip = act.get("skip") or {}
        if not skip:
            continue
        days = sorted(skip)
        generic = (f"{act['short']}: the LII lists expression(s) {', '.join(days)}, but the Internet Archive holds no "
                   f"copy, so their changes appear in the next version that is archived.")
        corpus["decisions"] = [d for d in corpus["decisions"] if d != generic]
        for day in days:
            corpus["decisions"].append(f"{act['short']}: {skip[day]}")
            vs = by_slug[act["slug"]]["versions"]
            nxt = next((v for v in vs if v["from"] > day), None)
            if nxt is not None:
                prev = max((v["from"] for v in vs if v["from"] < day), default=None)
                nxt["note"] = (f"SeyLII's {day} consolidation is left out (see REPRODUCE.md, decisions); this version "
                               f"follows the {prev} version directly.")
    # law dates from the History tab of the law's own page, where its coverpage is not in the archived copy
    for uri, p in pins.get("laws", {}).items():
        key = peachjam.law_key(uri)
        if not p or key not in corpus["laws"]:
            continue
        law = corpus["laws"][key]
        if law.get("enacted") and law.get("published"):
            continue
        info = peachjam.page_info(cache.get(p["url"]))
        for t in info["timeline"]:
            for e in t["events"]:
                if not law.get("enacted") and e["text"].startswith("Assented to"):
                    law["enacted"] = t["date"]
                if not law.get("published") and e["text"].startswith("Published"):
                    law["published"] = t["date"]
        if not law.get("title") or law["title"] == corpus["acts"][0]["title"]:
            law["title"] = p.get("title_checked") or law["title"]
    for a in corpus["acts"]:
        if a["slug"] == "constitution" and a.get("first_law"):
            corpus["laws"][a["first_law"]]["kind"] = "law"


RESIDUE = re.compile(r'^(?:\((?:[0-9]+[A-Za-z]*|[a-z]{1,4})\)|[0-9]+[A-Z]?\.|"[^"]+")$')
EN_DASH = re.compile(r'(?<![0-9])–|–(?![0-9])')


def _clean_text(text: str, removed: list) -> tuple[str, int]:
    out, dashes = [], 0
    for ln in text.split("\n"):
        if RESIDUE.match(ln.strip()):
            removed.append(ln.strip())
            continue
        ln, n = EN_DASH.subn("—", ln)
        dashes += n
        out.append(ln)
    return "\n".join(out), dashes


def clean(corpus: dict) -> None:
    """Steps 4 and 5 on every version, then drop changes (and their credits) that the clean-up made empty."""
    for act in corpus["acts"]:
        prev: dict = {}
        log: dict[str, list] = {}
        dashes = 0
        for v in act["versions"]:
            for field in ("units", "changes"):
                for k, u in (v.get(field) or {}).items():
                    if u is not None:
                        removed: list = []
                        u["text"], n = _clean_text(u["text"], removed)
                        dashes += n
                        if removed:
                            log[k] = sorted(set(log.get(k, [])) | set(removed))
            state = dict(v["units"]) if "units" in v else dict(prev)
            if "changes" in v:
                for k, u in list(v["changes"].items()):
                    if u is not None and k in prev and prev[k] == u:
                        del v["changes"][k]  # a typesetting-only change: no change of wording
                        (v.get("credits") or {}).pop(k, None)
                    elif u is None:
                        state.pop(k, None)
                    else:
                        state[k] = u
            prev = state
        if log:
            corpus["decisions"].append(
                f"{act['short']}: lines that held only a number or a quoted term, left over from a subprovision whose "
                f"whole printed content is an editorial remark (SeyLII's '[... repealed by ...]' or its notes to the "
                f"1991 edition), are removed: " + "; ".join(f"{k} {' '.join(v)}" for k, v in sorted(log.items())) + ".")
        if dashes:
            corpus["decisions"].append(
                f"{act['short']}: an en dash not between two digits is printed as an em dash ({dashes} in all "
                f"versions): SeyLII typeset some expressions' chapeaux with en dashes and later ones with em dashes, "
                f"so this is one form of dash, not a change of wording.")


def _laws_of(act: dict) -> set:
    keys = {act.get("first_law")} | set(act.get("earlier_laws") or [])
    for v in act["versions"]:
        for ks in (v.get("credits") or {}).values():
            keys |= set(ks)
    return {k for k in keys if k}


def split_parts(corpus: dict) -> dict:
    """Step 6: {part name: part corpus} for acts held back from main; removes them from `corpus`."""
    cfg = peachjam.load_config(HERE)
    want = {a["slug"]: a for a in cfg["acts"] if a.get("part")}
    parts: dict = {}
    for act in [a for a in corpus["acts"] if a["slug"] in want]:
        c = want[act["slug"]]
        corpus["acts"].remove(act)
        p = parts.setdefault(c["part"], {"acts": [], "laws": {}, "decisions": []})
        p["acts"].append(act)
        p["decisions"].append(f"{act['short']}: held back from main (corpus.d/{c['part']}.json, no .PUBLISH): "
                              f"{c['held_back']}")
        mine = [d for d in corpus["decisions"] if d.startswith(act["short"] + ":")]
        corpus["decisions"] = [d for d in corpus["decisions"] if d not in mine]
        p["decisions"] += mine
    used = set().union(*(_laws_of(a) for a in corpus["acts"])) if corpus["acts"] else set()
    for p in parts.values():
        for act in p["acts"]:
            for k in sorted(_laws_of(act)):
                p["laws"][k] = corpus["laws"][k]
    for p in parts.values():
        for k in list(p["laws"]):
            if k not in used:
                corpus["laws"].pop(k, None)
    return parts


def write_parts(parts: dict) -> None:
    d = HERE / "corpus.d"
    for name, part in sorted(parts.items()):
        d.mkdir(exist_ok=True)
        tmp = d / f"{name}.json.tmp"
        tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        tmp.replace(d / f"{name}.json")


corpus, report = peachjam.parse(HERE)
post(corpus, report)
clean(corpus)
parts = split_parts(corpus)
write_parts(parts)
peachjam.write_corpus(HERE, corpus)
peachjam.write_docs(HERE, corpus)
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
