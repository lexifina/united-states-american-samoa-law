"""Build corpus.json for Colombia from the cached Secretaría del Senado "basedoc" pages.

Reads only .cache/ (written by fetch.py); no network. Deterministic: same cache, same bytes.

The basedoc gives today's text of each act with, per provision:
  * inline amendment markers ("<Inciso adicionado por el artículo 1 del Acto Legislativo 1 de 2005. El nuevo
    texto es el siguiente:>"), struck text for parts the Constitutional Court struck (<s>, "<Aparte tachado
    INEXEQUIBLE>");
  * note boxes, held in one JavaScript file per page: "Notas de Vigencia" (which act changed it, Diario Oficial
    and date), "Jurisprudencia Vigencia" (Constitutional Court rulings) and "Legislación Anterior" (the earlier
    texts: "Texto original de la Constitución Política:", "Texto modificado por el Acto Legislativo 2 de 2003:").

parse.py rebuilds the dated versions of each provision from those earlier texts and markers, and credits each
change only to the act or ruling the source names. See `decisions` in the output for every rule.

Usage:  python -X utf8 parse.py            (writes corpus.json atomically)
        python -X utf8 parse.py --report   (also prints the reconstruction gaps)
"""
from __future__ import annotations

import difflib
import hashlib
import html
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
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
    return [norm(html.unescape(re.sub(r"<[^>]+>", "", m))).replace('"', "").replace("'", "")
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
    m = re.search(r"(\d{1,2})(?:o\.|º|°)?\s+(?:de\s+)?([a-zA-Z]+)\s+(?:(?:de|del)\s+)?(\d{4})", s)
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
                cur["items"].append(("box", plain(m.group(3)), js.get(m.group(2), "")))
    return res


def box_paras(b: str) -> list[str]:
    return re.findall(r"<p\b[^>]*>(.*?)</p>", b, re.S | re.I)


# ---------------------------------------------------------------- laws

LAWS: dict[str, dict] = {}

# Vigencia clauses that tie an Acto Legislativo to an election day, as the basedoc notes quote them. The election
# day is read from a cached Registraduría Nacional del Estado Civil page (fetch.py ELECTION_SOURCES): the regex must
# find the day there, or parse.py stops. `year` is used when the page gives day and month only (the year of the
# pinned Wayback capture).
ELECTION_SOURCES = {
    ("2", "2005"): {
        "clause": "Rige a partir de las elecciones del 2006",
        "url": "https://www.registraduria.gov.co/Calendario-Electoral-2006-2010.html",
        "regex": r"elecci\S+n de congresistas que se llevar\S+ a cabo el d\S+a (\d+ de \w+ de \d{4})",
        "year": None,
        "what": "Registraduría, 'Calendario Electoral 2006 - 2010' (Resolución 0497 de 2005): congressional election "
                "'el día 12 de marzo de 2006'"},
    ("3", "2005"): {
        "clause": "regirá a partir de las elecciones que se celebren en el año 2010",
        "url": "https://web.archive.org/web/20110726040247id_/http://www.registraduria.gov.co/ESTA-LISTO-EL-PRE-CALENDARIO.html",
        "regex": r"el (\d+ de \w+ de \d{4}) se realizar\S+ las elecciones legislativas",
        "year": None,
        "what": "Registraduría, Comunicado de Prensa No. 050 de 2009 (Wayback capture 2011-07-26): 'el 14 de marzo "
                "de 2010 se realizarán las elecciones legislativas'"},
    ("3", "2007"): {
        "clause": "Rige a partir de las elecciones que se celebren en el año 2007",
        "url": "https://web.archive.org/web/20070930160642id_/http://www.registraduria.gov.co/",
        "regex": r"proceso electoral del (\d+ de \w+)",
        "year": "2007",
        "what": "Registraduría home page, Wayback capture of 30 September 2007: 'el proceso electoral del 28 de "
                "octubre' (the local elections of 2007)"},
}


def election_day(key: tuple[str, str]) -> str:
    src = ELECTION_SOURCES[key]
    p = cache_path(src["url"])
    if not os.path.exists(p):
        raise SystemExit(f"not cached: {src['url']}; run fetch.py all")
    with open(p, "rb") as f:
        t = plain(re.sub(r"<(script|style).*?</\1>", "", f.read().decode("utf-8", "replace"), flags=re.S | re.I))
    m = re.search(src["regex"], t)
    if not m:
        raise SystemExit(f"election day not found in {src['url']}")
    d = date_es(m.group(1) + (f" de {src['year']}" if src["year"] else ""))
    if not d:
        raise SystemExit(f"election day unreadable in {src['url']}: {m.group(1)}")
    return d


ELECTION_DAYS: dict[tuple[str, str], str] = {}


def al_key(n: str, y: str) -> str:
    return f"al-{int(n)}-{y}"


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


AL_DATES: dict[str, tuple[str, str]] = {}  # al key -> (in force, published)


def load_al_table(units: list[dict]) -> None:
    """The base page's 'Resumen de Notas de Vigencia' lists every Acto Legislativo with its Diario Oficial date."""
    head = units[0]
    box = next(b for kind, *rest in head["items"] if kind == "box" for t, b in [rest] if t.startswith("Resumen"))
    for ph in box_paras(box):
        t = plain(ph)
        m = re.match(r"(\d+)\.\s+Modificad[oa] por el Acto Legislativo (?:No\.\s*)?(\d+) de (?:\d+ de \w+ de )?(\d{4})", t)
        if not m:
            continue
        n, y = m.group(2), m.group(3)
        key = al_key(n, y)
        title = re.search(r"'([^']*)'", t)
        pub = None
        dm = re.search(r"Diario Oficial No\.\s*[\d.]+,?\s*(.{0,40})", t)
        if dm:
            pub = date_es(dm.group(1))
        href = re.search(r"href='(acto_legislativo_[^'#]+\.html)", ph)
        LAWS[key] = {"label": f"Acto Legislativo {int(n)} de {y}",
                     "title": norm(title.group(1)).rstrip(" .,'") if title else f"Acto Legislativo {int(n)} de {y}",
                     "kind": "law", "enacted": None, "published": pub,
                     "url": BASE + (href.group(1) if href else f"acto_legislativo_{int(n):02d}_{y}.html"),
                     "temporary_until": None, "restores": None, "note": None}
        force = pub
        rige = re.search(r"(?:Empieza a regir|Entra a regir|Rige) a partir del? (\d{1,2}(?:o\.|º)? de [a-z]+ de \d{4})", t)
        if rige and date_es(rige.group(1)):
            force = date_es(rige.group(1))
        AL_DATES[key] = (force, pub)


def al_from_note(n: str, y: str, text: str) -> str:
    """Register (or complete) an Acto Legislativo from an article note; return its in-force day."""
    key = al_key(n, y)
    if key not in LAWS:
        LAWS[key] = {"label": f"Acto Legislativo {int(n)} de {y}", "title": f"Acto Legislativo {int(n)} de {y}",
                     "kind": "law", "enacted": None, "published": None,
                     "url": BASE + f"acto_legislativo_{int(n):02d}_{y}.html",
                     "temporary_until": None, "restores": None, "note": None}
        note(f"law {key} not in the summary table; taken from an article note")
    law = LAWS[key]
    if not law["published"]:
        dm = re.search(r"Diario Oficial No\.\s*[\d.]+,?\s*(.{0,40})", text)
        if dm and date_es(dm.group(1)):
            law["published"] = date_es(dm.group(1))
    force = AL_DATES.get(key, (None, None))[0] or law["published"]
    rige = re.search(r"(?:Empieza a regir|Entra a regir|Rige) a partir del? (\d{1,2}(?:o\.|º)? de [a-z]+ de \d{4})", text)
    if rige and date_es(rige.group(1)):
        force = date_es(rige.group(1))
    ek = (str(int(n)), y)
    if ek in ELECTION_SOURCES:
        if ek not in ELECTION_DAYS:
            ELECTION_DAYS[ek] = election_day(ek)
        force = ELECTION_DAYS[ek]
    if force:
        AL_DATES[key] = (force, law["published"])
    return key


def law_day(key: str) -> str | None:
    if key in AL_DATES:
        return AL_DATES[key][0]
    law = LAWS.get(key)
    return law and (law.get("enacted") or law.get("published"))


AL_RE = re.compile(r"Acto [Ll]egislativ[oi]\s+(?:No\.\s*|número\s*)?(\d+)\s+(?:de\s+\d{1,2}\s+de\s+[a-z]+\s+)?de\s+(\d{4})")
RULING_RE = re.compile(r"(?:Sentencia|Auto)\s+(?:No\.\s*)?(C-\d+A?-\d{2,4})\s*,?\s+(?:de|del)\s+(\d{1,2}(?:o\.|º)?\s+de\s+[a-z]+\s+(?:de\s+)?\d{4})", re.I)


# ---------------------------------------------------------------- one article

class Unknown:
    pass


UNKNOWN = Unknown()
GACETA125 = "aclaracion-gaceta-125"


def parse_header(h: str) -> tuple[str, str | None] | None:
    """Map a 'Legislación Anterior' heading to a state: ('orig', None) | ('after', law) | ('before', law)."""
    t = h.rstrip(" :")
    if not t.lower().startswith("texto"):
        return None
    als = [al_key(n, y) for n, y in AL_RE.findall(t)]
    for n, y in AL_RE.findall(t):
        al_from_note(n, y, "")
    if re.search(r"Gaceta No\. 125", t):
        return ("after", GACETA125)
    if re.search(r"Gaceta No\. 116", t):
        return ("orig", None)
    if re.search(r"(antes de|hasta) la modificaci", t) and als:
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
        sp = re.match(r"\s*<span class='b_aj'>(.*?)</span>\s*$", ph, re.S)
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
                t = plain(ph)
                if not t.startswith("-"):
                    continue
                als = AL_RE.findall(t)
                if not als or not re.search(VERB, t, re.I):
                    continue
                keys = [al_from_note(n, y, t) for n, y in als[:1]]
                nv.append({"text": t, "law": keys[0], "article": bool(SCOPE_ART.match(t)),
                           "verb": (re.search(VERB, t, re.I).group(1).lower()),
                           "struck": "INEXEQUIBLE" in t.upper()})
        elif title == "Jurisprudencia Vigencia":
            for ph in box_paras(b):
                t = plain(ph)
                if not t.startswith("-") or "estarse a lo resuelto" in t or re.match(r"- La Corte Constitucional se declar\S+ INHIBID", t, re.I):
                    continue
                m = RULING_RE.search(t)
                if not m:
                    continue
                d = date_es(m.group(2))
                href = re.search(r"href='([^'#]+\.html)", ph)
                up = t.upper()
                dm = re.search(r"DECLARAD[OA]S?\s+(CONDICIONALMENTE\s+)?(IN)?EXEQUIBLES?", up)
                if not dm:
                    continue
                if dm.group(2) or re.search(r"(?:DECLARAD|DELCRAD)[OA]S?\s+INEXEQUIBLES?(?![\s,]+(EN|POR) LA (SENTENCIA )?C-)", up):
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
ART_MARK = re.compile(r"^Art[íi]culo\s+(?:transitorio\s+)?" + VERB + r".*?" + AL_RE.pattern, re.I)


def ruling_for(jv: list[dict], al: str | None) -> dict | None:
    """The ruling that struck a given Acto Legislativo (or, with al=None, the text of this provision)."""
    inex = [r for r in jv if r["dec"] == "inexequible" and r["date"]]
    if al:
        hit = [r for r in inex if r["al"] == al]
        if hit:
            return min(hit, key=lambda r: r["date"])
        n, y = al.split("-")[1:]
        hit = [r for r in inex if re.search(rf"Acto Legislativo\s+(?:No\.\s*)?0?{int(n)}\s+de\s+{y}", r["text"])]
        if hit:
            return min(hit, key=lambda r: r["date"])
        whole = [r for r in inex if re.match(r"- Art\S+ (?:\d+\S* del Acto Legislativo [^,]* )?declarad", r["text"])]
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
    if st[n] is UNKNOWN:
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
            if epi:
                ph = html.escape(epi, quote=False) + " " + ph
        mk = markers(ph)
        corr = any(re.search(r"subrayad\w* corresponde a la correcci", m, re.I) for m in mk)
        cur.append({"idx": i, "pre": tidy(to_text(ph, True, corr)), "post": tidy(to_text(ph, False)), "marks": mk,
                    "struck": bool(re.search(r"<s\b", ph, re.I)) or any(re.search(r"INEXEQUIBLE", m, re.I) for m in mk)})

    art_marks = [m for c in cur[:1] for m in c["marks"] if ART_MARK.match(m)]
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

    # "<Artículo INEXEQUIBLE>": the whole article was struck; today it is gone, and the act that last wrote it
    # (if not already known to be struck) is the one the ruling undid.
    if cur and any(re.match(r"Art[íi]culo(\s+transitorio)?\s+INEXEQUIBLE", m, re.I) for m in cur[0]["marks"]):
        for c in cur:
            c["pre"] = c["post"] = ""
        if art_events and not struck_als:
            latest = max(art_events, key=lambda l: (law_day(l) or "", l))
            struck_als[latest] = None

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
    if has_strike:
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

    shist = [slot_states(s) for s in slots]
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


# ---------------------------------------------------------------- the Constitution

CONST = "constitucion_politica_1991"


def unit_key(name: str) -> tuple[str, str] | None:
    """Anchor name -> (unit key, label)."""
    m = re.fullmatch(r"(\d+)([A-Z]?)", name)
    if m:
        return f"art-{int(m.group(1)):03d}{m.group(2).lower()}", f"Art. {int(m.group(1))}{m.group(2)}"
    m = re.fullmatch(r"TRANSITORIO (\d+)", name)
    if m:
        return f"art-transitorio-{int(m.group(1)):03d}", f"Art. transitorio {int(m.group(1))}"
    if name == "TRANSITORIO FINAL":
        return "art-transitorio-059-final", "Art. transitorio (final)"
    m = re.fullmatch(r"TRANSITORIO ACL0(\d)0(\d\d)-(\d+)", name)
    if m:
        n, yy, a = m.groups()
        return (f"art-transitorio-al-20{yy}-{int(n):02d}-{int(a):03d}",
                f"Art. transitorio {int(a)} (AL {int(n)} de 20{yy})")
    return None


def heading_level(label: str) -> int | None:
    l = label.upper()
    if l.startswith(("TÍTULO", "TITULO", "DISPOSICIONES")):
        return 1
    if l.startswith(("CAPÍTULO", "CAPITULO", "<CIRCUNSCRIPCIONES")):
        return 2
    return None


CONST_FIRST = "constitucion-1991"


def build_constitution() -> dict:
    units = doc_units(CONST)
    load_al_table(units)
    LAWS[CONST_FIRST] = {"label": "Constitución Política de 1991",
                         "title": "Constitución Política de Colombia, promulgada en la Gaceta Constitucional No. 114 de 4 de julio de 1991",
                         "kind": "law", "enacted": "1991-07-04", "published": "1991-07-04",
                         "url": BASE + CONST + ".html", "temporary_until": None, "restores": None, "note": None}
    LAWS[GACETA125] = {"label": "Aclaración, Gaceta Constitucional No. 125",
                       "title": "Aclaración de la Secretaría General de la Asamblea Nacional Constituyente, publicada en la Gaceta Constitucional No. 125",
                       "kind": "decree", "enacted": None, "published": None, "url": None,
                       "temporary_until": None, "restores": None,
                       "note": "Corrections to the published text, issued by the Secretariat of the National Constituent "
                               "Assembly in 1991; the source gives the earlier and corrected wording."}
    start = "1991-07-04"
    # The Aclaración's day, from the source's own note.
    for u in units:
        for it in u["items"]:
            if it[0] == "box" and it[1] == "Notas de Vigencia" and "Gaceta" in it[2] and "Aclaraci" in it[2]:
                t = plain(it[2])
                m = re.search(r"Gaceta Constitucional No\. 125,? (?:de|del)\s+(\d+ de \w+ de \d{4})", t)
                if m:
                    LAWS[GACETA125]["published"] = date_es(m.group(1))
                    m2 = re.search(r"Aclaraci[óo]n de la Secretar[íi]a General de la Asamblea Nacional Constituyente del? (\d+ de \w+ de \d{4})", t)
                    if m2:
                        LAWS[GACETA125]["enacted"] = date_es(m2.group(1))
                    break
    AL_DATES[GACETA125] = (LAWS[GACETA125]["published"] or LAWS[GACETA125]["enacted"], LAWS[GACETA125]["published"])

    # Preamble.
    head = units[0]
    pre_lines, on = [], False
    for it in head["items"]:
        if it[0] != "p":
            continue
        t = tidy(to_text(it[1]))
        if t.upper().startswith("PRE") and "MBULO" in t.upper():
            on = True
            continue
        if on and t:
            pre_lines.append(t)
    timelines: dict[str, list] = {}
    labels: dict[str, str] = {}
    notes_all: dict[str, list] = {}
    order = []
    timelines["preambulo"] = [("", pre_lines, "")]
    labels["preambulo"] = "Preámbulo"
    order.append(("unit", "preambulo"))

    headings = []  # (key, level, line)
    for u in units[1:]:
        lvl = heading_level(u["label"])
        if u["name"].startswith("Nivel") or lvl:
            title = " ".join(t for t in (tidy(to_text(p)) for k, p in [(it[0], it[1]) for it in u["items"] if it[0] == "p"]) if t)
            line = tidy(f"{u['label']} {title}".replace("<", "").replace(">", ""))
            headings.append(line)
            order.append(("head", (lvl or 2, line)))
            continue
        uk = unit_key(u["name"])
        if not uk:
            note(f"skipped anchor {u['name']!r} {u['label']!r}")
            continue
        key, label = uk
        h = article_history(u)
        if key in timelines:
            note(f"duplicate unit {key}")
            continue
        timelines[key] = h["states"]
        notes_all[key] = h["notes"]
        labels[key] = label
        order.append(("unit", key))
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
            gaps.append(f"{key}: 1991 text not in the source")
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
                units[x] = {"label": labels[x], "kind": "transitional" if "transitorio" in x else ("preamble" if x == "preambulo" else "art"),
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
                             and k in units and k not in prev_units})
                if cs:
                    credits["titulos"] = cs
        for k in list(credits):
            credits[k] = sorted(set(credits[k]), key=lambda l: (law_day(l) or "", l))
        if prev_units is not None and units == prev_units and not credits:
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

