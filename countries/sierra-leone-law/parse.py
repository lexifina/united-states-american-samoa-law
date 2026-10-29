"""Build Sierra Leone's corpus from the cache only.

    python -X utf8 scripts/sierra-leone-law/parse.py

Two parts, each written atomically to corpus.d/ (the shared builder merges them):
- 10-constitution.json: the Constitution of Sierra Leone, 1991, replayed from Parliament's PDFs (constitution.py).
  Not published to main: two 2022 amending Acts have no usable text (see its decisions).
- 20-sierralii.json: acts from SierraLII through the shared Peachjam adapter (peachjam.py, acts.json, sources.json).
  It carries the country block.
Also writes verification.json and repo/README.md, repo/LICENSE, repo/jurisdiction.json. Deterministic.
"""
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHARED = HERE.parent / "africa-law" / "peachjam.py"
if SHARED.exists() and (not (HERE / "peachjam.py").exists()
                        or SHARED.read_bytes() != (HERE / "peachjam.py").read_bytes()):
    shutil.copyfile(SHARED, HERE / "peachjam.py")
sys.path.insert(0, str(HERE))
import constitution  # noqa: E402
import peachjam  # noqa: E402


def write_part(name: str, part: dict) -> None:
    d = HERE / "corpus.d"
    d.mkdir(exist_ok=True)
    tmp = d / (name + ".tmp")
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, d / name)


def who(laws: dict, act: dict, i: int, pub: str) -> str:
    v = act["versions"][i]
    if i == 0:
        return laws[act["first_law"]]["label"] + " (as enacted)" if act.get("first_law") else f"{pub}: oldest version"
    return ", ".join(sorted({laws[x]["label"] for ls in v.get("credits", {}).values() for x in ls})) or "no change"


def readme(c: dict, laws: dict, acts: list, missing: list[str]) -> str:
    cc = c["country"]
    L = [f"# {cc['name']}: law history in git", "",
         f"The law of {cc['name']} as a git history: one file per provision, one commit per law on the day it took "
         "effect, and the law that made each change as the commit's author. `git blame` names the law behind every "
         "paragraph; `git log` lists every change to a provision; `tools/on.py` gives the text in force on any day.", "",
         "It follows the shared design of [lexifina/global-law](https://github.com/lexifina/global-law), which places "
         "it at `sl/`.", "", "**What is in it now**", "", "| Folder | Act | Versions | History | Source |",
         "| --- | --- | ---: | --- | --- |"]
    for a in acts:
        vs = a["versions"]
        src = "Parliament of Sierra Leone PDFs, replayed" if a["slug"] == "constitution" else "SierraLII"
        L.append(f"| `{a['slug']}/` | [{a['title']}]({a['url']}) | {len(vs)} | {vs[0]['from']} to {vs[-1]['from']} | {src} |")
    for a in acts:
        L += ["", f"**{a['title']}**", "", "| In force | Author |", "| --- | --- |"]
        for i, v in enumerate(a["versions"]):
            L.append(f"| {v['from']} | {who(laws, a, i, cc['publisher']['name'])} |")
    L += ["", "## Sources", "",
          "- **The Constitution** is not on SierraLII, and no consolidated, dated text of it is published anywhere we "
          "could read. Its history is rebuilt from the Parliament of Sierra Leone's own PDFs (parliament.gov.sl, which "
          "publishes the Constitution as enacted and the amending Acts with a text layer): each amending Act's "
          "instructions are applied by code to the text before it, and the new wording is read from the Act's own PDF. "
          "Parliament's site serves an invalid TLS certificate, so each PDF is read from its Internet Archive copy, "
          "pinned by capture time and sha256. The 1991 text and the 2001 Act are Sierra Leone Web (sierra-leone.org) "
          "transcriptions that Parliament publishes.",
          "- **Other acts** are SierraLII's (Sierra Leone Legal Information Institute, on the Laws.Africa Peachjam "
          "platform). SierraLII publishes about 80 acts, each as one expression, the act as published; it has no "
          "point-in-time consolidations. Its document pages answer automated clients with a bot challenge, so each page "
          "is read from an archived copy (Common Crawl or the Internet Archive), pinned in `tools/sources.json`.",
          "", "## What is missing", ""]
    L += [f"- {m}" for m in missing]
    L += ["", "## Dates", "",
          f"- Each commit is dated at **noon, {cc['tz']}, on the day the change took effect**; the day is also in the "
          "`In-force:` trailer, which the tools read.",
          "- An Act of Parliament comes into operation on its publication in the Gazette, or on the date it prescribes "
          "(Constitution, s. 106(3)). Each Constitution version is dated by the amending Act's stated commencement or, "
          "where the Act leaves it blank, its Gazette date; the Constitution itself commenced on 1 October 1991 "
          "(s. 192). SierraLII acts are dated by SierraLII's expression date or its stated commencement.",
          "- `--before=\"YYYY-MM-DD\"` alone uses your clock's time of day; use `T23:59:59Z`, or the tool.", "",
          "## A lawyer's questions as git commands", "", "| Question | Command |", "| --- | --- |",
          "| What did section 38 say on 2010-01-01? | `python tools/on.py 2010-01-01 constitution sec-038` |",
          "| Which law wrote each line? | `git blame constitution/sec-079.md` |",
          "| Every change, word by word | `git log -p --word-diff constitution/sec-038.md` |",
          "| Every law in the record, in order | `git log --reverse --format=\"%ad %an\" --date=short main` |",
          "| Everything one law changed | `git show law/<key>` |", "",
          "## How it is checked", "",
          "- Every version is read back from git on the day it took effect and on the day before "
          "(`tools/check_repo.py`); both must match `corpus.json`. Results are in `REPRODUCE.md`.",
          "- Constitution: the 1991 parse keeps every character of the source's body text (page heads, the "
          "Arrangement of Sections, and chapter and part headings aside); each replayed amendment changes exactly the "
          "provisions its Act names.",
          "- SierraLII acts: the Internet Archive's index of every archived SierraLII page holds exactly one expression "
          "of each act (SierraLII's listing itself is not read: only archived copies are), and that expression is "
          "the version here.", "",
          "## Licence", "",
          f"- SierraLII content: {cc['licence_note']} The repository is private: CC BY-NC 4.0 allows only "
          "non-commercial use.",
          "- Acts of Parliament from parliament.gov.sl: no licence is stated there; they are public legislation.",
          "- Archived copies come from the Internet Archive and Common Crawl (https://commoncrawl.org/terms-of-use).",
          "", "## What \"author\" means", "",
          "The author of a commit is the law that made the change, with an e-mail address that cannot exist, so "
          "`git blame` and `git log --author` name laws. The committer is always Lexifina.", "",
          "This repository is not legal advice.", ""]
    return "\n".join(L)


