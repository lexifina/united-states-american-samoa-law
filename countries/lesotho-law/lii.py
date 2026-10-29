"""Lesotho's extension of the shared Peachjam adapter: staged commencement.

peachjam.parse dates an act's first version by the single "Commenced on D" its page states. When the page instead says
"There are multiple commencements" and prints a commencements table (Provisions | commenced on D by <notice>), the
adapter keeps the Gazette publication date for the whole text and reports the act under `staged_commencement`
(see scripts/africa-law/ISSUES-lesotho.md). This module rebuilds such an act's start from that table, reading only
the cached first expression page:

- the first version is dated by the earliest commencement and holds only the provisions that commenced that day
  (plus the long title, preamble and any schedule whose own heading ties it to a provision that commenced that day);
- each later commencement is its own version, adding the provisions it brought into force, credited
  to the commencement notice alone (a law with a `note`: it brings the act's words into force and writes none);
- the act's later versions follow unchanged.

The shared adapter could adopt `commencements()` and `stage()` as they are.
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import peachjam


def commencements(b: bytes) -> list[dict]:
    """Rows of a Peachjam commencements table: [{'provisions': str, 'sections': set[int], 'date', 'by', 'by_label'}]."""
    t = b.decode("utf-8", "replace")
    m = re.search(r'<table class="commencements-table">(.*?)</table>', t, re.S)
    if not m:
        return []
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", m.group(1), re.S):
        tds = re.findall(r"<td>(.*?)</td>", tr, re.S)
        if len(tds) != 2:
            continue
        prov = peachjam.norm(html.unescape(re.sub(r"<[^>]+>", " ", tds[0])))
        status = peachjam.norm(html.unescape(re.sub(r"<[^>]+>", " ", tds[1])))
        d = re.search(r"commenced on (\d{1,2} \w+ \d{4})", status)
        a = re.search(r'<a href="([^"]+)">([^<]+)</a>', tds[1])
        secs: set[int] = set()
        for lo, hi in re.findall(r"section (\d+)(?:[–-](\d+))?", prov):
            secs.update(range(int(lo), int(hi or lo) + 1))
        rows.append({"provisions": prov, "sections": secs, "date": peachjam.parse_date(d.group(1)) if d else None,
                     "by": a.group(1) if a else None, "by_label": a.group(2).strip() if a else None})
    return rows


def _sec(key: str) -> int | None:
    m = re.match(r"sec-(\d+)", key)
    return int(m.group(1)) if m else None


def stage(folder: Path, corpus: dict, report: dict) -> None:
    folder = Path(folder)
    cfg = peachjam.load_config(folder)
    pins = __import__("json").loads((folder / "sources.json").read_text(encoding="utf-8"))
    cache = peachjam.Cache(folder, offline=True)
    lii = cfg["lii"]["name"]
    for act in corpus["acts"]:
        if act["slug"] not in report.get("staged_commencement", []):
            continue
        conf = next(a for a in cfg["acts"] if a["slug"] == act["slug"])
        ex = pins["acts"][conf["work"]]["expressions"]
        first_day = min(ex)
        b = cache.get(ex[first_day]["url"])
        rows = [r for r in commencements(b) if r["date"] and r["sections"]]
        if not rows:
            continue
        titles = {href: txt for item in peachjam.page_info(b)["timeline"] for e in item["events"]
                  for href, txt in e["links"]}
        rows.sort(key=lambda r: r["date"])
        v0 = act["versions"][0]
        units = v0["units"]
        all_secs = {_sec(k) for k in units if _sec(k) is not None}
        listed = set().union(*(r["sections"] for r in rows))
        if listed != all_secs or sum(len(r["sections"]) for r in rows) != len(listed):
            report.setdefault("staged_commencement_unresolved", []).append(act["slug"])
            continue
        nxt = act["versions"][1]["from"] if len(act["versions"]) > 1 else "9999-12-31"
        if rows[-1]["date"] >= nxt:
            report.setdefault("staged_commencement_unresolved", []).append(act["slug"])
            continue

        def tied(key: str) -> int | None:
            """A schedule's heading names the section it belongs to: '# Schedule 1 (Section 2)'."""
            m = re.match(r"# Schedule \S+ \((?:[Ss]ection) (\d+)", units[key]["text"])
            return int(m.group(1)) if m else None

        first = rows[0]
        later_keys: dict[int, list[str]] = {}
        for i, r in enumerate(rows[1:], 1):
            later_keys[i] = sorted(k for k in units if (_sec(k) in r["sections"])
                                   or (_sec(k) is None and tied(k) in r["sections"]))
        moved = {k for ks in later_keys.values() for k in ks}
        untied = sorted(k for k in units if _sec(k) is None and k.startswith("sch") and tied(k) is None)
        if untied:
            report.setdefault("staged_commencement_unresolved", []).append(act["slug"])
            continue
        new_versions = [{**v0, "from": first["date"],
                         "units": {k: u for k, u in units.items() if k not in moved},
                         "note": (f"The {lii} expression of {first_day} (the act as published in the Gazette), in "
                                  f"force from {first['date']} except the provisions that commenced later: "
                                  f"{first['provisions']} commenced on {first['date']} by {first['by_label']}.")}]
        for i, r in enumerate(rows[1:], 1):
            key = peachjam.law_key(r["by"])
            corpus["laws"][key] = {
                "label": r["by_label"], "title": titles.get(r["by"], r["by_label"]), "kind": "decree",
                "enacted": None, "published": None, "url": f"https://{cfg['lii']['hosts'][0]}{r['by']}",
                "temporary_until": None, "restores": None,
                "note": (f"Commencement notice: it brings {r['provisions']} of the {act['title']} into force on "
                         f"{r['date']}. It writes no words; the words are the Act's as published.")}
            new_versions.append({
                "from": r["date"], "source_url": v0["source_url"], "sha256": v0["sha256"],
                "changes": {k: units[k] for k in later_keys[i]},
                "credits": {k: [key] for k in later_keys[i]},
                "note": f"{r['provisions']} commenced on {r['date']} by {r['by_label']} ({lii}'s commencements table).",
            })
        rest = act["versions"][1:]
        for v in rest:  # the adapter's note listing the events since the old first version named the commencement
            if re.fullmatch(r"Commences\. \(\d{4}-\d{2}-\d{2}\)", v.get("note") or ""):
                del v["note"]
        act["versions"] = new_versions + rest
        corpus["decisions"] = [d for d in corpus["decisions"]
                               if not d.startswith(f"{conf['short']}: {lii} gives no single commencement date")]
        corpus["decisions"].append(
            f"{conf['short']}: {lii}'s page says \"There are multiple commencements\" and prints a commencements "
            f"table; the act's start is built from it (lii.py): "
            + "; ".join(f"{r['provisions']} from {r['date']} ({r['by_label']})" for r in rows)
            + f". The long title, the preamble and the schedules whose headings tie them to a section are dated with "
              f"that section; the text of every provision is the {first_day} expression's, the Act as published.")
        report["staged_commencement"] = [s for s in report["staged_commencement"] if s != act["slug"]]
        report.setdefault("staged_commencement_built", []).append(act["slug"])


