"""Fetch batch 4 (Código Nacional de Seguridad y Convivencia Ciudadana, Ley 100 de 1993, Código General Disciplinario,
Código Electoral) and the basedoc pages of the acts that amended them. Same cache, log, User-Agent and curl
(--compressed) as ../fetch.py; reuses phase2/fetch_phase2.py and batch3/fetch_batch3.py, with at least 2.1 s between
requests to one host (the Senado's rule for this run: at most 1 request per 2 s).

Usage:  python -X utf8 batch4/fetch_batch4.py docs | laws | url <url>... | colp <page name>...
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "batch3"))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase2"))
import fetch_batch3 as B3  # noqa: E402

P2 = B3.P2
P2.DOCS = ["ley_1801_2016", "ley_0100_1993", "ley_1952_2019", "decreto_2241_1986"]

if __name__ == "__main__":
    if sys.argv[1:2] == ["colp"]:
        B3.colp(sys.argv[2:])
    else:
        P2.main(sys.argv[1:])
