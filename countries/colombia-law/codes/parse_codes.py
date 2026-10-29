"""Build corpus.d/50-codes.json for Colombia: the Código Civil and Ley 1581 de 2012 (data protection).

Reads only ../.cache/ (written by ../fetch.py and fetch_codes.py); no network. Deterministic: same cache, same bytes.
Owned by the Colombia "codes" helper; the Constitution is built by ../parse.py into ../corpus.json. This file began
as a copy of ../parse.py (the same basedoc layout and the same per-provision reconstruction engine), generalised
from Actos Legislativos to Leyes, Decretos and Constitutional Court rulings.

The basedoc gives today's text of each act with, per provision:
  * inline amendment markers ("<Artículo modificado por el artículo 1o. del Decreto 2820 de 1974. El nuevo texto
    es el siguiente:>"), struck text for parts the Constitutional Court struck (<s>, "<Aparte tachado INEXEQUIBLE>");
  * note boxes, held in one JavaScript file per page: "Notas de Vigencia" (which act changed it, Diario Oficial
    and date), "Jurisprudencia Vigencia" (Constitutional Court rulings) and "Legislación Anterior" (the earlier
    texts: "Texto original del Código Civil:", "Texto modificado por la Ley 1a. de 1976:").

Usage:  python -X utf8 parse_codes.py            (writes ../corpus.d/50-codes.json atomically)
        python -X utf8 parse_codes.py --report   (also prints the reconstruction gaps)
        python -X utf8 parse_codes.py --out <file>
"""
from __future__ import annotations

import collections
import difflib
import hashlib
import html
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
COUNTRY = os.path.dirname(HERE)
CACHE = os.path.join(COUNTRY, ".cache")
BASE = "http://www.secretariasenado.gov.co/senado/basedoc/"
RETRIEVED = "2026-10-28"

MONTHS = {m: i + 1 for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split())}
MONTHS["setiembre"] = 9

REPORT: list[str] = []


def note(msg: str) -> None:
    REPORT.append(msg)


# ---------------------------------------------------------------- cache

def cache_path(url: str) -> str:
    return os.path.join(CACHE, hashlib.sha256(url.encode("utf-8")).hexdigest())


def read(url: str) -> str | None:
    p = cache_path(url)
    if not os.path.exists(p):
        return None
    with open(p, "rb") as f:
        return f.read().decode("latin-1")


def raw(url: str) -> bytes:
    with open(cache_path(url), "rb") as f:
        return f.read()


