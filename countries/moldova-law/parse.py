"""Moldova: read only .cache/ and write corpus.json (gitlaw_common SCHEMA.md). Deterministic.

    python -X utf8 fetch_all.py    -> fills .cache/ (archive.org captures pinned in SOURCES below, and presedinte.md)
    python -X utf8 parse.py        -> corpus.json (atomically) and parse.log
"""
import hashlib
import html as _html
import json
import os
import re

import ustav

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
RETRIEVED = "2026-10-29"
LOG = []

# Pinned Internet Archive captures (id_ raw form) and the one direct download.
REG_2013 = ("20130527162646", "http://lex.justice.md:80/index.php?action=view&view=doc&lang=1&id=311496")
REG_2016 = ("20160325021004", "http://lex.justice.md/viewdoc.php?action=view&view=doc&id=311496&lang=1")
HCC7 = ("20160831022417", "http://lex.justice.md/md/363742/")
L185 = ("20120215095935", "http://lex.justice.md/document_rom.php?id=820F45E1:6DD1EBC3")
MOLDPRES_2024 = "https://presedinte.md/app/webroot/Constitutia_RM/Constitutia_2024_ro.pdf"
PRES_PAGE = "https://presedinte.md/rom/constitutia-republicii-moldova"
SOURCES = [REG_2013, REG_2016, HCC7, L185]


def ia_url(cap):
    return f"https://web.archive.org/web/{cap[0]}id_/{cap[1]}"


def cached(url):
    p = os.path.join(CACHE, hashlib.sha256(url.encode("utf-8")).hexdigest())
    with open(p, "rb") as f:
        return f.read()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def text_of(raw):
    t = _html.unescape(re.sub(r"<[^>]+>", "\n", raw.decode("utf-8")))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t)


def requests_count(prefix):
    n = 0
    with open(os.path.join(CACHE, "requests.jsonl"), encoding="utf-8") as f:
        for line in f:
            if json.loads(line)["url"].startswith(prefix):
                n += 1
    return n


def law(label, title, enacted, published, url, kind="law", note=None):
    return {"label": label, "title": title, "kind": kind, "enacted": enacted, "published": published, "url": url,
            "temporary_until": None, "restores": None, "note": note}


# The amending acts the State Register lists for the Constitution (its "MODIFICAT" block, 2013 capture), with the
# register's own citations. enacted / published dates are the register's ("din DD.MM.YY", "MO.../DD.MM.YY").
REGISTER_ACTS = [
    ("rmo-1994-08-19", "Rectificare la art.88, MO1 din 19 august 1994", "1994-08-19", "1994-08-19", "publisher",
     "Rectificare la art.88, Monitorul Oficial nr.1 din 19 august 1994, partea II, pag.1"),
    ("rmo-1994-10-20", "Rectificare la art.75, MO10 din 20 octombrie 1994", "1994-10-20", "1994-10-20", "publisher",
     "Rectificare la art.75, Monitorul Oficial nr.10 din 20 octombrie 1994, pag.2"),
    ("lp-957-xiii-1996", "LP957-XIII din 19.07.96", "1996-07-19", "1996-08-15", "law",
     "LP957-XIII din 19.07.96, MO54/15.08.96 art.517"),
    ("lp-1115-xiv-2000", "LP1115-XIV din 05.07.00", "2000-07-05", "2000-07-28", "law",
     "Legea nr. 1115-XIV din 5 iulie 2000 pentru modificarea și completarea Constituției Republicii Moldova "
     "(MO88-89/28.07.00 art.661)"),
    ("lp-351-xv-2001", "LP351-XV din 12.07.01", "2001-07-12", "2001-08-02", "law",
     "LP351-XV din 12.07.01, MO90-91/02.08.01 art.699"),
    ("lp-1469-xv-2002", "LP1469-XV din 21.11.02", "2002-11-21", "2002-12-12", "law",
     "LP1469-XV din 21.11.02, MO169/12.12.02 art.1290"),
    ("lp-1470-xv-2002", "LP1470-XV din 21.11.02", "2002-11-21", "2002-12-12", "law",
     "LP1470-XV din 21.11.02, MO169/12.12.02 art.1292"),
    ("lp-1471-xv-2002", "LP1471-XV din 21.11.02", "2002-11-21", "2002-12-12", "law",
     "LP1471-XV din 21.11.02, MO169/12.12.02 art.1294"),
    ("lp-344-xv-2003", "LP344-XV din 25.07.03", "2003-07-25", "2003-08-08", "law",
     "LP344-XV din 25.07.03, MO170-172/08.08.03 art.721"),
    ("lp-185-xvi-2006", "LP185-XVI din 29.06.06", "2006-06-29", "2006-07-14", "law",
     "Legea nr. 185-XVI din 29 iunie 2006 (LP185-XVI din 29.06.06, MO106-111/14.07.06 art.502)"),
]

