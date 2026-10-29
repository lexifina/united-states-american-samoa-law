"""Compare corpus.json's latest version of each act with today's official text in the cache.

Today's text of an article = its paragraphs on the basedoc page, editorial markers removed, struck (INEXEQUIBLE)
words removed. Prints every unit that differs. Usage: python -X utf8 verify.py [corpus.json]
"""
import json
import sys

import parse as P


def today_constitution() -> dict:
    units = P.doc_units(P.CONST)
    P.load_al_table(units)
    out = {}
    for u in units[1:]:
        uk = P.unit_key(u["name"])
        if not uk:
            continue
        lines = []
        first = True
        for it in u["items"]:
            if it[0] != "p":
                continue
            ph = it[1]
            t0 = P.plain(ph)
            if t0 in ("Nota Aclaratoria",) or P.re.match(r"(Art[íi]culo|Inciso|Numeral)s? corregid", t0) or (
                    "antsig" in ph):
                continue
            if first and P.re.search(r"&lt;Art\S+\s+(transitorio\s+)?INEXEQUIBLE&gt;", ph, P.re.I):
                break  # the whole article was struck: it is not in force today
            if first:
                epi = P.tidy(P.ART_HEAD.sub("", u["label"], count=1)) if P.ART_HEAD.match(u["label"]) else ""
                if epi:
                    ph = P.html.escape(epi, quote=False) + " " + ph
                first = False
            t = P.tidy(P.to_text(ph, False))
            if t:
                lines.append(t)
        out[uk[0]] = lines
    return out


def main():
    c = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "corpus.json", encoding="utf-8"))
    act = next(a for a in c["acts"] if a["slug"] == "constitucion")
    last = act["versions"][-1]["units"]
    today = today_constitution()
    bad = 0
    for k, lines in today.items():
        got = last.get(k, {}).get("text")
        want = (f"# {last[k]['label']}\n" if k in last else "") + "".join(l + "\n" for l in lines)
        if not lines:
            want = None
        if got != want:
            bad += 1
            print("DIFF", k)
            a, b = (got or "").splitlines(), (want or "").splitlines()
            for d in P.difflib.unified_diff(a, b, "corpus", "today", n=0, lineterm=""):
                if not d.startswith(("@@", "---", "+++")):
                    print("   ", d[:400])
    extra = [k for k in last if k not in today and k not in ("titulos", "preambulo")]
    print(f"{len(today)} units today, {bad} differ, extra in corpus: {extra}")


if __name__ == "__main__":
    main()
