"""The Constitution of 8 November 2016 (Loi n° 2016-886) and its revision by Loi constitutionnelle n° 2020-348.

Two born-digital sources with a text layer, both cached by fetch.py:
- AN_2016: the Assemblée nationale's PDF "Loi n° 2016-886 du 08 novembre 2016 portant Constitution", the text as
  promulgated (signed "Fait à Abidjan, le 08 novembre 2016").
- WIPO_2020: WIPO Lex record 22491, "Loi n° 2016-886 ... telle que modifiée par la loi constitutionnelle n°2020-348
  du 19 mars 2020" (author "Côte d'Ivoire"), which marks each article the 2020 law rewrote "Article N - Nouveau".

Version 2 (2020-03-19) is version 1 with every article marked "Nouveau" replaced by its WIPO text, credited to
Loi 2020-348 (the source's own marker). Every article not so marked is compared word for word with WIPO; those that
agree keep the 2016 wording (no change). Any that do not agree are listed by `report()` and handled in parse.py.
"""
from __future__ import annotations

import html
import re
import unicodedata

from fetch import fetch
from pdftext import paragraphs

AN_2016 = ('https://www.assnat.ci/IMG/pdf/constitution_de_la_republique_de_cote_d_ivoireloi_-_no_2016-886_du_08_'
           'novembre_2016.pdf')
WIPO_2020 = ('https://wipolex-res.wipo.int/edocs/lexdocs/laws/fr/ci/ci023fr_1.pdf?last-modified=1773752329&Expires='
             '1793224426&Signature=P451hFRNMHwdF8sa3jTIFfjMInu0Hb5--7U9P5DbbEVowLv4mfTZ4iKsg4ox5MWvCYBYsZoOVZcjXLgf5DWj'
             '5xcUlVlzRCk~ZLz2DiMAEz1GjA-H0cpY4uKirMcgSEs-QjOCUHtmiiYULJ3SDiojoTwEim7KlXixVGG31EgGjXum5RDm4q95CYKp8jUE2'
             'yLllSRhgL3PCTAcGJWh5lxIkFYd3B82T9ldpozcn3kinaktzjEMKS8qHEqbFs~38WAyOcs50p70wkSerm7m1uZgbV~4m0kZR8zCZBzNQ'
             'gwBn931RHyyfs9RPcUs9QOWn7ccRhWUunI5ZqPq3Lh3xS1rmQ__&Key-Pair-Id=K1QGBX7Y6FHYJN')
WIPO_2020_STABLE = 'https://wipolex-res.wipo.int/edocs/lexdocs/laws/fr/ci/ci023fr_1.pdf'
WIPO_RECORD = 'https://www.wipo.int/wipolex/fr/legislation/details/22491'
# WIPO serves the PDF only through a signed link printed on the record page (the bare file URL answers with an HTML
# page), so the PDF is read through the link in the cached record page; WIPO_2020 is the link in today's cache.
WIPO_PDF_LINK = re.compile(r'https://wipolex-res\.wipo\.int/edocs/lexdocs/laws/fr/ci/ci023fr_1\.pdf\?[^"\'\s<>]+')


def wipo_pdf_url(record: bytes) -> str:
    return html.unescape(WIPO_PDF_LINK.search(record.decode('utf-8')).group(0))

HEADING = re.compile(r'^(TITRE|CHAPITRE|SECTION|PREAMBULE|PRÉAMBULE)\b', re.I)
END = re.compile(r'^Fait à Abidjan', re.I)


def words(s: str) -> list[str]:
    """Words for comparing two transcriptions: case, accents, punctuation and line-wrap hyphens ignored."""
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'(\w)- (\w)', r'\1\2', s)
    s = s.replace('-', '')
    return re.sub(r'[^\w]+', ' ', s).split()


def _hyphen_words(*texts: str) -> set[str]:
    """Words printed whole (not split at a line end) anywhere in the sources: a split "écono- mique" or a line-end
    "abso-" + "lue" is joined only if the whole word is printed somewhere."""
    out = set()
    for t in texts:
        out.update(w.lower() for w in re.findall(r'\w+', t))
    return out


