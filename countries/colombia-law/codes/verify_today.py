"""Check: the last version of each act equals today's text on the source page (struck words removed, publisher
markers and epigraphs dropped). Usage: python -X utf8 codes/verify_today.py [part.json]"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_codes as P

part = sys.argv[1] if len(sys.argv) > 1 else os.path.join(P.COUNTRY, "corpus.d", "50-codes.json")
c = json.load(open(part, encoding="utf-8"))
for act, name, stop in (("codigo-civil", P.CC, None), ("ley-1581-2012", P.DP, "SENTENCIA")):
    a = next(x for x in c["acts"] if x["slug"] == act)
    last = {}
    for v in a["versions"]:
        if "units" in v:
            last = v["units"]
        elif "changes" in v:
            last = dict(last)
            for k, x in v["changes"].items():
                if x is None:
                    last.pop(k, None)
                else:
                    last[k] = x
    bad, n = [], 0
    for u in P.doc_units(name)[1:]:
        if stop and u["name"].upper().startswith(stop):
            break
        u, _ = P.split_libro(u)
        lm = re.match(r"ART[IÍ]CULO\s+(\d+)", u["label"])
        if not lm:
            continue
        key = f"art-{int(lm.group(1)):04d}"
        lines = []
        for it in u["items"]:
            if it[0] != "p" or ("antsig" in it[1]):
                continue
            if re.match(r"\s*FIN DEL C", P.plain(it[1])):
                break
            tacit = any(P.TACIT.search(m) for m in P.markers(it[1]))
            t = P.tidy(P.to_text(it[1], keep_struck=tacit))
            if t:
                lines.append(t)
        mine = (last.get(key, {}).get("text", "").split("\n", 1) + [""])[1].replace("\n", " ")
        n += 1
        lines = [l for l in lines if re.search(r"\w", l)]
        if P.norm(" ".join(lines)).replace(" ", "") not in P.norm(mine).replace(" ", "") and lines:
            bad.append(key)
        elif not lines and key in last:
            bad.append(key + "(should be absent)")
    print(act, n, "articles,", len(bad), "differ:", " ".join(bad[:40]))
