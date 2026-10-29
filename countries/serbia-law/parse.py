"""Serbia: parse cached PIS (Pravno-informacioni sistem) register HTML into corpus.json.

First cut (2026-10-29, wind-down): the Constitution only, two versions (2006 text, 2022 amendments I-XXIX).
Reads only .cache/ (files named by sha256 of the URL). Text is Cyrillic, as the register gives it.
"""
import hashlib, html, json, os, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
VIEW = "https://reg.pravno-informacioni-sistem.rs/api/viewAct/f0d72ce3-dad2-4395-a2c1-c3d3226f22c2?lawActId={}"


def load(url):
    b = (CACHE / hashlib.sha256(url.encode()).hexdigest()).read_bytes()
    return b, hashlib.sha256(b).hexdigest()


def paras(raw):
    t = raw.decode("utf-8-sig")
    t = re.sub(r"<(style|script)\b.*?</\1>", "", t, flags=re.S | re.I)
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"<(/p|br|/h\d|/div|/li|/tr)\b[^>]*>", "\n", t, flags=re.I)
    t = html.unescape(re.sub(r"<[^>]+>", "", t)).replace(" ", " ")
    out = []
    for line in t.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        line = line.replace("“", "”")
        if line:
            out.append(line)
    return out


def units(lines):
    u, credits = {}, {}
    idx = [i for i, l in enumerate(lines) if re.fullmatch(r"Члан \d+\.", l)]
    first = idx[0]
    start = next(i for i, l in enumerate(lines) if l.startswith("Полазећи од државне традиције"))
    pre = lines[start:lines.index("грађани Србије доносе", start) + 1]
    u["preambula"] = {"label": "Преамбула", "kind": "preamble", "text": "\n".join(pre) + "\n"}
    for n, i in enumerate(idx):
        end = idx[n + 1] if n + 1 < len(idx) else len(lines)
        body = lines[i + 1:end]
        while body and not re.search(r"[.:;,]$", body[-1]) and not body[-1].startswith("*"):
            body.pop()  # captions and part headings that belong to the next article
        num = int(re.match(r"Члан (\d+)", lines[i]).group(1))
        key = f"clan-{num:03d}"
        notes = [b for b in body if b.startswith("*Службени гласник")]
        body = [b for b in body if not b.startswith("*Службени гласник")]
        if notes:
            credits[key] = notes
        u[key] = {"label": f"Члан {num}.", "kind": "art", "text": "\n".join(body) + "\n"}
    return u, credits


def main():
    v = []
    for lid, frm in [(408046, "2006-11-08"), (433539, "2022-02-09")]:
        b, sha = load(VIEW.format(lid))
        u, notes = units(paras(b))
        v.append((frm, VIEW.format(lid), sha, u, notes))
    versions = []
    prev = None
    for frm, url, sha, u, notes in v:
        ver = {"from": frm, "source_url": url, "sha256": sha, "units": u}
        if prev is not None:
            changed = sorted(k for k in set(u) | set(prev) if u.get(k) != prev.get(k))
            ver["credits"] = {k: ["amandmani-2021"] for k in changed}
        versions.append(ver)
        prev = u
    corpus = {
        "country": {"code": "RS", "name": "Serbia", "slug": "serbia", "lang": "sr", "tz": "Europe/Belgrade",
                    "future_branch": "buduci",
                    "publisher": {"name": "Службени гласник (Правно-информациони систем РС)", "email": "pis@pravno-informacioni-sistem.invalid"},
                    "default_in_force_rule": {"text": "Устав чл. 196: закон ступа на снагу најраније осмог дана од дана објављивања; Устав и акт о промени Устава ступају на снагу проглашењем (чл. 203)",
                                              "source": "https://pravno-informacioni-sistem.rs/eli/rep/sgrs/skupstina/ustav/2006/98/1/reg"},
                    "licence_note": "Text from the Pravno-informacioni sistem Republike Srbije (Službeni glasnik), the free official register."},
        "sources": [{"name": "Pravno-informacioni sistem RS, register API (reg.pravno-informacioni-sistem.rs/api)",
                     "url": "https://pravno-informacioni-sistem.rs", "retrieved": "2026-10-29", "requests": 2,
                     "licence": "Free public official register; robots.txt allows /eli/rep/*", "notes": "viewAct HTML per version id; dates from GetEliMetadata and GetLawActTimeline"}],
        "laws": {
            "ustav-2006": {"label": "Устав РС (СГ РС 98/2006)", "title": "Устав Републике Србије", "kind": "law",
                           "enacted": "2006-09-30", "published": "2006-11-10",
                           "url": "https://pravno-informacioni-sistem.rs/eli/rep/sgrs/skupstina/ustav/2006/98/1/reg",
                           "temporary_until": None, "restores": None, "note": None},
            "amandmani-2021": {"label": "Амандмани I-XXIX (СГ РС 115/2021, 16/2022)",
                               "title": "Акт о промени Устава Републике Србије (Амандмани I-XXIX)", "kind": "law",
                               "enacted": "2021-11-30", "published": "2022-02-09",
                               "url": "https://pravno-informacioni-sistem.rs/eli/rep/sgrs/skupstina/ustav/2006/98/1/reg",
                               "temporary_until": None, "restores": None, "note": None}},
        "acts": [{"slug": "ustav", "short": "Устав", "title": "Устав Републике Србије",
                  "url": "https://pravno-informacioni-sistem.rs/eli/rep/sgrs/skupstina/ustav/2006/98/1/reg",
                  "first_law": "ustav-2006", "earlier_laws": [], "versions": versions}],
        "applies": [],
        "decisions": [
            "Version dates come from the register's ELI metadata: 2006 text in force 2006-11-08 (proclamation, Art. 206); amended text version_date 2022-02-09 (Act on amendment proclaimed, SG 16/2022).",
            "Changes in 2022 are credited to Amendments I-XXIX; the register's per-article notes name SG 115/2021 (Amandman N).",
            "Article captions and part headings are dropped from article files in this first cut (unverified heuristic: trailing lines without final punctuation).",
        ],
        "ai_use": ["Claude Code (claude-opus-5-5) wrote fetch/parse code; no model wrote or altered legal text."],
    }
    tmp = HERE / "corpus.json.tmp"
    tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, HERE / "corpus.json")
    for ver in versions:
        print(ver["from"], len(ver["units"]), len(ver.get("credits", {})))


if __name__ == "__main__":
    main()
