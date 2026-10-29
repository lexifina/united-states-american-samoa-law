"""Fetch batch 5 (Estatuto Tributario, Ley 80 de 1993, Estatuto del Consumidor, Código Nacional de Tránsito) and the
basedoc pages of the acts that amended them. Same cache, log, User-Agent and curl (--compressed) as ../fetch.py; reuses
phase2/fetch_phase2.py and batch3/fetch_batch3.py, at ../fetch.py's own pacing (at least 1.05 s between requests to one
host; the coordinator's SPEED RULE allows up to 3 a second for direct official sources).

Usage:  python -X utf8 batch5/fetch_batch5.py docs | laws | url <url>... | colp <page name>...
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "batch3"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase2"))
import fetch_batch3 as B3  # noqa: E402

P2 = B3.P2
P2.get = P2._orig_get
P2.F.get = P2._orig_get
P2.DOCS = ["estatuto_tributario", "ley_0080_1993", "ley_1480_2011", "ley_0769_2002"]

if __name__ == "__main__":
    if sys.argv[1:2] == ["colp"]:
        B3.colp(sys.argv[2:])
    else:
        P2.main(sys.argv[1:])
