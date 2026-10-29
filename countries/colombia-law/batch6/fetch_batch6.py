"""Fetch batch 6 (Estatuto Orgánico del Sistema Financiero, Código de Minas, Código Procesal del Trabajo y de la
Seguridad Social (Decreto-Ley 2158 de 1948 and Ley 2452 de 2025), Régimen de Insolvencia (Ley 1116 de 2006), Régimen de
Servicios Públicos Domiciliarios (Ley 142 de 1994), Ley 222 de 1995 (fetched, not built)) and the basedoc pages of the
acts that amended them. Bogotá's Sisjur copy of Decreto 673 de 1994 was fetched with `url`. Same cache, log, User-Agent
and curl
(--compressed) as ../fetch.py; reuses phase2/fetch_phase2.py and batch3/fetch_batch3.py, at ../fetch.py's own pacing (at
least 1.05 s between requests to one host).

Usage:  python -X utf8 batch6/fetch_batch6.py docs | laws | url <url>... | colp <page name>...
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
P2.DOCS = ["estatuto_organico_sistema_financiero", "ley_0685_2001", "codigo_procedimental_laboral", "ley_1116_2006",
           "ley_0142_1994", "ley_0222_1995", "ley_2452_2025"]

if __name__ == "__main__":
    if sys.argv[1:2] == ["colp"]:
        B3.colp(sys.argv[2:])
    else:
        P2.main(sys.argv[1:])
