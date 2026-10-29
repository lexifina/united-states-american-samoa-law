"""Batch 6 of the Argentine record (gitlaw-AR-2): writes corpus.d/70-batch6.json from the cache only.

    python -X utf8 batch6/parse_batch6.py            # writes ../corpus.d/70-batch6.json (atomically)
    python -X utf8 batch6/parse_batch6.py report     # replay report per act
    python -X utf8 batch6/parse_batch6.py --dry      # writes batch6/.tmp/70-batch6.json instead

It reuses the replay engine of ../parse.py and the helpers of ../batch4/parse_batch4.py (imported, not copied).

Two of its acts have no text on InfoLEG before today's consolidated text: the Código Procesal Civil y Comercial de
la Nación (Ley 17.454, texto ordenado 1981) and the Código Procesal Penal de la Nación (Ley 23.984). Their first
version is InfoLEG's own consolidated page as the Internet Archive captured it on a pinned day (SNAPSHOTS); every
later version replays the amending norms' own texts on InfoLEG, and the result is checked against InfoLEG's
consolidated text of the retrieval day and against every later archived capture of that page (CHECKS).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "batch4"))
import acts as A  # noqa: E402
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402
import parse_batch4 as B4  # noqa: E402

PART = ROOT / "corpus.d" / "70-batch6.json"
WAYBACK = "https://web.archive.org/web/{ts}id_/{url}"

ACTS = [
    {
        "slug": "codigo-procesal-civil-y-comercial",
        "short": "CPCCN",
        "id": 16547,
        "base_id": -16547,  # the archived consolidated page (SNAPSHOTS), read by act_lines below
        "title": "Código Procesal Civil y Comercial de la Nación (Ley 17.454, texto ordenado 1981)",
        "start": r"^Art\. 1\s*[°º]\s*-\s*La competencia atribuida",
        "end": r"^Antecedentes Normativos$",
        "texact": True,
        "target": r"C[oó]digo\s+Procesal\s+Civil\s+y\s+Comercial",
    },
    {
        "slug": "codigo-procesal-penal",
        "short": "CPPN",
        "id": 383,
        "base_id": -383,
        "title": "Código Procesal Penal de la Nación (Ley 23.984)",
        "start": r"^Art[ií]culo 1\s*[°º]\s*-\s*Nadie podr[aá] ser juzgado",
        "end": r"^(Antecedentes Normativos|FE DE ERRATAS)$",
        "texact": True,
        # not the Código Procesal Penal of Ley 27.063 (today's Código Procesal Penal Federal), which norms of 2014-2019
        # also call "Código Procesal Penal de la Nación"
        "target": (r"C[oó]digo\s+Procesal\s+Penal(?!\s+Federal)(?!(?:\s+de\s+la\s+Naci[oó]n)?,?\s+\(?(?:aprobado\s+por\s+"
                   r"(?:la\s+)?)?[Ll]ey\s+(?:N[°º]\s*)?27\.?063)"),
    },
    {
        "slug": "ley-24522",
        "short": "LCQ",
        "id": 25379,
        "base_id": -25379,
        "title": "Ley 24.522 de Concursos y Quiebras",
        "start": r"(?i)^art[ií]culo 1\s*[º°]?\s*\.?\s*-?\s*Cesaci[oó]n de pagos",
        "end": r"^(Antecedentes Normativos|DADA EN LA SALA)",
        "texact": True,
        "target": r"(?:[Ll]ey\s+de\s+Concursos\s+y\s+Quiebras|[Ll]ey\s*(?:N[°º]\s*)?24\.?522)",
    },
]

# the archived InfoLEG consolidated pages: (Wayback timestamp, page URL as captured); the first is the base
SNAPSHOTS = {
    "codigo-procesal-civil-y-comercial": [
        ("20130404170145", "http://infoleg.mecon.gov.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
    ],
    "codigo-procesal-penal": [
        ("20130404141841", "http://infoleg.mecon.gov.ar/infolegInternet/anexos/0-4999/383/texact.htm"),
    ],
    "ley-24522": [
        ("20130820110229", "http://www.infoleg.gov.ar/infolegInternet/anexos/25000-29999/25379/texact.htm"),
    ],
}

SETUP = {
    "codigo-procesal-civil-y-comercial": {
        "first_day": "2013-04-04", "first_law": None, "base_published": "2013-04-04", "base_from_texact": True,
        "earlier_ids": [16547],
        "extra_ids": [230088, 270045, 317531, 333669, 365429, 398015, 415307],  # Acordadas on art. 242's amount
        # art. 698, fourth paragraph ("Si durante la tramitación extrajudicial se suscitasen desinteligencias …"): in
        # the 2013 capture, missing from every capture from November 2014 on and from today's page, with no note
        "keep_base_words": ["art-698"],
        "note": ("The Code as InfoLEG's consolidated text showed it on 4 April 2013, the oldest full text available: the "
                 "Internet Archive's capture of that day of http://infoleg.mecon.gov.ar/infolegInternet/anexos/15000-19999/"
                 "16547/texact.htm. It is Ley 17.454 (1967) in the texto ordenado of Decreto 1042/1981 with every later "
                 "change InfoLEG had applied by then, the last named being Ley 26.589 (B.O. 2010-05-06). InfoLEG serves "
                 "no other text of the code before today's. Dated by the capture, not by the day those words took "
                 "effect."),
    },
    "codigo-procesal-penal": {
        "first_day": "2013-04-04", "first_law": None, "base_published": "2013-04-04", "base_from_texact": True,
        "earlier_ids": [383],
        "note": ("The Code as InfoLEG's consolidated text showed it on 4 April 2013, the oldest full text available: the "
                 "Internet Archive's capture of that day of http://infoleg.mecon.gov.ar/infolegInternet/anexos/0-4999/"
                 "383/texact.htm. It is Ley 23.984 (1991) with every later change InfoLEG had applied by then, the last "
                 "named being Ley 26.842 (B.O. 2012-12-27). InfoLEG serves no other text of the code before today's. "
                 "Dated by the capture, not by the day those words took effect."),
    },
    "ley-24522": {
        "first_day": "2013-08-20", "first_law": None, "base_published": "2013-08-20", "base_from_texact": True,
        "earlier_ids": [25379],
        # amended before the base day; the words differ from today's consolidated text only by InfoLEG's later
        # corrections of its transcription ("estuvieron" for "estuvieran", "siguiente" for "siguientes")
        "transcription": {"art-011": "InfoLEG's transcription corrected after 2013", "art-050": "InfoLEG's transcription corrected after 2013"},
        "note": ("Ley 24.522 as InfoLEG's consolidated text showed it on 20 August 2013, the oldest full text available: "
                 "the Internet Archive's capture of that day of http://www.infoleg.gov.ar/infolegInternet/anexos/25000-"
                 "29999/25379/texact.htm. It is the law of 1995 with every later change InfoLEG had applied by then, the "
                 "last named being Ley 26.684 (B.O. 2011-06-30). InfoLEG serves no text of the law as enacted (published "
                 "before 5 May 1997). Dated by the capture, not by the day those words took effect."),
    },
}

IN_FORCE: dict[int, tuple[str, str]] = {}

_act_lines = B4.act_lines
DROPPED: dict[str, list[str]] = {}  # every heading or epigraph line left out, per page, for the report

# a sentence, not a title: any future-tense verb ("quedará", "fijarán") or a common present or subjunctive form.
# Keeping a title by mistake shows up as a difference from InfoLEG's text; dropping a sentence would not, so the test
# leans towards keeping
VERB_RE = re.compile(r"\b(?:\w+r[áé]n?|\w+rá|ser[aá]n?|deber[aá]n?|podr[aá]n?|tendr[aá]n?|es|son|se|no|lo|la\s+ley|"
                     r"hab?r[aá]n?|har[aá]n?|corresponden?|regir[aá]n?|estar[aá]n?|fuere|fueren|hubiere|hubieren|ha|han|"
                     r"sea|sean|tiene|tienen|requiere|requieren|puede|pueden|debe|deben|rige|rigen|procede|proceden|"
                     r"comprende|implica|importa|existe|existiere|hay|queda|quedan|deja|dejan|valdr[aá]|cabe|caben)\b", re.I)


def is_epi(line: str) -> bool:
    """A title line: an epigraph printed above an article ("Admisibilidad", "PRORROGA EXPRESA O TACITA",
    "Juez natural, juicio previo. ...") or a heading of a book, title, chapter or section."""
    s = H.strip_links(line).strip()
    if not s or len(s) > 120 or P.heading(s) or P.is_note(line) or re.match(r"^[\d(\-]|^[a-z]\)", s):
        return False
    if re.match(r"^(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|PARTE)\b", s):
        return True
    if not re.search(r"[a-záéíóúñ]", s):
        return True  # in capitals
    return len(s.split()) <= 12 and not re.search(r"[:;,]$", s) and not VERB_RE.search(s)


def drop_titles(L: list[str], tag: str) -> list[str]:
    """Leave out title lines: lines in capitals and section headings anywhere, and any other title-like line that
    stands directly above an article heading (also when that heading has a title line of its own above it)."""
    out = []
    for i, l in enumerate(L):
        s = H.strip_links(l).strip()
        nxt = next((H.strip_links(x).strip() for x in L[i + 1:]
                    if not P.is_note(x) and (not is_epi(x) or P.heading(H.strip_links(x).strip()))), "")
        caps = is_epi(l) and (re.match(r"^(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|PARTE)\b", s) or not re.search(r"[a-záéíóúñ]", s))
        if is_epi(l) and (caps or P.heading(nxt)):
            DROPPED.setdefault(tag, []).append(s)
            continue
        out.append(l)
    return out


def snapshot_url(slug: str, i: int = 0) -> str:
    ts, url = SNAPSHOTS[slug][i]
    return WAYBACK.format(ts=ts, url=url)


def act_lines(nid: int, page: str, start: str, end: str):
    """B4.act_lines; a negative id reads the act's archived consolidated page (its first SNAPSHOTS entry)."""
    if nid >= 0:
        L, url, sha = _act_lines(nid, page, start, end)
        for pat, rep in TEXT_FIXES.get((nid, page), []):
            L = [re.sub(pat, rep, l) for l in L]
        if nid in TITLED:
            L = drop_titles(L, f"{nid} {page}")
        return L, url, sha
    slug = next(a["slug"] for a in ACTS if a.get("base_id") == nid)
    out, gone, url, sha = snapshot_lines(slug, 0, start, end)
    REPEALED_IN_BASE[slug] = sorted(gone)
    return out, url, sha


