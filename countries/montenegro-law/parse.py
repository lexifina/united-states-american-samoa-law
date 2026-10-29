"""Montenegro: read only .cache/ and write corpus.json (gitlaw_common SCHEMA.md). Deterministic.

    python -X utf8 parse.py        -> corpus.json (atomically) and parse.log
"""
import json, os
import gazette, ustav, ustav_replay, zakon

HERE = os.path.dirname(os.path.abspath(__file__))
RETRIEVED = "2026-10-29"
LOG = []


def requests_count(prefix):
    n = 0
    with open(os.path.join(gazette.CACHE, "requests.jsonl"), encoding="utf-8") as f:
        for line in f:
            if json.loads(line)["url"].startswith(prefix):
                n += 1
    return n


def law(label, title, enacted, published, act_id, kind="law", note=None):
    return {"label": label, "title": title, "kind": kind, "enacted": enacted, "published": published,
            "url": gazette.page_url(act_id), "temporary_until": None, "restores": None, "note": note}


def constitution(laws, decisions):
    versions, texts = ustav_replay.replay()
    for name, ok in ustav_replay.checks(versions, texts):
        LOG.append(f"check {'OK ' if ok else 'FAIL'} {name}")
        assert ok, name
    laws["ustav-2007"] = law("Ustav Crne Gore (2007)", "Ustav Crne Gore", "2007-10-19", "2007-10-25", ustav.USTAV)
    for day, act, (_i, _c), romans in ustav_replay.BATCHES:
        m = gazette.meta(act)
        for r in romans:
            laws[f"amandman-{ustav.ROMAN.index(r) + 1:02d}"] = law(
                f"Amandman {r}", f"Amandman {r} na Ustav Crne Gore ({m['issue']})", day, m["published"], act)
    out = []
    for day, act, credits, units, log in versions:
        LOG.extend(log)
        m = gazette.meta(act)
        v = {"from": day, "source_url": gazette.pdf_url(act), "sha256": gazette.sha(act), "units": units,
             "credits": credits,
             "note": f"{m['title']}, {m['issue']} (published {m['published']})."}
        out.append(v)
    decisions += [
        "Constitution: there is no official consolidated text. Officially it is the 2007 text (Službeni list CG "
        "1/2007) plus Amendments I-XVI (38/2013) and XVII-XXI (126/2026), each 'sastavni dio Ustava'. Each "
        "amendment is applied by its own last paragraph ('Ovim amandmanom zamjenjuje se ...'), transcribed in "
        "ustav_replay.py (OPS) and checked word for word against that paragraph (INSTR) on every run.",
        "Script: the gazette published the 2007 Constitution in Cyrillic and the amendments in Latin; both scripts "
        "are official (Constitution art. 13). Every provision keeps the script of the text that gave it its words, "
        "so an amended article can mix Cyrillic and Latin lines. Nothing is transliterated.",
        "'Zamjenjuje se stav N ... i dopunjava' puts all of the amendment's paragraphs in place of stav N. Amendment "
        "XVII (2026) confirms this for Amendment IV: the 'stav 3 člana 91 (Amandman IV)' it replaces is IV's second "
        "paragraph. 'Dopunjava se član N' alone (XIV, XV) adds the paragraphs at the end of the article.",
        "A numbered point ('1) ...') belongs to the paragraph before it, so 'stav 3' counts paragraphs, not points "
        "(Amendment XIX deletes stav 3 of art. 128, the last paragraph after the points of stav 1).",
        "In-force days: the 2007 Constitution took effect on its proclamation, 22 October 2007 (gazette 'Datum "
        "stupanja na snagu'; art. 158 with the constitutional law). Each batch of amendments says it 'stupa na snagu "
        "danom proglašenja': 31 July 2013 (published 2 August 2013) and 24 August 2026 (published 26 August 2026).",
        "Article captions (the bold heading above 'Član N') are the second line of the article file ('## ...'); "
        "Amendments II and XX replace a caption ('naziv člana'). Part and chapter headings are units of their own "
        "(dio-N, dio-N-poglavlje-M); Amendment VI renames chapter 5 of Part Three from 'СУД' to 'SUDSTVO'.",
        "Letter-spaced headings ('5. С У Д') are joined into one word; runs of spaces are collapsed. Otherwise the "
        "gazette's words, punctuation and spelling are kept, including 'Ustavnog suda,vrhovnog' in Amendment III.",
        "Left out: the promulgation decisions printed before each text, the signatures, and the two constitutional "
        "laws for implementing the amendments (Ustavni zakon, 38/2013 and 126/2026), which are separate acts. The "
        "draft Amendment XXII (Skupština, October 2026) is not adopted and is not included.",
    ]
    return {"slug": "ustav", "short": "Ustav", "title": "Ustav Crne Gore", "url": gazette.page_url(ustav.USTAV),
            "first_law": "ustav-2007", "earlier_laws": [], "versions": out}


ZZPL_2026 = 398066


