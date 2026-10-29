"""Debug helper: print the rebuilt states of some Código Civil articles. Usage: python -X utf8 dbg_unit.py 2674 117"""
import sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
import parse_codes as P
units = P.doc_units(P.CC)
P.scan_law_dates(units)
for u in units:
    lm = __import__("re").match(r"ART[IÍ]CULO\s+(\d+)", u["label"])
    if lm and lm.group(1) in sys.argv[1:]:
        P.UNIT_DAYS.clear()
        u2, _ = P.split_libro(u)
        h = P.article_history(u2)
        print("=====", lm.group(1))
        for d, st, law in h["states"]:
            print(" ", d, law, "UNKNOWN" if st is P.UNKNOWN else (None if st is None else [x[:70] for x in st]))
        print("  notes", h["notes"])
print("\n".join(P.REPORT[-10:]))
