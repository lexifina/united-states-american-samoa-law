"""Build Eswatini's corpus.json from the cache only, through the shared Peachjam adapter.

    python -X utf8 scripts/eswatini-law/parse.py

Reads acts.json (configuration), sources.json (pinned Wayback captures, written by fetch.py) and .cache/; writes
corpus.json (atomically) and verification.json (the checks). Deterministic: the same cache gives the same bytes.
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

corpus, report = peachjam.parse(HERE)

import lii  # noqa: E402  (local: dates of the PDF-only amending Acts, see lii.py)

lii.enrich(peachjam, corpus, report)
peachjam.write_corpus(HERE, corpus)
peachjam.write_docs(HERE, corpus)
# Local: the README names what is missing (FANOUT rule), appended after the adapter's generated README.
MISSING = """
## What is missing

- **The Employment Act 1980, the Companies Act 2009 and most other acts.** EswatiniLII's only archived version with text of each is dated 1 December 1998 and marked "Consolidation", even for Acts of 2009, so that date is a placeholder and cannot date the text. Most other acts have one version only.
- **The Gazette.** EswatiniLII's Gazette copies (Swaziland Government Gazette Extraordinary 73 of 26 July 2005 for the Constitution; Gazettes 99 of 2017 and 118 of 2016 for the amending Acts) are not archived as text, and scans are not read (no OCR). EswatiniLII itself notes that the original publication of the Constitution and of the Money Laundering Act 2011 "is not available and this content could not be verified".
- **The amending Acts' own text.** Act 11 of 2017 and Act 5 of 2016 are PDF-only on EswatiniLII; their dates come from their History tabs.
"""
readme = HERE / "repo" / "README.md"
t = readme.read_text(encoding="utf-8")
if "## What is missing" not in t:
    t = t.replace("\n## How it is built", MISSING + "\n## How it is built", 1)
    readme.write_text(t, encoding="utf-8", newline="\n")
(HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(peachjam.summary(corpus, report), indent=1))
