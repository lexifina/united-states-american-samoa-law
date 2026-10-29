"""Batch 7 of the Argentine record (gitlaw-AR-3): writes corpus.d/80-batch7.json from the cache only.

    python -X utf8 batch7/parse_batch7.py            # writes ../corpus.d/80-batch7.json (atomically)
    python -X utf8 batch7/parse_batch7.py report     # replay report per act
    python -X utf8 batch7/parse_batch7.py --dry      # writes batch7/.tmp/80-batch7.json instead

It reuses the replay engine of ../parse.py and helpers of ../batch4 and ../batch6 (imported, not copied).

The Código Aduanero (Ley 22.415) has no text on InfoLEG before today's consolidated text: norma.htm is an error page
and texact.htm is an index of 29 sub-pages. legalize-ar (github.com/legalize-dev/legalize-ar, CC BY 4.0, SAIJ) has
only that index page for it ("reform_quality: bootstrap-only"), so it gives no text either. The first version is
the set of InfoLEG's consolidated sub-pages as the Internet Archive captured it on 20-24 April 2013 (pinned in
batch7/snapshots.json); every later version replays the amending norms' own texts on InfoLEG, and the result is
checked against today's sub-pages and against the later archived sets.
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
sys.path.insert(0, str(ROOT / "batch6"))
import acts as A  # noqa: E402
import fetch as F  # noqa: E402
import htmltext as H  # noqa: E402
import parse as P  # noqa: E402
import parse_batch4 as B4  # noqa: E402
import parse_batch6 as B6  # noqa: E402

PART = ROOT / "corpus.d" / "80-batch7.json"
WAYBACK = "https://web.archive.org/web/{ts}id_/{url}"
NID = 16536
SETS = json.loads((HERE / "snapshots.json").read_text(encoding="utf-8"))
BASE = SETS[0]  # www.infoleg.gov.ar, April 2013
BASE_DAY = max(ts for ts, _ in BASE["pages"].values())[:8]
BASE_DAY = f"{BASE_DAY[:4]}-{BASE_DAY[4:6]}-{BASE_DAY[6:8]}"

ACTS = [
    {
        "slug": "codigo-aduanero",
        "short": "CA",
        "id": NID,
        "base_id": -NID,
        "width": 4,
        "title": "Código Aduanero (Ley 22.415)",
        "start": r"^ARTICULO 1\s*[°º]\s*-\s*Las disposiciones de este c[oó]digo rigen",
        "end": r"^FIRMANTES$",
        "texact": True,
        "target": r"(?:C[oó]digo\s+Aduanero|[Ll]ey\s*(?:N[°º]\s*)?22\.?415)",
    },
]

SETUP = {
    "codigo-aduanero": {
        "first_day": BASE_DAY, "first_law": None, "base_published": "2013-04-19", "base_from_texact": True,
        "earlier_ids": [NID],
        # the 2013 pages print the amount of art. 959 inc. b) as enacted (CIENTO SESENTA MIL (160.000) pesos); today's
        # page prints the amount Resolución ANA 2344/1991 (B.O. 1991-12-10) set, "Australes 581.000", with its note:
        # in force since 1991, so before the base day; today's words are used from the first version
        "transcription": {"art-0959": "amount of Resolución ANA 2344/1991, missing from InfoLEG's 2013 page"},
        "note": ("The Code as InfoLEG's consolidated text showed it on 20-24 April 2013, the oldest full text available: "
                 "the Internet Archive's captures of those days of the 29 pages of "
                 "http://www.infoleg.gov.ar/infolegInternet/anexos/15000-19999/16536/texact.htm. It is Ley 22.415 (1981) "
                 "with every later change InfoLEG had applied by then. InfoLEG serves no other text of the code before "
                 "today's, and legalize-ar has none. Dated by the last capture day, not by the day those words took "
                 "effect."),
    },
}

# vigencia clauses that name a day, read by hand from each norm's own text (parse.auto_rule reads them as "unknown");
# only DNU 41/2026 changes words of the code, the others are listed by InfoLEG as modifying or complementing it
IN_FORCE = {
    422548: ("2026-01-23", "DNU 41/2026, art. 3: entrará en vigencia el día de su dictado (signed 2026-01-23; B.O. 2026-01-26)"),
    318254: ("2019-01-01", "Decreto 1201/2018, art. 9: entrará en vigencia el 1° de enero de 2019"),
    342163: ("2020-09-15", "Decreto 744/2020, art. 10: a partir del primer día hábil siguiente al de su publicación (B.O. Monday 2020-09-14)"),
    345886: ("2021-01-01", "Decreto 1060/2020, art. 4: entrará en vigencia el día 1° de enero de 2021"),
    359138: ("2022-01-01", "Decreto 911/2021, art. 5: entrará en vigencia el 1° de enero de 2022"),
    395804: ("2024-01-03", "Decreto 9/2024, art. 3: entrará en vigencia el día de su dictado (2024-01-03)"),
    414510: ("2025-07-01", "Decreto 439/2025, art. 5: entrará en vigencia el 1° de julio de 2025"),
}

DROP = [r"^DISPOSICIONES TRANSITORIAS$",  # a section's title line that parse.split_units would read as a marker
        r"^Esta norma fue consultada a trav[eé]s de InfoLEG"]  # the footer of each page in the 2013 captures


# InfoLEG's notes at the end of a paragraph that parse.INLINE_NOTE_RE misses because they hold an unbalanced ")" ("(Párrafo
# incorporado por art. 9° inc. l) del Decreto N° 1.684/1993 …)") or follow another note: removed, as notes are
TAIL_NOTE = re.compile(r"\s*\((?:Importe|P[aá]rrafos?|Incisos?|Numeral|Apartados?|Punto)\b[^⟦]{0,60}?(?:sustituid|incorporad|derogad)"
                       r"[oa]s?\b.*?B\.O\.\s*\d+/\d+/\d+\.?(?:\s*Vigencia:[^()]*?(?:\([^()]*\)[^()]*?)?)?\)\s*$")


# the same with its "(" missing (art. 1166 in the 2013 capture: "… (100%). Párrafo sustituido por art. 19 inc. 6) de la
# Ley N° 25.239 B.O. 31/12/1999. Vigencia: a partir del 1° de enero de 2000.)")
TAIL_NOTE_OPEN = re.compile(r"(?<=[.;])\s+P[aá]rrafos? (?:sustituid|incorporad)[oa]s? por art\.[^()⟦]*?\)[^()]*?B\.O\.\s*\d+/\d+/\d+\."
                            r"(?:\s*Vigencia:[^()]*)?\)\s*$")


def strip_tail_notes(l: str) -> list[str]:
    """The line without its trailing notes, followed by each note as a line of its own (links kept), which
    parse.split_units then files as notes of the article."""
    notes = []
    m = TAIL_NOTE_OPEN.search(l)
    if m:
        notes.append("(" + m.group(0).strip())
        l = l[:m.start()].rstrip()
    while True:
        m = TAIL_NOTE.search(l)
        if not m or m.start() == 0:  # a whole line that is a note stays: parse.split_units files it as a note
            return [l] + notes[::-1]
        note = m.group(0).strip()
        notes.append(note if P.is_note(note) else f"(Nota Infoleg: {note})")  # "(Numeral 1. incorporado al …)"
        l = l[:m.start()].rstrip()


def page_lines(b: bytes) -> list[str]:
    return [y for l in H.lines(b) for x in re.split(r"(?<=\.)\s+(?=ART[IÍ]CULO\s+\d+\s*[º°]?\s*\.-)", l)
            for y in strip_tail_notes(x)]


def set_lines(pages: list[tuple[str, bytes]], start: str, end: str) -> tuple[list[str], str]:
    """All pages' lines in index order, sliced from `start` to `end`; sha256 of the pages' bytes concatenated."""
    L, h = [], hashlib.sha256()
    for _, b in pages:
        L += page_lines(b)
        h.update(b)
    i = next(i for i, l in enumerate(L) if re.search(start, H.strip_links(l)))
    j = next((j for j in range(i + 1, len(L)) if re.search(end, H.strip_links(L[j]))), len(L))
    L = [l for l in L[i:j] if not any(re.match(p, H.strip_links(l)) for p in DROP)]
    return drop_titles(L), h.hexdigest()


DROPPED_TITLES: set[str] = set()


def drop_titles(L: list[str]) -> list[str]:
    """Title lines of chapters and sub-chapters that parse.split_units does not skip: a second title line under a
    chapter's ("Arribo por vía terrestre" / "Transporte por automotor") or a sub-title between two articles
    ("Ingreso por otros medios", "Responsabilidad"): a short line with no closing punctuation, not an item or a
    note, standing directly above an article heading or a chapter or section heading. Every line dropped is listed."""
    out = []
    for n, l in enumerate(L):
        s = H.strip_links(l).strip()
        nxt = H.strip_links(L[n + 1]).strip() if n + 1 < len(L) else ""
        if (len(s) < 80 and len(s.split()) <= 10 and not re.search(r"[.;:,)]$", s) and not s.startswith("(")
                and not P.item_no(s) and not P.heading(s) and not P.MARKER_RE.match(s)
                and (P.heading(nxt) or P.MARKER_RE.match(nxt))):
            DROPPED_TITLES.add(s)
            continue
        out.append(l)
    return out


def subpages() -> list[str]:
    s = H.decode(F.cached(F.norma_url(NID, "texact.htm")))
    links = re.findall(r'href="([^"]+\.htm)"', s, re.I)
    return [l for l in sorted(set(links), key=links.index) if "antecedentes" not in l]


def archived(s: dict) -> list[tuple[str, bytes]]:
    out = []
    for p in subpages():
        if p not in s["pages"]:
            continue
        ts, url = s["pages"][p]
        b = F.cached(WAYBACK.format(ts=ts, url=url))
        if b is None:
            raise SystemExit(f"not cached: {ts} {url} (run batch7/fetch_batch7.py archive)")
        out.append((p, b))
    return out


def drop_repealed(L: list[str], width: int) -> tuple[list[str], set[str]]:
    """Articles printed only as their heading and a repeal note are not in force: their lines are left out."""
    gone = {k for k, u in P.split_units(L, width=width).items() if B6.repealed_in_texact(u)}
    out, cur = [], None
    for l in L:
        h = P.heading(H.strip_links(l).strip())
        if h:
            cur = P.key_of(h[0], h[1], h[2], width)
        if cur not in gone:
            out.append(l)
    return out, gone


# InfoLEG notes in today's pages that parse.split_units would read as words of the article: the amount notes at the
# end of a line of arts. 959 and 1028 ("…; (Monto sustituido por art. 1° de la Resolución N° 2344/1991 …)"), and the
# second line of the Nota Infoleg on art. 791 (Resolución General AFIP 4082/2017, "La tasa mencionada se aplicará …")
TEXACT_FIXES = [
    (r"\s*\(Monto sustituido por art\. 1° de la Resoluci[oó]n N° 2344/1991.*$", ""),
    (r"^La tasa mencionada se aplicar[aá] desde el vencimiento del plazo establecido en el Art[ií]culo 54 inciso a\)", None),
]

REPEALED_IN_BASE: list[str] = []
_act_lines = B4.act_lines


def act_lines(nid: int, page: str, start: str, end: str):
    if nid == NID and page == "texact.htm":
        pages = [(p, F.cached(F.norma_url(NID, p))) for p in subpages()]
        L, sha = set_lines(pages, start, end)
        L = [re.sub(pat, rep, l) for l in L for pat, rep in [TEXACT_FIXES[0]]]
        L = [l for l in L if not re.match(TEXACT_FIXES[1][0], H.strip_links(l))]
        return L, F.norma_url(NID, "texact.htm"), sha
    if nid == -NID:
        L, sha = set_lines(archived(BASE), start, end)
        L, gone = drop_repealed(L, 4)
        REPEALED_IN_BASE[:] = sorted(gone)
        first = next(iter(BASE["pages"].values()))
        return L, WAYBACK.format(ts=first[0], url=first[1].rsplit("/", 1)[0] + "/texact.htm"), sha
    return _act_lines(nid, page, start, end)


def check_sets(versions: list[dict], act: dict) -> list[dict]:
    """The replay on each later archived set's last capture day against that set, article by article (P.loose),
    over the pages the set has."""
    out = []
    for s in SETS[1:]:
        if s.get("skip"):
            continue
        pages = archived(s)
        L, sha = [], hashlib.sha256()
        for _, b in pages:
            pl = page_lines(b)
            i = next((i for i, l in enumerate(pl) if re.search(act["start"], H.strip_links(l))), None)
            if i is None:  # a page without the code's first article: from its first heading of any kind
                i = next((i for i, l in enumerate(pl) if P.heading(H.strip_links(l)) or P.MARKER_RE.match(H.strip_links(l))), len(pl))
            j = next((j for j in range(i, len(pl)) if re.search(act["end"], H.strip_links(pl[j]))), len(pl))
            L += pl[i:j]
            sha.update(b)
        L = drop_titles([l for l in L if not any(re.match(p, H.strip_links(l)) for p in DROP)])
        units = {k: P.body_of(u) for k, u in P.split_units(L, width=4).items()
                 if P.body_of(u) and not B6.repealed_in_texact(u)}
        last = max(ts for ts, _ in s["pages"].values())
        day = f"{last[:4]}-{last[4:6]}-{last[6:8]}"
        v = [x for x in versions if x["from"] <= day][-1]
        st = {k: P.body_of(u) for k, u in v["state"].items()}
        keys = set(units)  # only the articles on the pages this set has
        if len(pages) < len(subpages()):
            st = {k: b for k, b in st.items() if k in units or k in KEYS_BY_PAGE_SET(pages)}
        diff = sorted(k for k in set(st) | keys if P.loose(st.get(k, [])) != P.loose(units.get(k, [])))
        out.append({"set": f"{s['host']} {s['month']}", "pages": len(pages), "day": day, "version": v["from"],
                    "units": len(units), "diff": diff, "sha256": sha.hexdigest()})
    return out


def KEYS_BY_PAGE_SET(pages: list[tuple[str, bytes]]) -> set[str]:
    """Article keys that today's InfoLEG sub-pages of these names hold (to compare a partial set fairly)."""
    keys = set()
    for p, _ in pages:
        for l in page_lines(F.cached(F.norma_url(NID, p))):
            h = P.heading(H.strip_links(l).strip())
            if h:
                keys.add(P.key_of(h[0], h[1], h[2], 4))
    return keys


