"""Reads only .cache/ (filled by fetch.py) and writes corpus.json. Deterministic.

Phase 1 so far: the Constitution of the Russian Federation, all 21 editions (редакции) on the
official IPS (actual.pravo.gov.ru API, bpa=ebpi, ttl=3), 1993-12-12 .. 2022-10-05.
Each edition's date is the portal's own edition date ("на DD.MM.YYYY"); each edition names one
amending act (reddocrefid -> card), and every unit that differs from the previous edition is
credited to that act. Editorial notes (class P, "(В редакции ...)") are kept out of the text.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402

SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
TR = {"ФКЗ": "fkz", "ФЗ": "fz", "П": "p", "рп": "rp", "р": "r", "О": "o"}


def load(url: str):
    return json.loads(fetch.path_for(url).read_bytes())


def paras(redid: int) -> list[tuple[str, str]]:
    h = load(fetch.redtext_url(redid))["redtext"]
    body = h[h.find("<body"):]
    out = []
    for m in re.finditer(r'<p(?:\s+class="([A-Za-z]+)")?[^>]*>(.*?)</p>', body, re.S):
        cls, inner = m.group(1) or "", m.group(2)
        inner = re.sub(r'<span class="HD">.*?</span>', "", inner, flags=re.S)
        inner = re.sub(r'<span class="W9">([^<]*)</span>', lambda x: x.group(1).translate(SUP), inner)
        inner = re.sub(r'<span class="mark">.*?</span>\s*(?=</span>|$)', "", inner, flags=re.S) if cls != "P" else inner
        t = html.unescape(re.sub(r"<[^>]+>", "", inner)).replace("\xa0", " ")
        t = re.sub(r"\s+", " ", t).strip()
        # editorial notes appended to a paragraph: "(В редакции ...)" / "(Часть ... в редакции ...)"
        t = re.sub(r"\s*\((?:[А-Яа-я ,0-9.¹²³⁴⁵⁶⁷⁸⁹]*)?[Вв] редакции [^()]*(?:\([^()]*\)[^()]*)*\)$", "", t)
        if cls == "P" or not t:
            continue
        out.append((cls, t))
    return out


def units_of(redid: int) -> dict:
    units: dict = {}
    cur, lines, label = "preambula", [], "Преамбула"
    heads: list[str] = []

    def flush():
        if lines:
            units[cur] = {"label": label, "kind": "art" if cur.startswith("art") else "other",
                          "text": "\n".join(lines) + "\n"}

    for cls, t in paras(redid):
        m = re.fullmatch(r"Статья (\d+)([¹²³⁴⁵⁶⁷⁸⁹]*)", t)
        if cls in ("T", "C") and m:
            flush()
            n = int(m.group(1))
            cur, label = f"art-{n:03d}", t
            lines = [f"# {t}"]
            continue
        if cls in ("T", "C") and re.match(r"(РАЗДЕЛ|ГЛАВА|КОНСТИТУЦИЯ)", t) or (cls == "T" and t.isupper()):
            if t.startswith("РАЗДЕЛ ВТОРОЙ"):
                flush()
                cur, label, lines = "razdel-2", "Раздел второй. Заключительные и переходные положения", [f"# {t}"]
                continue
            if cur == "razdel-2":
                lines.append(t)
            else:
                heads.append(t)
            continue
        if cls == "S" and not lines and cur == "preambula":
            heads.append(t)
            continue
        lines.append(t)
    flush()
    units["struktura"] = {"label": "Заголовки разделов и глав", "kind": "other", "text": "\n".join(heads) + "\n"}
    return units


def law_key(card: dict) -> tuple[str, dict]:
    ad = (card.get("adoptions") or [{}])
    ad = ad[0] if isinstance(ad, list) and ad else {}
    passing = card["docpassing"].replace("\xa0", " ")
    num = ad.get("onumber") or ""
    d = ad.get("odate") or ""
    y = d[-4:]
    if passing.startswith("Указ"):
        pre = "ukaz"
    elif "поправке" in passing:
        pre = "popravka"
    elif passing.startswith("Постановление Конституционного"):
        pre = "ks"
    else:
        pre = "zakon"
    n = num
    for k, v in TR.items():
        n = n.replace(k, v)
    n = re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")
    key = f"{pre}-{y}-{n}" if n else f"{pre}-{y}-doc{card['docid']}"
    pubs = card.get("publications") or []
    pub = None
    for p in pubs if isinstance(pubs, list) else []:
        m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", p)
        if m:
            c = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            pub = c if pub is None or c < pub else pub
    en = f"{y}-{d[3:5]}-{d[:2]}" if len(d) == 10 else None
    return key, {"label": passing, "title": card.get("docname") or passing, "kind": "court" if pre == "ks" else (
        "decree" if pre == "ukaz" else "law"), "enacted": en, "published": pub,
        "url": card.get("docimagepath") or "http://pravo.gov.ru/", "temporary_until": None, "restores": None,
        "note": None}


def build_act(slug: str, short: str, title: str, first_law: str | None, laws: dict) -> dict:
    h = fetch.resolve(slug)
    reds = sorted(load(fetch.redactions_url(h))["redactions"], key=lambda r: (r["reddate"], r["redid"]))
    versions, prev, prev_from = [], None, None
    for r in reds:
        frm = f"{r['reddate'][:4]}-{r['reddate'][4:6]}-{r['reddate'][6:]}"
        u = units_of(r["redid"])
        url = fetch.redtext_url(r["redid"])
        import hashlib
        v = {"from": frm, "source_url": url, "sha256": hashlib.sha256(fetch.path_for(url).read_bytes()).hexdigest(),
             "units": u, "credits": {}}
        if prev is not None:
            lk = None
            if r["reddocrefid"]:
                lk, meta = law_key(load(fetch.card_url(r["reddocrefid"])))
                laws.setdefault(lk, meta)
            changed = sorted(k for k in set(u) | set(prev) if u.get(k, {}).get("text") != prev.get(k, {}).get("text"))
            if lk:
                v["credits"] = {k: [lk] for k in changed}
            if frm == prev_from:
                v["same_day"] = True
            v["note"] = f"Редакция портала: {r['redcaption'].strip()}"
        versions.append(v)
        prev, prev_from = u, frm
    return {"slug": slug, "short": short, "title": title, "url": "http://pravo.gov.ru/", "first_law": first_law,
            "earlier_laws": [], "versions": versions}


def main():
    laws = {"referendum-1993": {"label": "Всенародное голосование 12.12.1993", "title": "Конституция Российской Федерации, принята всенародным голосованием 12 декабря 1993 г.",
                                "kind": "referendum", "enacted": "1993-12-12", "published": "1993-12-25",
                                "url": "http://pravo.gov.ru/", "temporary_until": None, "restores": None, "note": None}}
    acts = [build_act("konstitutsiya", "Конституция РФ", "Конституция Российской Федерации", "referendum-1993", laws)]
    corpus = {
        "country": {"code": "RU", "name": "Russia", "slug": "russia", "lang": "ru", "tz": "Europe/Moscow",
                    "future_branch": "budushchee",
                    "publisher": {"name": "Официальный интернет-портал правовой информации (pravo.gov.ru)", "email": "ips@pravo.invalid"},
                    "default_in_force_rule": {"text": "Federal Law 5-FZ of 14.06.1994, art. 6: federal laws enter into force throughout the Russian Federation 10 days after official publication unless they set another date; here every edition uses the portal's own edition date.",
                                              "source": "http://pravo.gov.ru/"},
                    "licence_note": "Тексты: Официальный интернет-портал правовой информации (pravo.gov.ru), ИПС «Законодательство России». Official texts of laws are not objects of copyright (Civil Code art. 1259(6))."},
        "sources": [{"name": "Официальный интернет-портал правовой информации, ИПС «Законодательство России» (actual.pravo.gov.ru API)",
                     "url": "http://actual.pravo.gov.ru/", "retrieved": "2026-10-29",
                     "requests": sum(1 for _ in (fetch.LOG).open(encoding="utf-8")),
                     "licence": "Official texts are not copyright objects (ГК РФ ст. 1259 п. 6)",
                     "notes": "redactions/?t={hash,ttl:3} lists every edition; redtext?t=<redid>&ttl=3 gives its text; card/?t={docid} names the amending act."}],
        "laws": dict(sorted(laws.items())),
        "acts": acts,
        "applies": [],
        "decisions": [
            "Each version's date is the portal's own edition date (reddate, 'на DD.MM.YYYY'), taken as the in-force date of that edition.",
            "Every unit that differs from the previous edition is credited to the single act the portal names for that edition (reddocrefid, resolved with card/).",
            "Editorial notes ('(В редакции ...)', class P paragraphs) are kept out of the provision text; superscripts are written as Unicode superscript digits.",
            "Section and chapter headings are collected in the unit 'struktura'; Section Two (final and transitional provisions) is one unit 'razdel-2'.",
            "Same-day editions (2008-12-30, 2022-10-05) are kept as separate same_day versions in the portal's order.",
        ],
        "ai_use": ["none: no model wrote or transformed any text; Claude Code (claude-opus-5-5) wrote fetch.py and parse.py."],
    }
    tmp = HERE / "corpus.json.tmp"
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, HERE / "corpus.json")
    for a in acts:
        print(a["slug"], len(a["versions"]), "versions", len(a["versions"][-1]["units"]), "units")


if __name__ == "__main__":
    main()
