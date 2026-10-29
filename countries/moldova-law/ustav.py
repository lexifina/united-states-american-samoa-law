"""Moldova: the Constitution (Constituția Republicii Moldova, 29.07.1994) parsed into units.

Two official expressions are read:
- the State Register of Legal Acts in its earlier home, lex.justice.md (Ministry of Justice), as archived by the
  Internet Archive (HTML, one page per act, consolidated, with "[Art.N în redacția ...]" notes);
- the Moldpres edition "Constituția Republicii Moldova. Cu modificări și completări la data de 20 octombrie 2024"
  (Moldpres, the state agency that publishes the Monitorul Oficial; PDF with a text layer, hosted by the Presidency).

Both are reduced to the same unit keys: preambul, titlul-NN[-capitolul-NN[-sectiunea-N]] headings, art-NNN[-N]
articles and tranz-NN (Titlul VII, Articolul I-VIII). Typesetting is normalised the same way for both
(norm()); words, spelling and punctuation are kept.
"""
import html as _html
import re
import subprocess

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def norm(s):
    if re.fullmatch(r"(?:\S ){3,}\S", s.strip()):
        s = s.replace(" ", "")                       # letter-spaced headings: "G U V E R N U L"
    s = s.replace(" ", " ").replace("­", "")
    s = s.translate(str.maketrans("şŞţŢ", "șȘțȚ"))   # cedilla and comma-below forms are one letter
    s = s.replace("‐", "-").replace("‑", "-")
    s = re.sub(r"\s+[-–—]\s+", " – ", s)            # a spaced dash is one dash
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,;.:)])", r"\1", s)
    s = re.sub(r"\(\s+", "(", s)
    return s


def roman(n):
    return ROMAN.index(n) + 1


# ------------------------------------------------------------------ structure from a flat list of lines

ART = re.compile(r"^Arti?colul\s+(\d+)(?:\^(\d+))?(?:\s*[-–]\s*(abrogat|exclus)\.?)?$")
TART = re.compile(r"^Articolul\s+([IVX]+)$")
TITLU = re.compile(r"^Titlul\s+([IVX]+)(?:\^(\d))?$")
CAP = re.compile(r"^Capitolul\s+([IVX]+)(?:\^(\d))?$", re.I)
SECT = re.compile(r"^Secțiunea\s+(?:a\s+)?(\d)(?:-a)?$")


def art_key(n, sup):
    return f"art-{int(n):03d}" + (f"-{sup}" if sup else "")