CHECK_RESULTS: list[dict] = []


def amenders() -> list[int]:
    """parse.amenders_of over the sub-pages: norms linked from any sub-page or listed by InfoLEG as modifying the
    code, laws or decrees published after the base captures, whose own text InfoLEG serves."""
    B = P.bulk()
    ids = {m["id"] for m in P.modifiers(NID)}
    for p in subpages():
        ids |= {int(x) for l in H.lines(F.cached(F.norma_url(NID, p))) for x in H.LINK_RE.findall(l)}
    return [i for i in sorted(ids) if i in B and B[i]["tipo_norma"] in ("Ley", "Decreto")
            and (B[i]["fecha_boletin"] or "") > SETUP["codigo-aduanero"]["base_published"]
            and F.cached(F.norma_url(i)) is not None]


def replay(act: dict) -> dict:
    r = P_replay(act)
    for v in r["versions"]:
        v["state"] = {k: u for k, u in v["state"].items() if P.body_of(u)}
    CHECK_RESULTS[:] = check_sets(r["versions"], act)
    return r


P_replay = P.replay


def install() -> None:
    A.ACTS[:] = [a for a in A.ACTS if a["slug"] not in SETUP] + ACTS
    P.ACT_SETUP.update(SETUP)
    P.IN_FORCE.update(IN_FORCE)
    P.apply_lines = B4.apply_lines
    P.act_lines = act_lines
    P.repealed_in_texact = B6.repealed_in_texact
    P.replay = replay
    SETUP["codigo-aduanero"]["amenders"] = amenders()
    SETUP["codigo-aduanero"]["overrides"] = OVERRIDES


