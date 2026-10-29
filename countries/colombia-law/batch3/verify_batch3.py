"""Check corpus.d/80-batch3.json against today's text on the source pages (same check as phase2/verify_phase2.py).

Usage: python -X utf8 batch3/verify_batch3.py [part.json] [-v]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "phase2"))
sys.path.insert(0, HERE)
import parse_batch3  # noqa: E402,F401  (its page repairs and sign-off rule apply to the check too)
import verify_phase2 as V  # noqa: E402

V.ACTS = (("codigo-de-comercio", "codigo_comercio"), ("cpaca", "ley_1437_2011"),
          ("codigo-de-procedimiento-penal", "ley_0906_2004"),
          ("codigo-de-la-infancia-y-la-adolescencia", "ley_1098_2006"))
V.P.OUT = os.path.join(os.path.dirname(HERE), "corpus.d", "80-batch3.json")

if __name__ == "__main__":
    V.main(sys.argv[1:])