def main() -> None:
    cpart = constitution.build()
    write_part("10-constitution.json", cpart)
    report = {}
    acts = list(cpart["acts"])
    laws = dict(cpart["laws"])
    cfg = peachjam.load_config(HERE)
    if (HERE / "sources.json").exists():
        corpus, report = peachjam.parse(HERE)
        write_part("20-sierralii.json", corpus)
        acts += corpus["acts"]
        laws.update(corpus["laws"])
        country = corpus
    else:
        country = {"country": cfg["country"]}
        write_part("20-sierralii.json", {"country": cfg["country"], "sources": [], "laws": {}, "acts": [],
                                         "applies": [], "decisions": cfg["decisions"], "ai_use": cfg["ai_use"]})
    missing = [
        "Constitution: the Constitution of Sierra Leone (Amendment) Act, 2022 (Act No. 22 of 2022, Gazette of "
        "22 December 2022; Political Parties Regulation Commission, ss. 34 and 35): its only copy is a scan whose OCR "
        "layer is unusable, and no OCR is done here.",
        "Constitution: a Constitution of Sierra Leone (Amendment) Act, 2022 amending s. 32(2) and (8) (Electoral "
        "Commission): its only copy is an unnumbered, undated print, so no in-force date can be sourced.",
        "Constitution: the Constitution of Sierra Leone Amendment Decree, 1997 and the Constitution Reinstatement "
        "(1996): scans only. The suspension of the Constitution under military rule is not recorded.",
        "Constitution: because of these, its last version (2016) is not today's text; the Constitution is on the "
        "`preview` branch only.",
        "SierraLII acts: one version each (the act as published); later amendments are not on SierraLII.",
    ]
    (HERE / "verification.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    repo = HERE / "repo"
    repo.mkdir(exist_ok=True)
    lic = peachjam.licence(HERE).replace("point-in-time versions of each act, read", "acts as published, read")
    lic += ("\nThe Constitution of Sierra Leone, 1991 and its amending Acts (folder constitution/) come from the\n"
            "Parliament of Sierra Leone, https://www.parliament.gov.sl, read from Internet Archive copies of its PDFs.\n"
            "They are Acts of Parliament; parliament.gov.sl states no licence. The 1991 text and the 2001 amending Act\n"
            "are Sierra Leone Web (https://www.sierra-leone.org) transcriptions published by Parliament. Lexifina\n"
            "applied each amending Act's instructions to the text before it; the wording of each Act was not changed.\n")
    files = {"README.md": readme(country, laws, acts, missing), "LICENSE": lic}
    j = repo / "jurisdiction.json"
    if j.exists():
        jd = json.loads(j.read_text(encoding="utf-8"))
        jd["build"] = "built: " + "; ".join(f"{a['title']} ({len(a['versions'])} version"
                                           f"{'s' if len(a['versions']) != 1 else ''}, {a['versions'][0]['from']} to "
                                           f"{a['versions'][-1]['from']})" for a in acts)
        files["jurisdiction.json"] = json.dumps(jd, indent=2, ensure_ascii=False) + "\n"
    for name, text in files.items():
        p = repo / name
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            p.write_text(text, encoding="utf-8", newline="\n")
    for a in acts:
        print(a["slug"], len(a["versions"]), [v["from"] for v in a["versions"]])


if __name__ == "__main__":
    main()