def main(argv: list[str]) -> None:
    const = build_constitution()
    sha = doc_sha(CONST)
    for v in const["versions"]:
        v["source_url"] = BASE + CONST + ".html"
        v["sha256"] = sha
    const["versions"][0]["note"] = ("Text of the second corrected edition, Gaceta Constitucional No. 116 of 20 July 1991, as the "
                                    "source gives it; the source does not reproduce the first printing in Gaceta No. 114.")
    for (n, y), day in sorted(ELECTION_DAYS.items()):
        src = ELECTION_SOURCES[(n, y)]
        for v in const["versions"]:
            if v["from"] == day:
                v["note"] = (f"Acto Legislativo {n} de {y}: '{src['clause']}'. The election day, {day}, is from "
                             f"{src['what']}: {src['url']}")
    acts = [{"slug": "constitucion", "short": "CP", "title": "Constitución Política de Colombia 1991",
             "url": BASE + CONST + ".html", "first_law": CONST_FIRST, "earlier_laws": [],
             "versions": const["versions"]}]
    used = {l for a in acts for v in a["versions"] for ls in v["credits"].values() for l in ls} | {CONST_FIRST}
    laws = {k: dict(v) for k, v in sorted(LAWS.items()) if k in used}
    for k, v in laws.items():
        if v["kind"] == "law" and k.startswith("al-"):
            force, pub = AL_DATES.get(k, (None, v["published"]))
    corpus = {
        "country": {
            "code": "CO", "name": "Colombia", "slug": "colombia", "lang": "es", "tz": "America/Bogota",
            "future_branch": "futuro",
            "publisher": {"name": "Secretaría General del Senado (basedoc)", "email": "basedoc@secretariasenado.invalid"},
            "default_in_force_rule": {
                "text": "Ley 4 de 1913 (Código de Régimen Político y Municipal), arts. 52 and 53: a law binds two months "
                        "after its promulgation unless it fixes its own day. Actos Legislativos (amendments to the "
                        "Constitution) state their own vigencia, almost always 'rige a partir de su publicación'.",
                "source": BASE + "ley_0004_1913.html"},
            "licence_note": "Texto oficial de la Constitución y las leyes de la República de Colombia (de libre reproducción, "
                            "Ley 23 de 1982, art. 41). Fuente: Secretaría General del Senado de la República, "
                            "www.secretariasenado.gov.co (compilación de Avance Jurídico Casa Editorial)."},
        "sources": [{
            "name": "Secretaría General del Senado, basedoc (Leyes desde 1992 - Vigencia expresa y control de constitucionalidad)",
            "url": BASE, "retrieved": RETRIEVED, "requests": request_count(),
            "licence": "Official legal text is free to reproduce (Ley 23 de 1982, art. 41). The compilation's editorial notes "
                       "(Avance Jurídico) are not reproduced; only the official text and the facts the notes state "
                       "(which act changed what, Diario Oficial dates, ruling numbers and dates) are used.",
            "notes": "HTML pages in ISO-8859-1 (<name>.html, <name>_prNNN.html) with the note boxes in js/<page>.js. "
                     "Source last updated 15 October 2026 (Diario Oficial No. 53.651) per its footer."},
            {"name": "Registraduría Nacional del Estado Civil (election days only)",
             "url": "https://www.registraduria.gov.co", "retrieved": RETRIEVED, "requests": len(ELECTION_SOURCES),
             "licence": "Official public information; only the dates of three elections are taken from it.",
             "notes": "Pages: " + "; ".join(s["url"] for s in ELECTION_SOURCES.values())
                      + ". Two are Internet Archive captures pinned by timestamp."}],
        "laws": laws,
        "acts": acts,
        "applies": [],
        "decisions": DECISIONS + [
            "Placeholder line: where the source names the act that changed a provision but gives no text in force after it (or no 1991 text), "
            "the provision reads '" + MISSING_LINE + "' for that period, credited to the act named. Cases: "
            + ", ".join(sorted(set(MISSING_UNITS))) + ".",
            "Approximations, from the source's own notes: "
            + "; ".join(sorted({r.strip() for r in REPORT if "slot chain ends" in r or "no dated ruling" in r})) + ".",
        ],
        "ai_use": ["None at data-build time: fetch.py and parse.py are deterministic code, written with Claude Code "
                   "(claude-opus-5-5); no model reads, writes or summarises legal text. The README was drafted with the "
                   "same tool."],
    }
    out = argv[argv.index("--out") + 1] if "--out" in argv else os.path.join(HERE, "corpus.json")
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write("\n")
    os.replace(tmp, out)
    nv = sum(len(a["versions"]) for a in acts)
    print(f"wrote corpus.json: {len(acts)} acts, {nv} versions, {len(laws)} laws")
    if "--report" in argv:
        for r in REPORT:
            print("  ", r)
    else:
        print(f"  {len(REPORT)} report lines (--report to print)")