def snapshot_lines(slug: str, i: int, start: str, end: str, checks: bool = False):
    """The act's lines in an archived consolidated page (SNAPSHOTS[slug][i], or CHECKS[slug][i] when checks), with
    title lines (for TITLED acts) and repealed articles left out: (lines, repealed keys, url, sha256)."""
    ts, page = (CHECKS if checks else SNAPSHOTS)[slug][i]
    url = WAYBACK.format(ts=ts, url=page)
    b = F.cached(url)
    if b is None:
        raise SystemExit(f"not cached: {url} (run batch6/fetch_batch6.py archive)")
    L = [x for l in H.lines(b) for x in re.split(r"(?<=\.)\s+(?=ART[IÍ]CULO\s+\d+\s*[º°]?\s*\.-)", l)]
    i0 = next(i for i, l in enumerate(L) if re.search(start, H.strip_links(l)))
    j0 = next((j for j in range(i0 + 1, len(L)) if re.search(end, H.strip_links(L[j]))), len(L))
    L = L[i0:j0]
    nid = next(a["id"] for a in ACTS if a["slug"] == slug)
    for pat, rep in TEXT_FIXES.get((nid, "texact.htm"), []):
        L = [re.sub(pat, rep, l) for l in L]
    if nid in TITLED:
        L = drop_titles(L, f"{slug} {'check' if checks else 'snapshot'} {ts}")
    # the consolidated page prints a repealed article as its heading and a note "(Artículo derogado por …)",
    # sometimes with its epigraph: such an article is not in force on the base day and is left out of the base
    gone = {k for k, u in P.split_units(L, width=3).items() if repealed_in_texact(u)}
    out, cur = [], None
    for l in L:
        h = P.heading(H.strip_links(l).strip())
        if h:
            cur = P.key_of(h[0], h[1], h[2], 3)
        if cur not in gone:
            out.append(l)
    return out, gone, url, hashlib.sha256(b).hexdigest()


