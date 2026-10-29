"""Reading-only comparison of the replayed COIP with the Ediciones Legales consolidation (to 13-X-2021).

Nothing is taken from the consolidation: it only shows where the replay and an editor's reading of the gazette
disagree, so each difference can be explained in decisions. Articles that acts not applied here (image-only
editions) touched are reported separately.

    python -X utf8 coip/reconcile_coip.py [--show ART]
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import fetch  # noqa: E402
import index_notes  # noqa: E402

import fitz  # noqa: E402

PART = Path(__import__("os").environ.get("COIP_OUT", HERE.parent / "corpus.d" / "60-coip.json"))


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    for a in "“”„«»":
        s = s.replace(a, '"')
    for a in "‘’":
        s = s.replace(a, "'")
    for a in "‐‑–—‒−":
        s = s.replace(a, "-")
    s = s.replace(" ", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def body(text: str) -> str:
    """An article without its number heading, normalised for comparison."""
    t = norm(text)
    t = re.sub(r"^(Artículo|Art\.)\s*[\d.]+\s*(A\b)?\s*[.:]?-?\s*", "", t)
    t = t.replace('"', "").replace("'", "")
    t = t.replace(".-", " ")
    t = re.sub(r"\s*([.,;:])", r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t.lower()


def consolidation() -> dict[str, str]:
    d = fitz.open(fetch.cached(index_notes.CONSOLIDATION))
    t = unicodedata.normalize("NFC", "\n".join(p.get_text() for p in d))
    t = re.sub(r"Página \d+ de \d+", " ", t)
    t = re.sub(index_notes.NOTE, " ", t)  # inline amendment notes
    t = re.sub(r"Nota:.*?(?=\nArt\.|\n[A-ZÁÉÍÓÚ]{4,})", " ", t, flags=re.S)
    out: dict[str, str] = {}
    parts = re.split(r"\n(?=Art\.\s*\d+(?:\.\d+)?\s*(?:A\s*)?\.-)", t)
    for p in parts:
        m = re.match(r"Art\.\s*(\d+)(?:\.(\d+))?\s*(A\s*)?\.-", p)
        if not m:
            continue
        n = int(m.group(1))
        key = f"art-{n:03d}" + (f"-{m.group(2)}" if m.group(2) else "") + ("-a" if m.group(3) else "")
        # drop trailing headings (LIBRO / TÍTULO / CAPÍTULO / SECCIÓN / PARÁGRAFO lines)
        lines = [ln for ln in p.split("\n")]
        keep = []
        for ln in lines:
            if re.match(r"(?i)\s*(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|PAR[AÁ]GRAFO|Secci[oó]n|Par[aá]grafo|"
                        r"DISPOSICIONES)\b", unicodedata.normalize("NFC", ln)):
                break
            keep.append(ln)
        out.setdefault(key, " ".join(keep))
    return out


def state(on: str) -> dict:
    c = json.loads(PART.read_text(encoding="utf-8"))
    vs = c["acts"][0]["versions"]
    u = dict(vs[0]["units"])
    for v in vs[1:]:
        if v["from"] > on:
            break
        for k, x in v.get("changes", {}).items():
            if x is None:
                u.pop(k, None)
            else:
                u[k] = x
    return u, c


def main(argv: list[str]) -> None:
    u, c = state("2021-10-13")
    el = consolidation()
    na = {}
    for v in c["acts"][0]["versions"]:
        for k, ls in v.get("credits", {}).items():
            for law in ls:
                if "NOT APPLIED" in (c["laws"][law].get("title") or ""):
                    na.setdefault(k, []).append(law)
    # acts after the replay's last version that the indexes name (not yet replayed)
    later = {}
    for art, ro, _ in index_notes.notes():
        m = re.search(r"(\d{1,2})-([IVX]+)-(\d{4})", ro)
        if m and int(m.group(3)) >= 2020 and ro not in ("R.O.107-S,24-XII-2019",):
            later.setdefault(f"art-{int(art.split('.')[0]):03d}" + (f"-{art.split('.')[1]}" if '.' in art else ""), []).append(ro)
    same = diff = 0
    rows = []
    for k in sorted(k for k in u if k.startswith("art-")):
        if k not in el:
            rows.append(("missing-in-consolidation", k, ""))
            continue
        if body(u[k]["text"]) == body(el[k]):
            same += 1
            continue
        diff += 1
        why = "not applied: " + ",".join(sorted(set(na[k]))) if k in na else (
            "later act: " + ",".join(sorted(set(later[k]))) if k in later else "UNEXPLAINED")
        rows.append((why, k, ""))
    extra = sorted(k for k in el if k not in u)
    print(f"same {same}, different {diff}, only in consolidation {len(extra)}: {extra[:30]}")
    for why, k, _ in sorted(rows):
        print(f"{k:12s} {why}")
    if "--show" in argv:
        k = argv[argv.index("--show") + 1]
        a, b = body(u[k]["text"]), body(el[k])
        import difflib
        for op in difflib.SequenceMatcher(None, a, b).get_opcodes():
            if op[0] != "equal":
                print(op[0], "| ours:", a[op[1] - 30:op[2] + 30], "| EL:", b[op[3] - 30:op[4] + 30])


if __name__ == "__main__":
    main(sys.argv[1:])
