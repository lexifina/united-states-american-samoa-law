"""Reading-only comparison of the Código de Comercio part with the Lexis consolidation of 10-XII-2020
(derechoecuador.com, Internet Archive capture). Compares the version in force on 2020-12-10 article by article after
normalising spacing, quotes and dashes, and drops Lexis's 'Nota:' lines. Writes codes/reconcile_comercio.json.

    python -X utf8 codes/reconcile_comercio.py [part.json]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / ".cache"
LEXIS = ("https://web.archive.org/web/20240527012147id_/"
         "https://derechoecuador.com/uploads/content/2021/01/file_1609955536_1609955541.pdf")


def norm(s: str) -> str:
    s = s.replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def lexis_articles() -> dict[str, str]:
    import fitz
    d = fitz.open(CACHE / hashlib.sha256(LEXIS.encode()).hexdigest())
    lines = []
    for page in d:
        for ln in page.get_text().split("\n"):
            if re.match(r"\s*(CÓDIGO DE COMERCIO - Página \d+|LEXIS FINDER - www\.lexis\.com\.ec)", ln):
                continue
            lines.append(ln)
    t = "\n".join(lines)
    t = re.sub(r"Nota:.*?(?=\n\s*\n|\nArt\. |\Z)", " ", t, flags=re.S)
    out = {}
    parts = re.split(r"\n\s*Art\. (\d+(?:\.\d+)?)\.-", t)
    for i in range(1, len(parts) - 1, 2):
        out[parts[i]] = parts[i + 1]
    return out


def main(argv: list[str]) -> None:
    part = Path(argv[0]) if argv else HERE.parent / "corpus.d" / "70-comercio.json"
    act = json.loads(part.read_text(encoding="utf-8"))["acts"][0]
    units = dict(act["versions"][0]["units"])
    for v in act["versions"][1:]:
        if v["from"] > "2020-12-10":
            break
        for k, u in (v.get("changes") or {}).items():
            if u is None:
                units.pop(k, None)
            else:
                units[k] = u
    lx = lexis_articles()
    same, diff, missing = [], {}, []
    for k, u in units.items():
        m = re.match(r"art-(\d{4})$", k)
        if not m:
            continue
        n = str(int(m.group(1)))
        if n not in lx:
            missing.append(n)
            continue
        ours = norm(re.sub(r"^Art[íi]culo \d+\.? ?-\s*", "", u["text"]))
        theirs = norm(lx[n])
        # Lexis runs the next heading lines into the article; compare on our length
        if theirs.startswith(ours) or ours == theirs:
            same.append(n)
        else:
            j = next((i for i, (a, b) in enumerate(zip(ours, theirs)) if a != b), min(len(ours), len(theirs)))
            diff[n] = {"ours": ours[max(0, j - 60):j + 80], "lexis": theirs[max(0, j - 60):j + 80]}
    extra = sorted(set(lx) - {str(int(k[4:8])) for k in units if re.match(r"art-\d{4}$", k)}, key=float)
    out = {"same": len(same), "differ": diff, "missing_in_lexis": missing, "only_in_lexis": extra}
    (HERE / "reconcile_comercio.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"same {len(same)}, differ {len(diff)}, missing in Lexis {len(missing)}, only in Lexis {extra}")


if __name__ == "__main__":
    main(sys.argv[1:])