def request_count() -> int:
    p = os.path.join(CACHE, "requests.jsonl")
    if not os.path.exists(p):
        return 0
    with open(p, encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


# ---------------------------------------------------------------- text

def norm(s: str) -> str:
    """Normalise publisher typesetting: NBSP, runs of spaces, quotes, dashes."""
    s = unicodedata.normalize("NFC", s)
    s = s.replace(" ", " ").replace("​", "")
    s = re.sub(r"[‘’‚´`]", "'", s)
    s = re.sub(r"[“”„«»]", '"', s)
    s = re.sub(r"[–—−]", "-", s)
    s = s.replace("…", "...")
    s = re.sub(r"[ \t\r\n]+", " ", s)
    return s.strip()


def strip_markers(h: str) -> str:
    """Drop Avance Jurídico's editorial markers, written as &lt;...&gt; in the page (they may hold links)."""
    return re.sub(r"&lt;.*?&gt;", " ", h, flags=re.S)


def markers(h: str) -> list[str]:
    return [norm_refs(norm(html.unescape(re.sub(r"<[^>]+>", "", m))).replace('"', "").replace("'", ""))
            for m in re.findall(r"&lt;(.*?)&gt;", h, flags=re.S)]


def to_text(h: str, keep_struck: bool = True, drop_underlined: bool = False) -> str:
    h = strip_markers(h)
    if not keep_struck:
        h = re.sub(r"<s\b[^>]*>.*?</s>", " ", h, flags=re.S | re.I)
    if drop_underlined:
        h = re.sub(r"<u\b[^>]*>.*?</u>", " ", h, flags=re.S | re.I)
    h = re.sub(r"<br\s*/?>", " ", h, flags=re.I)
    h = re.sub(r"<[^>]+>", "", h)
    return norm(html.unescape(h))


def tidy(t: str) -> str:
    """Spacing left behind where markers or struck text were cut out."""
    t = re.sub(r"\s+([,.;:])", r"\1", t)
    t = re.sub(r"\(\s+", "(", t)
    t = re.sub(r"\s+\)", ")", t)
    return re.sub(r" {2,}", " ", t).strip()


def plain(h: str) -> str:
    return norm(html.unescape(re.sub(r"<[^>]+>", "", h)))


def date_es(s: str) -> str | None:
    m = re.search(r"(\d{1,2})(?:o\.|º|°)?\s+(?:de\s+)?([a-zA-Z]+)\s+(?:(?:de|del)\s+)*(\d{4})", s)
    if not m or m.group(2).lower() not in MONTHS:
        return None
    return f"{int(m.group(3)):04d}-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"


# ---------------------------------------------------------------- basedoc pages

def pages(name: str) -> list[str]:
    base = read(BASE + name + ".html")
    if base is None:
        raise SystemExit(f"not cached: {name}; run fetch.py doc {name}")
    nums = sorted(set(re.findall(r'value="_pr(\d{3})', base)) | set(re.findall(re.escape(name) + r"_pr(\d{3})\.html", base)))
    return [name] + [f"{name}_pr{n}" for n in nums]


def doc_sha(name: str) -> str:
    h = hashlib.sha256()
    for pg in pages(name):
        for u in (BASE + pg + ".html", BASE + "js/" + pg + ".js"):
            if os.path.exists(cache_path(u)):
                h.update(raw(u))
    return h.hexdigest()


def js_boxes(js: str | None) -> dict[str, str]:
    out = {}
    for m in re.finditer(r"function insRow(\d+)\(\)\s*\{(.*?)\n\}", js or "", re.S):
        d = re.search(r'description\[0\]\s*=\s*"(.*?)";\s*\n', m.group(2), re.S)
        out[m.group(1)] = d.group(1) if d else ""
    return out


TOK = re.compile(r'<p\b[^>]*>(.*?)</p>|<div><a class="caja_vja_encabezado[^"]*" href="javascript:insRow(\d+)\(\)">(.*?)</a></div>',
                 re.S | re.I)
ANC = re.compile(r'<a (?:class="?bookmarkaj"? )?name="([^"]*)">(.*?)</a>', re.I | re.S)


def doc_units(name: str) -> list[dict]:
    """Split a basedoc document into anchored blocks: [{name, label, items: [('p', html) | ('box', title, html)]}]."""
    res = [{"name": "_head", "label": "", "items": [], "page": name}]
    cur = res[0]
    for pg in pages(name):
        h = read(BASE + pg + ".html") or ""
        js = js_boxes(read(BASE + "js/" + pg + ".js"))
        i, j = h.find("<!--Inicio documento-->"), h.find("<!--Fin documento-->")
        for m in TOK.finditer(h[i:j if j > 0 else len(h)]):
            if m.group(1) is not None:
                p = m.group(1)
                a = ANC.search(p)
                if a and html.unescape(a.group(1)).strip().lower() not in ("top", "inicio"):
                    cur = {"name": html.unescape(a.group(1)).strip(), "label": plain(a.group(2)), "items": [], "page": pg}
                    res.append(cur)
                    p = p[:a.start()] + p[a.end():]
                else:
                    # An article heading the publisher left without an anchor ("ARTICULO 247. ...").
                    h2 = re.match(r"\s*(ART(?:I|&Iacute;|Í)CULO\s+(\d+[A-Z]?)o?\.)\s*", p)
                    if h2 and not any(u["name"] == h2.group(2) for u in res):
                        cur = {"name": h2.group(2), "label": plain(h2.group(1)), "items": [], "page": pg}
                        res.append(cur)
                        p = p[h2.end():]
                cur["items"].append(("p", p))
            else:
                cur["items"].append(("box", box_title(plain(m.group(3))), js.get(m.group(2), "")))
    return res


BOX_TITLES = {t.lower(): t for t in ("Notas de Vigencia", "Jurisprudencia Vigencia", "Legislación Anterior",
                                     "Notas del Editor", "Concordancias", "Resumen de Notas de Vigencia")}
BOX_TITLES["notase vigencia"] = "Notas de Vigencia"


def box_title(t: str) -> str:
    """The publisher's box titles vary in case ("Notas de vigencia"); one form each."""
    return BOX_TITLES.get(t.strip().lower(), t)


def box_paras(b: str) -> list[str]:
    return re.findall(r"<p\b[^>]*>(.*?)</p>", b, re.S | re.I)


# ---------------------------------------------------------------- laws

LAWS: dict[str, dict] = {}

# How the notes write an amending act: "Ley 57 de 1887", "Ley 1a. de 1976", "Decreto 2820 de 1974",
# "Decreto Ley 1400 de 1970", "Ley 2442 de 27 de diciembre de 2024".
AL_RE = re.compile(r"\b([Ll]ey|[Dd]ecreto(?:[- ][Ll]ey| Legislativo| Extraordinario)?)\s+(?:No\.\s*|número\s*)?(\d[\d.]*)"
                   r"(?:a\.|o\.|ª|º)?\s+(?:de\s+\d{1,2}\s+de\s+[a-z]+\s+)?de\s+(\d{4})")
# Typing slips in the notes, fixed by what the same note says (its Diario Oficial date or the act's kind).
KEY_FIXES = {"ley-25-1892": "ley-25-1992", "ley-2820-1974": "dec-2820-1974", "ley-95-1980": "ley-95-1890"}
# Codes the notes cite by name only.
CODE_NAMES = [
    (re.compile(r"C[óo]digo de Procedimiento Civil(?:\s*-\s*Decreto 1400 de 1970)?|C\.\s?P\.\s?C\.(?=[\s,.])"), "Decreto 1400 de 1970"),
    (re.compile(r"C\.\s?S\.\s?del\s?T\."), "Decreto 2663 de 1950"),
]
LAW_PAGE = {}  # law key -> basedoc page name, or the URL of the Colpensiones copy (when a source has the act)
# Acts the basedoc keeps under a code's name.
CODE_PAGES = {"dec-1400-1970": "codigo_procedimiento_civil", "dec-2737-1989": "codigo_menor"}
# The same Avance Jurídico compilation as published by Colpensiones (a state company); used only for the heading
# (sanction and Diario Oficial days) and the vigencia clause of acts the basedoc does not hold.
COLPENSIONES = "https://normativa.colpensiones.gov.co/colpens/docs/"


def norm_refs(t: str) -> str:
    for rx, rep in CODE_NAMES:
        t = rx.sub(rep, t)
    return t


def al_key(kind: str, n: str, y: str) -> str:
    k = f"{'dec' if kind.lower().startswith('decreto') else 'ley'}-{int(n.replace('.', ''))}-{y}"
    return KEY_FIXES.get(k, k)


def law_label(key: str) -> str:
    kind, n, y = key.split("-")
    return f"{'Decreto' if kind == 'dec' else 'Ley'} {n} de {y}"


def register(key: str) -> str:
    if key not in LAWS:
        kind, n, y = key.split("-")
        page = CODE_PAGES.get(key) or f"{'decreto' if kind == 'dec' else 'ley'}_{int(n):04d}_{y}"
        url = None
        if os.path.exists(cache_path(BASE + page + ".html")):
            url = BASE + page + ".html"
            LAW_PAGE[key] = page
        elif os.path.exists(cache_path(COLPENSIONES + page + ".htm")):
            url = COLPENSIONES + page + ".htm"
            LAW_PAGE[key] = url
        LAWS[key] = {"label": law_label(key), "title": TITLES.get(key) or law_label(key),
                     "kind": "decree" if kind == "dec" else "law", "enacted": None,
                     "published": PUB.get(key), "url": url,
                     "temporary_until": None, "restores": None, "note": None}
        compute_in_force(key)
    return key


def al_from_note(kind: str, n: str, y: str, text: str) -> str:
    return register(al_key(kind, n, y))


# Per-provision vigencia, as the provision's own note states it ("La derogatoria rige a partir del 1o. de enero
# de 2014"): set while one provision is parsed.
UNIT_DAYS: dict[str, str] = {}
IN_FORCE: dict[str, str] = {}   # law key -> in-force day
IN_FORCE_WHY: dict[str, str] = {}
PUB: dict[str, str] = {}        # law key -> Diario Oficial day
TITLES: dict[str, str] = {}


def law_day(key: str) -> str | None:
    if key in UNIT_DAYS:
        return UNIT_DAYS[key]
    if key in IN_FORCE:
        return IN_FORCE[key]
    law = LAWS.get(key)
    return law and (law.get("enacted") or law.get("published"))


MONTH_FIRST = re.compile(r"\b([a-z]+)\s+(\d{1,2})(?:o\.|º)?\s+(?:de|del)\s+(\d{4})")


def date_any(s: str) -> str | None:
    d = date_es(s)
    m = MONTH_FIRST.match(s.strip())
    if m and m.group(1).lower() in MONTHS and (not d or s.strip().index(m.group(0)) == 0):
        return f"{int(m.group(3)):04d}-{MONTHS[m.group(1).lower()]:02d}-{int(m.group(2)):02d}"
    return d


RULING_RE = re.compile(r"(?:Sentencia|Auto)\s+(?:No\.\s*)?(C-\d+A?-\d{2,4})\s*,?\s+(?:de la Sala Plena\s+)?(?:de|del)\s+"
                       r"(\d{1,2}(?:o\.|º)?\s+de\s+[a-z]+\s+(?:de\s+)?\d{4}|[a-z]+\s+\d{1,2}(?:o\.|º)?\s+de\s+\d{4})", re.I)


def court_key(c: str) -> str:
    m = re.match(r"([A-Z]+)-(\d+)([A-Z]?)-(\d{2,4})", c.upper())
    pre, num, suf, yy = m.groups()
    y = int(yy)
    y = y if y > 1000 else (1900 + y if y > 50 else 2000 + y)
    return f"{pre.lower()}-{int(num):03d}{suf.lower()}-{y % 100:02d}"


def court_label(c: str) -> str:
    m = re.match(r"([A-Z]+)-(\d+)([A-Z]?)-(\d{2,4})", c.upper())
    pre, num, suf, yy = m.groups()
    y = int(yy)
    y = y if y > 1000 else (1900 + y if y > 50 else 2000 + y)
    return f"Sentencia {pre}-{int(num):03d}{suf} de {y}"


def add_court(cid: str, date: str, href: str | None, note_text: str | None = None) -> str:
    k = court_key(cid)
    law = LAWS.get(k)
    if law is None:
        LAWS[k] = {"label": court_label(cid), "title": f"Corte Constitucional, {court_label(cid)}", "kind": "court",
                   "enacted": date, "published": None,
                   "url": BASE + href if href else None, "temporary_until": None, "restores": None, "note": note_text}
    elif note_text and not law.get("note"):
        law["note"] = note_text
    return k


# ---------------------------------------------------------------- one article

class Unknown:
    pass


UNKNOWN = Unknown()
GACETA125 = "aclaracion-gaceta-125"


def parse_header(h: str) -> tuple[str, str | None] | None:
    """Map a 'Legislación Anterior' heading to a state: ('orig', None) | ('after', law) | ('before', law)."""
    t = norm_refs(h).rstrip(" :.")
    if not t.lower().startswith("texto"):
        return None
    if re.match(r"Texto vigente hasta su declaratoria de INEXEQUIBILIDAD", t, re.I):
        return ("before_ruling", None)
    als = [al_from_note(*g, "") for g in AL_RE.findall(t)]
    if re.search(r"(antes de|hasta) la (modificaci|derogatori)", t) and als:
        return ("before", als[-1])
    if als:
        return ("after", max(als, key=lambda k: (law_day(k) or "", k)))
    if re.match(r"Texto original", t):
        return ("orig", None)
    return None


def la_blocks(b: str) -> list[dict]:
    """Split a Legislación Anterior box into headed blocks."""
    blocks = []
    cur = None
    for ph in box_paras(b):
        sp = re.match(r"(?:\s|&#160;|&nbsp;)*<span class='b_aj'>(.*?)</span>(?:\s|&#160;|&nbsp;)*$", ph, re.S)
        head = plain(sp.group(1)) if sp else None
        st = parse_header(head) if head else None
        if head and st is None and head.lower().startswith("texto"):
            note(f"unparsed heading: {head}")
        if st is not None:
            cur = {"head": head, "state": st, "struck": "INEXEQUIBLE" in head.upper(), "paras": []}
            blocks.append(cur)
            continue
        if cur is not None:
            cur["paras"].append(ph)
    return blocks


ART_HEAD = re.compile(r"^\s*ART[IÍ]CULO\s+(TRANSITORIO\s*)?([0-9]+[A-Z]?|NUEVO|[IVXL]+)?\s*(?:o\.|º|°)?\s*[.\-:]*\s*", re.I)


def block_text(paras: list[str], full: bool) -> list[str]:
    out = []
    for i, ph in enumerate(paras):
        t = tidy(to_text(ph))
        if i == 0 and full:
            t = ART_HEAD.sub("", t, count=1)
            t = tidy(t)
        if t and not re.fullmatch(r"\(?\.\.\.\)?", t):
            out.append(t)
    return out


def patch_paras(lines: list[str], frag: list[str]) -> list[str] | None:
    """Replace, for each fragment line, the most similar line of `lines` (ratio >= 0.6), or None."""
    out = list(lines)
    for f in frag:
        best = max(range(len(out)), key=lambda i: (difflib.SequenceMatcher(None, out[i], f).ratio(), -i))
        if difflib.SequenceMatcher(None, out[best], f).ratio() < 0.6:
            return None
        out[best] = f
    return out


def para_label(t: str) -> str | None:
    """The enumeration label a paragraph starts with: '8.', 'b)', 'PARÁGRAFO 2o.' (normalised)."""
    m = re.match(r"\s*(\d{1,2}[A-Za-z]?)\s*[.)]\s", t)
    if m:
        return m.group(1).lower() + "."
    m = re.match(r"\s*([a-zñ])\)\s", t)
    if m:
        return m.group(1) + ")"
    m = re.match(r"\s*PAR[ÁA]GRAFO(\s+TRANSITORIO)?(\s+\d+|\s+[A-ZÚ][a-zú]+)?", t, re.I)
    if m:
        return "par" + (" t" if m.group(1) else "") + (" " + m.group(2).strip().lower() if m.group(2) else "")
    return None


def is_full(paras: list[str]) -> bool:
    return bool(paras) and bool(re.match(r"\s*ART[IÍ]CULO\b", to_text(paras[0]), re.I))


TACIT = re.compile(r"t[áa]citamente|org[áa]nicamente", re.I)
VERB = r"(modificad|adicionad|subrogad|derogad|sustituid|corregid|reformad)"
SCOPE_ART = re.compile(r"^-?\s*Art[íi]culo\s+(?:transitorio\s+)?" + VERB, re.I)


def parse_notes(items) -> tuple[list[dict], list[dict]]:
    """Notas de Vigencia -> amendment events; Jurisprudencia Vigencia -> rulings."""
    nv, jv = [], []
    for kind, *rest in items:
        if kind != "box":
            continue
        title, b = rest
        if title == "Notas de Vigencia":
            for ph in box_paras(b):
                t = norm_refs(plain(ph))
                if not t.startswith("-") or re.search(r"t[áa]citamente|org[áa]nicamente", t):
                    continue
                als = AL_RE.findall(t)
                if not als or not re.search(VERB, t, re.I):
                    continue
                keys = [al_from_note(*g, t) for g in als[:1]]
                unit_day(keys[0], t)
                nv.append({"text": t, "law": keys[0], "article": bool(SCOPE_ART.match(t)),
                           "verb": (re.search(VERB, t, re.I).group(1).lower()),
                           "struck": "INEXEQUIBLE" in t.upper()})
        if title in ("Jurisprudencia Vigencia", "Notas de Vigencia"):
            # Rulings: in the Jurisprudencia box, and sometimes in the Notas de Vigencia ('Artículo declarado
            # INEXEQUIBLE por la Corte Constitucional, mediante Sentencia C-379-98 ...').
            for ph in box_paras(b):
                t = plain(ph)
                if title == "Notas de Vigencia" and "Corte Constitucional" not in t:
                    continue
                if not t.startswith("-") or "estarse a lo resuelto" in t or re.match(r"- La Corte Constitucional se declar\S+ INHIBID", t, re.I):
                    continue
                m = RULING_RE.search(t)
                if not m:
                    continue
                d = date_any(m.group(2))
                href = re.search(r"href='([^'#]+\.html)", ph)
                up = t.upper()
                dm = re.search(r"DECLARAD[OA]S?\s+(CONDICIONALMENTE\s+)?(IN)?EXEQUIBLES?", up)
                if not dm:
                    continue
                if dm.group(2) or re.search(r"\bSE DECLARA\w*\s+INEXEQUIBLE|TACHAD\w*[^.]{0,40}INEXEQUIBLE", up) or re.search(r"(?:DECLARAD|DELCRAD)[OA]S?\s+INEXEQUIBLES?(?![\s,]+(EN|POR) LA (SENTENCIA )?C-)", up):
                    dec = "inexequible"
                elif dm.group(1) or "EN EL ENTENDIDO" in up or "BAJO EL ENTENDIDO" in up:
                    dec = "conditional"
                else:
                    dec = "exequible"
                subj_al = AL_RE.search(t.split("declarad")[0]) if "declarad" in t else None
                jv.append({"text": t, "id": m.group(1), "date": d, "href": href.group(1) if href else None, "dec": dec,
                           "al": al_key(*subj_al.groups()) if subj_al else None})
    return nv, jv


PARA_MARK = re.compile(r"^(Inciso|Incisos|Par[áa]grafo|Par[áa]grafos|Numeral|Numerales|Literal|Literales|Aparte|Apartes|"
                       r"Expresi[óo]n|Ordinal|Frase|Texto)\b.*?" + VERB + r".*?" + AL_RE.pattern, re.I)
STRIKE_MARK = re.compile(r"^(Inciso|Incisos|Par[áa]grafo|Par[áa]grafos|Numeral|Numerales|Literal|Literales|Aparte|Apartes|"
                         r"Expresi[óo]n|Ordinal|Frase)\b[^<>]*INEXEQUIBLE", re.I)
ART_MARK = re.compile(r"^(?:Art[íi]culo\s+(?:transitorio\s+)?)?" + VERB + r".*?" + AL_RE.pattern, re.I)


def ruling_for(jv: list[dict], al: str | None) -> dict | None:
    """The ruling that struck a given Acto Legislativo (or, with al=None, the text of this provision)."""
    inex = [r for r in jv if r["dec"] == "inexequible" and r["date"]]
    if al:
        hit = [r for r in inex if r["al"] == al]
        if hit:
            return min(hit, key=lambda r: r["date"])
        kind, n, y = al.split("-")
        word = "Decreto" if kind == "dec" else "Ley"
        hit = [r for r in inex if re.search(rf"{word}\s+(?:No\.\s*)?0?{int(n)}(?:a\.|o\.)?\s+de\s+{y}", r["text"])]
        if hit:
            return min(hit, key=lambda r: r["date"])
        whole = [r for r in inex if re.match(r"- Art\S+ (?:\d+\S* de(?:l| la) (?:Ley|Decreto) [^,]* )?declarad", r["text"])]
        if whole:
            return min(whole, key=lambda r: r["date"])
        after = [r for r in inex if r["date"] >= (law_day(al) or "")]
        if len(after) == 1:
            return after[0]
        return None
    rest = inex
    return max(rest, key=lambda r: r["date"]) if rest else None


def chain(events: list[tuple[str, str]], known: dict, base_known: list | None | Unknown, last: list | None,
          struck: dict, added: set) -> list[tuple[str, object, str]]:
    """Resolve states for a list of (day, law) events.

    known: law -> state after that law; 'before:<law>' -> state before; base_known: state before the first event.
    struck: AL law -> court law that undid it (after court = before AL).
    added: laws whose change only added this text (state before = absent).
    Returns [(day, state | UNKNOWN, law)], with the state before the first event as ('', state, '').
    """
    for e in events:
        if not e[0] or e[0] == "9999":
            note(f"event without a day dropped: {e[1]}")
    evs = sorted({e for e in events if e[0] and e[0] != "9999"}, key=lambda e: (e[0], e[1]))
    n = len(evs)
    st: list = [UNKNOWN] * (n + 1)  # st[i] = state after event i-1; st[0] = base
    st[0] = base_known
    for i, (d, law) in enumerate(evs):
        if law in known:
            st[i + 1] = known[law]
        if f"before:{law}" in known and st[i] is UNKNOWN:
            st[i] = known[f"before:{law}"]
    if st[n] is UNKNOWN or (last is not UNKNOWN and last is not None and st[n] != last):
        # Today's text on the page is the consolidated text in force; it wins over an earlier-text box that
        # differs from it in small ways.
        st[n] = last
    for _ in range(4):
        for i, (d, law) in enumerate(evs):
            if law in added and st[i] is UNKNOWN:
                st[i] = None
            for al, court in struck.items():
                if court == law:
                    j = next((k for k, e in enumerate(evs) if e[1] == al), None)
                    if j is not None:
                        if st[i + 1] is UNKNOWN and st[j] is not UNKNOWN:
                            st[i + 1] = st[j]
                        if st[j] is UNKNOWN and st[i + 1] is not UNKNOWN:
                            st[j] = st[i + 1]
    return [("", st[0], "")] + [(d, st[i + 1], law) for i, (d, law) in enumerate(evs)]


def article_history(u: dict, jv_extra=None) -> dict:
    """Rebuild one provision. Returns {'states': [(day, lines|None|UNKNOWN, law)], 'notes': [(day, court)], ...}."""
    items = u["items"]
    nv, jv = parse_notes(items)
    paras = [(i, it[1]) for i, it in enumerate(items) if it[0] == "p"]
    la = []  # (item index, block)
    for i, it in enumerate(items):
        if it[0] == "box" and it[1] in ("Legislación Anterior", "Redacción Anterior"):
            for blk in la_blocks(it[2]):
                blk["full"] = is_full(blk["paras"])
                if any("INEXEQUIBLE" in m.upper() for ph in blk["paras"] for m in markers(ph)):
                    blk["struck"] = True
                la.append((i, blk))

    # The current paragraphs, with their markers. Avance's "Nota Aclaratoria" paragraphs are editorial.
    cur = []
    skip_next = False
    for i, ph in paras:
        t0 = plain(ph)
        if skip_next and re.match(r"(Art[íi]culo|Inciso|Numeral|Literal|Par[áa]grafo)s? corregid", t0):
            skip_next = False
            continue
        skip_next = False
        if re.fullmatch(r"Nota Aclaratoria:?", t0):
            skip_next = True
            continue
        if re.match(r"(Anterior|Siguiente)\b", t0) and "antsig" in ph:
            continue
        if not cur:
            # The article's own epigraph sits in the heading anchor ("ARTÍCULO TRANSITORIO 5o. JURISDICCIÓN ...").
            epi = tidy(ART_HEAD.sub("", u["label"], count=1)) if ART_HEAD.match(u["label"]) else ""
            # Epigraphs in angle brackets ('<DISPOSICIONES COMPRENDIDAS>.') are the publisher's, not the law's.
            epi = tidy(re.sub(r"<[^>]*>?", "", epi))
            if not re.search(r"\w", epi):
                epi = ""
            if epi:
                ph = html.escape(epi, quote=False) + " " + ph
        mk = markers(ph)
        corr = any(re.search(r"subrayad\w* corresponde a la correcci", m, re.I) for m in mk)
        c = {"idx": i, "pre": tidy(to_text(ph, True, corr)), "post": tidy(to_text(ph, False)),
             "marks": [m for m in mk if not TACIT.search(m)],
             "struck": bool(re.search(r"<s\b", ph, re.I)) or any(re.search(r"INEXEQUIBLE", m, re.I) for m in mk)}
        if not re.search(r"\w", c["pre"]):
            c["pre"] = c["post"] = ""  # a paragraph left with only a full stop after the publisher's marker
        if any(TACIT.search(m) for m in mk) and not any(re.search(r"INEXEQUIBLE", m, re.I) for m in mk):
            # Words the source shows struck as derogated tacitly ('derogado tácitamente'): no act removed them.
            c["post"], c["struck"] = c["pre"], False
        cur.append(c)
    tacit_whole = bool(cur) and not any(c["post"] for c in cur) and any(
        TACIT.search(m) for m in markers(paras[0][1])) if paras else False
    if cur and not any(c["post"] for c in cur):
        # Nothing of the article is in force today: an earlier text the source gives without its "ARTÍCULO N."
        # heading is still the whole article.
        for _, blk in la:
            if blk["state"][0] in ("orig", "after", "before", "before_ruling"):
                blk["full"] = True

    art_marks = [m for c in cur[:1] for m in c["marks"] if ART_MARK.match(m) and not TACIT.search(m)]
    whole = {}  # article-level: law -> lines (full earlier texts)
    orig_full = None
    full_blocks = [blk for _, blk in la if blk["full"]]
    struck_als = {}
    # Article-level events: notes about the whole article, the article marker, full earlier texts.
    art_events = set()
    for e in nv:
        if e["article"]:
            art_events.add(e["law"])
            if e["struck"]:
                struck_als[e["law"]] = None
    if cur and not any(c["post"] for c in cur):
        # An article gone today that several acts derogated: it was gone after each of them.
        for e in nv:
            if e["article"] and e["verb"] == "derogad":
                whole.setdefault(e["law"], None)
    art_added = set()
    for m in art_marks:
        a = AL_RE.search(m)
        k = al_from_note(*a.groups(), m)
        art_events.add(k)
        if re.search(r"adicionad|nuevo", m, re.I):
            art_added.add(k)
    for blk in full_blocks:
        kind, law = blk["state"]
        lines = block_text(blk["paras"], True)
        if any(re.fullmatch(r"Revivi[óo]", x) for x in lines) or not lines:
            continue
        if kind == "orig":
            orig_full = lines
        elif kind == "after":
            art_events.add(law)
            whole.setdefault(law, lines)
            if blk["struck"]:
                struck_als[law] = None
        elif kind == "before":
            whole.setdefault(f"before:{law}", lines)
    if any(blk["state"] == ("after", GACETA125) for blk in full_blocks):
        art_events.add(GACETA125)
        # The 1991 text of a corrected article: the corrected text with the paragraph the source gives in its
        # Gaceta No. 116 wording put back (matched by similarity).
        if orig_full is None:
            frs = [block_text(blk["paras"], False) for _, blk in la if not blk["full"] and blk["state"] == ("orig", None)]
            if frs:
                orig_full = patch_paras(whole[GACETA125], [l for f in frs for l in f])
                if orig_full is None:
                    note(f"{u['name']}: Gaceta 116 fragment did not match")

    # "Texto vigente hasta su declaratoria de INEXEQUIBILIDAD": the whole article as it stood when the Court struck it,
    # with words an act had repealed shown struck ('Aparte tachado derogado por el artículo 70 del Decreto 2820 de
    # 1974'). Before that act the article had those words; after it, not; after the ruling, nothing.
    before_ruling = [blk for blk in full_blocks if blk["state"][0] == "before_ruling"]
    r_whole = ruling_for(jv, None) if before_ruling else None
    if r_whole:
        ck = add_court(r_whole["id"], r_whole["date"], r_whole["href"])
        paras_b = before_ruling[0]["paras"]
        pre_l, post_l, by = [], [], None
        for k, ph in enumerate(paras_b):
            mk = markers(ph)
            tacit = any(TACIT.search(m) for m in mk)
            a = next((AL_RE.search(m) for m in mk if re.search(r"tachad\w*\s+derogad", m, re.I) and not TACIT.search(m)
                      and AL_RE.search(m)), None)
            if a and by is None:
                by = al_from_note(*a.groups(), "")
            t_pre = tidy(to_text(ph))
            t_post = t_pre if tacit else tidy(to_text(ph, False))
            if k == 0:
                t_pre, t_post = tidy(ART_HEAD.sub("", t_pre, count=1)), tidy(ART_HEAD.sub("", t_post, count=1))
            if t_pre:
                pre_l.append(t_pre)
            if t_post:
                post_l.append(t_post)
        if by and pre_l != post_l:
            if orig_full is None:
                orig_full = pre_l
            whole[by] = post_l
            art_events.add(by)
        elif orig_full is None and not art_events - {ck}:
            orig_full = post_l
        whole[f"before:{ck}"] = post_l
        whole[ck] = None
        art_events.add(ck)
        for c in cur:
            c["pre"] = c["post"] = ""
    # "<Artículo INEXEQUIBLE>": the whole article was struck; today it is gone, and the act that last wrote it
    # (if not already known to be struck) is the one the ruling undid.
    if r_whole:
        pass
    elif cur and any(re.match(r"Art[íi]culo(\s+transitorio)?\s+INEXEQUIBLE", m, re.I) for m in cur[0]["marks"]):
        for c in cur:
            c["pre"] = c["post"] = ""
        if art_events and not struck_als:
            latest = max(art_events, key=lambda l: (law_day(l) or "", l))
            struck_als[latest] = None
        elif not art_events:
            # The article as enacted, struck whole by the ruling.
            r = ruling_for(jv, None)
            if r:
                ck = add_court(r["id"], r["date"], r["href"])
                whole[ck] = None
                art_events.add(ck)

    # Rulings that undid whole Actos Legislativos.
    for al in list(struck_als):
        r = ruling_for(jv, al)
        if r:
            struck_als[al] = add_court(r["id"], r["date"], r["href"])
        else:
            note(f"{u['name']}: {al} marked INEXEQUIBLE but no dated ruling found")
            del struck_als[al]

    # Earlier texts of parts (fragments): matched to a current paragraph by its label ("8.", "b)",
    # "PARÁGRAFO 2o.") when it has one, otherwise to the paragraphs just before the box that holds them.
    frag_target = {}
    for n, (i, blk) in enumerate(la):
        if blk["full"]:
            continue
        lines = block_text(blk["paras"], False)
        lab = para_label(lines[0]) if lines else None
        hit = [c["idx"] for c in cur if lab and para_label(c["pre"]) == lab and c["idx"] < i]
        if hit:
            frag_target[n] = hit[-1]
    starts = set(frag_target.values())

    # Slots: the current paragraphs, grouped where a marker names a change to part of the article.
    slots = []
    for c in cur:
        pm = [m for m in c["marks"] if (PARA_MARK.match(m) or STRIKE_MARK.match(m)) and not ART_MARK.match(m)]
        if pm or not slots or slots[-1].get("closed") or c["idx"] in starts or (
                para_label(c["pre"]) and starts and slots[-1]["paras"][0]["idx"] in starts):
            slots.append({"paras": [c], "marks": pm, "frags": []})
        else:
            slots[-1]["paras"].append(c)
        if not c["pre"] and any(STRIKE_MARK.match(m) for m in pm):
            slots[-1]["closed"] = True  # a struck part shown only by its marker is a slot of its own
        # a box after this paragraph closes the slot
        nxt = c["idx"] + 1
        if nxt < len(items) and items[nxt][0] == "box":
            slots[-1]["closed"] = True
    for n, (i, blk) in enumerate(la):
        if blk["full"]:
            continue
        if n in frag_target:
            s = next(s for s in slots if s["paras"][0]["idx"] == frag_target[n])
            s["frags"].append(blk)
            continue
        before = [s for s in slots if s["paras"][-1]["idx"] < i]
        prev_box = max([j for j in range(i) if items[j][0] == "box" and j < i and
                        not any(c["idx"] == j for c in cur) and
                        (not before or j < before[-1]["paras"][0]["idx"])] or [-1])
        marked = [s for s in before if s["marks"] and s["paras"][0]["idx"] > prev_box]
        if marked:
            marked[-1]["frags"].append(blk)
        elif before:
            before[-1]["frags"].append(blk)
        else:
            note(f"{u['name']}: fragment with no slot: {blk['head']}")

    has_strike = any(c["struck"] and c["pre"] != c["post"] for c in cur) or any(
        any(re.search(r"INEXEQUIBLE", m, re.I) for m in s["marks"]) for s in slots)
    part_ruling = None
    by_law = [AL_RE.search(m) for c in cur for m in c["marks"] if re.search(r"tachad\w*\s+derogad", m, re.I) and AL_RE.search(m)]
    if any(c["pre"] != c["post"] for c in cur) and by_law:
        # Words shown struck because an act repealed them ('Aparte tachado derogado por el artículo 626 de la Ley 1564').
        part_ruling = al_from_note(*by_law[0].groups(), "")
    elif has_strike:
        r = ruling_for(jv, None)
        if r:
            part_ruling = add_court(r["id"], r["date"], r["href"])
        else:
            note(f"{u['name']}: struck text but no dated ruling; struck text dropped from all versions")

    # Last article-level event: the slot model applies from its day.
    art_list = sorted(((law_day(l) or "9999", l) for l in art_events), key=lambda e: e)
    for al, court in struck_als.items():
        if court:
            art_list.append((law_day(court), court))
    art_list.sort()

    # Slot histories.
    def slot_states(s) -> list:
        evs, known, added, sstruck = [], {}, set(), {}
        base = UNKNOWN
        strike_slot = any(STRIKE_MARK.match(m) and not AL_RE.search(m) for m in s["marks"])
        for m in s["marks"]:
            a = AL_RE.search(m)
            if not a:
                continue
            law = al_from_note(*a.groups(), m)
            evs.append((law_day(law), law))
            if re.search(r"adicionad", m, re.I):
                added.add(law)
            if re.search(r"INEXEQUIBLE", m, re.I):
                r = ruling_for(jv, law)
                if r:
                    ck = add_court(r["id"], r["date"], r["href"])
                    sstruck[law] = ck
                    evs.append((r["date"], ck))
        for blk in s["frags"]:
            kind, law = blk["state"]
            lines = block_text(blk["paras"], False)
            if kind == "orig":
                base = lines
            elif kind == "after":
                if law == GACETA125:
                    evs.append((law_day(GACETA125), GACETA125))
                else:
                    evs.append((law_day(law), law))
                known.setdefault(law, lines)
                if re.match(r"Texto adicionado", blk["head"], re.I) and not re.search(r"modificad", blk["head"], re.I):
                    added.add(law)
                if (blk["struck"] or strike_slot) and law not in sstruck:
                    r = ruling_for(jv, law) or (part_ruling and {"id": None, "key": part_ruling})
                    if r:
                        ck = r["key"] if r.get("key") else add_court(r["id"], r["date"], r["href"])
                        sstruck[law] = ck
                        evs.append((law_day(ck), ck))
            elif kind == "before":
                known.setdefault(f"before:{law}", lines)
        post = [c["post"] for c in s["paras"] if c["post"]]
        pre = [c["pre"] for c in s["paras"] if c["pre"]]
        if part_ruling and pre != post and not sstruck:
            evs.append((law_day(part_ruling), part_ruling))
            known[part_ruling] = post
            last = post
            # the state just before the ruling had the struck words
            pre_state = pre
        else:
            last = post if not sstruck else post
            pre_state = None
        if not evs:
            return [("", post or None, "")]
        out = chain(evs, known, base, last or None, sstruck, added)
        if pre_state is not None:
            for k, (d, stt, law) in enumerate(out):
                if law == part_ruling and k > 0 and out[k - 1][1] is UNKNOWN:
                    out[k - 1] = (out[k - 1][0], pre_state, out[k - 1][2])
        # Today's text is the last state. If the chain ends elsewhere, a later ruling struck it (when the
        # provision names one); otherwise today's text is put on the last event and the case reported.
        if out[-1][1] is not UNKNOWN and (out[-1][1] or None) != (last or None):
            if part_ruling and law_day(part_ruling) > out[-1][0] and part_ruling not in [o[2] for o in out]:
                out.append((law_day(part_ruling), last or None, part_ruling))
            else:
                note(f"{u['name']}: slot chain ends on a text other than today's; today's text used from {out[-1][0]}")
                out[-1] = (out[-1][0], last or None, out[-1][2])
        return out

    if tacit_whole and orig_full is not None and not art_events:
        # A whole article the source calls tacitly derogated: no act removed its words, so they stay.
        return {"states": [("", orig_full, "")], "notes": []}
    shist = [slot_states(s) for s in slots]
    if os.environ.get("CO_DEBUG") == u["name"]:
        for s_, h_ in zip(slots, shist):
            print("SLOT", [c["idx"] for c in s_["paras"]], s_["marks"], [b["head"] for b in s_["frags"]], [(d, l, None if v is UNKNOWN else (v and len(v))) for d, v, l in h_])
    start = art_list[-1][0] if art_list else ""

    # Article text at each day from `start`: join the slot states.
    days = sorted({d for h in shist for d, _, _ in h if d and d > start})

    def slot_at(h, day):
        val = h[0][1]
        for d, stt, law in h[1:]:
            if d <= day:
                val = stt
        return val

    def laws_on(h, day):
        return [law for d, stt, law in h[1:] if d == day]

    def compose(day):
        lines = []
        for h in shist:
            v = slot_at(h, day)
            if v is UNKNOWN:
                return UNKNOWN
            if v:
                lines += v
        return lines or None

    states = []
    # Before `start`: the article-level history.
    if art_list:
        last_art = compose(start)
        if os.environ.get("CO_DEBUG") == u["name"]:
            print("START", start, "LAST_ART", last_art if last_art is UNKNOWN else len(last_art or []), art_list, [ (h[0][1] is UNKNOWN) for h in shist])
        evs = [(d, l) for d, l in art_list]
        ch = chain(evs, whole, orig_full if orig_full is not None else UNKNOWN, last_art, struck_als,
                   {l for l in art_events if any(e["law"] == l and e["verb"] == "adicionad" and e["article"] for e in nv)}
                   | art_added
                   | ({next(iter(art_events))} if u["name"].startswith("TRANSITORIO ACL") and len(art_events) == 1 else set()))
        if ch[0][1] is UNKNOWN and orig_full is None and not any(e["verb"] == "adicionad" for e in nv if e["article"]):
            pass
        states = ch
    else:
        states = [("", compose(""), "")]
    for d in days:
        laws = [l for h in shist for l in laws_on(h, d)]
        states.append((d, compose(d), "+".join(sorted(set(laws)))))
    notes_ = []
    for r in jv:
        if r["dec"] == "conditional" and r["date"]:
            k = add_court(r["id"], r["date"], r["href"],
                          "A Constitutional Court ruling that upheld this text on a condition of interpretation "
                          "(exequibilidad condicionada). It did not change the words.")
            notes_.append((r["date"], k))
    return {"states": states, "notes": notes_}


# ---------------------------------------------------------------- in-force days of the amending acts

CC = "codigo_civil"
DP = "ley_1581_2012"
DO_RE = re.compile(r"Diario Oficial (?:No\.?\s*)?[\d.]+(?:bis)?(?:\s*y\s*[\d.]+)?\s*,?\s*(?:de|del)?\s*(\d{1,2}\s+de\s+[a-z]+\s+(?:de\s+)*\d{4})")
VIG_RE = re.compile(r"\b(rige|regir[áa]n?|entrar[áa]n? (?:a regir|en vigencia)|entra en vigencia|empezar[áa] a regir|"
                    r"comenzar[áa] a regir)\b", re.I)
NUMS = {"un": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "seis": 6, "doce": 12, "dieciocho": 18, "veinticuatro": 24}


def add_months(day: str, n: int) -> str:
    import calendar
    y, m, d = map(int, day.split("-"))
    m += n
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return f"{y:04d}-{m:02d}-{min(d, calendar.monthrange(y, m)[1]):02d}"


def add_days(day: str, n: int) -> str:
    import datetime
    return (datetime.date.fromisoformat(day) + datetime.timedelta(days=n)).isoformat()


def page_paras(page: str) -> list[str]:
    """Plain paragraphs of a cached basedoc act: its base page and its last continuation page."""
    if page.startswith("http"):
        urls = [page]
    else:
        base = read(BASE + page + ".html") or ""
        nums = sorted(set(re.findall(r'value="_pr(\d{3})', base)) | set(re.findall(re.escape(page) + r"_pr(\d{3})\.html", base)))
        urls = [BASE + pg + ".html" for pg in [page] + ([f"{page}_pr{nums[-1]}"] if nums else [])]
    out = []
    for u in urls:
        h = read(u) or ""
        i, j = h.find("<!--Inicio documento-->"), h.find("<!--Fin documento-->")
        out += [tidy(plain(strip_markers(p))) for p in
                re.findall(r"<p\b[^>]*>(.*?)</p>", h[max(i, 0):j if j > 0 else len(h)], re.S | re.I)]
    return [p for p in out if p]


def page_header(page: str, year: str) -> tuple[str | None, str | None]:
    """(enacted, published) from an act page's heading: '(julio 8)' and 'Diario Oficial No. 53.176 de 9 de julio de 2025'."""
    enacted = pub = None
    for p in page_paras(page)[:14]:
        m = re.fullmatch(r"\(([a-z]+)\s+(\d{1,2})(?:o\.|º)?\)", p.lower())
        if m and m.group(1) in MONTHS and not enacted:
            enacted = f"{int(year):04d}-{MONTHS[m.group(1)]:02d}-{int(m.group(2)):02d}"
        m = DO_RE.search(p)
        if m and not pub:
            pub = date_es(m.group(1))
            if pub and pub[:4] < year:
                # A typing slip in the year ('Diario Oficial No. 18.199bis, del 23 de febrero de 1913' for Ley 8 de
                # 1922): an act cannot be published before the year it is dated.
                note(f"{page}: Diario Oficial day {pub} before the act's year; year {year} used")
                pub = year + pub[4:]
    return enacted, pub


def page_clause(page: str) -> str | None:
    """The act's own vigencia clause: the last article that says when the act 'rige'."""
    hits = [p for p in page_paras(page) if VIG_RE.search(p)
            and re.search(r"promulgaci|publicaci|sanci[óo]n|expedici|meses|enero", p)
            and len(p) < 900 and re.match(r"(ART[IÍ]CULO|Esta|Está|La presente|Este|El presente|\d\. Los)", p)]
    return hits[-1] if hits else None


# Clauses read by hand from the cached act pages (or quoted on the Código Civil page), where the act's rule does not
# fit the simple patterns of rule_from_clause. law key -> (day or rule, the clause as the source gives it).
HAND_RULES = {
    "ley-57-1887": ("pub+90d", "Ley 57 de 1887, art. 1 (quoted on the Código Civil page): 'Regirán en la República, noventa "
                               "días despues de la publicación de esta ley, con las condiciones y reformas de que ella trata, "
                               "los códigos siguientes: El Civil de la Nación, sancionado el 26 de mayo de 1873 ...'"),
    "ley-1564-2012": ("pub", "Ley 1564 de 2012, art. 627 num. 1: 'Los artículos 24, 30 numeral 8 y parágrafo, 31 numeral 2, "
                             "33 numeral 2, 206, 467, 610 a 627 entrarán a regir a partir de la promulgación de esta ley' (art. "
                             "626, the derogations, is among them; the derogations of its literal c) take effect on the day "
                             "the provision's own note gives, 1 January 2014, under art. 627 num. 6)"),
    "ley-1934-2018": ("2019-01-01", "Ley 1934 de 2018, art. 22: 'Esta ley entrará a regir a partir del 1 de enero del año "
                                    "siguiente de su expedición ...'"),
    "dec-1400-1970": ("1971-07-01", "Decreto 1400 de 1970 (Código de Procedimiento Civil), art. 699: 'El presente código "
                                    "entrará en vigencia el primero de julio de mil novecientos setenta y uno.'"),
    "dec-2737-1989": ("1990-03-01", "Decreto 2737 de 1989 (Código del Menor), art. 354: 'El presente Código entrará a regir a "
                                    "partir de la fecha de su publicación y su vigencia se iniciará, con excepción de las normas "
                                    "contenidas en la Sección Quinta del Capítulo Cuarto del Título Segundo, el 1o. de marzo de 1990.'"),
    "dec-2150-1995": ("pub", "Decreto 2150 de 1995, art. 152: 'Las normas contenidas en el presente decreto entrarán a regir a "
                             "partir de su publicación, con excepción de las contenidas en el Capítulo II del Título I y en el "
                             "Capítulo XV del Título II, las cuales entrarán a regir 3 meses después ...'"),
}


def rule_from_clause(clause: str) -> str | None:
    t = clause.lower()
    m = re.search(r"(?:regir[áa]?|rige|vigencia)\s+(?:a partir\s+)?(?:el|del|desde el)\s+(?:d[íi]a\s+)?(\d{1,2}(?:o\.|º)?\s+de\s+[a-z]+\s+de\s+\d{4})", t)
    if m and date_es(m.group(1)):
        return date_es(m.group(1))
    m = re.search(r"\b(" + "|".join(NUMS) + r")\s*(?:\(\d+\)\s*)?meses\s+(?:después|contados|siguientes)", t)
    if m:
        return f"pub+{NUMS[m.group(1)]}m"
    if re.search(r"promulgaci|publicaci", t):
        return "pub"
    if re.search(r"sanci[óo]n|expedici", t):
        return "enacted"
    return None


def apply_rule(rule: str, pub: str | None, enacted: str | None) -> str | None:
    if re.fullmatch(r"\d{4}-\d\d-\d\d", rule):
        return rule
    if rule == "pub":
        return pub
    if rule == "enacted":
        return enacted or pub
    m = re.fullmatch(r"pub\+(\d+)([md])", rule)
    if m and pub:
        return add_months(pub, int(m.group(1))) if m.group(2) == "m" else add_days(pub, int(m.group(1)))
    return None


def scan_law_dates(units: list[dict]) -> None:
    """Diario Oficial days and titles of the amending acts, from every note that names them."""
    days: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for u in units:
        for it in u["items"]:
            if it[0] != "box" or it[1] not in ("Notas de Vigencia", "Resumen de Notas de Vigencia"):
                continue
            for ph in box_paras(it[2]):
                t = norm_refs(plain(ph))
                ms = list(AL_RE.finditer(t))
                for i, m in enumerate(ms):
                    key = al_key(*m.groups())
                    seg = t[m.end():ms[i + 1].start() if i + 1 < len(ms) else len(t)]
                    dm = DO_RE.search(seg)
                    d = date_es(dm.group(1)) if dm else None
                    if d and 0 <= int(d[:4]) - int(key.split("-")[2]) <= 2:
                        days[key][d] += 1
                    if it[1].startswith("Resumen") and key not in TITLES:
                        tm = re.match(r"\s*(?:,\s*)?(?:-\s*|')([^']{8,}?)(?:'|,\s*publicad|;|$)", seg)
                        if tm:
                            TITLES[key] = norm(tm.group(1)).strip(" .,'-")
    for key, c in days.items():
        best = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
        PUB[key] = best[0][0]
        if len(best) > 1:
            note(f"law {key}: Diario Oficial days in the notes {dict(c)}; {PUB[key]} taken")


def compute_in_force(key: str) -> None:
    law = LAWS[key]
    kind, n, y = key.split("-")
    enacted = pub = None
    if key in LAW_PAGE:
        enacted, pub = page_header(LAW_PAGE[key], y)
    pub = PUB.get(key) or pub
    law["enacted"], law["published"] = enacted, pub
    rule = why = None
    if key in HAND_RULES:
        rule, why = HAND_RULES[key]
    elif key in LAW_PAGE and page_clause(LAW_PAGE[key]):
        cl = page_clause(LAW_PAGE[key])
        rule, why = rule_from_clause(cl), f"{law['label']}: '{cl[:300]}'"
    if rule is None:
        if pub and int(y) < 1913:
            rule, why = "pub", ("rule before 1913 (Código Civil arts. 11 and 12: a law binds after its promulgation, "
                                "which in the capital is the day of its insertion in the Diario Oficial)")
        elif pub:
            rule, why = "pub+2m", "default rule (Ley 4 de 1913, art. 52: two months after promulgation)"
    day = apply_rule(rule, pub, enacted) if rule else None
    if day:
        IN_FORCE[key], IN_FORCE_WHY[key] = day, why
    else:
        note(f"law {key}: no in-force day (published {pub}, rule {rule})")


def unit_day(key: str, text: str) -> None:
    """A provision's own note may give the day its change took effect ('La derogatoria rige a partir del 1o. de enero
    de 2014'); that day applies to this provision only."""
    m = re.search(r"(?:rige|entra a regir|empieza a regir|comienza a regir) a partir del?\s+"
                  r"(\d{1,2}(?:o\.|º)?\s+de\s+[a-z]+\s+de\s+\d{4})", text)
    if m and date_es(m.group(1)):
        d = date_es(m.group(1))
        if d != law_day(key):
            UNIT_DAYS[key] = d


# ---------------------------------------------------------------- the codes

def unit_key(name: str) -> tuple[str, str] | None:
    m = re.fullmatch(r"(\d+)([A-Z]?)(?:-(\d+))?", name)
    if m:
        k = f"art-{int(m.group(1)):04d}{m.group(2).lower()}" + (f"-{int(m.group(3)):02d}" if m.group(3) else "")
        return k, f"Art. {int(m.group(1))}{m.group(2)}" + (f"-{m.group(3)}" if m.group(3) else "")
    return None


def heading_level(label: str) -> int | None:
    l = label.upper()
    if l.startswith("LIBRO"):
        return 1
    if l.startswith(("TÍTULO", "TITULO")):
        return 2
    if l.startswith(("CAPÍTULO", "CAPITULO")):
        return 3
    if l.startswith(("SECCIÓN", "SECCION", "PARTE")):
        return 4
    return None


def split_libro(u: dict) -> tuple[dict, list[str]]:
    """The publisher puts a 'LIBRO ...' heading (and its name) at the end of the article before it."""
    for k, it in enumerate(u["items"]):
        if it[0] == "p" and re.match(r"\s*LIBRO\b", plain(it[1])):
            rest = [tidy(to_text(x[1])) for x in u["items"][k:] if x[0] == "p"]
            return dict(u, items=u["items"][:k]), [r for r in rest if r]
    return u, []


def build_act(name: str, start: str, stop_anchor: str | None = None, tail_stop: str | None = None) -> dict:
    """Rebuild every provision of one basedoc act and assemble its dated versions."""
    units = doc_units(name)
    timelines: dict[str, list] = {}
    labels: dict[str, str] = {}
    notes_all: dict[str, list] = {}
    order = []
    for u in units[1:]:
        if stop_anchor and u["name"].upper().startswith(stop_anchor):
            break
        u, libro = split_libro(u)
        lvl = heading_level(u["label"])
        if u["name"].startswith("Nivel") or lvl or re.match(r"(T[ÍI]TULO|CAP[ÍI]TULO)\b", u["name"]):
            title = " ".join(t for t in (tidy(to_text(it[1])) for it in u["items"] if it[0] == "p") if t and t != ".")
            line = tidy(f"{u['label']} {title}".replace("<", "").replace(">", ""))
            order.append(("head", (lvl or 3, line)))
            continue
        lm = re.match(r"ART[IÍ]CULO\s+(\d+)\s*([A-Z](?![a-zÁÉÍÓÚ]))?", u["label"])
        uk = unit_key(lm.group(1) + (lm.group(2) or "") if lm else u["name"])
        if not uk:
            note(f"{name}: skipped anchor {u['name']!r} {u['label']!r}")
            continue
        if tail_stop:
            for k, it in enumerate(u["items"]):
                if it[0] == "p" and re.match(tail_stop, plain(it[1])):
                    u = dict(u, items=u["items"][:k])
                    break
        key, label = uk
        if key in timelines:
            note(f"{name}: duplicate unit {key}")
            continue
        UNIT_DAYS.clear()
        h = article_history(u)
        UNIT_DAYS.clear()
        timelines[key] = h["states"]
        notes_all[key] = h["notes"]
        labels[key] = label
        order.append(("unit", key))
        if libro:
            order.append(("head", (1, tidy(" ".join(libro)))))
    return assemble(timelines, labels, notes_all, order, start)


def heading_line(label: str) -> str:
    return label


MISSING_LINE = "[La fuente no da el texto vigente en esta fecha.]"
MISSING_UNITS: list[str] = []


def assemble(timelines, labels, notes_all, order, start) -> dict:
    """Turn per-unit state lists into dated act versions with credits."""
    # Resolve each unit's dated states. A state the source does not give is a placeholder line, credited to the
    # act that made it (the source names the act but not the wording it left).
    resolved: dict[str, list[tuple[str, object, list[str]]]] = {}
    gaps = []
    for key, sts in timelines.items():
        out = []
        base = sts[0][1]
        first_unknown = base is UNKNOWN
        cur = [MISSING_LINE] if base is UNKNOWN else base
        out.append((start, cur, []))
        for d, stt, law in sts[1:]:
            laws = [l for l in law.split("+") if l]
            day = max(d, start)
            if stt is UNKNOWN:
                gaps.append(f"{key}: text after {law} ({day}) not in the source")
                MISSING_UNITS.append(f"{key} from {day}")
                stt = [MISSING_LINE]
            out.append((day, stt, laws))
        if first_unknown:
            gaps.append(f"{key}: text at {start} not in the source")
            MISSING_UNITS.append(f"{key} from {start}")
        resolved[key] = out
    for g in gaps:
        note("gap " + g)

    days = sorted({d for r in resolved.values() for d, _, _ in r} | {d for ns in notes_all.values() for d, _ in ns})
    versions = []
    prev_units = None
    for day in days:
        units = {}
        credits: dict[str, list[str]] = {}
        heads_cur = []
        for kind, x in order:
            if kind == "head":
                heads_cur.append(x)
                continue
            r = resolved[x]
            val, cr = None, []
            for d, stt, laws in r:
                if d <= day:
                    val = stt
                if d == day:
                    cr = laws
            if val:
                units[x] = {"label": labels[x], "kind": "art",
                            "text": f"# {labels[x]}\n" + "".join(l + "\n" for l in val)}
            if cr:
                credits[x] = cr
            for d, k in notes_all.get(x, []):
                if d == day:
                    credits.setdefault(x, []).append(k)
        # Headings: kept in order in one file; a heading is shown when an article below it exists that day.
        tl = titulos_lines(order, resolved, day)
        units["titulos"] = {"label": "Títulos y capítulos", "kind": "headings", "text": "".join(l + "\n" for l in tl)}
        if prev_units is not None:
            pt = prev_units.get("titulos", {}).get("text")
            if pt != units["titulos"]["text"]:
                cs = sorted({l for k, ls in credits.items() for l in ls if LAWS.get(l, {}).get("kind") != "court"
                             and (k in units) != (k in prev_units)})
                if cs:
                    credits["titulos"] = cs
        for k in list(credits):
            credits[k] = sorted(set(credits[k]), key=lambda l: (law_day(l) or "", l))
        if prev_units is not None and units == prev_units and not credits:
            continue
        if prev_units is not None and units == prev_units:
            # An event that changed no words (a ruling that only interprets): the builder reads it as the version
            # before it, so the corpus need not repeat the text.
            versions.append({"from": day, "credits": credits})
            continue
        versions.append({"from": day, "units": units, "credits": credits if versions else {}})
        prev_units = units
    return {"versions": versions}


def titulos_lines(order, resolved, day) -> list[str]:
    def exists(key):
        val = None
        for d, stt, _ in resolved[key]:
            if d <= day:
                val = stt
        return bool(val) and val is not UNKNOWN
    lines = []
    n = len(order)
    for i, (kind, x) in enumerate(order):
        if kind != "head":
            continue
        lvl, line = x
        j = i + 1
        alive = False
        while j < n:
            k2, x2 = order[j]
            if k2 == "head" and x2[0] <= lvl:
                break
            if k2 == "unit" and exists(x2):
                alive = True
                break
            j += 1
        if alive:
            lines.append(("## " if lvl == 1 else "### ") + line)
    return lines


# ---------------------------------------------------------------- corpus


def build_codigo_civil() -> dict:
    units = doc_units(CC)
    scan_law_dates(units)
    LAWS["ley-84-1873"] = {"label": "Ley 84 de 1873", "title": "Código Civil de los Estados Unidos de Colombia",
                           "kind": "law", "enacted": "1873-05-26", "published": None, "url": BASE + CC + ".html",
                           "temporary_until": None, "restores": None, "note": None}
    res = build_act(CC, "1873-05-26", tail_stop=r"\s*FIN DEL C[ÓO]DIGO")
    sha = doc_sha(CC)
    for v in res["versions"]:
        v["source_url"] = BASE + CC + ".html"
        v["sha256"] = sha
    res["versions"][0]["note"] = (
        "Text of Ley 84 de 1873 as the source gives it: the source says the 1873 law was never printed in the Diario "
        "Oficial and reproduces it from the 1873 Imprenta de Gaitán edition, adapted to present-day spelling. It is "
        "dated from its sanction (26 May 1873); the source gives no other day. The source gives today's headings of "
        "books, titles and chapters only, so titulos.md is today's wording throughout.")
    return {"slug": "codigo-civil", "short": "CC", "title": "Código Civil", "url": BASE + CC + ".html",
            "first_law": "ley-84-1873", "earlier_laws": [], "versions": res["versions"]}


def build_ley_1581() -> dict:
    key = "ley-1581-2012"
    LAWS[key] = {"label": "Ley 1581 de 2012", "title": "Ley Estatutaria 1581 de 2012, por la cual se dictan disposiciones "
                                                        "generales para la protección de datos personales",
                 "kind": "law", "enacted": "2012-10-17", "published": "2012-10-18", "url": BASE + DP + ".html",
                 "temporary_until": None, "restores": None, "note": None}
    IN_FORCE[key] = "2012-10-18"
    IN_FORCE_WHY[key] = "Ley 1581 de 2012, art. 30: 'La presente ley rige a partir de su promulgación.'"
    start = "2012-10-18"
    res = build_act(DP, start, stop_anchor="SENTENCIA")
    vs = res["versions"]
    # Decreto Legislativo 538 de 2020, art. 8 (COVID-19 health emergency): limits literal g) of art. 4 while the
    # emergency lasts; it changed no words. The source states it in the article's Notas de Vigencia.
    dk = "dec-538-2020"
    LAWS[dk] = {"label": "Decreto 538 de 2020", "title": "Decreto Legislativo 538 de 2020, por el cual se adoptan medidas en el "
                "sector salud, para contener y mitigar la pandemia de COVID-19 ...", "kind": "decree",
                "enacted": None, "published": "2020-04-12", "url": BASE + "decreto_0538_2020.html",
                "temporary_until": None, "restores": None,
                "note": "Decreto Legislativo 538 de 2020, art. 8, limited literal g) of art. 4 (security of data) to the "
                        "technical, human and administrative security measures of health providers while the COVID-19 "
                        "health emergency lasted. It changed no words."}
    IN_FORCE[dk] = "2020-04-12"
    IN_FORCE_WHY[dk] = "Decreto 538 de 2020, art. 29: 'El presente derecho rige a partir de la fecha de su publicación.'"
    ev = {"from": "2020-04-12", "credits": {"art-0004": [dk]}}
    vs = sorted(vs + [ev], key=lambda v: v["from"])
    sha = doc_sha(DP)
    for v in vs:
        v["source_url"] = BASE + DP + ".html"
        v["sha256"] = sha
    vs[0]["note"] = ("The law as promulgated. The Constitutional Court reviewed the bill before it was signed (Sentencia "
                     "C-748 de 2011, 6 October 2011, prior review of a statutory bill): it struck words of arts. 6, 10, "
                     "26 and others and whole articles of the bill, and upheld others on conditions of interpretation. "
                     "The promulgated text already reflects that review.")
    return {"slug": "ley-1581-2012", "short": "LPDP", "title": "Ley 1581 de 2012, protección de datos personales",
            "url": BASE + DP + ".html", "first_law": key, "earlier_laws": [], "versions": vs}


def as_changes(versions: list[dict]) -> list[dict]:
    """Every version after the first gives only `changes` ({unit key: unit, or null to remove}) against the version
    before it (SCHEMA.md, "Large acts"); the builder rebuilds the full text."""
    out, prev = [], None
    for v in versions:
        if prev is None or "units" not in v:
            out.append(v)
            prev = v.get("units", prev)
            continue
        cur = v["units"]
        ch = {k: cur.get(k) for k in sorted(set(prev) | set(cur)) if prev.get(k) != cur.get(k)}
        w = {k: x for k, x in v.items() if k != "units"}
        w["changes"] = ch
        out.append(w)
        prev = cur
    return out


def main(argv: list[str]) -> None:
    acts = [build_codigo_civil(), build_ley_1581()]
    full = "--full-units" in argv  # the earlier layout, for comparing builds
    if not full:
        for a in acts:
            a["versions"] = as_changes(a["versions"])
    used = {l for a in acts for v in a["versions"] for ls in v["credits"].values() for l in ls} | {a["first_law"] for a in acts}
    laws = {k: dict(v) for k, v in sorted(LAWS.items()) if k in used}
    rules = [f"In force {IN_FORCE[k]}: {laws[k]['label']} ({IN_FORCE_WHY[k]})." for k in sorted(laws, key=lambda k: (IN_FORCE.get(k, ""), k))
             if k in IN_FORCE]
    part = {
        "sources": [{
            "name": "Secretaría General del Senado, basedoc: Código Civil, Ley 1581 de 2012 and the acts that amended them",
            "url": BASE + CC + ".html", "retrieved": RETRIEVED, "requests": request_count(),
            "licence": "Official legal text is free to reproduce (Ley 23 de 1982, art. 41). The compilation's editorial notes "
                       "(Avance Jurídico) are not reproduced; only the official text and the facts the notes state are used.",
            "notes": "codigo_civil.html + 83 continuation pages and their js/ note files; ley_1581_2012.html; the base page "
                     "and last page of each amending act the basedoc has (for its own vigencia clause)."},
            {"name": "Colpensiones, Normativa (Avance Jurídico compilation): acts before 1992 that the basedoc lacks",
             "url": COLPENSIONES, "retrieved": RETRIEVED, "requests": 0,
             "licence": "Official legal text (Ley 23 de 1982, art. 41); only headings and vigencia clauses are read.",
             "notes": "Requests are counted in the basedoc source's figure (one shared log)."}],
        "laws": laws,
        "acts": acts,
        "decisions": DECISIONS + rules,
        "ai_use": ["None at data-build time: codes/fetch_codes.py and codes/parse_codes.py are deterministic code, written "
                   "with Claude Code (claude-opus-5-5); no model reads, writes or summarises legal text."],
    }
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(COUNTRY, "corpus.d", "50-codes.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(part, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    os.replace(tmp, out)
    nv = sum(len(a["versions"]) for a in acts)
    print(f"wrote {out}: {len(acts)} acts, {nv} versions, {len(laws)} laws, {os.path.getsize(out) // 1024} KB")
    for a in acts:
        print(f"  {a['slug']}: {len(a['versions'])} versions, "
              f"{sum(1 for v in a['versions'] if 'units' not in v and 'changes' not in v)} note-only")
    if "--report" in argv:
        for r in REPORT:
            print("  ", r)
    else:
        print(f"  {len(REPORT)} report lines (--report to print)")


DECISIONS = [
    "Código Civil and Ley 1581 de 2012 (codes/parse_codes.py): source is the Secretaría General del Senado's basedoc, the only free official source that keeps each article's earlier texts ('Legislación Anterior'). SUIN-Juriscol serves an Angular application with no text to a plain request.",
    "Código Civil: versions are rebuilt per article from the source's earlier texts ('Texto original del Código Civil:', 'Texto modificado por la Ley 1a. de 1976:'), its inline amendment markers ('<Artículo modificado por el artículo 1o. del Decreto 2820 de 1974 ...>') and its Notas de Vigencia. A part marked 'adicionado' did not exist before the act that added it.",
    "Código Civil: the first version is Ley 84 de 1873 (the code of the United States of Colombia), dated from its sanction on 26 May 1873 because the source gives no other day; Ley 57 de 1887 adopted it for the Republic from 90 days after its own publication (19 July 1887), with the reforms it made.",
    "Código Civil: derogations the source calls tacit ('derogado tácitamente', 'orgánicamente') change no text and are not recorded; only express changes are.",
    "Código Civil: the notes cite the Código de Procedimiento Civil and the Código Sustantivo del Trabajo by name; they are Decreto 1400 de 1970 and Decreto 2663 de 1950.",
    "In-force days of amending acts: the act's own vigencia clause as its basedoc page gives it, or as the Código Civil page quotes it; a day that a provision's own note gives ('La derogatoria rige a partir del 1o. de enero de 2014') applies to that provision. Acts the basedoc does not hold (most acts before 1992) are dated by the default rule: before 1913, from publication in the Diario Oficial (Código Civil arts. 11 and 12); from 1913, two months after it (Ley 4 de 1913, art. 52). The list below gives the day and the rule for each act.",
    "Typing slips in the source, corrected: 'Ley 25 de 1892' (its note gives the Diario Oficial of 18 December 1992) is Ley 25 de 1992; 'Ley 2820 de 1974' is Decreto 2820 de 1974; 'Ley 95 de 1980' in art. 217's earlier text is Ley 95 de 1890 (the reform of arts. 214-217 that Ley 1060 de 2006 later repealed as 'los artículos 5o y 6o de la Ley 95 de 1890'); the Colpensiones heading of Ley 8 de 1922 dates its Diario Oficial No. 18.199bis to 23 February 1913, read as 1922.",
    "Old acts the basedoc does not hold are read, for their heading and vigencia clause only, from the same Avance Jurídico compilation as published by Colpensiones (normativa.colpensiones.gov.co).",
    "Where the source shows words struck as INEXEQUIBLE but names no dated ruling for them (arts. 669, 1119, 1527), the struck words are left out of every version; art. 312's struck text is likewise left out.",
    "Today's text on the source page is taken as the text in force now; where an earlier-text box gives the same act's wording slightly differently (art. 200), the page's current text wins. Articles the source calls derogated only tacitly or 'orgánicamente' by Court opinion (arts. 50, 196, 208, 636) keep their words in every version, since no act or ruling removed them; the page itself shows no current text for them.",
    "Codes/verify_today.py checks the last version of every article of both acts against the source page's current text (struck words removed, publisher markers and bracketed epigraphs dropped): all match except the four tacitly derogated articles above.",
    "Constitutional Court rulings that struck text (INEXEQUIBLE) are laws of kind 'court', dated by the day of the ruling as the source gives it. Rulings that upheld text on a condition of interpretation change no words: they are court laws with a note, credited to the article on the ruling's day. Plain EXEQUIBLE rulings and inhibitions are not recorded.",
    "Where the source names an act that changed an article but does not give the text in force after it, the article's text for that period is the line '[La fuente no da el texto vigente en esta fecha.]'; parse_codes.py --report lists every such gap.",
    "Avance Jurídico's editorial notes, markers (<...>) and article epigraphs in angle brackets are not part of the text. The headings of books, titles and chapters are kept in titulos.md, a heading shown while an article under it exists.",
    "Ley 1581 de 2012: one text since promulgation on 18 October 2012 (no amendment to its words); the Constitutional Court's prior review of the bill (C-748 de 2011) predates it. Decreto Legislativo 538 de 2020 art. 8 is recorded as an event that changed no words.",
]


if __name__ == "__main__":
    main(sys.argv[1:])
