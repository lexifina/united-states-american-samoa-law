"""Reading-only comparison of the Código del Trabajo as rebuilt here (version in force on 1-II-2023) with the Lexis-style
consolidation of that date (LegalCloud DOCX, 'Última modificación: 01-02-2023', codes/index_docx.py). Nothing here
becomes legal text: it lists the numbered articles whose words differ after normalising spacing, quotes, dashes and
the article heading, with the differing words. Articles innumerados ('Art. ...', 'Art. (...)') are cut off the
numbered article they follow in the DOCX and compared by hand (codes/trabajo.py decisions).

    python -X utf8 codes/reconcile_trabajo.py [part.json]      -> codes/reconcile_trabajo.json
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import index_docx  # noqa: E402

DAY = "2023-02-01"


def norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("’", "'").replace("–", "-").replace("—", "-").replace(" ", " ")
    s = re.sub(r"^\s*Art(?:ículo|\.)?\s*\d+(?:\.\d+)?\s*\.?-?\s*", "", s)
    s = re.sub(r"\s+([.,;:)])", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def lexis() -> dict[str, str]:
    t = "\n".join(index_docx.paras("trabajo"))
    t = re.split(r"\nDISPOSICIONES TRANSITORIAS\n", t)[0]
    out: dict[str, str] = {}
    marks = list(re.finditer(r"(?:^|\s)Art\.\s*(\d+)(?:\.(\d+))?\s*\.-", t, re.M))
    for i, m in enumerate(marks):
        body = t[m.start():marks[i + 1].start() if i + 1 < len(marks) else len(t)]
        body = re.split(r"\s(?:Nota:|Concordancias:|Jurisprudencia:)", body)[0]
        body = re.split(r"\sArt\.\s*(?:\.\.\.|\(\.\.\.\)|innumerado)", body)[0]
        body = re.sub(r"(?:\n|\s{2,})(?:TÍTULO|TITULO|Capítulo|CAPÍTULO|CAPITULO|Parágrafo|PARÁGRAFO)\s.*", "", body,
                      flags=re.S)
        n = int(m.group(1))
        key = f"art-{n:04d}" + (f"-{int(m.group(2))}" if m.group(2) else "")
        out.setdefault(key, body)
    return out


SRI = ("https://web.archive.org/web/20250422103829id_/https://www.sri.gob.ec/o/sri-portlet-biblioteca-alfresco-internet/"
       "descargar/a5c99ffe-c498-4722-b408-fe672321c82c/Codigo_Trabajo_act_27062024.pdf")
SRI_DAY = "2024-06-27"


def sri() -> dict[str, str]:
    """The SRI's consolidation 'Última modificación: Tercer Suplemento del Registro Oficial 588 de 27 de junio de 2024'
    (Internet Archive capture 20250422103829): numbered articles without the SRI's notes in parentheses and 'Nota(s):'."""
    import hashlib
    import fitz
    path = HERE.parent / ".cache" / hashlib.sha256(SRI.encode()).hexdigest()
    t = "\n".join(p.get_text() for p in fitz.open(path))
    t = re.sub(r"Pág\. \d+ de \d+", " ", t)
    t = re.split(r"\nDISPOSICIONES TRANSITORIAS\s*\n", t)
    t = "\n".join(t[:-1]) if len(t) > 1 else t[0]  # the Code's own come last (Ley 2006-48 has some after art. 346)
    t = re.sub(r"\s+", " ", t)
    out: dict[str, str] = {}
    marks = list(re.finditer(r"Art\.\s*(\d+)(?:\.(\d+))?\s*\.?-", t))
    for i, m in enumerate(marks):
        body = t[m.start():marks[i + 1].start() if i + 1 < len(marks) else len(t)]
        body = re.sub(r"\((?:[^()]|\([^()]*\))*R\.\s?O\.(?:[^()]|\([^()]*\))*\)\.?-?", "", body)
        body = re.split(r"\sNotas?:", body)[0]
        body = re.split(r"\sArt\.\s*(?:\.\.\.|\(\.\.\.\)|innumerado)", body)[0]
        body = re.sub(r"\s(?:TÍTULO|TITULO|Capítulo|CAPÍTULO|CAPITULO|Parágrafo|PARÁGRAFO) [IVXL0-9]+[a-z]*\.?\s[A-ZÁÉÍÓÚ ,]+$", "",
                      body)
        n = int(m.group(1))
        key = f"art-{n:04d}" + (f"-{int(m.group(2))}" if m.group(2) else "")
        out.setdefault(key, body)
    return out


def ours(path: Path, day: str = DAY) -> dict[str, str]:
    act = json.loads(path.read_text(encoding="utf-8"))["acts"][0]
    units = dict(act["versions"][0]["units"])
    for v in act["versions"][1:]:
        if v["from"] > day:
            break
        for k, x in (v.get("changes") or {}).items():
            if x is None:
                units.pop(k, None)
            else:
                units[k] = x
    return {k: u["text"] for k, u in units.items() if k.startswith("art-")}


def main(argv: list[str]) -> None:
    use_sri = "--sri" in argv
    argv = [x for x in argv if x != "--sri"]
    path = Path(argv[0]) if argv else HERE.parent / "corpus.d" / "90-trabajo.json"
    day = SRI_DAY if use_sri else DAY
    a, b = ours(path, day), (sri() if use_sri else lexis())
    rows = {}
    same = 0
    for k in sorted(set(a) | set(b)):
        x, y = norm(a.get(k, "")), norm(b.get(k, ""))
        if x == y:
            same += 1
            continue
        sm = difflib.SequenceMatcher(None, x.split(), y.split(), autojunk=False)
        d = [f"{' '.join(x.split()[i1:i2])!r} -> {' '.join(y.split()[j1:j2])!r}"
             for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
        rows[k] = d[:8] if k in a and k in b else ["only here" if k in a else "only in the consolidation"]
    out = HERE / ("reconcile_trabajo_sri.json" if use_sri else "reconcile_trabajo.json")
    out.write_text(json.dumps({"day": day, "agree": same, "differ": rows}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"{same} agree, {len(rows)} differ -> {out.name}")
    for k, d in rows.items():
        print(k, "|", " ; ".join(d)[:300])


if __name__ == "__main__":
    main(sys.argv[1:])