DECISIONS = [
    "Source: the Secretaría General del Senado's basedoc, the only free official-site source that keeps each provision's earlier texts ('Legislación Anterior'). SUIN-Juriscol (Ministerio de Justicia) is an Angular app that serves no text to a plain request, and it does not give earlier texts.",
    "Versions are rebuilt per provision from the source's earlier texts ('Texto original de la Constitución Política:', 'Texto modificado por el Acto Legislativo N de AAAA:'), its inline amendment markers ('<Inciso adicionado por el artículo 1 del Acto Legislativo 1 de 2005 ...>') and its Notas de Vigencia. A part marked 'adicionado' did not exist before the act that added it.",
    "In-force days: an Acto Legislativo takes effect on the day of its publication in the Diario Oficial, as the source's notes state ('Rige a partir de su publicación'), unless the note quotes another vigencia clause: Acto Legislativo 1 de 2001 from 1 January 2002, Actos Legislativos 1 and 4 de 2007 from 1 January 2008, and the election-day clauses of Actos Legislativos 2 de 2005 (12 March 2006), 3 de 2005 (14 March 2010) and 3 de 2007 (28 October 2007).",
    "Election days are read by parse.py from cached Registraduría Nacional del Estado Civil pages, not written by hand: 12 March 2006 from 'Calendario Electoral 2006 - 2010' (Resolución 0497 de 2005), https://www.registraduria.gov.co/Calendario-Electoral-2006-2010.html; 14 March 2010 from Comunicado de Prensa No. 050 de 2009, https://web.archive.org/web/20110726040247id_/http://www.registraduria.gov.co/ESTA-LISTO-EL-PRE-CALENDARIO.html; 28 October 2007 from the Registraduría home page as captured on 30 September 2007 ('el proceso electoral del 28 de octubre'; the year is the capture's), https://web.archive.org/web/20070930160642id_/http://www.registraduria.gov.co/. All three agree with the days used before.",
    "Acto Legislativo 3 de 2002 says it 'rige a partir de su aprobación' and applies gradually from 2005; its text changes are dated from its publication (20 December 2002).",
    "Constitutional Court rulings that struck text (INEXEQUIBLE) are laws of kind 'court', dated by the day of the ruling as the source gives it (rulings take effect from their date unless the Court says otherwise, Ley 270 de 1996 art. 45). When a whole Acto Legislativo was struck, the provision returns to its text before that act. Struck words shown in the current text are in force until the ruling and removed from it.",
    "Rulings that upheld text on a condition of interpretation (exequibilidad condicionada) change no words: they are court laws with a note, credited to the provision on the ruling's day. Plain EXEQUIBLE rulings, inhibitions and 'estarse a lo resuelto' rulings are not recorded.",
    "The first version is the 1991 Constitution as the source gives it: the second corrected edition (Gaceta Constitucional No. 116 of 20 July 1991), dated from promulgation on 4 July 1991 (art. 380). The 1991 Aclaración published in Gaceta Constitucional No. 125 is its own commit, kind 'decree'.",
    "Where the source names an act that changed a provision but does not give the text in force after it (a later act changed the same words again), that act and the next one with a known text are credited together on the later day; parse.py --report lists every such gap.",
    "Avance Jurídico's editorial notes and markers (<...>) are not part of the text. The article heading is written as '# Art. N'; the heading of books, titles and chapters are kept in titulos.md, a heading shown while an article under it exists.",
]


if __name__ == "__main__":
    main(sys.argv[1:])