def build_units(items):
    """items: list of ("head", text) | ("para", text) in reading order. Returns {key: unit}."""
    units = {}
    order = []
    cur = None        # key of the unit being filled
    title = chapter = None
    pending_caption = None  # key of a heading/article whose caption comes next
    cap_open = False        # the last line added was a caption, which may go on on the next line

    def start(key, label, kind, heading):
        nonlocal cur
        assert key not in units, key
        units[key] = {"label": label, "kind": kind, "lines": [heading]}
        order.append(key)
        cur = key

    for kind, text in items:
        structural = any(r.match(text) for r in (ART, TART, TITLU, CAP, SECT))
        if cap_open and not structural and (kind in ("bold", "head") or (kind == "para" and units[cur]["kind"] in ("title", "chapter")
                                             and text.upper() == text and not text.startswith("("))):
            units[cur]["lines"][-1] += " " + text   # a caption set on two lines
            continue
        cap_open = False
        if kind == "bold":
            kind = "head" if (pending_caption and pending_caption == cur) else "para"
        if kind == "head":
            m = ART.match(text)
            if m:
                n, sup, gone = m.groups()
                key = art_key(n, sup)
                lab = f"Art. {int(n)}" + (f"^{sup}" if sup else "")
                start(key, lab, "art", f"# Articolul {n}" + (f"^{sup}" if sup else ""))
                if gone:
                    units[key]["lines"][0] += f" – {gone}."
                    pending_caption = None
                else:
                    pending_caption = key
                continue
            m = TART.match(text)
            if m:
                key = f"tranz-{roman(m.group(1)):02d}"
                start(key, f"Art. {m.group(1)} (dispoziții tranzitorii)", "transitional", f"# Articolul {m.group(1)}")
                pending_caption = None
                continue
            m = TITLU.match(text)
            if m:
                title = f"titlul-{roman(m.group(1)):02d}" + (f"-{m.group(2)}" if m.group(2) else "")
                chapter = None
                start(title, f"Titlul {m.group(1)}" + (f"^{m.group(2)}" if m.group(2) else ""), "title",
                      f"# Titlul {m.group(1)}" + (f"^{m.group(2)}" if m.group(2) else ""))
                pending_caption = title
                continue
            m = CAP.match(text)
            if m:
                # chapters are numbered through the whole Constitution (I-IX), so the key does not need the title
                chapter = f"capitolul-{roman(m.group(1).upper()):02d}" + (f"-{m.group(2)}" if m.group(2) else "")
                start(chapter, f"Capitolul {m.group(1).upper()}" + (f"^{m.group(2)}" if m.group(2) else ""),
                      "chapter", f"# Capitolul {m.group(1).upper()}" + (f"^{m.group(2)}" if m.group(2) else ""))
                pending_caption = chapter
                continue
            m = SECT.match(text)
            if m:
                key = f"{chapter}-sectiunea-{m.group(1)}"
                start(key, f"Secțiunea {m.group(1)} ({chapter})", "section",
                      "# Secțiunea " + ("1" if m.group(1) == "1" else f"a {m.group(1)}-a"))
                pending_caption = key
                continue
            if pending_caption and pending_caption == cur:
                u = units[cur]
                u["lines"].append(("## " if u["kind"] == "art" else "") + text)
                pending_caption = None
                cap_open = True
                continue
            raise ValueError(f"unplaced heading: {text!r} after {cur}")
        else:
            pending_caption = None
            if cur is None:
                cur = "preambul"
                units[cur] = {"label": "Preambul", "kind": "preamble", "lines": []}
                order.append(cur)
            units[cur]["lines"].append(text)
    out = {}
    for k in order:
        u = units[k]
        out[k] = {"label": u["label"], "kind": u["kind"], "text": "\n".join(u["lines"]) + "\n"}
    return out


# ------------------------------------------------------------------ lex.justice.md (archived HTML)

NOTE = re.compile(r"^\[(.+)\]$")


def register_items(raw):
    """Lines of the consolidated text from a lex.justice.md page, and the bracketed notes per unit."""
    s = raw.decode("utf-8")
    i = s.find("NOI,")
    j = s.find("Articolul VIII", s.find("TRANZITORII"))
    assert i > 0 and j > i
    j = s.find("</div>", s.find("vigoare", j))
    body = s[s.rfind("<", 0, i):j]
    body = re.sub(r"<sup>\s*(\d+)\s*</sup>", r"^\1", body, flags=re.I)
    body = re.sub(r"<br\s*/?>|</div>|</p>|<div[^>]*>|<p[^>]*>", "\n", body, flags=re.I)
    # bold spans that open a heading become their own lines
    body = re.sub(r"<span[^>]*font-weight:\s*bold[^>]*>", "\n\x01", body, flags=re.I)
    body = re.sub(r"<[^>]+>", "", body)
    body = _html.unescape(body)
    items, notes = [], []
    for line in body.split("\n"):
        bold = "\x01" in line
        line = norm(line.replace("\x01", ""))
        if not line:
            continue
        line = re.sub(r"^T\s?i\s?t\s?l\s?u\s?l\b", "Titlul", line)
        line = re.sub(r"^Articolul\s+(\d+)\s+(\d)$", r"Articolul \1^\2", line)
        m = NOTE.match(line)
        if m:
            notes.append((len(items), m.group(1)))
            continue
        kind = "bold" if bold and not line.startswith("(") and len(line) < 140 else "para"
        if ART.match(line) or TART.match(line) or TITLU.match(line) or CAP.match(line) or SECT.match(line):
            kind = "head"
        items.append((kind, line))
    return items, notes