# The acts the Moldpres 2024 edition lists as amending the Constitution after the register's last entry (HCC7).
LATER_ACTS = ("LP256 din 25.11.16 (MO415/29.11.16 art.845), LP70 din 13.04.17 (MO155-161/19.05.17 art.261), "
              "LP255 din 22.11.18 (MO467-479/14.12.18 art.786), LP120 din 23.09.21 (MO238/01.10.21 art.274), "
              "LP52 din 16.03.23 (MO97-99/24.03.23 art.150), HCC8 din 11.03.24 (MO104-107/21.03.24 art.42), "
              "Legea nr.244 din 20.10.24 (MO457-458/05.11.24 art.633)")


def hcc7_text():
    """Point 8 b) of HCC7/2016: 'articolele 78 și 89 din Constituție vor avea următorul cuprins: „...'. Returns
    {art key: [caption, paragraphs...]} and checks the dispositive's other points this build relies on."""
    t = text_of(cached(ia_url(HCC7)))
    assert "Data intrarii in vigoare : 04.03.2016" in t
    assert "intră în vigoare la data adoptării" in t
    i = t.index("articolele 78 și 89 din Constituție vor avea următorul cuprins:")
    j = t.index("c) Constituția se va republica", i)
    block = [ustav.norm(l).strip("„“”\" ") for l in t[i:j].split("\n")[1:]]
    block = [l for l in block if l]
    out, cur = {}, None
    for l in block:
        m = re.fullmatch(r"Articolul (\d+)", l)
        if m:
            cur = f"art-{int(m.group(1)):03d}"
            out[cur] = []
            continue
        out[cur].append(l)
    assert list(out) == ["art-078", "art-089"], out
    # point 3: the phrase struck from art. 85 (4)
    assert "sintagma „ , cu excepţia cazului prevăzut la art.78 alin.(5)” de la punctul 5" in t
    return out


def hcc7_version(prev):
    new = hcc7_text()
    units = {k: dict(v) for k, v in prev.items()}
    credits = {}
    for key, lines in new.items():
        old = units[key]["text"].split("\n")
        units[key] = {**units[key], "text": "\n".join([old[0], "## " + lines[0]] + lines[1:]) + "\n"}
        credits[key] = ["hcc-7-2016"]
        LOG.append(f"HCC7 8 b): {key} replaced ({len(lines) - 1} paragraphs)")
    t = units["art-085"]["text"]
    phrase = " cu excepția cazului prevăzut la articolul 78 alineatul (5),"
    assert t.count(phrase) == 1, t
    units["art-085"] = {**units["art-085"], "text": t.replace(phrase, "")}
    credits["art-085"] = ["hcc-7-2016"]
    LOG.append("HCC7 3: art-085 (4) phrase removed:" + phrase)
    return units, credits


def check_register_2016(v2006, v2016_reg):
    """The 2016 register page must hold the 2006 words except (a) its notes on HCC7 and (b) the units its markup
    corrupted and the typo corrections listed here; anything else stops the build."""
    known = {"art-024", "art-026", "art-034", "art-035", "art-072", "art-075", "art-078", "art-085", "art-088",
             "art-089", "art-093", "art-129", "art-136", "tranz-04"}
    diff = sorted(k for k in set(v2006) | set(v2016_reg)
                  if v2006.get(k, {}).get("text") != v2016_reg.get(k, {}).get("text"))
    assert set(diff) <= known, diff
    LOG.append("register 2013 vs 2016 differs only in: " + ", ".join(diff))


