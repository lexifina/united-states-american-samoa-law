"""Check corpus.d/60-phase2.json against today's text on the source pages.

For every article of each code: today's text = its paragraphs on the basedoc page, editorial markers (<...>) removed,
words struck as INEXEQUIBLE removed (words the source marks as only tacitly derogated are kept), the signatures after
the last article cut off. It must equal, line for line, the article in the part's last version (the "# Art. N" heading
line aside; the article's epigraph is the start of its first line). A whole article struck or repealed is absent.

Usage: python -X utf8 phase2/verify_phase2.py [part.json] [-v]
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parse_phase2 as P  # noqa: E402

E = P.E
ACTS = (("codigo-penal", "ley_0599_2000"), ("codigo-general-del-proceso", "ley_1564_2012"),
        ("codigo-sustantivo-del-trabajo", "codigo_sustantivo_trabajo"))


def today(name: str) -> dict[str, list[str]]:
    out = {}
    for u in P.doc_units(name)[1:]:
        u, _ = E.split_libro(u)
        num = E.label_num(u["label"])
        if not num:
            continue
        uk = E.unit_key(num)
        if not uk or uk[0] in out:
            continue
        lines, first = [], True
        for it in u["items"]:
            if it[0] != "p" or "antsig" in it[1]:
                continue
            ph = it[1]
            if first:
                first = False
                if re.search(r"&lt;Art\S+\s+(transitorio\s+)?(INEXEQUIBLE|derogado)", ph, re.I) and not E.to_text(ph, False).strip():
                    lines = []
                    break
                epi = E.tidy(E.ART_HEAD.sub("", u["label"], count=1)) if E.ART_HEAD.match(u["label"]) else ""
                epi = E.tidy(re.sub(r"<[^>]*>?", "", epi))  # epigraphs in angle brackets are the publisher's
                if epi and re.search(r"\w", epi):
                    ph = E.html.escape(epi, quote=False) + " " + ph
            tacit = any(E.TACIT.search(m) for m in E.markers(it[1]))
            t = P.debrace(E.tidy(E.to_text(ph, keep_struck=tacit)), False)
            if t and re.search(r"\w", t):
                lines.append(t)
        epi0 = E.tidy(re.sub(r"<[^>]*>?", "", E.tidy(E.ART_HEAD.sub("", u["label"], count=1)))) if E.ART_HEAD.match(u["label"]) else ""
        if epi0 and lines == [epi0]:
            lines = []  # only the epigraph is left: the article is not in force today
        out[uk[0]] = lines
    return out


def main(argv):
    part = next((a for a in argv if a.endswith(".json")), P.OUT)
    c = json.load(open(part, encoding="utf-8"))
    total_bad = 0
    for slug, name in ACTS:
        a = next((x for x in c["acts"] if x["slug"] == slug), None)
        if a is None:
            continue
        last = P.full_versions(a["versions"])[-1]["units"]
        bad = []
        t = today(name)
        for k, lines in t.items():
            mine = last.get(k, {}).get("text")
            mine_lines = [l for l in (mine or "").split("\n")[1:] if l]
            mine_lines = [l for l in mine_lines if re.search(r"\w", l)]
            if lines != mine_lines and not (not lines and mine is None):
                bad.append(k)
                if "-v" in argv:
                    print("DIFF", slug, k)
                    import difflib
                    for d in difflib.unified_diff(mine_lines, lines, "corpus", "today", n=0, lineterm=""):
                        if not d.startswith(("@@", "---", "+++")):
                            print("   ", d[:300])
        extra = [k for k in last if k not in t and k != "titulos"]
        total_bad += len(bad)
        print(f"{slug}: {len(t)} articles, {len(bad)} differ{': ' + ' '.join(bad[:30]) if bad else ''}; extra in corpus: {extra[:10]}")
    print("TOTAL differ:", total_bad)


if __name__ == "__main__":
    main(sys.argv[1:])
