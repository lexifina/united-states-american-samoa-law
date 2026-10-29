"""Build Ghana's corpus from the cache only.

    python -X utf8 scripts/ghana-law/parse.py

- corpus.json: the GhaLII acts configured in acts.json, through the shared Peachjam adapter (peachjam.py, vendored
  read-only copy of scripts/africa-law/peachjam.py), with verification.json and repo/README.md + repo/LICENSE.
- corpus.d/10-constitution.json: the Constitution of 1992, from two government-hosted PDFs (constitution.py), which
  is not a GhaLII text and is kept in its own part (see README.extra.md).
Reads acts.json, sources.json (pinned archive captures, written by fetch.py) and .cache/. Deterministic.
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "africa-law" / "peachjam.py"
if SHARED.exists() and (not (HERE / "peachjam.py").exists()
                        or SHARED.read_bytes() != (HERE / "peachjam.py").read_bytes()):
    shutil.copyfile(SHARED, HERE / "peachjam.py")
sys.path.insert(0, str(HERE))
import constitution  # noqa: E402
import peachjam  # noqa: E402


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


corpus, report = peachjam.parse(HERE)
act, laws, decisions, crep = constitution.build(HERE)
report["constitution"] = crep
part = {
    "sources": [s for s in json.loads((HERE / "acts.json").read_text(encoding="utf-8"))["sources"]
                if "osp.gov.gh" in s["url"] or "audit.gov.gh" in s["url"]],
    "laws": laws,
    "acts": [act],
    "decisions": decisions,
}
# the two government PDFs are this part's sources; the GhaLII sources stay with corpus.json
corpus["sources"] = [s for s in corpus["sources"] if s not in part["sources"]]
peachjam.write_corpus(HERE, corpus)
write_atomic(HERE / "corpus.d" / "10-constitution.json", part)
peachjam.write_docs(HERE, corpus)
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8",
                                        newline="\n")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
print(json.dumps({"constitution": {"versions": [v["from"] for v in act["versions"]], "units": crep["units"],
                                   "changed": crep["changed"]}}, indent=1))