def drop_editorial(units):
    """Editorial lines of the register that are not law: 'Notă: ...' (HCC7 notes), the footnote to Art. IV
    ('*Aprobat prin Legea din 24 martie 1961') with its rule and marker, and 'Originalul art.24'."""
    out = {}
    for k, u in units.items():
        lines = [l for l in u["text"].rstrip("\n").split("\n")
                 if not l.startswith("Notă:") and not re.fullmatch(r"_+", l) and not l.startswith("*Aprobat")
                 and not l.startswith("Originalul art.")]
        lines = [l[:-1] if l.endswith(".*") else l for l in lines]
        out[k] = {**u, "text": "\n".join(lines) + "\n"}
    return out


def drop_repealed_stubs(units):
    """The 2024 edition keeps 'Articolul 82 - abrogat.' as a line; a repealed article is a removed file here."""
    gone = [k for k, u in units.items() if re.fullmatch(r"# Articolul \S+ – abrogat\.\n", u["text"])]
    LOG.append("2024 edition: repealed-article lines not kept as files: " + ", ".join(gone))
    return {k: u for k, u in units.items() if k not in gone}


def constitution(laws, decisions):
    reg13 = cached(ia_url(REG_2013))
    v2006, notes13 = ustav.from_register(reg13)
    v2006 = drop_editorial(v2006)
    reg16, notes16 = ustav.from_register(cached(ia_url(REG_2016)))
    check_register_2016(v2006, drop_editorial(reg16))
    # the register's MODIFICAT block in 2013 ends at LP185-XVI; no act after it until HCC7 (2016)
    t13 = text_of(reg13)
    flat = re.sub(r"[\s-]", "", t13)
    for _k, lab, *_ in REGISTER_ACTS[2:]:
        num = re.match(r"LP(\d+)", lab).group(1)
        assert re.search(r"LP?%s(XIII|XIV|XV|XVI)din" % num, flat), lab
    assert "HCC7" not in t13
    l185 = text_of(cached(ia_url(L185)))
    assert "Nr. 185-XVI" in l185 and "vigoare" not in l185   # no in-force clause: Constitution art. 76 applies
    v2016, cred16 = hcc7_version(v2006)

    pdf = os.path.join(CACHE, hashlib.sha256(MOLDPRES_2024.encode()).hexdigest())
    known = set()
    for u in v2006.values():
        for w in re.findall(r"[\wăîâșțĂÎÂȘȚ]+(?:-[\wăîâșțĂÎÂȘȚ]+)+", u["text"]):
            known.add(w.lower())
    for _kind, line in ustav.pdf_lines(pdf):
        for w in re.findall(r"[\wăîâșțĂÎÂȘȚ]+(?:-[\wăîâșțĂÎÂȘȚ]+)+", ustav.norm(line)):
            known.add(w.lower())
    v2024 = drop_repealed_stubs(ustav.from_moldpres(pdf, known))
    import fitz
    with fitz.open(pdf) as doc:
        head = re.sub(r"\s+", " ", doc[0].get_text() + doc[1].get_text())
    assert "la data de 20 octombrie 2024" in head and "Moldpres, 2024" in head
    for a in ["Legea nr.244 din 20.10.24", "HCC8 din 11.03.24", "LP52 din 16.03.23", "LP120 din 23.09.21",
              "LP255 din 22.11.18", "LP70 din 13.04.17", "LP256 din 25.11.16"]:
        assert a in head, a
    LOG.append(f"units: 2006 {len(v2006)}, 2016 {len(v2016)}, 2024 {len(v2024)}")
    for k in ("art-078", "art-089", "art-085"):
        LOG.append(f"HCC7 unit {k} equals the 2024 edition: {v2016[k]['text'] == v2024[k]['text']}")
    changed = sorted(k for k in set(v2016) | set(v2024) if v2016.get(k) != v2024.get(k))
    LOG.append(f"2016 -> 2024: {len(changed)} units differ (uncredited)")

    for key, lab, enacted, published, kind, title in REGISTER_ACTS:
        laws[key] = law(lab, title, enacted, published, "https://www.legis.md/", kind=kind)
    laws["hcc-7-2016"] = law(
        "HCC7 din 04.03.2016",
        "Hotărârea Curții Constituționale nr. 7 din 4 martie 2016 privind controlul constituționalității unor "
        "prevederi ale Legii nr. 1115-XIV din 5 iulie 2000 cu privire la modificarea și completarea Constituției "
        "Republicii Moldova (modul de alegere a Președintelui)",
        "2016-03-04", "2016-03-18", ia_url(HCC7), kind="court")

    versions = [
        {"from": "2006-07-14", "source_url": ia_url(REG_2013), "sha256": sha(reg13), "units": v2006,
         "credits": {},
         "note": "Oldest version available: the consolidated text of the State Register of Legal Acts "
                 "(lex.justice.md, archived 27 May 2013), which records the Constitution of 29 July 1994 "
                 "(MO nr.1, 12 August 1994) as amended up to LP185-XVI of 29 June 2006 (MO 14 July 2006)."},
        {"from": "2016-03-04", "source_url": ia_url(HCC7), "sha256": sha(cached(ia_url(HCC7))),
         "units": v2016, "credits": cred16,
         "note": "Constitutional Court judgment HCC7/2016 (in force on its adoption, 4 March 2016): its point 8 b) "
                 "sets the text of articles 78 and 89; point 3 strikes the phrase on art. 78 (5) from art. 85 (4)."},
        {"from": "2024-10-20", "source_url": MOLDPRES_2024, "sha256": sha(open(pdf, "rb").read()),
         "units": v2024, "credits": {},
         "note": "Moldpres edition 'Constituția Republicii Moldova. Cu modificări și completări la data de "
                 "20 octombrie 2024' (republished). It lists these amending acts after HCC7/2016: " + LATER_ACTS +
                 ". It gives no per-article notes, so the changes since 2016 are not credited to them one by one; "
                 "they also include the current spelling (â, sunt) the republished text uses throughout."},
    ]
    decisions += [
        "Sources: www.legis.md (the State Register of Legal Acts) answers every request with a Cloudflare bot "
        "challenge, and its pages load their text by script, so archives hold no copy of the current text. The "
        "register's earlier home lex.justice.md is read through Internet Archive id_ captures, and the current text "
        "from the Moldpres edition of 2024 (Moldpres publishes the Monitorul Oficial), hosted by the Presidency at "
        "presedinte.md.",
        "No dated versions before 2006 are available: the register shows only the consolidated text, with notes "
        "('[Art.78 în redacția LP1115-XIV ...]') but not the earlier wording. The first version is the register's "
        "text as amended by LP185-XVI/2006 ('oldest version available', first_law null), dated 14 July 2006, the "
        "day LP185-XVI was published: it has no in-force clause, so Constitution art. 76 (in force on publication) "
        "applies. The register lists no amending act between LP185-XVI and HCC7/2016.",
        "The 2013-05-27 capture is used for that text: from 2015 the register page carries markup corruption inside "
        "art. 35, 75 and 129 (escaped tags in the middle of words). The 2016 capture is checked against it: it "
        "differs only in those units, in the HCC7 notes, and in typo corrections (art. 24, 26, 34, 72, 88, 93, 136, "
        "Art. IV), which reach this history with the 2024 edition.",
        "HCC7/2016: the register kept the 2000 words and added notes; this build applies the judgment itself. "
        "Articles 78 and 89 take the text its point 8 b) sets out ('vor avea următorul cuprins'), and the phrase "
        "point 3 strikes is removed from art. 85 (4) with its commas as the 2024 edition reads it. The judgment took "
        "effect on adoption, 4 March 2016 (its point 9).",
        "The 2024 version is the Moldpres edition dated 20 October 2024 (the day of the referendum that adopted Law "
        "244/2024), the date the edition gives itself. The sources give no per-article attribution for the seven "
        "acts it lists after 2016 (LP256/2016, LP70/2017, LP255/2018, LP120/2021, LP52/2023, HCC8/2024, Law "
        "244/2024), so those changes are one uncredited commit on that day rather than guessed credits. Any change "
        "after that edition is not shown, because legis.md cannot be read.",
        "Typesetting normalised the same way in every source: cedilla ş/ţ and comma-below ș/ț are one letter "
        "(written ș, ț); spaced dashes are '–'; runs of spaces collapse; thousands set with a space ('200 000') are "
        "joined; letter-spaced headings ('G U V E R N U L') are joined; line-end hyphens of the PDF are removed "
        "unless the hyphenated word is printed elsewhere with its hyphen. Spelling is kept as each source prints it, "
        "including the 2024 edition's 'nou- ales' (art. 80) and its misprint 'Artcolul 52' (the heading line is "
        "rewritten from the article number).",
        "Units: the preamble; titles, chapters and sections as heading files (titlul-NN, capitolul-NN, "
        "capitolul-NN-sectiunea-N); articles art-NNN with art-NNN-N for superscript numbers (106^1); Title VII's "
        "Articles I-VIII as tranz-NN. An article file's first line is '# Articolul N', its second its caption.",
        "Left out as not law: the register's bracketed notes and 'Notă:' lines (used only to check credits), the "
        "1961 footnote to Art. IV, a stray 'Originalul art.24' line, and the 2024 edition's 'Articolul 82 - abrogat.' "
        "/ 'Articolul 83 - abrogat.' lines (a repealed article is a removed file; the register omits them too).",
        "Not built (Phase 1 core acts): Law 133/2011 on personal data protection, repealed from 23 August 2026 by "
        "Law 195/2024; the Criminal Code (985/2002), amended by well over a hundred acts; and Law 195/2024 itself. "
        "Their current texts are only on legis.md, and archives hold only pre-2019 register pages for the older "
        "two, so no build of them could end at today's official text (over the 45-minute budget per act).",
    ]
    return {"slug": "constitutia", "short": "Constituția", "title": "Constituția Republicii Moldova",
            "url": "https://www.legis.md/cautare/getResults?doc_id=145723&lang=ro",
            "first_law": None, "earlier_laws": [k for k, *_ in REGISTER_ACTS], "versions": versions}


