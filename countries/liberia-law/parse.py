"""Liberia: read the cached LiberLII pages (Internet Archive id_ captures) and write corpus.json (gitlaw_common/SCHEMA.md).

Cache only, no network, deterministic. Run fetch.py --plan first.

    python -X utf8 parse.py            write corpus.json (atomically)
    python -X utf8 parse.py --report   also print unit counts per version

LiberLII pages are AustLII-style single HTML pages, one per Act or Title. They hold one text (no point-in-time
versions). The Penal Law's text prints a few dated editorial annotations ("(Effective December 6, 1994)", "(ONLY FOR
OFFENSES ON OR BEFORE JAN. 16, 2006.)", "as amended by the interim National Assembly, July 9, 1985"), and older
versions are rebuilt from those annotations only (see DECISIONS).
"""
from __future__ import annotations

import hashlib
import html as htmlmod
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
SOURCES = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
FILES = {f["id"]: f for f in SOURCES["files"]}
PLACEHOLDER = "[The source does not give the text in force on this date.]"

QUOTES = str.maketrans({"“": '"', "”": '"', "„": '"', "″": '"', "‘": "'", "’": "'",
                        "′": "'", " ": " ", " ": " ", " ": " ", " ": " ", "\t": " "})


def raw(fid: str) -> bytes:
    p = CACHE / hashlib.sha256(FILES[fid]["url"].encode("utf-8")).hexdigest()
    if not p.exists():
        sys.exit(f"not cached (run fetch.py --plan): {FILES[fid]['url']}")
    return p.read_bytes()


def sha(fid: str) -> str:
    return hashlib.sha256(raw(fid)).hexdigest()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).translate(QUOTES)
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s).strip()
    return s


BLOCK = re.compile(r"</?(?:p|li|blockquote|ul|ol|h\d|hr|div|table|tr|td|center)\b[^>]*>", re.I)


def blocks(b: bytes) -> list[tuple[bool, str]]:
    """The document body as (is_bold_start, line) pairs, one paragraph, list item or <br> line each."""
    t = b.decode("utf-8", "replace")
    start = t.index("<!--make_database header end-->")
    end = t.index("<!--make_database footer start-->")
    t = t[start:end]
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\x01", t, flags=re.I)
    out = []
    for seg in BLOCK.split(t):
        bold = bool(re.match(r"\s*(?:<i>\s*)?<b>", seg, re.I))
        for part in seg.split("\x01"):
            txt = norm(htmlmod.unescape(re.sub(r"<[^>]+>", "", part)))
            if txt:
                out.append((bold, txt))
                bold = False
    return out