def from_register(raw):
    items, notes = register_items(raw)
    units = build_units(items)
    return units, [n for _, n in notes]


# ------------------------------------------------------------------ Moldpres 2024 edition (PDF)

def pdf_lines(path):
    """[(kind, text)] from the PDF's text layer (PyMuPDF): kind is 'head' (bold), 'start' (a line indented past
    the page's text margin: a new paragraph) or 'cont'. Running heads (8 pt) and page numbers (10 pt) are dropped.
    Superscript spans (the 1 of 'Articolul 106^1') are written '^1'."""
    import fitz
    out = []
    with fitz.open(path) as doc:
        for page in doc:
            lines = []
            for b in page.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    spans = [sp for sp in l["spans"] if sp["text"].strip() or sp["text"]]
                    if not spans or max(sp["size"] for sp in spans) < 11:
                        continue
                    txt = "".join(("^" + sp["text"].strip()) if sp["flags"] & 1 else sp["text"] for sp in spans)
                    bold = all(sp["flags"] & 16 for sp in spans if sp["text"].strip())
                    lines.append((l["bbox"][0], bold, txt))
            body = [x for x, bold, _ in lines if not bold]
            margin = min(body) if body else 0
            for x, bold, txt in lines:
                if not txt.strip():
                    continue
                out.append(("head" if bold else ("start" if x > margin + 5 else "cont"), txt.strip()))
    return out


def moldpres_items(lines, known_words):
    """Paragraphs from pdf_lines(). A hyphen at a line end is a line-break hyphen unless the hyphenated form is a
    known word (known_words: words printed elsewhere with their hyphen)."""
    start = next(i for i, (_, t) in enumerate(lines) if t.startswith("NOI, reprezentan"))
    end = next(i for i, (_, t) in enumerate(lines) if "intrarea ei în vigoare" in t) + 1
    paras = []
    preamble = True
    for kind, t in lines[start:end]:
        if ART.match(norm(t)):
            kind = "head"                      # "Articolul 82 - abrogat." is set as body text
        if kind == "head" and t == "Titlul I":
            preamble = False
        if preamble:
            # the preamble is set flush left, partly in bold: each paragraph opens with a word in capitals
            kind = "start" if re.match(r"^([A-ZĂÂÎȘȚŞŢ]{3,}[ ,]|adoptăm )", t) else "cont"
        if kind == "head":
            paras.append(["head", [t]])
        elif kind == "start" or not paras or paras[-1][0] == "head":
            paras.append(["para", [t]])
        else:
            paras[-1][1].append(t)
    items = []
    for kind, ls in paras:
        if kind == "head":
            items.append(("head", norm(ls[0])))
            continue
        text = ls[0].rstrip("  ")
        for nxt in ls[1:]:
            nxt = nxt.strip("  ")
            if text.endswith("-") and not text.endswith(" -"):
                left = re.search(r"(\S+)-$", text).group(1)
                right = re.match(r"\S+", nxt).group(0)
                joined_h = (left + "-" + right).strip(",.;:()„”")
                if joined_h.lower() in known_words:
                    text = text + nxt
                else:
                    text = text[:-1] + nxt
            else:
                text = text + " " + nxt
            text = text.rstrip("  ")
        items.append(("para", norm(text)))
    return items


def fix_superscripts(items):
    """Turn the flattened 'Articolul 1061' / 'Titlul V1' / 'Capitolul III1' back into 106^1, V^1, III^1."""
    out, last = [], 0
    for kind, t in items:
        if kind == "head":
            t = norm(t)
            m = re.match(r"^Articolul (\d+)(.*)$", t)
            if m:
                n, rest = m.group(1), m.group(2)
                if int(n) > last + 1 and len(n) > len(str(last)) and n.startswith(str(last)):
                    t = f"Articolul {last}^{n[len(str(last)):]}{rest}"
                else:
                    last = int(n)
            t = re.sub(r"^(Titlul|Capitolul) ([IVX]+)1$", r"\1 \2^1", t)
        out.append((kind, t))
    return out


def from_moldpres(path, known_words):
    return build_units(moldpres_items(pdf_lines(path), known_words))