def zzpl_2026(laws, decisions):
    m = gazette.meta(ZZPL_2026)
    assert (m["published"], m["in_force"], m["applies"]) == ("2026-09-11", "2026-09-19", "2027-03-19"), m
    elems = zakon.read(ZZPL_2026)
    nums = [e[1] for e in elems if e[0] == "art"]
    assert nums == [str(i) for i in range(1, 107)], nums
    units = zakon.units(elems)
    # the law's own final article states the days the gazette metadata gives
    assert "stupa na snagu osmog dana od dana objavljivanja" in units["clan-106"]["text"]
    assert "primjenjivaće se nakon šest mjeseci od dana njegovog stupanja na snagu" in units["clan-106"]["text"]
    laws["zzpl-2026"] = law("Zakon o zaštiti podataka o ličnosti (133/2026)", "Zakon o zaštiti podataka o ličnosti",
                            "2026-09-04", m["published"], ZZPL_2026)
    decisions += [
        "Law on Personal Data Protection (2026): the new law (Službeni list CG 133/2026, published 11 September "
        "2026) is built as enacted. It takes effect on the eighth day after publication, 19 September 2026 (art. "
        "106; gazette 'Datum stupanja na snagu'), the commit date, and applies from 19 March 2027, six months later "
        "(gazette 'Datum početka primjene'); art. 104 defers some provisions to EU accession.",
        "The 2008 Law on Personal Data Protection (79/2008, amended 70/2009, 44/2012, 22/2017, 77/2024), which the "
        "2026 law repeals on its application day (art. 105, except arts. 35-40a on video surveillance), is not built "
        "yet: no consolidated official text exists, 44/2012 makes dozens of word-level edits across some 40 "
        "articles, and its PDF text layer splits words ('zloupo trebe', 'nad zornom', 'brisa nje'), so an exact "
        "replay would need hand-corrected words.",
        "Not built: the Criminal Code (Krivični zakonik, 70/2003), with more than a dozen amending laws on the "
        "gazette's record and no official consolidated text (over the 45-minute budget per act); and the Law on "
        "Obligations (Zakon o obligacionim odnosima, 47/2008; amended 22/2017, 123/2024, 94/2026, 117/2026), "
        "because 123/2024 replaces 'bračni drug' 'u različitom padežu' (in each grammatical case), so the new "
        "words in most cases are not printed in the gazette and would have to be composed.",
    ]
    note = (f"{m['title']}, {m['issue']} (published {m['published']}). In force {m['in_force']}; applies from "
            f"{m['applies']} (art. 106). Until then the 2008 law (79/2008 as amended) still applies.")
    return {"slug": "zakon-o-zastiti-podataka-o-licnosti", "short": "ZZPL",
            "title": "Zakon o zaštiti podataka o ličnosti", "url": gazette.page_url(ZZPL_2026),
            "first_law": "zzpl-2026", "earlier_laws": [],
            "versions": [{"from": m["in_force"], "source_url": gazette.pdf_url(ZZPL_2026),
                          "sha256": gazette.sha(ZZPL_2026), "units": units, "credits": {}, "note": note}]}


def main():
    laws, decisions, acts = {}, [], []
    acts.append(constitution(laws, decisions))
    acts.append(zzpl_2026(laws, decisions))
    corpus = {
        "country": {
            "code": "ME", "name": "Montenegro", "slug": "montenegro", "lang": "cnr", "tz": "Europe/Podgorica",
            "future_branch": "buduce",
            "publisher": {"name": "Službeni list Crne Gore", "email": "sluzbenilist@sluzbenilist.invalid"},
            "default_in_force_rule": {
                "text": "Ustav Crne Gore art. 146: a law or other regulation is published before it takes effect and "
                        "takes effect no earlier than the eighth day after its publication; each act's own final "
                        "article states its day. The Constitution and its amendments take effect on proclamation.",
                "source": gazette.page_url(ustav.USTAV)},
            "licence_note": "Laws and other official acts are not protected by copyright in Montenegro (Zakon o "
                            "autorskom i srodnim pravima). Text from Službeni list Crne Gore "
                            "(www.sluzbenilist.me), the official gazette and legal information system (PIS)."},
        "sources": [
            {"name": "Službeni list Crne Gore (Official Gazette of Montenegro, PIS)",
             "url": "https://www.sluzbenilist.me/propisi", "retrieved": RETRIEVED,
             "requests": requests_count("https://www.sluzbenilist.me/"),
             "licence": "Official texts, not protected by copyright (Zakon o autorskom i srodnim pravima)",
             "notes": "Act pages /propisi/<id> give the issue, publication, in-force and application dates and the "
                      "amending acts; /propisi/<id>/download gives the act's PDF with a text layer (no OCR used). "
                      "robots.txt allows all agents except named AI crawlers."},
            {"name": "Skupština Crne Gore (Parliament)", "url": "https://www.skupstina.me/me/ustav-crne-gore",
             "retrieved": RETRIEVED, "requests": requests_count("https://api.skupstina.me/"),
             "licence": "Official texts, not protected by copyright",
             "notes": "Probed for the Constitution: its PDFs (api.skupstina.me/media/files/...) have an unreadable "
                      "font encoding or lose diacritics, so no text is taken from them."},
        ],
        "laws": dict(sorted(laws.items())),
        "acts": acts,
        "applies": [],
        "decisions": decisions,
        "ai_use": ["Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote the fetch and parse scripts and "
                   "transcribed each amendment's instruction paragraph into an operation table (OPS), which the "
                   "parser checks against the gazette's own words. No model wrote or edited legal text, and no "
                   "model runs at parse or git-build time."],
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