# later archived captures of InfoLEG's consolidated page, read only to check the replay on their capture day
CHECKS = {
    "codigo-procesal-civil-y-comercial": [
        ("20141107120042", "http://www.infoleg.gov.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
        ("20170504193311", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
        ("20181227170720", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
        ("20190624205255", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
        ("20221006212724", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
        ("20240804080012", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
        ("20250811154755", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16547/texact.htm"),
    ],
    "codigo-procesal-penal": [
        ("20160615212253", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/383/texact.htm"),
        ("20170130055930", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/383/texact.htm"),
        ("20171210221417", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/383/texact.htm"),
        ("20190328060422", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/383/texact.htm"),
        ("20250421121840", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/0-4999/383/texact.htm"),
    ],
    "ley-24522": [
        ("20151003150032", "http://www.infoleg.gov.ar/infolegInternet/anexos/25000-29999/25379/texact.htm"),
        ("20180126023057", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/25000-29999/25379/texact.htm"),
        ("20190211221153", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/25000-29999/25379/texact.htm"),
        ("20220620171618", "http://servicios.infoleg.gob.ar/infolegInternet/anexos/25000-29999/25379/texact.htm"),
    ],
}


def check_captures(slug: str, versions: list[dict], act: dict) -> list[dict]:
    """Compare the replay, on each later capture's day, with that capture: same words (P.loose) per article."""
    out = []
    for i, (ts, _) in enumerate(CHECKS.get(slug, [])):
        L, _, url, sha = snapshot_lines(slug, i, act["start"], act["end"], checks=True)
        units = {k: P.body_of(u) for k, u in P.split_units(L, width=3).items() if P.body_of(u)}
        day = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
        v = [x for x in versions if x["from"] <= day][-1]
        st = {k: P.body_of(u) for k, u in v["state"].items()}
        diff = sorted(k for k in set(st) | set(units) if P.loose(st.get(k, [])) != P.loose(units.get(k, [])))
        out.append({"ts": ts, "day": day, "version": v["from"], "url": url, "sha256": sha, "units": len(units),
                    "same": len(set(st) & set(units)) - len([k for k in diff if k in st and k in units]), "diff": diff})
    return out


REPEALED_IN_BASE: dict[str, list[str]] = {}


TITLED = {16547, 383}  # acts whose articles carry epigraphs: their title lines are left out of every text
_clean_body = P.clean_body


def clean_body(body: list[str]) -> list[str]:
    """parse.clean_body, without title lines (an amending norm prints the epigraph above each new article)."""
    out = _clean_body(body)
    return [l for i, l in enumerate(out) if not (is_epi(l) and (i + 1 == len(out) or P.heading(out[i + 1])))]


# InfoLEG notes printed inside a paragraph of the consolidated text that parse.INLINE_NOTE_RE does not take as notes
TEXT_FIXES = {
    (16547, "texact.htm"): [(r"\s*\(Monto adecuado por Acordada[^()]*\)", "")],
}

# Acordadas of the Corte Suprema that set the amount in art. 242, second paragraph, of the Código Procesal Civil y
# Comercial ("Anualmente, la Corte Suprema de Justicia de la Nación adecuará, si correspondiere, el monto …"):
# (InfoLEG id, the day the new amount applies, as each Acordada states it)
ACORDADAS_242 = [
    (230088, "2014-05-19", "from its publication in the Boletín Oficial, for claims filed from that day (InfoLEG's note)"),
    (270045, "2016-12-30", "from its publication in the Boletín Oficial, for claims filed from that day (InfoLEG's note)"),
    (317531, "2019-01-01", "for claims filed from 1 January 2019 (its point 2)"),
    (333669, "2020-01-01", "for claims filed from 1 January 2020 (its point 2)"),
    (365429, "2022-06-01", "for claims filed from 1 June 2022 (its point 2)"),
    (398015, "2024-05-01", "for claims filed from the first day of the month after it was signed on 9 April 2024 (its point 2)"),
    (415307, "2025-08-01", "for claims filed from the first day of the month after it was signed on 15 July 2025 (its point 2)"),
]
AMOUNT_RE = r"PESOS [A-ZÁÉÍÓÚÑ ]+?\(\$ ?[\d.]+\)"


def acordada_amount(nid: int) -> str:
    """The amount an Acordada writes into art. 242 ("… en el importe de PESOS CINCUENTA MIL ($ 50.000).")."""
    for l in H.lines(F.cached(F.norma_url(nid))):
        m = re.search(r"Adecuar el monto fijado en el segundo p[aá]rrafo del art[ií]culo 242\b.*?importe de (" + AMOUNT_RE + ")",
                      H.strip_links(l))
        if m:
            return re.sub(r"\(\$\s*", "($ ", m.group(1))
    raise SystemExit(f"no amount in Acordada {nid}")


def multi(nid: int, art: int, op: str) -> list[dict]:
    """Several whole articles given one after another by one article of an amending norm."""
    lines = next(l for n, l in P.amender_articles(nid) if n == art)
    return [{"op": op, "keys": [k], "label": lab, "text": t} for k, lab, t in P.split_articles(lines[1:], 3)]


def ley(n: int) -> int:
    return next(k for k, r in P.bulk().items() if r["tipo_norma"] == "Ley" and r["numero_norma"] == str(n))


def setup_dynamic() -> None:
    """Set-up that reads the cache: the multi-article overrides and the Acordadas on art. 242."""
    # Ley 27.272, art. 17: "Los artículos 1° a 8°, y 16 de la presente ley entrarán en vigencia con la publicación de
    # la presente" (arts. 1 to 8 amend this code; arts. 9 to 15 amend the code of Ley 27.063 and are not replayed)
    P.IN_FORCE[ley(27272)] = ("pub", "Ley 27.272, art. 17: arts. 1 to 8 entrarán en vigencia con la publicación")
    # Ley 27.423 (honorarios) art. 63 would have replaced arts. 254 and 257 of Ley 24.522, but Decreto 1077/2017, which
    # promulgated the law, observed (vetoed) it ("resulta necesario observar … los artículos 47, 63 y 64"); InfoLEG's
    # consolidated text of Ley 24.522 keeps the old wording
    SETUP["ley-24522"]["overrides"] = {(ley(27423), 63): []}
    cp = SETUP["codigo-procesal-civil-y-comercial"]
    l27500 = ley(27500)
    # Ley 27.500 art. 2 "Sustitúyense los artículos 288 a 301 … y sus rúbricas, por los siguientes" and art. 3
    # "Incorpóranse … los artículos siguientes": parse.parse_head reads "rúbricas" as a change of headings only
    cp["overrides"] = {(l27500, 2): multi(l27500, 2, "replace"), (l27500, 3): multi(l27500, 3, "insert")}
    cp["steps"] = []
    cp["patches"] = {}
    for nid, day, why in ACORDADAS_242:
        r = P.bulk()[nid]
        label = f"Acordada {r['numero_norma']}/{r['fecha_sancion'][:4]}"
        P.IN_FORCE[nid] = (day, f"{label}: the new amount applies {why}")
        cp["steps"].append({"nid": nid, "from": day, "units": [242], "note": (
            f"{label} of the Corte Suprema de Justicia de la Nación set the amount in the second paragraph of art. 242 "
            f"of the Código Procesal Civil y Comercial (below which judgments cannot be appealed) at "
            f"{acordada_amount(nid)}, under the power art. 242 gives the Court; it applies {why}.")})
        cp["patches"][nid] = [("art-242", AMOUNT_RE, acordada_amount(nid))]


_replay = P.replay


_repealed_in_texact = P.repealed_in_texact


def repealed_in_texact(u: dict) -> bool:
    """parse.repealed_in_texact, except InfoLEG's notes on a repeal "en cuanto dispone …" (only in so far as the
    article gives the Ministerio Público a role), which leave the article's words in the text."""
    notes = " ".join(H.strip_links(n) for n in u.get("notes", []))
    if re.search(r"derogad[oa]\s+por\s+[^()]*?,\s*en\s+cuanto\b", notes, re.I):
        return False
    return _repealed_in_texact(u)


def replay(act: dict) -> dict:
    r = _replay(act)
    # an article InfoLEG prints only as its heading and a repeal note is not in force: no file
    for v in r["versions"]:
        v["state"] = {k: u for k, u in v["state"].items() if P.body_of(u)}
    # words of the base text that today's consolidated text lost with no note and no norm behind it: kept (P.replay
    # took today's wording from the first version, as for a corrected transcription slip)
    if act.get("keep_base_words"):
        L, _, _ = act_lines(act["base_id"], "norma.htm", act["start"], act["end"])
        base = P.split_units(L, width=act.get("width", 3))
        for k in act["keep_base_words"]:
            assert not any(k in v["credits"] for v in r["versions"]), k
            for v in r["versions"]:
                v["state"][k] = dict(v["state"][k], body=P.body_of(base[k]))
            r["report"]["transcription"] = [t for t in r["report"]["transcription"] if t.split(" ")[0] != k]
            r["report"].setdefault("kept", []).append(k)
    if act["slug"] in CHECKS:
        CHECK_RESULTS[act["slug"]] = check_captures(act["slug"], r["versions"], act)
    return r


CHECK_RESULTS: dict[str, list[dict]] = {}


def install() -> None:
    A.ACTS[:] = [a for a in A.ACTS if a["slug"] not in SETUP] + ACTS
    P.ACT_SETUP.update(SETUP)
    P.IN_FORCE.update(IN_FORCE)
    P.replay = replay
    P.apply_lines = B4.apply_lines
    P.act_lines = act_lines
    P.clean_body = clean_body
    P.repealed_in_texact = repealed_in_texact
    setup_dynamic()


def build() -> tuple[dict, list[dict]]:
    install()
    corpus, reports = P.build_corpus(set(SETUP))
    for nid, _, _ in ACORDADAS_242:
        lk = P.law_key(nid)
        if lk in corpus["laws"]:
            corpus["laws"][lk]["kind"] = "court"
    order = {a["slug"]: i for i, a in enumerate(ACTS)}
    acts = sorted(corpus["acts"], key=lambda a: order[a["slug"]])
    rep = {r["act"]: r for r in reports}
    used = sorted({n for r in reports for n in r["nids"]}, key=lambda n: (P.bulk()[n]["fecha_boletin"], n))
    caps = lambda slug: "; ".join(
        f"{c['ts']} (replay version of {c['version']}: {c['same']} of {c['units']} articles with the same words"
        + (f"; differ: {', '.join(c['diff'])}" if c["diff"] else "") + ")" for c in CHECK_RESULTS.get(slug, []))
    decisions = [
        "Batch 6 (corpus.d/70-batch6.json, built by tools/batch6/parse_batch6.py with the replay engine of tools/parse.py): the Código Procesal Civil y Comercial de la Nación, the Código Procesal Penal de la Nación (Ley 23.984) and Ley 24.522 de Concursos y Quiebras. InfoLEG serves no text of any of them before today's consolidated text (norma.htm of Leyes 17.454 and 23.984 answers \"No se pudo acceder al archivo solicitado\"; that of Ley 24.522 says the original text of norms published before 5 May 1997 is not in its base).",
        "Batch 6, first versions: the oldest full text of each act is InfoLEG's own consolidated page (texact.htm) as the Internet Archive's Wayback Machine captured it, read in its raw form (https://web.archive.org/web/<timestamp>id_/<page>) through scripts/gitlaw_common/wayback.py and pinned by timestamp: " + "; ".join(f"{s}: {SNAPSHOTS[s][0][0]} of {SNAPSHOTS[s][0][1]}" for s in SNAPSHOTS) + ". Each first version is dated by its capture day and committed by the publisher as the oldest version available; it does not say when those words took effect.",
        "Batch 6, later versions: every amending law or decree that InfoLEG's consolidated text of the retrieval day names (in its notes or its \"Antecedentes Normativos\"), or lists as modifying the act, and that was published in the Boletín Oficial after the capture day, is replayed from its own text on InfoLEG, and the result is compared with InfoLEG's consolidated text of the retrieval day article by article (results below).",
        "Batch 6, check against later captures: the replayed text in force on the day of each later Internet Archive capture of the same InfoLEG page was compared with that capture, article by article, by words (punctuation, case and accents aside). Código Procesal Civil y Comercial: " + caps("codigo-procesal-civil-y-comercial") + ". Código Procesal Penal: " + caps("codigo-procesal-penal") + ". Ley 24.522: " + caps("ley-24522") + ". Every difference is one of: CPCCN art. 698, whose fourth paragraph the captures from 2014 on lack and the record keeps (below); a slip in InfoLEG's transcription that it corrected later (CPCCN arts. 58 \"respecto\" for \"respeto\", 347 \"deiscapacidad\", 499 \"aportes\" for \"importes\"; CPPN arts. 22, 31, 195; Ley 24.522 art. 253 \"todos\" and the articles listed as transcription below), which the record corrects from the first version; a change InfoLEG wrote into its page on publication, before it took effect (CPCCN art. 242 on 2018-12-27 already showed the amount of Acordada 43/2018, which applies from 2019-01-01; CPPN art. 33 on 2017-12-10 already showed Ley 27.401, in force 2018-03-01; CPPN art. 24 in January 2017 kept an epigraph InfoLEG later removed); a note InfoLEG printed as text (CPCCN art. 286 in 2024, \"Sumas anteriores: Acordada …\"); or text InfoLEG showed for a while and later withdrew (Ley 24.522 arts. 254 and 257 in January 2018 carried the words of Ley 27.423 art. 63, which Decreto 1077/2017 vetoed).",
        "Batch 6, title lines: the article titles (epigraphs) of the two procedure codes (\"Admisibilidad\", \"PRORROGA EXPRESA O TACITA\", \"Juez natural, juicio previo. …\") and the headings of their books, titles, chapters and sections are left out of every text (the base capture, the consolidated text and the amending norms' texts), as the headings of the other codes in this record are. A line counts as a title only if it is in capitals, or is a short line with no verb directly above an article heading; every line left out was listed and read by hand. Ley 24.522's titles stay as InfoLEG prints them, as the first words of each article.",
        "Batch 6, repealed articles: an article that the base capture prints only as its heading and a repeal note (\"Art. 320. - (Artículo derogado por art. 3° de la Ley N° 25.488 …)\") is not in force on the base day and has no file: " + "; ".join(f"{s}: {len(REPEALED_IN_BASE.get(s, []))}" for s in SNAPSHOTS) + ". InfoLEG's notes on CPPN arts. 516 and 517 (\"derogado por art. 76 de la Ley N° 24.946 …, en cuanto dispone la intervención del Ministerio Público\") repeal nothing of their words, and both articles stay.",
        "Batch 6 in-force dates of the amending norms: " + "; ".join(f"{P.rule_of(n)[1]} -> {P.in_force(n)}" for n in used) + ".",
        "Código Procesal Civil y Comercial, art. 242: \"Anualmente, la Corte Suprema de Justicia de la Nación adecuará, si correspondiere, el monto establecido en el párrafo anterior\". Each Acordada of the Corte Suprema that set a new amount (16/2014, 45/2016, 43/2018, 41/2019, 14/2022, 10/2024, 20/2025, all on InfoLEG) is a commit (kind court) that writes its amount, in its own words (\"PESOS CINCUENTA MIL ($ 50.000)\"), into the second paragraph, on the day the Acordada says the amount applies to new claims. InfoLEG's notes on art. 286 about the deposit for a queja (Acordadas 27/2014 … 21/2025) are notes, not words of the article, and are not shown.",
        "Código Procesal Civil y Comercial, Leyes 26.853 and 27.500: Ley 26.853 (B.O. 2013-05-17, in force on publication, art. 15) replaced arts. 288 to 301 with a recurso de casación before new Cámaras de Casación and repealed arts. 302 and 303; those chambers were never constituted. Ley 27.500 (in force on publication 2019-01-10) repealed Ley 26.853 except its art. 13 and gave arts. 288 to 303 the recurso de inaplicabilidad de la ley and the plenary again; its arts. 2 and 3 replace and add articles under a section heading (\"y sus rúbricas\"), which parse.py reads as a change of headings only, so they are given as overrides that read the articles from Ley 27.500's own text. Ley 27.449 (arbitraje comercial internacional) art. 107 repealed art. 519 bis.",
        "Código Procesal Penal de la Nación: Ley 27.063 (B.O. 2014-12-10) art. 2 abrogated it, \"sin perjuicio de lo establecido en el artículo 5°\": it stays in force in each federal district until the Código Procesal Penal Federal starts there (see that act), so its text is kept whole; InfoLEG's consolidated text keeps it too. Norms of 2014 to 2019 also call the code of Ley 27.063 \"Código Procesal Penal de la Nación\"; their instructions that name Ley 27.063 (Ley 27.272 arts. 9 to 15, arts. 292 bis to 292 septies of that code) are not applied to this act. Ley 27.272 art. 17 brings its arts. 1 to 8 (this code's Título IX bis, procedure for flagrancia) into force on publication, 2016-12-01.",
        "Código Procesal Civil y Comercial, art. 698: the 2013 capture has six paragraphs; every capture from November 2014 on, and InfoLEG's page of the retrieval day, lack the fourth (\"Si durante la tramitación extrajudicial se suscitasen desinteligencias entre los herederos, o entre éstos y los organismos administrativos, aquéllas deberán someterse a la decisión del juez del proceso sucesorio.\") with no note and no norm that removed it. A paragraph does not leave the law without a norm, so the record keeps it in every version and records this one difference from today's consolidated text; it is the only one.",
        "Ley 24.522: Ley 27.423 (honorarios, B.O. 2017-12-22) art. 63 would have replaced arts. 254 and 257, but Decreto 1077/2017, which promulgated it, observed (vetoed) that article; it is not applied. Ley 26.684 (2011) and earlier changes are inside the base capture. Ley 24.522's own article titles (\"Funciones.\", \"Impugnación.\") are the first words of its articles, as InfoLEG prints them.",
    ]
    for slug in ("codigo-procesal-civil-y-comercial", "codigo-procesal-penal", "ley-24522"):
        r = rep[slug]
        decisions.append(f"{slug}: replay vs texact of the retrieval day: {len(r['mismatches'])} word mismatches; reconciled to InfoLEG's wording from the last norm its note names: {', '.join(r['reconciled']) or 'none'}; typography-only: {', '.join(r['typography']) or 'none'}; transcription (words corrected by InfoLEG after the base capture, used from the first version): {', '.join(r['transcription']) or 'none'}"
                         + (f"; kept as in the base capture, so differing from today's consolidated text: {', '.join(r['kept'])}" if r.get("kept") else "") + ".")
    log = [json.loads(l) for l in open(F.CACHE / "requests.jsonl", encoding="utf-8")]
    n_ia = sum(1 for x in log if x.get("via") == "gitlaw_common/wayback.py")
    n_il = sum(1 for x in log if x.get("t", "").startswith("2026-10-29") and "infoleg.gob.ar" in x["url"])
    sources = [
        {"name": "InfoLEG - Información Legislativa (Ministerio de Justicia de la Nación), batch 6", "url": "https://servicios.infoleg.gob.ar/infolegInternet/",
         "retrieved": "2026-10-29", "requests": n_il,
         "licence": "As for InfoLEG above: official texts; site footer \"Los contenidos de infoleg.gob.ar están licenciados bajo Creative Commons Reconocimiento 2.5 Argentina License\"; its Aviso Legal (https://www.infoleg.gob.ar/?page_id=762) restricts reproduction to strictly personal use. Attribution: Fuente: InfoLEG.",
         "notes": "Today's consolidated text of the Código Procesal Penal (id 383) and Ley 24.522 (id 25379), their records and link lists, and the own texts of the norms that amended the three acts of batch 6 after their base captures, including the Corte Suprema's Acordadas on art. 242 of the Código Procesal Civil y Comercial."},
        {"name": "Internet Archive Wayback Machine (captures of InfoLEG consolidated pages)", "url": "https://web.archive.org/",
         "retrieved": "2026-10-29", "requests": n_ia,
         "licence": "Served by the Internet Archive under its Terms of Use (https://archive.org/about/terms.php). The captured pages are InfoLEG's consolidated texts (Fuente: InfoLEG, Ministerio de Justicia de la Nación); the bare texact.htm pages carry no licence line of their own.",
         "notes": "Read through scripts/gitlaw_common/wayback.py (CDX listing, then raw id_ captures), pinned by timestamp. Base texts: " + "; ".join(f"{SNAPSHOTS[s][0][0]} {SNAPSHOTS[s][0][1]}" for s in SNAPSHOTS) + ". Checks only: " + "; ".join(f"{ts} {u}" for s in CHECKS for ts, u in CHECKS[s]) + "."},
    ]
    part = {"laws": corpus["laws"], "acts": acts, "sources": sources, "decisions": decisions,
            "ai_use": ["Batch 6: none at data-build time; fetch_batch6.py and parse_batch6.py are deterministic code written with Claude Code (claude-opus-5-5). The title lines left out were listed by the code and read by Claude Code; no model reads, writes or corrects legal text."]}
    return part, reports


def main(argv: list[str]) -> None:
    part, reports = build()
    for slug, res in CHECK_RESULTS.items():
        for c in res:
            print(f"== check {slug} capture {c['ts']} vs version {c['version']}: {c['same']} of {c['units']} same, "
                  f"differ: {' '.join(c['diff'])}")
    if "titles" in argv:
        for tag, ls in DROPPED.items():
            print(f"== title lines left out of {tag}: {len(ls)}")
            for l in ls:
                print("   ", l)
    for r in reports:
        print(f"== {r['act']}: {len(r['ops'])} ops, {len(r['mismatches'])} mismatches, typography {r['typography']}, "
              f"transcription {r['transcription']}, reconciled {r['reconciled']}, not applied {len(r['not_applied'])}")
        if "report" in argv:
            for o in r["ops"] + ["NOT APPLIED " + x for x in r["not_applied"]] + ["HEADING " + x for x in r["headings"]] \
                    + ["FROM NOTES " + x for x in r.get("from_notes", [])]:
                print("  ", o)
        for m in r["mismatches"]:
            print("   MISMATCH", m)
    out = HERE / ".tmp" / PART.name if "--dry" in argv else PART
    out.parent.mkdir(exist_ok=True)
    P.write_json(out, part)
    for a in part["acts"]:
        print(a["slug"], len(a["versions"]), "versions", [v["from"] for v in a["versions"]])
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
