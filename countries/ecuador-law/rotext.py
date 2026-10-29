"""Turn a cached Registro Oficial PDF into paragraphs.

The Registro Oficial is set in two justified columns. pymupdf gives one text
block per column, in reading order. Paragraphs are separated by whitespace-only
lines; a paragraph that runs over a column or page break is joined back when the
earlier part has no closing punctuation. Page headers ("Registro Oficial Nº 449
-- Lunes 20 de Octubre del 2008 -- 8") are dropped.
"""
from __future__ import annotations

import re
import unicodedata

import fitz  # pymupdf

_DAY = r"(Lunes|Martes|Mi[eé]rcoles|Jueves|Viernes|S[aá]bado|Domingo)"
_RO = r"Registro\s+Ofi\s?cial"
HEADERS = [
    # one-line running heads: "2 -- Suplemento -- Registro Oficial Nº 490 -- Miércoles 13 de Julio del 2011 -- 3"
    re.compile(rf"^[\d\s-]*((Primer|Segundo|Tercer|Cuarto|Quinto)?\s*Suplemento|Edici[oó]n\s+\w+)?[\s-]*{_RO}\s*"
               rf"(N[º°o]\.?|No\.?)\s*\d+[\s-]*{_DAY}.*\d{{4}}[\s-]*\d*$", re.I),
    # two-line running heads (2015 on): "2 - Lunes 21 de diciembre de 2015" / "Suplemento - Registro Oficial Nº 653"
    re.compile(rf"^(\d+\s*-+\s*)?{_DAY}\s+\d{{1,2}}\s+de\s+\w+\s+del?\s+\d{{4}}(\s*-+\s*\d+)?$", re.I),
    re.compile(rf"^[\d\s-]*((Primer|Segundo|Tercer|Cuarto|Quinto)?\s*Suplemento|Edici[oó]n\s+\w+)?[\s-]*{_RO}"
               rf"(\s*-\s*((Primer|Segundo|Tercer|Cuarto|Quinto)?\s*Suplemento|Edici[oó]n\s+\w+))?\s*"
               rf"(N[º°o]\.?|No\.?)\s*\d+(\s*-+\s*((Primer|Segundo|Tercer)?\s*Suplemento|Edici[oó]n\s+\w+))?[\s\d-]*$", re.I),
]


_HEAD_TOKENS = re.compile(
    rf"{_RO}|((Primer|Segundo|Tercer|Cuarto|Quinto|Sexto|S[eé]ptimo)\s+)?Suplemento|Edici[oó]n\s+(Especial|Constitucional|Jur[ií]dica)"
    rf"|N[º°o]\.?\s*\d+|No\.\s*\d+|[\d\s-]+", re.I)


class _Header:
    @staticmethod
    def match(s: str) -> bool:
        if len(s) >= 140:
            return False
        if any(h.match(s) for h in HEADERS):
            return True
        # running head made only of "Registro Oficial", "<n> Suplemento", "Nº 508", dashes and page numbers
        return bool(re.search(_RO, s, re.I)) and _HEAD_TOKENS.sub("", s).strip() == ""


HEADER = _Header()
STRUCT = re.compile(
    r"^(Art\.\s*\d+|Art[ií]culo\s+\d+|\d+\.\s|[A-ZÁÉÍÓÚ]{4,}[A-ZÁÉÍÓÚ]*\.-|T[IÍ]TULO\s|Cap[ií]tulo\s|CAP[IÍ]TULO\s|Secci[oó]n\s|SECCI[OÓ]N\s|DISPOSICI)"
)
HEADING = re.compile(r"^(T[IÍ]TULO\s|Cap[ií]tulo\s|CAP[IÍ]TULO\s|Secci[oó]n\s|SECCI[OÓ]N\s|DISPOSICI|R[EÉ]GIMEN DE TRANSICI|PRE[AÁ]MBULO)")
ART_START = re.compile(r"^Art\.\s*-?\s*\d+\s*\.?\s*-")
HEAD_LINE = re.compile(r"^(T[IÍ]TULO\s+[IVXL]+|Cap[ií]tulo\s+\w+|CAP[IÍ]TULO\s+[IVXL]+|Secci[oó]n\s+\w+)$")
ITEM_START = re.compile(r"^\d{1,2}\.\s+\S")


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    # ligatures; the 2015+ typesetting also leaves a space after them ("defi nitivos", "tráfi co de infl uencias")
    s = re.sub("\N{LATIN SMALL LIGATURE FI} (?=[a-záéíóúñü])", "fi", s)
    s = re.sub("\N{LATIN SMALL LIGATURE FL} (?=[a-záéíóúñü])", "fl", s)
    s = s.replace("\N{LATIN SMALL LIGATURE FI}", "fi").replace("\N{LATIN SMALL LIGATURE FL}", "fl")
    s = s.replace("\N{HYPHEN}", "-").replace("\N{NON-BREAKING HYPHEN}", "-")
    s = s.replace("\u00a0", " ").replace("\u00ad", "")
    for a in "\u201c\u201d\u201e\u00ab\u00bb\u2033":
        s = s.replace(a, '"')
    for a in "\u2018\u2019\u201a\u2032\u00b4":
        s = s.replace(a, "'")
    for a in "\u2013\u2014\u2012\u2212":
        s = s.replace(a, "-")
    s = s.replace("\u2026", "...")
    return re.sub(r"[ \t]+", " ", s).strip()


