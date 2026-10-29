"""Rebuild the Código Civil's history from 25 Dec 2012 to Aug 2024 from official text-layer sources.

- MINJUS 14th official edition (gob.pe, current to 1 Aug 2014): the text then, and its footnotes with the
  wording before each amendment ("Texto anterior a la modificación").
- Editora Perú NLA edition (current to 15 Aug 2024): the text at the end of the replay.
- The amending laws' own texts (amendlaws.py) for the wording between two amendments of one article, and as
  a check on the 2024 wording.

Why 25 Dec 2012: the 14th edition quotes the earlier wording for every modification, but not for repeals.
The last repeal it does not quote is Ley 29973 (published 24 Dec 2012), so the whole code can be known on
every day from 25 Dec 2012 on, and on no earlier day.

build(cc24, notes24) -> (versions, laws, report)
"""
from __future__ import annotations

import re
import sys
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import amendlaws  # noqa: E402
import cc14  # noqa: E402
import cc_spec  # noqa: E402

START = "2012-12-25"
MON = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
       "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}

# key: (label, title, kind, enacted, published, in force, url, how the in-force day was set)
LAWS = {
    "ley-29973": ("Ley 29973", "Ley General de la Persona con Discapacidad", "law", None, "2012-12-24", "2012-12-25",
                  "https://www.leyes.congreso.gob.pe/Documentos/Leyes/29973.pdf", "default"),
    "ley-30007": ("Ley 30007", "Ley que modifica los artículos 326, 724, 816 y 2030 del Código Civil, el inciso 4 del artículo 425 y el artículo 831 del Código Procesal Civil y los artículos 35, 38 y el inciso 4 del artículo 39 de la Ley 26662, a fin de reconocer derechos sucesorios entre los miembros de uniones de hecho",
                  "law", None, "2013-04-17", "2013-04-18", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30007.pdf", "default"),
    "ley-30084": ("Ley 30084", "Ley que modifica el artículo 22 del Código Civil para precisar el nombre en el caso de que un cónyuge o concubino adopte al hijo del otro",
                  "law", None, "2013-09-22", "2013-09-23", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30084.pdf", "default"),
    "ley-30162": ("Ley 30162", "Ley de Acogimiento Familiar", "law", None, "2014-01-29", "2014-01-30",
                  "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30162.pdf", "default"),
    "ley-30179": ("Ley 30179", "Ley que modifica el artículo 2001 del Código Civil", "law", None, "2014-04-06", "2014-04-07",
                  "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30179.pdf", "default"),
    "ley-30230": ("Ley 30230", "Ley que establece medidas tributarias, simplificación de procedimientos y permisos para la promoción y dinamización de la inversión en el país",
                  "law", None, "2014-07-12", "2014-07-13", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30230.pdf", "default"),
    "ley-30292": ("Ley 30292", "Ley que modifica el artículo 92 del Código de los Niños y Adolescentes y el artículo 472 del Código Civil sobre noción de alimentos",
                  "law", None, "2014-12-28", "2014-12-29", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30292.pdf", "default"),
    "ley-30311": ("Ley 30311", "Ley que permite la adopción de menores de edad declarados judicialmente en abandono por parte de las parejas que conforman una unión de hecho",
                  "law", None, "2015-03-18", "2015-03-19", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30311.pdf", "default"),
    "ley-30313": ("Ley 30313", "Ley de oposición al procedimiento de inscripción registral en trámite y cancelación del asiento registral por suplantación de identidad o falsificación de documentación y modificatoria de los artículos 2013 y 2014 del Código Civil y de los artículos 4 y 55 y la quinta y sexta disposiciones complementarias transitorias y finales del Decreto Legislativo 1049",
                  "law", None, "2015-03-26", "2015-03-27", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30313.pdf", "default"),
    "ley-30323": ("Ley 30323", "Ley que restringe el ejercicio de la patria potestad por la comisión de delitos graves",
                  "law", None, "2015-05-07", "2015-05-08", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30323.pdf", "default"),
    "ley-30364": ("Ley 30364", "Ley para prevenir, sancionar y erradicar la violencia contra las mujeres y los integrantes del grupo familiar",
                  "law", None, "2015-11-23", "2015-11-24", "https://www.leyes.congreso.gob.pe/Documentos/Leyes/30364.pdf", "default"),
    "ley-30403": ("Ley 30403", "Ley que prohíbe el uso del castigo físico y humillante contra los niños, niñas y adolescentes",
                  "law", None, "2015-12-30", "2015-12-31", amendlaws.SOURCES["ley-30403"][0], "default"),
    "ley-30473": ("Ley 30473", "Ley que modifica los artículos 2, 3 y 4, y la disposición complementaria única de la Ley 29471, Ley que promueve la obtención, la donación y el trasplante de órganos o tejidos humanos",
                  "law", None, "2016-06-29", "2016-06-30", amendlaws.SOURCES["ley-30473"][0], "default"),
    "ley-30490": ("Ley 30490", "Ley de la Persona Adulta Mayor", "law", None, "2016-07-21", "2016-07-22",
                  amendlaws.SOURCES["ley-30490"][0], "default"),
    "dleg-1297": ("Decreto Legislativo 1297", "Decreto Legislativo para la protección de niñas, niños y adolescentes sin cuidados parentales o en riesgo de perderlos",
                  "decree", None, "2016-12-30", "2018-02-11", amendlaws.SOURCES["dleg-1297"][0],
                  "in force the day after its reglamento (D.S. 001-2018-MIMP, El Peruano 10 Feb 2018), as its note in the 2024 edition says"),
    "ley-30550": ("Ley 30550", "Ley que modifica el Código Civil con la finalidad de incorporar en las resoluciones judiciales sobre pensiones alimentarias el criterio del aporte por trabajo doméstico no remunerado",
                  "law", None, "2017-04-05", "2017-04-06", amendlaws.SOURCES["ley-30550"][0], "default"),
    "dleg-1377": ("Decreto Legislativo 1377", "Decreto Legislativo que fortalece la protección integral de niñas, niños y adolescentes",
                  "decree", None, "2018-08-24", "2018-08-25", amendlaws.SOURCES["dleg-1377"][0], "default"),
    "dleg-1384": ("Decreto Legislativo 1384", "Decreto Legislativo que reconoce y regula la capacidad jurídica de las personas con discapacidad en igualdad de condiciones",
                  "decree", None, "2018-09-04", "2018-09-05", amendlaws.SOURCES["dleg-1384"][0], "default"),
    "ley-31309": ("Ley 31309", "Ley para la modernización y el fortalecimiento de los servicios de la Superintendencia Nacional de los Registros Públicos",
                  "law", None, "2021-07-24", "2021-07-25", amendlaws.SOURCES["ley-31309"][0], "default"),
    "ley-31338": ("Ley 31338", "Ley que modifica el artículo 696 del Código Civil, facilitando el otorgamiento de testamento por escritura pública, y modifica el artículo 38 del Decreto Legislativo 1049, Decreto Legislativo del Notariado, sobre la forma de llevar los registros",
                  "law", None, "2021-08-11", "2021-08-12", "https://www.leyes.congreso.gob.pe/Documentos/2021_2026/ADLP/Normas_Legales/31338-LEY.pdf", "default"),
    "ley-31643": ("Ley 31643", "Ley que modifica el Código Civil para facultar a los notarios a celebrar matrimonio civil",
                  "law", None, "2022-12-15", "2022-12-16", amendlaws.SOURCES["ley-31643"][0], "default"),
    "ley-31945": ("Ley 31945", "Ley que modifica el Código Civil, Decreto Legislativo 295, a fin de prohibir el matrimonio de personas menores de edad",
                  "law", None, "2023-11-25", "2023-11-26", amendlaws.SOURCES["ley-31945"][0], "default"),
    "ley-32006": ("Ley 32006", "Ley que modifica el Código Procesal Civil, respecto al acceso de oficio a información en línea sobre la capacidad económica del demandado",
                  "law", None, "2024-04-24", "2024-06-06", amendlaws.SOURCES["ley-32006"][0],
                  "its tercera disposición complementaria final: in force 30 business days after publication; counted from 25 Apr 2024 skipping 1 May, the 30th is 6 Jun 2024"),
    "dleg-1626": ("Decreto Legislativo 1626", "Decreto Legislativo que modifica los artículos 2033, 2037, 2038, 2040 y 2042 del Código Civil",
                  "decree", "2024-08-14", "2024-08-15", "2024-08-16", amendlaws.SOURCES["dleg-1626"][0], "default (arts. 2037, 2038: 90 days)"),
}
LAWREF = re.compile(r"(Ley|Decreto Legislativo)\s*N?\s*[°º]?\s*(\d{4,5})")
PUB = re.compile(r"publicad[oa]s?\s+(?:el\s+)?(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)\s+(?:de|del)\s+(\d{4})", re.I)


def note_laws(note: str):
    """[(law key, published)] named by an amendment note (pending texts left out)."""
    if re.search(r"entrará en vigencia|nuevo texto", note):
        return []
    out = []
    for m in LAWREF.finditer(note):
        rest = note[m.end():m.end() + 140]
        p = PUB.search(rest)
        if not p:
            continue
        key = ("ley-" if m.group(1) == "Ley" else "dleg-") + m.group(2)
        out.append((key, "%s-%02d-%02d" % (p.group(3), MON.get(p.group(2).lower(), 0), int(p.group(1)))))
    return out


def _find(lines, prefix, what):
    for ln in lines or []:
        if ln.startswith(prefix):
            return ln
    raise SystemExit(f"cc_spec: no line starting {prefix!r} in {what}")


def _law_piece(law, start, end):
    t = amendlaws.law_text(law)
    i = t.find(start)
    if i < 0:
        raise SystemExit(f"cc_spec: anchor {start!r} not in {law}")
    j = t.find(end, i + len(start)) if end else len(t)
    if j < 0:
        raise SystemExit(f"cc_spec: end anchor {end!r} not in {law}")
    s = " ".join(t[i:j].split())
    return s.strip(" “”«»\"")


def spec_lines(items, T14k, Ck, what):
    out = []
    for it in items:
        if it[0] == "C":
            out.append(_find(Ck, it[1], what + " (2024 text)"))
        elif it[0] == "T14":
            out.append(_find(T14k, it[1], what + " (14th edition)"))
        else:
            out.append(_law_piece(it[1], it[2], it[3]))
    return out


def fk(lines) -> str:
    return amendlaws.flat("\n".join(lines or []))


def build(cc24: dict, notes24: dict):
    """cc24: unit -> text (2024 base); notes24: unit -> [notes]. Returns (versions, laws, report, extra decisions)."""
    report: list[str] = []
    u14, _struct14, n14 = cc14.read()
    T14 = {k: cc14.text14(v) for k, v in u14.items()}
    T14 = {k: v for k, v in T14.items() if v}
    C = {k: v.rstrip("\n").split("\n") for k, v in cc24.items() if k.startswith(("art-", "tp-"))}

    # ---- events after the 14th edition (in force after 1 Aug 2014), by unit
    post: dict[str, set] = {}
    for k, ns in notes24.items():
        for nt in ns:
            for law, pub in note_laws(nt):
                if pub > "2014-08-01" and law in LAWS:
                    post.setdefault(k, set()).add(law)
                elif pub > "2014-08-01":
                    report.append(f"CC: note names a law with no entry in LAWS: {law} ({k})")
    for k, laws in cc_spec.HIDDEN.items():
        post.setdefault(k, set()).update(laws)
    for k, law in cc_spec.INCORPORATED_WITH.items():
        post.setdefault(k, set()).add(law)
    # dleg-1626's arts 2037/2038 take effect later (handled by the caller as their own version)
    for k in ("art-2037", "art-2038"):
        post.get(k, set()).discard("dleg-1626")

    timeline: dict[str, list] = {}   # unit -> [(day, lines or None, law)]
    keys = sorted(set(T14) | set(C) | set(post), key=sort_key)
    for k in keys:
        evs = sorted(post.get(k, ()), key=lambda l: LAWS[l][5])
        before = T14.get(k)
        after = C.get(k)
        if not evs:
            if (before is None) != (after is None):
                report.append(f"CC MISMATCH {k}: present in only one edition and no amendment noted "
                              f"(2014: {bool(before)}, 2024: {bool(after)})")
            # unchanged since 2014: the 2024 wording (editorial differences to the MINJUS text are listed)
            timeline[k] = [(None, after if after is not None else before, None)]
            continue
        states = [(None, before, None)]
        for i, law in enumerate(evs):
            if i == len(evs) - 1:
                st = after
            else:
                spec = cc_spec.INTERMEDIATE.get(k, {}).get(law)
                if spec is None:
                    report.append(f"CC MISSING intermediate wording for {k} after {law} (next {evs[i + 1]})")
                    st = after
                else:
                    st = spec_lines(spec, T14.get(k), C.get(k), k)
            states.append((LAWS[law][5], st, law))
        timeline[k] = states

    # ---- rewind 1 Aug 2014 -> 25 Dec 2012 with the 14th edition's footnotes
    pre_laws_used = set()
    for k, u in u14.items():
        evs = []
        for c in sorted(u["calls"], key=lambda x: int(re.sub(r"\D", "", x) or 0)):
            for num in re.findall(r"\d+", c):
                nt = n14.get(int(num))
                if not nt:
                    continue
                for law, pub in note_laws(nt["header"]):
                    if START <= LAWS.get(law, ("",) * 6)[5] <= "2014-08-01" and law != "ley-29973":
                        evs.append((LAWS[law][5], law, int(num), nt))
        if not evs:
            continue
        evs.sort(key=lambda e: (e[0], e[2]))
        st0 = timeline[k][0]
        base = st0[1]
        cur = list(base) if base else None
        rewound = []
        for day, law, num, nt in reversed(evs):
            pre_laws_used.add(law)
            prev = rewind_one(k, cur, u, num, nt, report)
            rewound.append((day, cur, law))
            cur = prev
        timeline[k] = [(None, cur, None)] + list(reversed(rewound)) + timeline[k][1:]

    # ---- versions
    days = sorted({d for tl in timeline.values() for d, _, _ in tl if d})
    versions = []
    prev_units: dict = {}
    for day in [START] + [d for d in days if d > START]:
        units = OrderedDict()
        credits: dict = {}
        for k in keys:
            tl = timeline[k]
            cur = None
            law = None
            for d, st, lw in tl:
                if d is None or d <= day:
                    cur, law = st, lw
                    if d == day:
                        if lw not in credits.setdefault(k, []):
                            credits[k].append(lw)
            if cur:
                units[k] = {"label": label(k), "kind": "art", "text": "\n".join(cur) + "\n"}
        versions.append({"from": day, "units": units, "credits": credits if day != START else {}})
        prev_units = units

    # ---- checks
    # 1. the replay's last state equals the 2024 text
    last = versions[-1]["units"]
    bad = [k for k in set(last) | set(C) if fk((last.get(k) or {}).get("text", "").rstrip("\n").split("\n") if k in last else None) != fk(C.get(k))]
    report.append(f"CC check: replay at {versions[-1]['from']} vs Editora Perú 2024 text: {len(bad)} unit(s) differ {sorted(bad)[:20]}")
    # 2. every piece a law quotes for a unit is in that unit's wording right after the law took effect
    qbad, qok = [], 0
    for law in amendlaws.SOURCES:
        if law not in LAWS:
            continue
        day = LAWS[law][5]
        try:
            q = amendlaws.quotes(law)
        except SystemExit as e:
            report.append(f"CC law text {law}: {e}")
            continue
        for k, pieces in q.items():
            if k not in post or law not in post[k]:
                continue
            st = None
            for d, s, lw in timeline.get(k, []):
                if lw == law:
                    st = s
            if st is None:
                continue
            hay = re.sub(r"art[íi]culo\d+", "", fk(st))
            tot = found = 0
            for p in pieces:
                # from the article heading to the closing quote; intro words before the heading are the law's own
                m = re.search(r"Art[íi]culo\s+\d+(?:\s*-\s*[A-Z])?\s*\.?\s*-?", p)
                body = p[m.start():] if m else p
                body = re.split(r"[”»]", body)[0]
                f = re.sub(r"art[íi]culo\d+", "", amendlaws.flat(body))
                for i in range(0, len(f) - 39, 40):
                    tot += 1
                    found += f[i:i + 40] in hay
            if tot:
                if found / tot >= 0.9:
                    qok += 1
                else:
                    qbad.append((law, k, f"{found}/{tot} 40-char windows found"))
    report.append(f"CC check: unit changes whose law text (40-character windows, >= 90%) is in the replayed wording: "
                  f"{qok}; below: {len(qbad)}")
    for b in qbad[:40]:
        report.append(f"  below: {b}")
    # 3. editorial differences 2014 MINJUS vs 2024 Editora Perú for units not amended in between
    ed = [k for k in keys if not post.get(k) and T14.get(k) and C.get(k) and fk(T14[k]) != fk(C[k])]
    report.append(f"CC editions: {len(ed)} unit(s) unamended 2014-2024 whose MINJUS 2014 and Editora Perú 2024 wording differ "
                  f"(typography/editorial; the 2024 wording is used): {ed}")
    used = {lw for tl in timeline.values() for _, _, lw in tl if lw}
    laws = {k: LAWS[k] for k in used}
    return versions, laws, report, ed


def rewind_one(k, cur, u, num, nt, report):
    """The unit's lines before the amendment in footnote `num`, given the lines after it."""
    head = nt["header"]
    call_paras = [cc14.CALLS.sub("", p).strip() for p in u["paras"]
                  if re.search(cc14.MARK + r"[^" + cc14.MARK + r"]*\b" + str(num) + r"\b", p)]
    if cur is None:
        report.append(f"CC rewind {k} note {num}: no text after the change")
        return cur
    incorporated = re.match(r"^\s*(Párrafo|Numeral|Inciso|Literal)\b.*?(incorporad|agregad|adicionad)", head, re.I)
    whole = re.match(r"^\s*Art[íi]culo\s+(modificad|sustituid)", head, re.I)
    part = re.match(r"^\s*(Párrafo|Numeral|Inciso|Literal|Extremo)\b.*?(modificad|sustituid)", head, re.I)
    if incorporated:
        targets = [amendlaws.flat(x)[:50] for x in call_paras]
        out = [ln for ln in cur if amendlaws.flat(ln)[:50] not in targets]
        if len(out) != len(cur) - len(call_paras):
            report.append(f"CC rewind {k} note {num}: removed {len(cur) - len(out)} line(s), expected {len(call_paras)}")
        return out
    if whole and nt["quote"]:
        q = [x for x in (cc14.norm14(p).strip(' "') for p in nt["quote"]) if x]
        q = [x for x in q if not x.startswith("CONCORDANCIA")]
        m = re.match(r"^([^\"“]{3,90}?)\s+\"?(Art[íi]culo\s+\d.*)$", q[0]) if q else None
        if m and not m.group(1).startswith("Artículo"):   # a quoted sumilla printed on the heading's line
            q = [m.group(1).strip(), m.group(2)] + q[1:]
        # keep the edition's sumilla line when the quoted text starts at the article heading
        keep = [cur[0]] if cur and not cur[0].startswith("Artículo") and q and q[0].startswith("Artículo") else []
        return keep + q
    if part and nt["quote"]:
        q = [x for x in (cc14.norm14(p).strip(' "') for p in nt["quote"]) if x]
        targets = [amendlaws.flat(x)[:50] for x in call_paras]
        out, done = [], False
        for ln in cur:
            if amendlaws.flat(ln)[:50] in targets:
                if not done:
                    out.extend(q)
                    done = True
                continue
            out.append(ln)
        if not done:
            report.append(f"CC rewind {k} note {num}: changed paragraph not found")
        return out
    report.append(f"CC rewind {k} note {num}: not handled: {head[:100]}")
    return cur


def label(k: str) -> str:
    if k.startswith("tp-"):
        return "Título Preliminar, art. " + ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"][int(k[3:]) - 1]
    m = re.fullmatch(r"art-(\d+)(?:-([a-z]))?", k)
    return "Art. %d%s" % (int(m.group(1)), "-" + m.group(2).upper() if m.group(2) else "")


def sort_key(k: str):
    if k.startswith("tp-"):
        return (0, int(k[3:]), "")
    m = re.fullmatch(r"art-(\d+)(?:-([a-z]))?", k)
    return (1, int(m.group(1)), m.group(2) or "")
