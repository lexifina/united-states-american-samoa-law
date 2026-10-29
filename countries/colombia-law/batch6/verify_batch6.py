"""Check corpus.d/97-batch6.json against today's text on the source pages (batch4/verify_batch4.py's check, with this
batch's page repairs, which parse_batch6 applies on import).

The Código Procesal del Trabajo of 1948 (Decreto-Ley 2158 de 1948) was repealed as a whole by Ley 2452 de 2025 from 2
April 2026; the page still prints its last text under '<Código derogado a partir del 2 de abril de 2026 ...>'. For it,
the version before the repeal is checked against that text, and the last version must hold no provisions.

Usage: python -X utf8 batch6/verify_batch6.py [part.json] [-v]
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
sys.path.insert(0, HERE)
for _d in ("batch5", "batch4", "batch3", "phase2"):
    sys.path.insert(0, os.path.join(COUNTRY, _d))
import parse_batch6  # noqa: E402,F401  (its page repairs apply to the check too)
import verify_batch4 as V4  # noqa: E402

V = V4.V
P = V.P
V.ACTS = (("estatuto-organico-del-sistema-financiero", "estatuto_organico_sistema_financiero"),
          ("codigo-de-minas", "ley_0685_2001"),
          ("codigo-procesal-del-trabajo", "ley_2452_2025"),
          ("regimen-de-insolvencia", "ley_1116_2006"),
          ("servicios-publicos-domiciliarios", "ley_0142_1994"),
          ("codigo-procesal-del-trabajo-1948", "codigo_procedimental_laboral"))
V.P.OUT = os.path.join(COUNTRY, "corpus.d", "97-batch6.json")
REPEALED = {"codigo-procesal-del-trabajo-1948": "2026-04-02"}
_full = P.full_versions
_today = V.today


def today(name):
    """EOSF arts. 168 to 175: the page prints their text under '<Artículo derogado el a partir del 25 de mayo de 2021 ...>',
    a marker parse_batch6 takes out of the text (it removes them on that day itself): not in force today."""
    t = _today(name)
    if name == parse_batch6.EOSF:
        for n in parse_batch6.DEROG_2021_UNITS:
            t[parse_batch6.E.unit_key(n)[0]] = []
    return t


V.today = today


def main(argv):
    part = next((a for a in argv if a.endswith(".json")), V.P.OUT)
    c = json.load(open(part, encoding="utf-8"))
    bad = 0
    for slug, day in REPEALED.items():
        a = next(x for x in c["acts"] if x["slug"] == slug)
        vs = _full(a["versions"])
        if vs[-1]["from"] != day or vs[-1]["units"] or vs[-2]["from"] >= day:
            print(f"{slug}: last version {vs[-1]['from']} holds {len(vs[-1]['units'])} units (expected none on {day})")
            bad += 1
        else:
            print(f"{slug}: last version {day} holds no provisions; the version before it is checked below")
    # full_versions(...)[-1] is what verify_phase2 checks: for a repealed act, the version before the repeal.
    P.full_versions = lambda versions: (lambda vs: vs[:-1] if vs and not vs[-1]["units"] else vs)(_full(versions))
    V.main(argv)
    if bad:
        print("REPEAL CHECK FAILED:", bad)


if __name__ == "__main__":
    main(sys.argv[1:])