class Units:
    def __init__(self):
        self.units: dict[str, dict] = {}
        self.cur: str | None = None

    def open(self, key: str, label: str, kind: str, heading: str):
        assert key not in self.units, key
        self.units[key] = {"label": label, "kind": kind, "lines": [f"# {heading}"]}
        self.cur = key

    def add(self, line: str):
        if self.cur is None:
            return
        self.units[self.cur]["lines"].append(line)

    def done(self) -> dict:
        return {k: {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"}
                for k, u in self.units.items()}


ROMAN = {"I": 1, "V": 5, "X": 10, "L": 50}


def roman(s: str) -> int:
    n = 0
    for a, b in zip(s, s[1:] + " "):
        v = ROMAN[a]
        n += -v if b != " " and ROMAN.get(b, 0) > v else v
    return n


# ---------------------------------------------------------------- the Constitution

def constitution() -> dict:
    u = Units()
    u.open("preamble", "Preamble", "preamble", "Preamble")
    for bold, line in blocks(raw("constitution")):
        if line in ("CONSTITUTION OF THE REPUBLIC OF LIBERIA",):
            continue
        if line == "PREAMBLE":
            continue
        m = re.match(r"^CHAPTER ([IVXL]+)\s*(.*)$", line)
        if m and bold:
            n = roman(m.group(1))
            u.open(f"chap-{n:02d}", f"Chapter {m.group(1)}", "chapter", f"Chapter {m.group(1)}")
            if m.group(2):
                u.add(m.group(2))
            continue
        m = re.match(r"^Article\s*(\d+)\s*(.*)$", line)
        if m and not re.match(r"^Article\s*\d+\s*(of|and|or|,)", line):
            n = int(m.group(1))
            key = f"art-{n:03d}"
            if key not in u.units and (not u.units or n == _last_art(u) + 1):
                u.open(key, f"Art. {n}", "art", f"Article {n}")
                if m.group(2):
                    u.add(m.group(2))
                continue
        if line == "SCHEDULE":
            u.open("schedule", "Schedule", "schedule", "Schedule")
            continue
        if line == "NATIONAL CONSTITUTION COMMISSION":
            u.open("signatories", "Signatories", "signatories", "Signatories")
        if u.cur and u.cur.startswith("chap-") and len(u.units[u.cur]["lines"]) >= 2 and not line.isupper():
            pass
        u.add(line)
    units = u.done()
    arts = sorted(k for k in units if k.startswith("art-"))
    assert arts == [f"art-{i:03d}" for i in range(1, len(arts) + 1)], arts[-5:]
    return units


def _last_art(u: Units) -> int:
    arts = [int(k[4:]) for k in u.units if k.startswith("art-")]
    return max(arts) if arts else 0


# ---------------------------------------------------------------- the Penal Law (Title 26)

SEC = re.compile(r"^§\s*(\d+)\.(\d+)\.?\s*(.*)$")


def penal_units(fid: str) -> tuple[dict, dict]:
    """All units as LiberLII prints them, plus the extra texts it prints for earlier periods (keyed 'old:<key>')."""
    u = Units()
    extra: dict[str, dict] = {}
    body_started = False
    bl = blocks(raw(fid))
    for i, (bold, line) in enumerate(bl):
        if line == "PART I":  # Part I's own heading; everything before it is the Contents list
            body_started = True
        if not body_started:
            continue
        m = re.match(r"^PART ([IVX]+)\.?$", line)
        if m:
            n = roman(m.group(1))
            u.open(f"part-{n}", f"Part {m.group(1)}", "part", f"Part {m.group(1)}")
            continue
        m = re.match(r"^Chapter (\d+)\.\s*(.*)$", line)
        if m and bold:
            n = int(m.group(1))
            u.open(f"chap-{n:02d}", f"Chapter {n}", "chapter", f"Chapter {n}. {m.group(2)}")
            continue
        m = re.match(r"^Subchapter ([A-Z])\.\s*(.*)$", line)
        if m and bold:
            # Subchapter headings belong to the chapter's own file, not to the section before them. A chapter's own
            # list of sections also names its subchapters: those are followed by a plain (not bold) section line.
            nxt = bl[i + 1] if i + 1 < len(bl) else (False, "")
            ch = _chapter_of(u)
            if ch and nxt[0] and SEC.match(nxt[1]):
                u.units[ch]["lines"].append(f"Subchapter {m.group(1)}. {m.group(2)}")
            u.cur = None
            continue
        m = SEC.match(line)
        if m and bold:
            ch, sn, rest = int(m.group(1)), int(m.group(2)), m.group(3)
            key = f"sec-{ch:02d}-{sn:03d}"
            note = None
            mm = re.search(r"\s*\((ONLY FOR OFFENSES[^)]*|Effective [^)]*)\)\s*$", rest)
            if mm:
                note = mm.group(1)
                rest = rest[:mm.start()].strip()
            heading = f"§ {ch}.{sn}. {rest}".strip()
            if key in u.units:  # a second text of the same section: the one for earlier offenses
                extra_key = "old:" + key
                u.units[extra_key] = {"label": f"§ {ch}.{sn}", "kind": "sec", "lines": [f"# {heading}"], "note": note}
                u.cur = extra_key
                continue
            u.open(key, f"§ {ch}.{sn}", "sec", heading)
            u.units[key]["note"] = note
            continue
        if u.cur and u.cur.startswith("chap-") and SEC.match(line):
            continue  # the chapter's list of sections (an outline, not law text)
        u.add(line)
    notes = {}
    out = {}
    for k, v in u.units.items():
        if v.get("note"):
            notes[k] = v["note"]
        target = extra if k.startswith("old:") else out
        target[k] = {"label": v["label"], "kind": v["kind"], "text": "\n".join(v["lines"]) + "\n"}
    return out, {"old": extra, "notes": notes}


def _chapter_of(u: Units) -> str | None:
    chaps = [k for k in u.units if k.startswith("chap-")]
    return chaps[-1] if chaps else None


def penal_versions() -> list[dict]:
    units, info = penal_units("penal-law")
    units17, _ = penal_units("penal-law-2017")
    assert units == units17, "the 2017 and 2026 captures differ: rebuild the version logic"
    notes = info["notes"]
    old = info["old"]
    assert notes == {"sec-14-054": "Effective December 6, 1994",
                     "sec-14-070": "ONLY FOR OFFENSES COMMITTED ON OR AFTER JAN 17, 2006.",
                     "sec-14-071": "ONLY FOR OFFENSES COMMITTED ON OR BEFORE JAN. 16, 2006.",
                     "old:sec-14-070": "ONLY FOR OFFENSES ON OR BEFORE JAN. 16, 2006."}, notes
    assert list(old) == ["old:sec-14-070"]
    s1251 = units["sec-12-051"]["text"]
    amended = ", as amended by the interim National Assembly, July 9, 1985."
    assert amended in s1251
    units["sec-12-051"] = dict(units["sec-12-051"], text=s1251.replace(amended, "."))

    today = dict(units)
    # 14.71: the source marks it as applying only to offences committed on or before 16 Jan 2006.
    t71 = units["sec-14-071"]["text"].split("\n", 1)
    today["sec-14-071"] = dict(units["sec-14-071"], text=t71[0] + "\n(Only for offenses committed on or before Jan. 16, 2006.)\n" + t71[1])

    v1978 = dict(units)
    v1978["sec-12-051"] = dict(units["sec-12-051"], text="# § 12.51. Unlawful rewarding of public servants.\n" + PLACEHOLDER + "\n")
    del v1978["sec-14-054"]
    v1978["sec-14-070"] = old["old:sec-14-070"]

    v1985_changes = {"sec-12-051": units["sec-12-051"]}
    v1994_changes = {"sec-14-054": units["sec-14-054"]}
    v2006_changes = {"sec-14-070": units["sec-14-070"], "sec-14-071": today["sec-14-071"]}

    src = FILES["penal-law"]["url"]
    h = sha("penal-law")
    return [
        {"from": "1978-04-03", "source_url": src, "sha256": h, "units": dict(sorted(v1978.items())),
         "credits": {},
         "note": ("Rebuilt from LiberLII's text of the Penal Law: the provisions LiberLII marks as later "
                  "(§ 12.51 as amended 9 July 1985, § 14.54 effective 6 December 1994, § 14.70 for offences from "
                  "17 January 2006) are shown as they stood before; LiberLII prints the earlier § 14.70 itself. "
                  "Provisions LiberLII does not date are shown as it prints them and may include later amendments "
                  "it does not mark. The earlier wording of § 12.51 is not given by the source.")},
        {"from": "1985-07-09", "source_url": src, "sha256": h, "changes": v1985_changes,
         "credits": {"sec-12-051": ["ina-1985-07-09"]},
         "note": "LiberLII prints § 12.51(2) with the note \"as amended by the interim National Assembly, July 9, 1985\"."},
        {"from": "1994-12-06", "source_url": src, "sha256": h, "changes": v1994_changes, "credits": {},
         "note": "LiberLII heads § 14.54 (Terrorism) \"(Effective December 6, 1994)\" and does not name the law that inserted it."},
        {"from": "2006-01-17", "source_url": src, "sha256": h, "changes": v2006_changes, "credits": {},
         "note": ("LiberLII prints the new § 14.70 (Rape, including gang rape) \"(ONLY FOR OFFENSES COMMITTED ON OR "
                  "AFTER JAN 17, 2006.)\", and keeps the earlier § 14.70 and § 14.71 marked for offences on or before "
                  "16 January 2006, which they continue to govern. It does not name the amending law. The new § "
                  "14.70(5)(b) repeals § 14.78(3) and (4); LiberLII still prints them, so they are left in.")},
    ]


# ---------------------------------------------------------------- the Freedom of Information Act 2010

def foi() -> dict:
    u = Units()
    u.open("preamble", "Preamble", "preamble", "Preamble")
    for bold, line in blocks(raw("foi-act")):
        if line == "AN ACT TO ESTABLISH THE FREEDOM OF INFORMATION":
            u.add(line)
            continue
        if line == "PREAMBLE":
            continue
        m = re.match(r"^Chapter (\d+)\s+(.*)$", line)
        if m and bold:
            n = int(m.group(1))
            u.open(f"chap-{n:02d}", f"Chapter {n}", "chapter", f"Chapter {n} {m.group(2)}")
            continue
        m = re.match(r"^Section\s*(\d+)\.(\d+)\s*(.*)$", line)
        if m and bold:
            a, b_, rest = int(m.group(1)), int(m.group(2)), m.group(3)
            key = f"sec-{a:02d}-{b_:02d}"
            if key not in u.units:
                title, _, body = rest.partition(":")
                if body:
                    u.open(key, f"s. {a}.{b_}", "sec", f"Section {a}.{b_} {title.strip()}".strip())
                    u.add(body.strip())
                else:
                    u.open(key, f"s. {a}.{b_}", "sec", f"Section {a}.{b_}")
                    if rest:
                        u.add(rest)
                continue
        mm = re.match(r"^ANY LAW TO THE CONTRARY NOTWITHSTANDING\s*(.*)$", line)
        if mm:
            u.open("enactment", "Enactment", "enactment", "Enactment")
            u.add("ANY LAW TO THE CONTRARY NOTWITHSTANDING")
            rest = mm.group(1)
            for piece in re.split(r"(?=Published:)", rest):
                if piece.strip():
                    u.add(piece.strip())
            continue
        u.add(line)
    return u.done()


# ---------------------------------------------------------------- the corpus

def corpus() -> dict:
    con = constitution()
    pen = penal_versions()
    f = foi()
    lii = ("LiberLII (Liberia Legal Information Institute), read only through Internet Archive id_ captures. "
           "LiberLII's robots.txt (fetched 2026-10-28) allows User-agent * with Content-Signal search=yes, "
           "ai-train=no, use=reference.")
    files = [dict(f_, sha256=sha(f_["id"])) for f_ in SOURCES["files"]]
    return {
        "country": {
            "code": "LR", "name": "Liberia", "slug": "liberia", "lang": "en", "tz": "Africa/Monrovia",
            "future_branch": "future",
            "publisher": {"name": "LiberLII (Liberia Legal Information Institute)", "email": "liberlii@liberlii.invalid"},
            "default_in_force_rule": {
                "text": ("No general default rule was found in the sources read (the General Construction Law, "
                         "Title 15, on LiberLII has none). Each act's own effective-date clause is used: the "
                         "Penal Law and the Freedom of Information Act each take effect immediately upon "
                         "publication, on the publication date the act itself prints."),
                "source": "https://web.archive.org/web/20240714145606id_/http://www.liberlii.org/lr/legis/codes/gclt15lcolr538/"},
            "licence_note": ("Text from LiberLII (www.liberlii.org), read through the Internet Archive's Wayback "
                             "Machine. LiberLII publishes no licence for its legislation pages; Liberian "
                             "legislation is public law. Dates of the Constitution from WIPO Lex."),
        },
        "sources": [
            {"name": "LiberLII via the Internet Archive (web.archive.org id_ captures)", "url": "https://www.liberlii.org",
             "retrieved": "2026-10-28", "requests": len(files) - 1, "licence": "none published; legislation is public law",
             "notes": lii + " Pinned captures: " + "; ".join(f'{x["id"]} {x.get("capture", "")} sha256 {x["sha256"][:16]}' for x in files if x.get("capture"))},
            {"name": "WIPO Lex: Constitution of the Republic of Liberia", "url": FILES["wipo-constitution"]["url"],
             "retrieved": "2026-10-28", "requests": 1, "licence": "WIPO terms of use",
             "notes": "Gives 'Entry into force: January 6, 1986; Adopted: July 3, 1984'."},
        ],
        "laws": {
            "constitution-1986": {"label": "Constitution of the Republic of Liberia (1986)",
                                  "title": "Constitution of the Republic of Liberia", "kind": "referendum",
                                  "enacted": "1984-07-03", "published": None,
                                  "url": FILES["wipo-constitution"]["url"], "temporary_until": None, "restores": None,
                                  "note": None},
            "penal-law-1976": {"label": "Act Adopting a New Penal Law (1976)",
                               "title": "An Act Adopting a New Penal Law (Title 26, Liberian Code of Laws Revised)",
                               "kind": "law", "enacted": "1976-07-19", "published": "1978-04-03",
                               "url": FILES["penal-law"]["original"], "temporary_until": None, "restores": None,
                               "note": None},
            "ina-1985-07-09": {"label": "Interim National Assembly (9 July 1985)",
                               "title": "Amendment of § 12.51 of the Penal Law by the Interim National Assembly, July 9, 1985",
                               "kind": "law", "enacted": "1985-07-09", "published": None,
                               "url": FILES["penal-law"]["original"], "temporary_until": None, "restores": None,
                               "note": None},
            "foi-act-2010": {"label": "Freedom of Information Act 2010", "title": "An Act to Establish the Freedom of Information",
                             "kind": "law", "enacted": "2010-09-16", "published": "2010-10-06",
                             "url": FILES["foi-act"]["original"], "temporary_until": None, "restores": None, "note": None},
        },
        "acts": [
            {"slug": "constitution", "short": "Const.", "title": "Constitution of the Republic of Liberia (1986)",
             "url": FILES["constitution"]["original"], "first_law": "constitution-1986", "earlier_laws": [],
             "versions": [{"from": "1986-01-06", "source_url": FILES["constitution"]["url"], "sha256": sha("constitution"),
                           "units": con, "credits": {},
                           "note": ("The Constitution as adopted by the referendum of 3 July 1984, in force 6 January "
                                    "1986 (WIPO Lex). LiberLII's text has no amendments applied. The constitutional "
                                    "referendums of 23 August 2011 (Joint Resolution 001 (2010): Arts. 52(c), 72(b), "
                                    "83(a), 83(b)) and of 2020 are not applied: no source with a text layer gives "
                                    "amended wording, and the 2011 outcome of Proposition 4 (Art. 83(b)) was "
                                    "disputed before the Supreme Court.")}]},
            {"slug": "penal-law", "short": "PL", "title": "Penal Law (Title 26, Liberian Code of Laws Revised)",
             "url": FILES["penal-law"]["original"], "first_law": None, "earlier_laws": ["penal-law-1976"],
             "versions": pen},
            {"slug": "freedom-of-information-act", "short": "FOIA", "title": "Freedom of Information Act of 2010",
             "url": FILES["foi-act"]["original"], "first_law": "foi-act-2010", "earlier_laws": [],
             "versions": [{"from": "2010-10-06", "source_url": FILES["foi-act"]["url"], "sha256": sha("foi-act"),
                           "units": f, "credits": {},
                           "note": "As enacted: approved 16 September 2010, published into handbills 6 October 2010 (Chapter 8: in force on publication)."}]},
        ],
        "applies": [],
        "decisions": DECISIONS,
        "ai_use": ["none: no model wrote, summarised or parsed legal text. Claude Code (Claude Opus 5.5, claude-opus-5-5) wrote "
                   "fetch.py and parse.py and chose the sources; parsing is deterministic code."],
    }


DECISIONS = [
    "Source: no Liberian government site gives legislation with a text layer. emansion.gov.lr and moj.gov.lr PDFs "
    "probed on 2026-10-28 (Data Protection Act 2026, Cybercrime Act 2025, FOI Act, Police Act) are scans with only a "
    "cover-page text layer, so they are not used (no OCR). legislature.gov.lr did not resolve.",
    "LiberLII is read only through Internet Archive id_ captures, never from liberlii.org (user decision of "
    "2026-10-28: 'scraping wayback is fair game, dont overdo it'). The captures are pinned in sources.json.",
    "LiberLII gives one text per act, not dated versions. Its pages carry an internal 'sino date' (Penal Law 3 April "
    "1978, Constitution 1 January 1986, FOI Act 16 September 2010) that is not an as-at date and is not used.",
    "Constitution: one version, in force 6 January 1986 and adopted 3 July 1984 (WIPO Lex). Art. 94(b) names 12 April "
    "1985 as the planned inauguration; WIPO Lex's in-force date is used.",
    "Constitution: the 2011 referendum (Joint Resolution 001 (2010), adopted by the Legislature 17 August 2010 per the "
    "NEC Referendum Regulations of 28 February 2011) and the 2020 referendum are not applied: LiberLII prints Art. "
    "83(b) unamended, and no source with a text layer gives amended wording.",
    "Constitution units: preamble, chapter headings (chap-NN), Articles 1-97 (art-NNN), the Schedule (oath), and the "
    "signatories (National Constitution Commission, Constitutional Advisory Assembly).",
    "Penal Law in force 3 April 1978: the Act Adopting a New Penal Law, approved 19 July 1976, published 3 April 1978 "
    "(the Title's own cover), says 'This act shall take effect immediately upon publication' (its section 3, printed "
    "at the end of § 51.3); LiberLII's Criminal Procedure Law cites the same act and dates for its repeal of §§ 31.3 "
    "and 32.1.",
    "Penal Law versions are rebuilt only from LiberLII's own dated annotations: § 12.51 ('as amended by the interim "
    "National Assembly, July 9, 1985'), § 14.54 ('Effective December 6, 1994'), § 14.70 and § 14.71 ('ONLY FOR "
    "OFFENSES ... ON OR AFTER JAN 17, 2006' / 'ON OR BEFORE JAN. 16, 2006'). The 2017-04-20 and 2026-07-03 captures "
    "give identical text.",
    "Penal Law § 12.51: the 1985 note is taken as an editorial note and removed from the text; its date is used as "
    "the in-force date of the change. The wording before 9 July 1985 is not given, so the 1978 version reads "
    "'" + PLACEHOLDER + "' (anachronism rule) and the 1985 change is credited to 'Interim National Assembly (9 July "
    "1985)', the body the note names.",
    "Penal Law § 14.54 (Terrorism) is absent before 6 December 1994; LiberLII names no amending law, so the change is "
    "committed as unexplained by the publisher.",
    "Penal Law § 14.70 (Rape): the text marked for offences on or before 16 January 2006 is the 1978-2006 text, the "
    "one marked from 17 January 2006 is today's; § 14.71 gains the source's marker line in 2006. LiberLII names no "
    "amending law (unexplained). The earlier texts continue to govern offences committed before 17 January 2006.",
    "Penal Law § 14.78(3) and (4) are repealed by the new § 14.70(5)(b), but LiberLII still prints them; they are "
    "kept as printed, so today's text equals the source.",
    "Penal Law: provisions LiberLII does not date are shown in every version as it prints them; they may include "
    "later amendments LiberLII does not mark (for example any made after 2006). The first version is credited to the "
    "publisher as the oldest version available, naming the 1976 Act, not as the act as enacted.",
    "Penal Law units: part-N, chapter headings with their subchapter headings (chap-NN), and sections "
    "(sec-CC-SSS). The Contents list and each chapter's list of sections are outlines and are left out.",
    "Freedom of Information Act 2010: one version, in force 6 October 2010 (approved 16 September 2010, published "
    "into handbills 6 October 2010; Chapter 8: effective on publication into handbills). No amendment is known to "
    "LiberLII.",
    "Criminal Procedure Law (Title 2) and Civil Procedure Law (Title 1) are not built yet: LiberLII gives no "
    "effective date for either Title, so a first version cannot be dated from the source.",
]


def main() -> None:
    c = corpus()
    tmp = HERE / "corpus.json.tmp"
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, HERE / "corpus.json")
    if "--report" in sys.argv:
        for a in c["acts"]:
            for v in a["versions"]:
                print(a["slug"], v["from"], len(v.get("units") or {}), "changes:", list((v.get("changes") or {}).keys()))


if __name__ == "__main__":
    main()