# instructions that replace one numbered apartado ("Sustitúyese el apartado 1 del artículo 1149 …", "el punto 1. del
# artículo 51"), which parse.parse_head does not read: each new apartado is one line, numbered like the old one
def _apartado(key: str, n: str) -> list[dict]:
    return [{"op": "lines", "action": "replace", "items": [n], "keys": [key]}]


OVERRIDES = {
    (305262, 259): _apartado("art-1144", "2"),
    (305262, 261): _apartado("art-1149", "1"),
    (305262, 272): _apartado("art-1161", "1"),
    (305262, 277): _apartado("art-1173", "1"),
    (395521, 103): _apartado("art-0051", "1"),
    (395521, 110): _apartado("art-0103", "1"),
    # Ley 27.467 art. 79: "Sustitúyese el segundo párrafo del apartado 2 del artículo 91": the first line after the
    # apartado's own line "2. …", up to apartado 3
    (316974, 79): [{"op": "lines", "action": "replace", "paras": [1], "keys": ["art-0091"], "within": r"^2\.\s",
                    "until": r"^3\.\s", "check": r"^En los supuestos previstos en el apartado 2"}],
}


LEGALIZE = {"repo": "https://github.com/legalize-dev/legalize-ar", "commit": "3d2450b5c09aafcdd59a085360a5c7ec19b65205",
            "file": "ar/LEY-22415.md"}


