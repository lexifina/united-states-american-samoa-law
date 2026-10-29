"""Shared text helpers for the DR Congo parsers: PDF text layer -> clean paragraphs.

Reads only cached bytes (fetch.cache_path). The text layer comes from poppler's `pdftotext -layout -enc UTF-8`
(run on a temporary copy of the cached file), which keeps article numbers that MuPDF splits across lines.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

from fetch import cache_path


def sha256(url: str) -> str:
    return hashlib.sha256(cache_path(url).read_bytes()).hexdigest()


def pdf_text(url: str) -> str:
    data = cache_path(url).read_bytes()
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / 'in.pdf'
        src.write_bytes(data)
        out = subprocess.run(['pdftotext', '-layout', '-enc', 'UTF-8', str(src), '-'], capture_output=True, check=True)
    return out.stdout.decode('utf-8', 'replace')


def norm_chars(s: str) -> str:
    s = unicodedata.normalize('NFC', s)
    s = s.replace(' ', ' ').replace(' ', ' ').replace('\t', ' ').replace('\f', '\n')
    s = s.replace('‘', '’').replace("'", '’')
    s = s.replace('“', '«').replace('”', '»')
    s = s.replace('—', '–').replace('…', '...')
    s = s.replace('', '-').replace('•', '-').replace('', '-')
    s = s.replace('­', '')
    return s


LIST_START = re.compile(r'^(\d+[.°)]|\d+\s*[-–]|[a-z]\)|[a-z][.]\s|[-–•]\s|[ivx]+\)|[A-Z][.)]\s)')
END_PARA = re.compile(r'[.;:!?»]$')
# no paragraph ends on one of these words: a line ending on one continues after a page break or blank line
# ("... aux articles 218 à" / "220 de la présente Constitution ;", "... du parquet près cette" / "Cour ;")
OPEN_TAIL = re.compile(r'(?:^|\s)(?:à|au|aux|de|des|du|la|le|les|ce|cet|cette|ces|et|ou|près|en|par|pour|sur|dans|'
                       r'un|une|entre)$', re.I)


def paragraphs(lines: list[str]) -> list[str]:
    """Join wrapped lines into paragraphs: a paragraph ends at a blank line or at terminal punctuation, and a new one
    starts at a list marker. Hyphenated line ends are joined without a space."""
    paras: list[str] = []
    cur = ''
    gap = False
    for raw in lines:
        line = re.sub(r'\s+', ' ', raw).strip()
        if not line:
            gap = True
            continue
        if cur and gap and not (line[0].islower() and not END_PARA.search(cur)) \
                and not (OPEN_TAIL.search(cur) and not LIST_START.match(line)):
            paras.append(cur)
            cur = ''
        gap = False
        if cur and re.fullmatch(r'\d+[.°)]|[a-z]\)|[-–]', cur):
            cur = cur + ' ' + line  # a list marker alone on its line
            continue
        if cur and (END_PARA.search(cur) or LIST_START.match(line)):
            paras.append(cur)
            cur = ''
        if not cur:
            cur = line
        elif cur.endswith('-') and not cur.endswith(' -'):
            cur = cur + line
        else:
            cur = cur + ' ' + line
    if cur:
        paras.append(cur)
    return [tidy(p) for p in paras if p.strip()]


def tidy(p: str) -> str:
    p = re.sub(r'\s+', ' ', p).strip()
    p = re.sub(r'\s+([,.])', r'\1', p)
    p = re.sub(r'«\s*', '« ', p)
    p = re.sub(r'\s*»', ' »', p)
    p = re.sub(r'\s+([;:!?])', r' \1', p)
    p = re.sub(r'(?<=\w)([;:!?])(?=\s|$)', r' \1', p)
    p = p.replace(' :', ' :').replace('( ', '(').replace(' )', ')')
    return p


def flat(text: str) -> str:
    """Comparison form: one line, single spaces, no space before punctuation."""
    t = re.sub(r'\s+', ' ', text).strip()
    t = re.sub(r'\s+([,.;:!?»)])', r'\1', t)
    t = re.sub(r'([«(])\s+', r'\1', t)
    return t