def unapplied(folder: Path, corpus: dict) -> None:
    """Name, in decisions, every dated amendment the act's latest archived page lists after its own version date: the
    text from then on lacks it (LesLII marks them "amendment not yet applied")."""
    import json  # noqa: PLC0415
    folder = Path(folder)
    cfg = peachjam.load_config(folder)
    pins = json.loads((folder / "sources.json").read_text(encoding="utf-8"))
    cache = peachjam.Cache(folder, offline=True)
    for conf in cfg["acts"]:
        ex = pins["acts"].get(conf["work"], {}).get("expressions")
        if not ex:
            continue
        last = max(ex)
        info = peachjam.page_info(cache.get(ex[last]["url"]))
        later = [(t["date"], e["text"]) for t in info["timeline"] if t["date"] > last for e in t["events"]
                 if e["kind"] == "amended"]
        if later:
            corpus["decisions"].append(
                f"{conf['short']}: not applied, because no archived copy gives the consolidated text after them: "
                + "; ".join(f"{txt} (dated {d} by {cfg['lii']['name']})" for d, txt in sorted(later))
                + f". {cfg['lii']['name']}'s own latest version ({last}) does not apply them either; so from the "
                  f"earliest of those dates the text here is not the law in force.")


def fix_readme(folder: Path) -> None:
    """Two sentences of the adapter's generic README do not hold for Lesotho; replace them with what was done."""
    p = Path(folder) / "repo" / "README.md"
    s = p.read_text(encoding="utf-8")
    old_check = re.search(r"- \*\*Against LesLII today:\*\*[^\n]*\n", s)
    if old_check:
        s = s.replace(old_check.group(0),
                      "- **Against LesLII:** LesLII's own pages are never read, so the last version of each act is the "
                      "latest expression archived. For the two acts on LesLII's current site, that expression's own "
                      "History tab (archived June 2023) names every later amendment; any it lists after the last "
                      "version is not applied, and is named under \"Lesotho: what is missing\" below.\n")
    s = s.replace("LesLII's document pages answer automated clients with a bot challenge, so `tools/fetch.py` reads "
                  "each expression page from its latest Internet Archive capture",
                  "LesLII's terms prohibit scraping its website, so no LesLII page is fetched: `tools/fetch.py` reads "
                  "each expression page from an archived copy, the latest Internet Archive capture")
    s = s.replace("its listing page names the current version | The text and dates of every version |",
                  "its earlier website (to 2023) printed the Constitution of 1993 | The text and dates of every "
                  "version |")
    p.write_text(s, encoding="utf-8", newline="\n")
