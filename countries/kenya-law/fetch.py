"""Fetch Kenya's configured acts (acts.json) through the shared Peachjam adapter.

    python -X utf8 scripts/kenya-law/fetch.py

All the work is in peachjam.py (canonical copy: scripts/africa-law/peachjam.py; this folder carries the exact copy it
was built with). Network: the Wayback Machine CDX API and raw (`id_`) captures of Kenya Law expression pages, plus
Kenya Law's open listing page. Cache: .cache/ (sha256 of the URL), every request in .cache/requests.jsonl.
"""
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

peachjam.fetch(HERE)
