"""Build Lesotho's corpus from the cache only.

    python -X utf8 scripts/lesotho-law/parse.py

1. The shared Peachjam adapter (peachjam.py; canonical copy scripts/africa-law/peachjam.py, this folder carries the
   exact copy it was built with) reads acts.json, sources.json (pinned archived captures, written by fetch.py) and
   .cache/, for the acts on LesLII's current site.
2. lii.py rebuilds the start of any act whose page gives several commencement dates (staged commencement).
3. constitution.py writes corpus.d/10-constitution.json: the Constitution of 1993 from LesLII's earlier website.
Writes corpus.json (atomically), corpus.d/10-constitution.json, repo/README.md and repo/LICENSE, and
verification.json (the checks). Deterministic: the same cache gives the same bytes.
"""
import json
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
import lii  # noqa: E402
import constitution  # noqa: E402

corpus, report = peachjam.parse(HERE)
lii.stage(HERE, corpus, report)
lii.unapplied(HERE, corpus)
constitution.write(constitution.parse())
peachjam.write_corpus(HERE, corpus)
peachjam.write_docs(HERE, corpus)
lii.fix_readme(HERE)
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