def build() -> tuple[dict, list[dict]]:
    install()
    corpus, reports = P.build_corpus(set(SETUP))
    r = reports[0]
    used = sorted({n for x in reports for n in x["nids"]}, key=lambda n: (P.bulk()[n]["fecha_boletin"], n))
    checks = "; ".join(f"{c['set']} ({c['pages']} of 29 pages, last captured {c['day']}; replay version of {c['version']}: "
                       f"{c['units']} articles, differ: {', '.join(c['diff']) or 'none'})" for c in CHECK_RESULTS)
    decisions = [
        "Batch 7 (corpus.d/80-batch7.json, built by tools/batch7/parse_batch7.py with the replay engine of tools/parse.py): the Código Aduanero (Ley 22.415, InfoLEG id 16536). InfoLEG serves no text of it before today's consolidated text: norma.htm is an error page and texact.htm is an index of 29 sub-pages (Ley22415_Titulo_preliminar.htm … Ley22415_S16.htm), read together as one text.",
        f"Batch 7, legalize-ar: the Legalize project's Argentine repository ({LEGALIZE['repo']}, commit {LEGALIZE['commit']}; data CC BY 4.0 with attribution to SAIJ, pipeline MIT) was checked as a source. Its file {LEGALIZE['file']} holds only InfoLEG's index page of the code (front matter \"reform_quality: bootstrap-only\", 805 reforms skipped), so it gives no text of any version and none is taken from it. Its pipeline rebuilds histories from the same InfoLEG pages this record reads (norma.htm, then the amending norms, checked against texact.htm), dates commits by publication, and for acts whose original InfoLEG lacks it commits today's consolidated text as the \"original version\" (its first commits are dated 1970-01-02); it was used only to confirm that it has no older text of the code.",
        f"Batch 7, first version: InfoLEG's 29 consolidated sub-pages as the Internet Archive's Wayback Machine captured them on www.infoleg.gov.ar between 2013-04-20 and 2013-04-24, read in raw form (https://web.archive.org/web/<timestamp>id_/<page>) through scripts/gitlaw_common/wayback.py; every timestamp is pinned in tools/batch7/snapshots.json. The version is dated {BASE_DAY}, the last capture day, and committed by the publisher as the oldest version available; it says nothing about when those words took effect. Its sha256 is that of the 29 captured pages' bytes concatenated in index order. No amending norm was published between the first and the last capture.",
        "Batch 7, later versions: every law or decree that a sub-page of InfoLEG's consolidated text links to, or that InfoLEG lists as modifying the code (verVinculos), published in the Boletín Oficial after 2013-04-19 and served by InfoLEG, was read (105 norms); the instructions aimed at the code in their own texts are replayed. Only Leyes 27.302, 27.430, 27.445 and 27.467 and Decretos 27/2018, 70/2023, 575/2025 and 41/2026 (DNU) change its words; the rest set duty rates, suspend measures or regulate, which the code allows without changing its text.",
        "Batch 7, apartados: instructions that replace one numbered apartado (\"Sustitúyese el apartado 1 del artículo 1149\", \"el punto 1. del artículo 51\", Ley 27.430 arts. 259, 261, 272, 277; DNU 70/2023 arts. 103, 110) and Ley 27.467 art. 79 (second paragraph of apartado 2 of art. 91) are given as overrides that replace exactly that apartado or paragraph with the norm's own words.",
        "Batch 7, in-force dates: " + "; ".join(f"{P.rule_of(n)[1]} -> {P.in_force(n)}" for n in used) + ". DNU 41/2026 says it takes effect \"el día de su dictado\": it was signed on 2026-01-23 and published on 2026-01-26; the record follows its own clause.",
        f"Batch 7, today's text: the replayed text of the retrieval day matches InfoLEG's consolidated sub-pages article by article: {len(r['mismatches'])} word mismatches. Typography only (the texact wording is used from the article's last change): {', '.join(r['typography'])}. Partial changes reconciled to InfoLEG's wording from the last norm its note names: {', '.join(r['reconciled'])}. InfoLEG's 2013 transcription corrected later, so today's words are used from the first version: {', '.join(r['transcription'])} (arts. 260, 401, 973, 987 and 1028 are slips such as \"queja sido\" for \"que ha sido\"; art. 959 inc. b) printed the amount of 1981, CIENTO SESENTA MIL (160.000) pesos, where every later capture and today's page give the amount Resolución ANA 2344/1991 set, Australes 581.000, in force before the first version).",
        "Batch 7, InfoLEG's notes inside the text: notes at the end of a paragraph (\"(Párrafo incorporado por art. 9° inc. l) del Decreto N° 1.684/1993 …)\", \"(Importe sustituido por …)\", \"(Numeral 1. incorporado …)\", and one in the 2013 capture of art. 1166 with its opening bracket missing), the amount notes of arts. 959 and 1028 and the second line of the Nota Infoleg on art. 791 (Resolución General AFIP 4082/2017) are notes, not words of the code, and are removed from every text.",
        f"Batch 7, headings: titles of sections, titles, chapters and sub-chapters are not kept, as in the other acts; a short line with no closing punctuation standing directly above an article or a chapter heading counts as a title ({len(DROPPED_TITLES)} distinct lines, each read by hand, e.g. \"Transporte por automotor\", \"Penas\", \"DISPOSICIONES ESPECIALES\"). Articles that a page prints only as their heading and a repeal note are not in force and have no file ({len(REPEALED_IN_BASE)} in the base capture, among them arts. 17 to 35, repealed by Decreto 618/1997).",
        "Batch 7, check against later captures: the replayed text in force on the last capture day of each later archived set of the same sub-pages was compared with that set, article by article, by words (punctuation, case and accents aside): " + checks + ". Every difference is a transcription slip InfoLEG corrected later (arts. 260, 973, 987, 1028), a note InfoLEG prints as a paragraph (arts. 791 and 1028), or DNU 70/2023 written into the page on its publication day, before it took effect (art. 1037 on 2023-12-21).",
        "Batch 7, what it does not show: changes before April 2013 (the code of 1981 and its amendments up to then are inside the first version); duty rates, export suspensions and other measures taken under the code's delegations; DNU 70/2023 art. 116, which renamed a chapter (headings are not kept). The record has \"Código Aduanero: not built\" in the decisions of corpus.json from an earlier batch; batch 7 supersedes it.",
    ]
    log = [json.loads(l) for l in open(F.CACHE / "requests.jsonl", encoding="utf-8")]
    mine = {F.norma_url(n) for n in SETUP["codigo-aduanero"]["amenders"]} | {F.ficha_url(n) for n in SETUP["codigo-aduanero"]["amenders"]}
    n_il = sum(1 for x in log if x["url"] in mine or "/16536/" in x["url"] and "infoleg.gob.ar" in x["url"].split("/")[2])
    n_ia = sum(1 for x in log if "web.archive.org" in x["url"] and "16536" in x["url"])
    sources = [
        {"name": "InfoLEG - Información Legislativa (Ministerio de Justicia de la Nación), batch 7", "url": "https://servicios.infoleg.gob.ar/infolegInternet/",
         "retrieved": "2026-10-29", "requests": n_il,
         "licence": "As for InfoLEG above: official texts; site footer \"Los contenidos de infoleg.gob.ar están licenciados bajo Creative Commons Reconocimiento 2.5 Argentina License\"; its Aviso Legal (https://www.infoleg.gob.ar/?page_id=762) restricts reproduction to strictly personal use. Attribution: Fuente: InfoLEG.",
         "notes": "Today's consolidated text of the Código Aduanero (texact.htm of id 16536 and its 29 sub-pages), its record and link list, and the own texts and records of the 105 norms published after April 2013 that link to it or modify it."},
        {"name": "Internet Archive Wayback Machine (captures of InfoLEG's Código Aduanero sub-pages)", "url": "https://web.archive.org/",
         "retrieved": "2026-10-29", "requests": n_ia,
         "licence": "Served by the Internet Archive under its Terms of Use (https://archive.org/about/terms.php). The captured pages are InfoLEG's consolidated texts (Fuente: InfoLEG, Ministerio de Justicia de la Nación).",
         "notes": "CDX listings, then raw id_ captures, pinned in tools/batch7/snapshots.json. Base: 29 pages of www.infoleg.gov.ar, 2013-04-20 to 2013-04-24. Checks only: infoleg.mecon.gov.ar 2014-12-16; servicios.infoleg.gob.ar 2016-06-14/16, 2023-12-06/21 (27 pages), 2024-09-11 (19 pages)."},
        {"name": "legalize-ar (Legalize project), checked, no text used", "url": LEGALIZE["repo"], "retrieved": "2026-10-29", "requests": 3,
         "licence": "Data: CC BY 4.0 (atribución obligatoria a SAIJ): \"Datos legislativos provistos por el Ministerio de Justicia de la República Argentina a través de la Dirección Nacional del Sistema Argentino de Información Jurídica (SAIJ). Publicados en https://datos.jus.gob.ar bajo licencia Creative Commons Atribución 4.0 Internacional.\" Pipeline: MIT (https://github.com/legalize-dev/legalize-pipeline).",
         "notes": f"Commit {LEGALIZE['commit']} (38,153 commits), read with a blob-less git clone. {LEGALIZE['file']} is InfoLEG's index page of the Código Aduanero (reform_quality bootstrap-only), so no version of the code comes from it. Its source field names InfoLEG (http://servicios.infoleg.gob.ar/infolegInternet/anexos/15000-19999/16536/texact.htm)."},
    ]
    part = {"laws": corpus["laws"], "acts": corpus["acts"], "sources": sources, "decisions": decisions,
            "ai_use": ["Batch 7: none at data-build time; fetch_batch7.py and parse_batch7.py are deterministic code written with Claude Code (claude-opus-5-5). The title lines left out were listed by the code and read by Claude Code; no model reads, writes or corrects legal text."]}
    return part, reports


