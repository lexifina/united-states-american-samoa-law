"""Generic reader for an ordinary law in the Official Gazette's act PDF (cache only).

Layout of the born-digital gazette text: a paragraph's first line is indented, its other lines are not; the
article number ("Član 12") is a centred plain line; the article caption above it is bold; chapters
("I. OSNOVNE ODREDBE") are indented capital lines, sections ("1. Opšte obaveze") bold numbered lines.
"""
import re
from collections import Counter
import gazette
from ustav import norm, group_stavs, join

CHAPTER = re.compile(r"^([IVXL]+)\.\s+([^a-zčćšžđ]+)$")
SECTION = re.compile(r"^(\d+)\.\s+(.+)$")
ARTICLE = re.compile(r"^Član\s+(\d+)\s*([a-z]?)$")


def read(act):
    L = gazette.pdf_lines(act)
    xs = Counter(round(l[1]) for l in L if not l[3])
    (a, _), (b, _) = xs.most_common(2)
    indent, cont = max(a, b), min(a, b)
    start = next(k for k, l in enumerate(L) if not l[3] and (CHAPTER.match(norm(l[2])) or ARTICLE.match(norm(l[2]))))
    end = max(k for k, l in enumerate(L) if norm(l[2]).startswith("Broj:"))
    elems, caption, cur, chap = [], None, None, None
    para = None  # the paragraph being built: [text] inside cur, or a pending chapter heading
    for pg, x, t, bold, sz in L[start:end]:
        t = norm(t)
        if not t:
            continue
        m = ARTICLE.match(t)
        if m and not bold and x > indent + 40:
            cur = ["art", f"{int(m.group(1))}{m.group(2)}", caption, []]
            elems.append(cur)
            caption, para = None, None
            continue
        if bold:
            s = SECTION.match(t)
            if s:
                elems.append(["section", chap, int(s.group(1)), t])
                cur = None
            else:
                caption = t if caption is None else caption + " " + t
            para = None
            continue
        if abs(round(x) - cont) <= 1 and para is not None:
            para[-1] = join(para[-1], t)
            continue
        c = CHAPTER.match(t)
        if c:
            chap = c.group(1)
            para = ["chapter", chap, t]
            elems.append(para)
            cur = None
            continue
        if cur is None:
            raise ValueError(f"text outside an article: {t!r}")
        cur[3].append(t)
        para = cur[3]
    for e in elems:
        if e[0] == "art":
            e[3] = group_stavs(e[3])
    return elems


ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11,
         "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18, "XIX": 19, "XX": 20}


def art_key(num):
    m = re.match(r"^(\d+)([a-z]?)$", num)
    return f"clan-{int(m.group(1)):03d}{m.group(2)}"


def units(elems):
    u = {}
    for e in elems:
        if e[0] == "chapter":
            k = f"poglavlje-{ROMAN[e[1]]:02d}"
            u[k] = {"label": f"Poglavlje {e[1]}", "kind": "heading", "text": e[2] + "\n"}
        elif e[0] == "section":
            k = f"poglavlje-{ROMAN[e[1]]:02d}-odjeljak-{e[2]}"
            assert k not in u, k
            u[k] = {"label": e[3], "kind": "heading", "text": e[3] + "\n"}
        else:
            k = art_key(e[1])
            assert k not in u, k
            lines = [f"# Član {e[1]}"] + ([f"## {e[2]}"] if e[2] else []) + [l for s in e[3] for l in s]
            u[k] = {"label": f"Član {e[1]}", "kind": "art", "text": "\n".join(lines) + "\n"}
    return u
