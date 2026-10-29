"""Debug: print every note paragraph of the CST pages that matches a regex (cache only)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E
rx = re.compile(sys.argv[1])
for u in E.doc_units("codigo_sustantivo_trabajo"):
    for it in u["items"]:
        if it[0] == "box":
            for ph in E.box_paras(it[2]):
                t = E.plain(ph)
                if rx.search(t):
                    print(f"[{u['name']}|{it[1]}] {t[:400]}")
        elif rx.search(E.plain(it[1])):
            print(f"[{u['name']}|p] {E.plain(it[1])[:400]}")
