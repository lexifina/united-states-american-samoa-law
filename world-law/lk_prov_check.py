"""gitlaw-scraper-dell (2026-10-31): independent letters-and-digits check of a parsed Sri Lanka provincial statute
against its Gazette PDF, read by a second engine (xpdf/poppler pdftotext -raw). Private.

Every word of the record (the "# label" lines and the marginal-note heading lines left out), reduced to ASCII letters
and digits, must be found in order in the PDF's text reduced the same way, from where the statute starts. Between two
words the source may hold only page furniture the parser set aside (running heads, masthead, footers, legacy-font
lines, marginal notes, the Council Secretary's publication notice) and page numbers. After the last word, the same
holds up to the next statute in the issue or the end of the issue.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path


MODE = '-raw'


def ld(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', s)


FURN = re.compile(r'^\s*IV\s*\(|GAZETTE\s+EXTRA\s*ORDINARY\s+OF\s+THE|^\s*\d{1,3}\s*A\s*$|downloaded\s+from'
                  r'|PRINTED\s+AT\s+THE|\bPG\s+\d{3,5}\b|^\s*\d{2}\s*-\s*\d{2,5}(/\d+)?\s*$', re.I)
# Lines in the legacy Sinhala/Tamil fonts (read as Latin-1 garble). A per cent sign counts only inside a word ("m%cd"),
# never after a number ("25%"), so English lines that print a percentage stay in the source (2026-10-31).
GARBLE = re.compile(r"[§úÜ¾¡ÉæøïÌÀ°åºàèÄ¼û¨´Ê]|[A-Za-z;,]%|%[A-Za-z]|\w\$\w|\d{4}'\d{2}'\d{2}")


# The second reader reads each PDF in two orders: content-stream order (-raw) and pdftotext's own physical reading
# order (no flag). A statute passes when every check below holds in full in one of them (2026-10-31: in Gazette issues
# holding several statutes, -raw often lists a later statute's lines between the lines of an earlier one on a shared
# page, and some marginal-note columns come out interleaved with the body; the physical order does not).
MODES = ('-raw', '')


def source(pdf: Path, mode: str | None = None) -> str:
    """pdftotext's own reading, its own page furniture removed line by line (running heads, legacy-font lines, page
    labels, footers), reduced to ASCII letters and digits."""
    mode = MODE if mode is None else mode
    out = subprocess.run(['pdftotext', *([mode] if mode else []), '-enc', 'UTF-8', str(pdf), '-'],
                         capture_output=True).stdout
    keep = [l for l in out.decode('utf-8', 'replace').splitlines() if not FURN.search(l) and not GARBLE.search(l)]
    return ld(' '.join(keep))


def words(units: dict, used_notes: list[str]) -> list[str]:
    out = []
    notes = set(used_notes)
    for u in units.values():
        lines = u['text'].split('\n')
        for k, line in enumerate(lines):
            if not line or line.startswith('# '):
                continue
            if k == 1 and line in notes and u['kind'] == 'section':
                continue
            out += [t for t in (ld(w) for w in line.split()) if t]
    return out


def skip_furniture(S: str, pos: int, aside: list[str]) -> int:
    moved = True
    while moved:
        moved = False
        for a in aside:
            if a and S.startswith(a, pos):
                pos += len(a)
                moved = True
                break
        if not moved:
            m = re.match(r'\d{1,3}A?', S[pos:])
            if m and m.end() <= 4:
                # a page label is only skipped when what follows is furniture or the end; the caller retries the word
                pass
    return pos


def furniture_only(gap: str, aside: list[str]) -> bool:
    for a in aside:
        if a:
            gap = gap.replace(a, '')
    return len(gap) <= 6 and re.fullmatch(r'[0-9A]*', gap) is not None


def align(R: str, S: str, pos: int, aside: list[str]) -> tuple[int, int] | str:
    """Find R in S from pos with only furniture in its gaps; (start, end) or an error message. Each place R's opening
    occurs is tried in turn (a statute's enacting words can repeat those of an earlier statute in the same issue); the
    first place where the whole paragraph aligns is taken, and the error is the first place's."""
    first = None
    at = S.find(R[:40], pos)
    if at < 0:
        return f'start "{R[:40]}" not found'
    while at >= 0:
        got = align_at(R, S, at, aside)
        if not isinstance(got, str):
            return got
        first = first or got
        at = S.find(R[:40], at + 1)
    return first


def align_at(R: str, S: str, pos: int, aside: list[str]) -> tuple[int, int] | str:
    start, ri = pos, 0
    while ri < len(R):
        n = 0
        while ri + n < len(R) and pos + n < len(S) and R[ri + n] == S[pos + n]:
            n += 1
        ri += n
        pos += n
        if ri >= len(R):
            break
        probe = R[ri:ri + 30]
        i = S.find(probe, pos)
        if i < 0:
            return f'record text "{probe}" not found after source position {pos}'
        if not furniture_only(S[pos:i], aside):
            return f'before "{probe}" the source has "{S[pos:i][:100]}" that is not in the record'
        pos = i
    return start, pos


def check_act(units: dict, used_notes: list[str], S: str, aside_texts: list[str], end_hint: str | None) -> tuple[bool, str]:
    """Each paragraph is found whole (only furniture inside it); the paragraphs together must cover the statute's stretch
    of the source (the content-stream order may put a heading block after the text below it), leaving only furniture."""
    # Set-aside texts of one or two letters (legacy-font fragments) are not used: removing every "a" or "c" from a gap
    # would let real text pass as furniture (2026-10-31; was >= 1).
    aside = sorted({ld(a) for a in aside_texts if len(ld(a)) >= 3}, key=len, reverse=True)
    spans = []
    prev = 0
    paras = []
    for key, u in units.items():
        lines = u['text'].split('\n')
        for k, line in enumerate(lines):
            if not line or line.startswith('# ') or (k == 1 and u['kind'] == 'section' and line in set(used_notes)):
                continue
            R = ''.join(ld(w) for w in line.split())
            if R:
                paras.append((key, R))
    for key, R in paras:
        got = align(R, S, prev, aside)
        if isinstance(got, str):
            got = align(R, S, 0, aside)
        if isinstance(got, str):
            return False, f'{key}: {got}'
        spans.append(got)
        prev = got[1]
    if not spans:
        return False, 'empty record'
    spans.sort()
    lo, hi = spans[0][0], max(e for _, e in spans)
    cur = lo
    for st, en in spans:
        if st > cur and not furniture_only(S[cur:st], aside):
            return False, f'source text between units is not in the record: "{S[cur:st][:100]}"'
        cur = max(cur, en)
    end = len(S)
    if end_hint:
        j = S.find(ld(end_hint), hi)
        if j >= 0:
            end = j
    if not furniture_only(S[hi:end], aside):
        return False, f'source text after the last unit is not in the record: "{S[hi:hi + 100]}"'
    return True, 'ok'
