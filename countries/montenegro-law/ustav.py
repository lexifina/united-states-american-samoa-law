"""Constitution of Montenegro (2007) and Amendments I-XXI, from the Official Gazette's act PDFs (cache only).

The 2007 text (Službeni list CG 1/2007, act 297951) is published in Cyrillic; the amendments (38/2013, act
307536; 126/2026, act 397527) in Latin. Each amendment replaces, supplements or deletes the provisions its last
paragraph names ("Ovim amandmanom zamjenjuje se ..."). There is no official consolidated text: officially the
Constitution is the 2007 text plus the amendments, each "sastavni dio Ustava". The words of every version are the
gazette's words in the gazette's own script; nothing is transliterated.

Structure of an article: number, caption (the bold heading above "Član N", if any), and paragraphs (stavovi).
A numbered point ("1) ...") belongs to the paragraph before it, so "stav 3" counts paragraphs, not points.
"""
import re
import gazette

USTAV, AM_2013, AM_2026 = 297951, 307536, 397527
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV", "XVI",
         "XVII", "XVIII", "XIX", "XX", "XXI"]
ORD = {"ПРВИ": 1, "ДРУГИ": 2, "ТРЕЋИ": 3, "ЧЕТВРТИ": 4, "ПЕТИ": 5, "ШЕСТИ": 6, "СЕДМИ": 7, "ОСМИ": 8}
ITEM = re.compile(r"^\d+\)")


def norm(s):
    s = s.replace(" ", " ").replace("­", "")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(\d+\))\s+", r"\1 ", s)
    return s


def join(a, b):
    """Join a continuation line; a line ending in a hyphen after a letter ('video-') keeps it and takes no space."""
    return a + b if re.search(r"\w-$", a) else a + " " + b


def unspace(s):
    """Letter-spaced headings ('5. С У Д', 'О Д Л У К У') -> one word: publisher typesetting."""
    return re.sub(r"(?<!\S)(\w(?: \w){2,})(?!\S)", lambda m: m.group(1).replace(" ", ""), s)


def paragraphs(lines, indent, cont):
    """Join PDF lines into paragraphs: a line at x=indent starts one, a line at x=cont continues it."""
    out = []
    for (_pg, x, t, _b, _sz) in lines:
        t = norm(t)
        if not t:
            continue
        if abs(x - cont) < 2 and out:
            out[-1] = join(out[-1], t)
        else:
            out.append(t)
    return out


def group_stavs(paras):
    """Paragraphs -> stavovi: a numbered point joins the paragraph before it."""
    stavs = []
    for p in paras:
        if ITEM.match(p) and stavs:
            stavs[-1].append(p)
        else:
            stavs.append([p])
    return stavs


# ------------------------------------------------------------------ the 2007 text

def read_2007():
    """-> (preamble paragraphs, ordered list of elements). Element: ('part', n, [lines]) | ('chapter', part, n,
    title) | ('art', n, caption, stavs)."""
    L = gazette.pdf_lines(USTAV)
    i = next(k for k, l in enumerate(L) if l[2].strip().startswith("Полазећи од"))
    j = next(k for k, l in enumerate(L) if l[3] and norm(l[2]) == "УСТАВ ЦРНЕ ГОРЕ" and k > i)
    pre = paragraphs([l for l in L[i:j]], 121.2, 85.2)
    end = next(k for k, l in enumerate(L) if norm(l[2]).startswith("СУ-СК Број 01-514/21"))
    body = L[j + 1:end]
    elems, part, chap, caption, cur = [], 0, 0, None, None
    k = 0
    while k < len(body):
        pg, x, t, bold, sz = body[k]
        t = norm(t)
        if bold:
            m = re.match(r"^Члан (\d+)$", t)
            if m:
                cur = ["art", int(m.group(1)), caption, []]
                elems.append(cur)
                caption = None
            elif re.match(r"^ДИО (\S+)$", t):
                part, chap = ORD[t.split()[1]], 0
                title = norm(body[k + 1][2])
                elems.append(["part", part, [t, title]])
                cur = None
                k += 1
            elif re.match(r"^\d+\. ", t) and t == t.upper():
                chap = int(t.split(".")[0])
                title = unspace(t)
                if not body[k + 1][3] or body[k + 1][2] != body[k + 1][2].upper():
                    pass
                else:  # a chapter title running onto a second bold capital line
                    nxt = norm(body[k + 1][2])
                    if not re.match(r"^(Члан|ДИО)", nxt):
                        title += " " + nxt
                        k += 1
                elems.append(["chapter", part, chap, title])
                cur = None
            else:
                caption = t if caption is None else caption + " " + t
        else:
            cur[3].append(body[k])
        k += 1
    for e in elems:
        if e[0] == "art":
            e[3] = group_stavs(paragraphs(e[3], 107.8, 85.2))
    return pre, elems


# ------------------------------------------------------------------ the amendments

def read_amendments(act, indent, cont):
    """-> {roman: dict(caption=bold caption or None, paras=[...], instruction=str)} in gazette order."""
    L = gazette.pdf_lines(act)
    out, cur, order = {}, None, []
    for l in L:
        t = norm(l[2])
        m = re.match(r"^AMANDMAN ([IVX]+)$", t)
        if l[3] and m:
            cur = {"caption": None, "lines": []}
            out[m.group(1)] = cur
            order.append(m.group(1))
            continue
        if cur is None:
            continue
        if t.startswith("Broj: 00-13/"):
            cur = None
            continue
        if l[3]:
            cur["caption"] = t if cur["caption"] is None else cur["caption"] + " " + t
        elif re.match(r"^Član \d+$", t):
            continue  # the article number printed above an amendment's text (XX)
        else:
            cur["lines"].append(l)
    for r in order:
        a = out[r]
        paras = paragraphs(a.pop("lines"), indent, cont)
        k = next(n for n, p in enumerate(paras) if p.startswith("Ovim amandmanom"))
        a["instruction"] = " ".join(paras[k:])
        a["paras"] = [p for p in paras[:k] if p != "Stav 3 briše se."]
    return out, order
