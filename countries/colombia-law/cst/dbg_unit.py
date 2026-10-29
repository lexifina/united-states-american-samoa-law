"""Debug: print a CST unit's paragraphs and note boxes as the engine reads them (cache only)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_cst as P
E = P.E
names = sys.argv[1:]
for u in P.doc_units("codigo_sustantivo_trabajo"):
    if u["name"] in names:
        print("=== anchor", repr(u["name"]), "label", repr(u["label"][:120]))
        for it in u["items"]:
            if it[0] == "p":
                print("  P:", it[1][:600])
            else:
                print("  BOX", it[1])
                for ph in E.box_paras(it[2]):
                    print("     |", E.plain(ph)[:400])