def main():
    laws, decisions, acts = {}, [], []
    acts.append(constitution(laws, decisions))
    corpus = {
        "country": {
            "code": "MD", "name": "Moldova", "slug": "moldova", "lang": "ro", "tz": "Europe/Chisinau",
            "future_branch": "viitor",
            "publisher": {"name": "Registrul de stat al actelor juridice (Ministerul Justiției)",
                          "email": "registru@legis.invalid"},
            "default_in_force_rule": {
                "text": "Constituția Republicii Moldova art. 76: a law is published in the Monitorul Oficial and "
                        "takes effect on the day of publication or on the day its text sets. A Constitutional Court "
                        "judgment takes effect on the day its own text sets (HCC7/2016: on adoption).",
                "source": "https://www.legis.md/cautare/getResults?doc_id=145723&lang=ro"},
            "licence_note": "Official texts (laws, Constitutional Court judgments) are not objects of copyright "
                            "under Law 139/2010 on copyright and related rights. Text from the State Register of "
                            "Legal Acts (lex.justice.md, via the Internet Archive) and the Moldpres edition of the "
                            "Constitution (2024)."},
        "sources": [
            {"name": "Registrul de stat al actelor juridice, lex.justice.md (via the Internet Archive)",
             "url": "http://lex.justice.md/md/311496/", "retrieved": RETRIEVED,
             "requests": requests_count("https://web.archive.org/web/2") ,
             "licence": "Official texts, not objects of copyright (Law 139/2010); Internet Archive Wayback Machine "
                        "captures (id_ raw form), pinned by timestamp",
             "notes": "Captures used: " + "; ".join(f"{c[1]} at {c[0]}" for c in SOURCES) + ". The current register "
                      "www.legis.md answers with a Cloudflare bot challenge and was not fetched after one probe."},
            {"name": "Moldpres: Constituția Republicii Moldova, cu modificări și completări la data de 20 octombrie "
                     "2024 (PDF, hosted by the Presidency)",
             "url": MOLDPRES_2024, "retrieved": RETRIEVED, "requests": requests_count(MOLDPRES_2024),
             "licence": "Official text, not an object of copyright (Law 139/2010)",
             "notes": "ISBN 978-9975-3618-2-8; text layer read with PyMuPDF; no OCR."},
        ],
        "laws": dict(sorted(laws.items())),
        "acts": acts,
        "applies": [],
        "decisions": decisions,
        "ai_use": ["Claude Code (Claude Opus 5.5, claude-opus-5-5) chose the sources and wrote the fetch and parse "
                   "scripts. No model wrote or edited legal text; the HCC7 wording is read from the judgment by code. "
                   "No model runs at parse or git-build time."],
    }
    tmp = os.path.join(HERE, "corpus.json.tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=1)
        f.write("\n")
    os.replace(tmp, os.path.join(HERE, "corpus.json"))
    with open(os.path.join(HERE, "parse.log"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(LOG) + "\n")
    print("acts", [(a["slug"], len(a["versions"])) for a in acts], "laws", len(laws))


if __name__ == "__main__":
    main()