def main(argv: list[str]) -> None:
    corpus, reports = build()
    if "titles" in argv:
        print("\n".join(sorted(DROPPED_TITLES)))
    for c in CHECK_RESULTS:
        print(f"== check {c['set']} ({c['pages']} pages, {c['day']}) vs version {c['version']}: {c['units']} units, "
              f"differ: {' '.join(c['diff'])}")
    print("repealed in base:", len(REPEALED_IN_BASE))
    for r in reports:
        print(f"== {r['act']}: {len(r['ops'])} ops, {len(r['mismatches'])} mismatches, typography {r['typography']}, "
              f"transcription {r['transcription']}, reconciled {r['reconciled']}, not applied {len(r['not_applied'])}, "
              f"base gaps {r['base_gaps']}")
        if "report" in argv:
            for o in r["ops"] + ["NOT APPLIED " + x for x in r["not_applied"]] + ["HEADING " + x for x in r["headings"]] \
                    + ["FROM NOTES " + x for x in r.get("from_notes", [])]:
                print("  ", o)
        for m in r["mismatches"]:
            print("   MISMATCH", m)
    out = HERE / ".tmp" / PART.name if "--dry" in argv else PART
    out.parent.mkdir(exist_ok=True)
    P.write_json(out, corpus)
    for a in corpus["acts"]:
        print(a["slug"], len(a["versions"]), "versions", [v["from"] for v in a["versions"]])
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1:])
