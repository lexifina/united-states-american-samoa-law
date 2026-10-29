"""Audit: the first version of each article against the source's own 'Texto original' block, where that block gives
the whole article (it starts with 'ARTICULO N'). Words only (case, punctuation and spacing ignored); braces resolved
to 'patrono'. Usage: python -X utf8 cst/audit_orig.py [part.json] [-v]"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_cst as P
E = P.E

def words(t):
    t = P.debrace(t, True)
    t = re.sub(r"<[^>]*>", " ", t)
    return re.findall(r"\w+", t.lower())

part = next((a for a in sys.argv[1:] if a.endswith(".json")), P.OUT)
c = json.load(open(part, encoding="utf-8"))
vs = P.full_versions(c["acts"][0]["versions"])
first = vs[0]["units"]
bad = 0
n = 0
for u in P.doc_units(P.PAGE)[1:]:
    num = E.label_num(u["label"])
    uk = E.unit_key(num) if num else None
    if not uk:
        continue
    for it in u["items"]:
        if it[0] != "box" or it[1] != "Legislación Anterior":
            continue
        ps = [E.plain(p) for p in E.box_paras(it[2])]
        for i, p in enumerate(ps):
            if re.match(r"Texto original del C[óo]digo", p) and i + 1 < len(ps) and re.match(r"ART[IÍ]CULO\s+\d", ps[i + 1]):
                blk = []
                for q in ps[i + 1:]:
                    if re.match(r"Texto (original|modificado|adicionado|subrogado)", q):
                        break
                    blk.append(q)
                src = words(E.ART_HEAD.sub("", " ".join(blk), count=1))
                mine = words(first.get(uk[0], {}).get("text", "").split("\n", 1)[-1])
                n += 1
                if src != mine:
                    bad += 1
                    print("DIFF", uk[0], f"src {len(src)} words, first version {len(mine)}")
                    if "-v" in sys.argv:
                        import difflib
                        sm = difflib.SequenceMatcher(None, src, mine, autojunk=False)
                        for op, a1, a2, b1, b2 in sm.get_opcodes():
                            if op != "equal":
                                print("   ", op, " ".join(src[a1:a2])[:200], "=>", " ".join(mine[b1:b2])[:200])
print(f"{n} original blocks, {bad} differ")
