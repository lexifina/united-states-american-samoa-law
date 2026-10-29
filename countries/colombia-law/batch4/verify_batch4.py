"""Check corpus.d/90-batch4.json against today's text on the source pages (the check of phase2/verify_phase2.py, with
batch 3's page repairs, which parse_batch4 imports).

Usage: python -X utf8 batch4/verify_batch4.py [part.json] [-v]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase2"))
sys.path.insert(0, HERE)
import parse_batch4  # noqa: E402,F401  (its page repairs apply to the check too)
import verify_phase2 as V  # noqa: E402

V.ACTS = (("codigo-nacional-de-seguridad-y-convivencia-ciudadana", "ley_1801_2016"),
          ("sistema-de-seguridad-social-integral", "ley_0100_1993"),
          ("codigo-general-disciplinario", "ley_1952_2019"),
          ("codigo-electoral", "decreto_2241_1986"))
V.P.OUT = os.path.join(os.path.dirname(HERE), "corpus.d", "90-batch4.json")
E = V.E
_units = V.P.doc_units
DEFER = re.compile(r"(?:\s*<[^<>]*>)*?\s*<Art[íi]culo INEXEQUIBLE\. Efectos diferidos[^>]*?hasta antes del (\d{1,2} de [a-z]+ de \d{4})>")


def doc_units(name):
    """An article struck with a deferred effect that has ended before the retrieval day is not in force today, though
    the page still prints it under the marker '<Artículo INEXEQUIBLE. Efectos diferidos ... hasta antes del D>'."""
    units = _units(name)
    for u in units:
        ps = [it for it in u["items"] if it[0] == "p"]
        m = DEFER.match(E.plain(ps[0][1])) if ps else None
        if m and E.date_es(m.group(1)) <= E.RETRIEVED:
            u["items"] = [("p", "&lt;Artículo INEXEQUIBLE&gt;")]
            continue
        # A paragraph marked both tacitly derogated and with words struck as INEXEQUIBLE (Ley 100 de 1993, art. 204):
        # the struck words are gone (the engine's reading); verify_phase2 keeps struck words whenever a tacit marker is
        # present, so they are dropped here first.
        u["items"] = [(it[0], re.sub(r"<s\b[^>]*>.*?</s>", " ", it[1], flags=re.S | re.I)) + tuple(it[2:])
                      if it[0] == "p" and any(E.TACIT.search(x) for x in E.markers(it[1]))
                      and any("INEXEQUIBLE" in x.upper() for x in E.markers(it[1])) else it for it in u["items"]]
    return units


V.P.doc_units = doc_units

if __name__ == "__main__":
    V.main(sys.argv[1:])