def _structure(paras: list[tuple[str, bool]], marked: bool) -> tuple[str, dict[int, list[str]], dict[int, bool]]:
    """(preamble text, {article number: paragraphs}, {article number: marked "Nouveau"}). Title, chapter and
    section headings end the article before them and are not part of any article."""
    pre: list[str] = []
    arts: dict[int, list[str]] = {}
    new: dict[int, bool] = {}
    cur = None
    in_pre = False
    expanded: list[tuple[str, bool]] = []
    for text, bold in paras:
        # The AN PDF glues a heading's second line to the next article's heading in one block:
        # "DE LA REPUBLIQUE Article 165". Split the article heading off.
        m = re.match(r'^(.*\S)\s+(Article\s+\d+)$', text)
        if m and bold and m.group(1).upper() == m.group(1):
            expanded += [(m.group(1), bold), (m.group(2), bold)]
        else:
            expanded.append((text, bold))
    for text, bold in expanded:
        if END.match(text):
            break
        # "PRÉAMBULE" (AN) or letter-spaced "P R É A M B U L E" (WIPO).
        if re.match(r'^P\s*R\s*[EÉ]\s*A\s*M\s*B\s*U\s*L\s*E$', text, re.I):
            in_pre = True
            continue
        m = re.match(r'^Article\s+(\d+)\s*(-\s*Nouveau\s*)?\.?\s*(?:—\s*)?(.*)$', text, re.S)
        if m and (marked or not m.group(3)):
            cur = int(m.group(1))
            in_pre = False
            arts[cur] = [m.group(3).strip()] if m.group(3).strip() else []
            new[cur] = bool(m.group(2))
            continue
        if HEADING.match(text) or (bold and text.upper() == text and not text[:1].isdigit()):
            cur = None
            in_pre = False
            continue
        # WIPO glues the next chapter or title heading to the end of an article's last line: "… judiciaire. CHAPITRE 3".
        g = re.match(r'^(.*?[.;:»])\s+((?:CHAPITRE|TITRE)\s+[\dIVXL]+(?:\s+NOUVEAU)?)$', text)
        if in_pre:
            pre.append(text)
        elif cur is not None:
            arts[cur].append(g.group(1) if g else text)
        if g:
            cur = None
            in_pre = False
    return '\n'.join(pre), arts, new


END_PUNCT = re.compile(r'[.;:!?»]$')
LIST_MARK = re.compile(r'^[-•—]\s*')


def repair(paras: list[str]) -> list[str]:
    """One paragraph or list item per line. The AN PDF blocks list items together ("… ; - la nationalité, …") and
    breaks blocks mid-sentence. A paragraph that does not end in . ; : ! ? » runs on into the next, as does one followed
    by a paragraph starting in lower case or with ";". Items are then split at "; -". List markers (-, •, the Symbol
    font bullet U+F0B7, —) are normalised to "— "."""
    out: list[str] = []
    for p in paras:
        if out and (not END_PUNCT.search(out[-1]) or p[:1].islower() or p[:1] in ';,'):
            out[-1] = out[-1] + ' ' + p
        else:
            out.append(p)
    items: list[str] = []
    for p in out:
        items += re.split(r'(?<=;)\s+(?=[-•—]\s?\w)', p)
    return [LIST_MARK.sub('— ', i) if LIST_MARK.match(i) else i for i in items]


def split_like(new: list[str], *witnesses: list[str], k: int = 6) -> tuple[list[str], int]:
    """WIPO's PDF reflows the text and runs some paragraphs together (it does so in 10 articles the 2020 law left
    alone). Split a paragraph after a sentence end when another witness of the same article (the 2016 text, WIPO's HTML
    rendering) breaks a paragraph at exactly that point: the k words before end one of its paragraphs and the k words
    after begin the next one. Returns (paragraphs, number of splits)."""
    breaks = {(tuple(words(a)[-k:]), tuple(words(b)[:k])) for old in witnesses for a, b in zip(old, old[1:])}
    out, n = [], 0
    for p in new:
        cut = 0
        for m in re.finditer(r'(?<=[.;:])\s+(?=[A-ZÀ-Ý«—])', p):
            if (tuple(words(p[cut:m.start()])[-k:]), tuple(words(p[m.end():])[:k])) in breaks:
                out.append(p[cut:m.start()])
                cut = m.end()
                n += 1
        out.append(p[cut:])
    return out, n


