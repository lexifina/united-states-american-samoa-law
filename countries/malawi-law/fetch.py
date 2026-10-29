"""Fetch Malawi's configured acts (acts.json): Common Crawl first, the Internet Archive for the gaps (lii.py).

    python -X utf8 scripts/malawi-law/fetch.py

Page parsing is the shared Peachjam adapter (canonical copy: scripts/africa-law/peachjam.py; this folder carries the
exact copy it was built with); archive access is scripts/gitlaw_common/wayback.py. No MalawiLII page is fetched.
Cache: .cache/ (sha256 of the URL or Common Crawl record key), every request in .cache/requests.jsonl.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for src in (HERE.parent / "africa-law" / "peachjam.py", HERE.parent / "gitlaw_common" / "wayback.py"):
    if src.exists() and (not (HERE / src.name).exists() or src.read_bytes() != (HERE / src.name).read_bytes()):
        shutil.copyfile(src, HERE / src.name)
sys.path.insert(0, str(HERE))
import lii  # noqa: E402

lii.fetch(HERE)