def join_lines(lines: list[str]) -> str:
    out = ""
    for ln in lines:
        ln = norm(ln)
        if not ln:
            continue
        if not out:
            out = ln
        elif re.search(r"[A-Za-zñÑáéíóúÁÉÍÓÚ]-$", out) and re.match(r"[a-zñáéíóú]", ln):
            out += ln  # word broken at a line end: keep the printed hyphen, no space
        else:
            out += " " + ln
    return re.sub(r" {2,}", " ", out).strip()


def _overlapped(blocks: list) -> set[int]:
    """Indexes of text blocks that lie mostly (>= half their area) inside a block holding more text: the stray
    fragments some editions carry over their real text (Suplemento 175 of 2018, page 28). Tiny blocks (at most 8
    characters, not a bare page number) that touch a fuller block at all are fragments too (Suplemento 107 of 2019:
    'a b', 'si 6' in the gutter between the columns)."""
    out = set()
    for i, b in enumerate(blocks):
        area = max((b[2] - b[0]) * (b[3] - b[1]), 1e-6)
        tiny = len(b[4].strip()) <= 8 and not b[4].strip().isdigit()
        for j, c in enumerate(blocks):
            if i == j or len(c[4]) <= len(b[4]):
                continue
            w = min(b[2], c[2]) - max(b[0], c[0])
            h = min(b[3], c[3]) - max(b[1], c[1])
            if w > 0 and h > 0 and (w * h >= area / 2 or tiny):
                out.add(i)
                break
    return out


def chunks(pdf_path, first_page: int = 0, last_page: int | None = None,
           drop_overlaps: bool = False) -> list[list[list[str]]]:
    """Per text block (column), the list of paragraphs (each a list of raw lines). With drop_overlaps, text blocks
    lying inside a fuller block are skipped (off by default, so existing outputs are unchanged)."""
    doc = fitz.open(pdf_path)
    out = []
    last = len(doc) if last_page is None else last_page
    for pn in range(first_page, last):
        blocks = [b for b in doc[pn].get_text("blocks", sort=False) if b[6] == 0]
        skip = _overlapped(blocks) if drop_overlaps else set()
        for bi, b in enumerate(blocks):
            if bi in skip:
                continue
            paras: list[list[str]] = []
            cur: list[str] = []
            if re.fullmatch(r"\s*\d{1,3}\s*", b[4]):
                continue  # a page number set as a block of its own
            lines = b[4].split("\n")
            heads = {i for i, raw in enumerate(lines) if HEADER.match(norm(raw))}
            # a bare page number printed between the two lines of a running head
            heads |= {i for i, raw in enumerate(lines)
                      if re.fullmatch(r"\s*\d{1,3}\s*", raw) and (i - 1 in heads or i + 1 in heads)}
            for i, raw in enumerate(lines):
                if i in heads:
                    continue
                if not raw.strip():
                    if cur:
                        paras.append(cur)
                        cur = []
                    continue
                n = norm(raw)
                prev = norm(cur[-1]) if cur else ""
                if cur and (ART_START.match(n) or HEAD_LINE.match(n) or (ITEM_START.match(n) and re.search(r"[.;:]$", prev))):
                    paras.append(cur)
                    cur = []
                cur.append(raw)
            if cur:
                paras.append(cur)
            if paras:
                out.append(paras)
    return out


def paragraphs(pdf_path, first_page: int = 0, last_page: int | None = None, drop_overlaps: bool = False) -> list[str]:
    """Paragraph strings in reading order, with paragraphs re-joined across column/page breaks."""
    out: list[str] = []
    for paras in chunks(pdf_path, first_page, last_page, drop_overlaps):
        for i, p in enumerate(paras):
            text = join_lines(p)
            if not text:
                continue
            if i == 0 and out:
                prev = out[-1]
                cont = not re.search(r"[.:;]\"?$", prev) and not STRUCT.match(text) and not HEADING.match(prev)
                if re.match(r"[a-zñáéíóú]", text) and not HEADING.match(prev):
                    cont = True
                if cont:
                    out[-1] = join_lines([prev, text])
                    continue
            out.append(text)
    return out
