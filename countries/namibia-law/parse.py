"""Build Namibia's corpus.json from the cache only, through the shared Peachjam adapter.

    python -X utf8 scripts/namibia-law/parse.py

Reads acts.json (configuration), sources.json (pinned Wayback captures, written by fetch.py) and .cache/; writes
corpus.json (atomically) and verification.json (the checks). Deterministic: the same cache gives the same bytes.

One local correction to the adapter's output (scripts/africa-law/ISSUES-namibia.md, item 4): when an act's oldest
NamibLII expression already takes in an amending law on its own day, that law is named in `earlier_laws` and the
first version's note says so, instead of "the act as published".
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "africa-law" / "peachjam.py"
if SHARED.exists() and (not (HERE / "peachjam.py").exists()
                        or SHARED.read_bytes() != (HERE / "peachjam.py").read_bytes()):
    shutil.copyfile(SHARED, HERE / "peachjam.py")
sys.path.insert(0, str(HERE))
import peachjam  # noqa: E402


def same_day_amendments(corpus: dict) -> None:
    cfg = peachjam.load_config(HERE)
    pins = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    cache = peachjam.Cache(HERE, offline=True)
    by_slug = {a["slug"]: a for a in cfg["acts"]}
    for act in corpus["acts"]:
        if act["first_law"]:
            continue
        ex = pins["acts"][by_slug[act["slug"]]["work"]]["expressions"]
        first_day = min(ex)
        latest = peachjam.page_info(cache.get(ex[max(ex)]["url"]))
        amend_text = {re.sub(r"^/[a-z]{2}(?=/akn/)", "", a["uri"] or ""): a["text"] for a in latest["amendments"]}
        same = []
        for t in latest["timeline"]:
            if t["date"] != first_day:
                continue
            for e in t["events"]:
                if e["kind"] != "amended" or e["unapplied"]:
                    continue
                for href, title in e["links"]:
                    if href and "/akn/" in href and "@" not in href:
                        uri = re.sub(r"^/[a-z]{2}(?=/akn/)", "", href)
                        key = peachjam.law_key(uri)
                        if key not in corpus["laws"]:
                            corpus["laws"][key] = {
                                "label": peachjam.label_from(amend_text.get(uri, ""), uri), "title": title,
                                "kind": peachjam.kind_of_law(uri), "enacted": None, "published": None,
                                "url": f"https://{cfg['lii']['hosts'][0]}{uri}", "temporary_until": None,
                                "restores": None, "note": None}
                        same.append(key)
        if not same:
            continue
        for k in same:
            if k not in act["earlier_laws"]:
                act["earlier_laws"].append(k)
        v0 = act["versions"][0]
        labels = ", ".join(f"{corpus['laws'][k]['title']} ({corpus['laws'][k]['label']})" for k in same)
        v0["note"] = (f"The NamibLII version of {first_day}, the oldest it publishes: the act as amended up to and "
                      f"including {labels}, which took effect that day.")
    corpus["laws"] = dict(sorted(corpus["laws"].items()))


BASIC_KEY = re.compile(r"^(?:[a-z0-9-]*-)?(?:art|sec|sch|rule|reg)-")


def editorial_only(corpus: dict) -> list[str]:
    """Drop units that are only a NamibLII editorial note on a container, not law: the Constitution's preface holds
    only a commencement note on the Second Amendment Act, and Chapters 10A and 10B only "[Chapter 10A ... is inserted
    by ...]" (the adapter keys these 'long-title', 'text', 'text-2'). A provision (art-, sec-, sch-) whose only text is
    its note stays: that is a repealed provision as the LII prints it."""
    dropped = []
    for act in corpus["acts"]:
        for v in act["versions"]:
            for field in ("units", "changes"):
                for k, u in list((v.get(field) or {}).items()):
                    if u is None or BASIC_KEY.match(k):
                        continue
                    body = u["text"].rstrip("\n").split("\n")[1:]
                    if body and body[0].startswith("[") and body[-1].endswith("]"):
                        del v[field][k]
                        v.get("credits", {}).pop(k, None)
                        dropped.append(f"{act['slug']}@{v['from']}:{k}")
    return dropped


corpus, report = peachjam.parse(HERE)
same_day_amendments(corpus)
report["editorial_only_dropped"] = editorial_only(corpus)
for attempt in range(10):  # autopush may be reading corpus.json at the moment of the rename (Windows)
    try:
        peachjam.write_corpus(HERE, corpus)
        break
    except PermissionError:
        time.sleep(2)
else:
    raise SystemExit("corpus.json is locked")
peachjam.write_docs(HERE, corpus)
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