def _join_spaced_hyphens(t: str, hw: set[str], hw_hyph: set[str] = frozenset()) -> str:
    """WIPO's text keeps the Journal officiel's column hyphenation as "écono- mique": joined when the whole word is
    printed somewhere, otherwise read as a real hyphen ("lui- même" -> "lui-même")."""
    def rep(m):
        w = m.group(1) + m.group(2)
        return w if w.lower() in hw else m.group(1) + '-' + m.group(2)
    t = re.sub(r'(\w+)- (\w+)', rep, t)

    def rep2(m):
        w = m.group(1) + m.group(2)
        return w if w.lower() in hw and m.group(0).lower() not in hw_hyph else m.group(0)
    # Hyphens left inside a word by the JO's column breaks: "empêche-ment", "impossibi-lité".
    return re.sub(r'(\w+)-(\w+)', rep2, t)


def wipo_html_articles(data: bytes) -> dict[int, list[str]]:
    """The article paragraphs of WIPO's HTML rendering of the same 2020 text (record page, one <p> per paragraph). It
    drops spaces between some words ("cettefin"), so it is used only as a witness for paragraph breaks."""
    t = data.decode('utf-8')
    t = t[t.find('<h1>PRÉAMBULE'):]
    arts: dict[int, list[str]] = {}
    cur = None
    for b in re.findall(r'<(?:p|h\d|li)[^>]*>(.*?)</(?:p|h\d|li)>', t, flags=re.S):
        b = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', b))).strip()
        if not b:
            continue
        m = re.match(r'Article (\d+)\s*(?:-\s*Nouveau)?\s*\.?\s*—?\s*(.*)$', b)
        if m:
            cur = int(m.group(1))
            arts[cur] = [m.group(2)] if m.group(2) else []
        elif re.match(r'(CHAPITRE|TITRE|Fait à)', b):
            cur = None
        elif cur:
            arts[cur].append(b)
    return arts


# WIPO's transcription prints "Journal official" in art. 177 (both its PDF and its HTML); the paragraph is otherwise
# word for word the 2016 paragraph, which reads "Journal officiel". Recorded in parse.py decisions.
SLIPS = {177: [('Journal official', 'Journal officiel')]}


def v2_articles(d: dict) -> tuple[dict[int, list[str]], list[str]]:
    """{article: paragraphs} for every article WIPO marks "Nouveau", and a log of what was done to them."""
    html_arts = wipo_html_articles(fetch(WIPO_RECORD, offline=True))
    out, log = {}, []
    for n in sorted(k for k, v in d['new20'].items() if v):
        ps = d['a20'][n]
        for a, b in SLIPS.get(n, []):
            ps = [p.replace(a, b) for p in ps]
            log.append(f'art. {n}: "{a}" read as "{b}"')
        ps, k = split_like(ps, d['a16'][n], html_arts.get(n, []))
        if k:
            log.append(f'art. {n}: {k} paragraph break(s) restored')
        if words(' '.join(ps)) != words(' '.join(html_arts.get(n, []))):
            log.append(f'art. {n}: WIPO PDF and HTML words differ')
        old = {tuple(words(p)): p for p in d['a16'][n]}
        kept = [old.get(tuple(words(p)), p) for p in ps]
        same = sum(1 for p, q in zip(ps, kept) if p is not q)
        if same:
            log.append(f'art. {n}: {same} of {len(ps)} paragraph(s) word for word as in 2016, 2016 typesetting kept')
        out[n] = kept
    return out, log


def load() -> dict:
    an_b = fetch(AN_2016, offline=True)
    wi_b = fetch(wipo_pdf_url(fetch(WIPO_RECORD, offline=True)), offline=True)
    raw_an = paragraphs(an_b, 'blocks')
    hw = _hyphen_words(*(t for t, _ in raw_an))
    raw_wi = paragraphs(wi_b, 'margin', hyphen_words=hw)
    hw = hw | _hyphen_words(*(t for t, _ in raw_wi))
    hw_hyph = {w.lower() for t, _ in raw_an for w in re.findall(r'\w+-\w+', t)}
    raw_wi = [(_join_spaced_hyphens(t, hw, hw_hyph), b) for t, b in raw_wi]
    pre16, a16, _ = _structure(raw_an, marked=False)
    pre20, a20, new20 = _structure(raw_wi, marked=True)
    pre16, pre20 = '\n'.join(repair(pre16.split('\n'))), '\n'.join(repair(pre20.split('\n')))
    a16 = {n: repair(ps) for n, ps in a16.items()}
    a20 = {n: repair(ps) for n, ps in a20.items()}
    return {'pre16': pre16, 'a16': a16, 'pre20': pre20, 'a20': a20, 'new20': new20,
            'an_bytes': an_b, 'wipo_bytes': wi_b}
