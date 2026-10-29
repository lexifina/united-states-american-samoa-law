"""Fetch batch 3 (Código de Comercio, CPACA, Código de Procedimiento Penal, Código de la Infancia y la Adolescencia)
and the basedoc pages of the acts that amended them. Same cache, log, User-Agent and pacing (2.1 s per host) as
phase2/fetch_phase2.py, whose functions it reuses.

Usage:  python -X utf8 batch3/fetch_batch3.py docs | laws | url <url>... | colp <page name>...
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase2"))
import fetch_phase2 as P2  # noqa: E402

P2.DOCS = ["codigo_comercio", "ley_1437_2011", "ley_0906_2004", "ley_1098_2006"]

COLPENSIONES = "https://normativa.colpensiones.gov.co/colpens/docs/"


def colp(names):
    """Acts the basedoc does not hold: the same Avance Jurídico compilation as published by Colpensiones (a state
    company), read only for the act's heading (sanction, Diario Oficial) and its vigencia clause."""
    for n in names:
        if P2.F.cached(P2.F.BASE + n + ".html") is None:
            b = P2.get(COLPENSIONES + n + ".htm")
            print(n, None if b is None else len(b), flush=True)


if __name__ == "__main__":
    if sys.argv[1:2] == ["colp"]:
        colp(sys.argv[2:])
    else:
        P2.main(sys.argv[1:])
