"""Apply Amendments I-XXI to the 2007 Constitution, each by its own instruction paragraph (cache only).

OPS is transcribed by hand from each amendment's last paragraph; INSTR holds that paragraph verbatim and the
replay refuses to run if the gazette text differs, so every operation stays tied to its official instruction.
"Replace stav N (and supplement)" puts all the amendment's paragraphs in place of stav N: Amendment XVII
(2026) replaces "stav 3 člana 91 (Amandman IV)" with the words of Amendment IV's second paragraph, which only
holds if IV's paragraphs took the place of the old stav 2; checks() confirms this and the other cross-references.
"""
import copy, re
import ustav

INSTR = {
    "I": "Ovim amandmanom zamjenjuje se član 33 Ustava Crne Gore.",
    "II": "Ovim amandmanom zamjenjuje se naziv člana 34 i član 34 Ustava Crne Gore.",
    "III": "Ovim amandmanom zamjenjuju se tač. 13 i 14 člana 82 Ustava Crne Gore.",
    "IV": "Ovim amandmanom zamjenjuju se stav 2 člana 91 i dopunjava član 91 Ustava Crne Gore.",
    "V": "Ovim amandmanom zamjenjuje se tačka 5 člana 95 Ustava Crne Gore.",
    "VI": "Ovim amandmanom zamjenjuje se naziv poglavlja 5. „SUD“ u Dijelu Trećem – Uređenje vlasti",
    "VII": "Ovim amandmanom zamjenjuju se st. 2, 3 i 4 člana 124 i dopunjava član 124 Ustava Crne Gore.",
    "VIII": "Ovim amandmanom zamjenjuje se član 127 Ustava Crne Gore.",
    "IX": "Ovim amandmanom zamjenjuje se član 128 Ustava Crne Gore.",
    "X": "Ovim amandmanom zamjenjuje se član 135 Ustava Crne Gore.",
    "XI": "Ovim amandmanom zamjenjuje se član 136 Ustava Crne Gore.",
    "XII": "Ovim amandmanom zamjenjuje se član 137 Ustava Crne Gore.",
    "XIII": "Ovim amandmanom zamjenjuje se član 138 Ustava Crne Gore.",
    "XIV": "Ovim amandmanom dopunjava se član 144 Ustava Crne Gore.",
    "XV": "Ovim amandmanom dopunjava se član 151 Ustava Crne Gore.",
    "XVI": "Ovim amandmanom zamjenjuje se član 153 Ustava Crne Gore.",
    "XVII": "Ovim amandmanom zamjenjuje se stav 3 člana 91 Ustava Crne Gore (Amandman IV).",
    "XVIII": "Ovim amandmanom zamjenjuje se član 127 Ustava Crne Gore (Amandman VIII).",
    "XIX": "Ovim amandmanom briše se stav 3 člana 128 Ustava Crne Gore (Amandman IX).",
    "XX": "Ovim amandmanom zamjenjuje se naziv člana 136 „Tužilački savjet”, zamjenjuje stav 3 člana 136 i "
          "dopunjava član 136 Ustava Crne Gore (Amandman XI).",
    "XXI": "Ovim amandmanom zamjenjuje se član 143 Ustava Crne Gore.",
}
# op, article (or part, chapter), argument
OPS = {
    "I": ("article", 33), "II": ("article+caption", 34), "III": ("points", 82, [13, 14]),
    "IV": ("stavs", 91, [2]), "V": ("points", 95, [5]), "VI": ("chapter", (3, 5)),
    "VII": ("stavs", 124, [2, 3, 4]), "VIII": ("article", 127), "IX": ("article", 128), "X": ("article", 135),
    "XI": ("article", 136), "XII": ("article", 137), "XIII": ("article", 138), "XIV": ("append", 144),
    "XV": ("append", 151), "XVI": ("article", 153),
    "XVII": ("stavs", 91, [3]), "XVIII": ("article", 127), "XIX": ("delete", 128, [3]),
    "XX": ("stavs+caption", 136, [3]), "XXI": ("article", 143),
}
BATCHES = [  # (in-force day, gazette act id, (indent, continuation x), amendments)
    ("2013-07-31", ustav.AM_2013, (93.1, 70.6), ustav.ROMAN[:16]),
    ("2026-08-24", ustav.AM_2026, (73.8, 56.8), ustav.ROMAN[16:]),
]


class State:
    def __init__(self):
        pre, elems = ustav.read_2007()
        self.preamble = pre
        self.parts, self.chapters, self.arts = {}, {}, {}
        for e in elems:
            if e[0] == "part":
                self.parts[e[1]] = e[2]
            elif e[0] == "chapter":
                self.chapters[(e[1], e[2])] = e[3]
            else:
                self.arts[e[1]] = {"caption": e[2], "stavs": e[3]}

    def units(self):
        u = {"preambula": {"label": "Преамбула", "kind": "preamble", "text": "\n".join(self.preamble) + "\n"}}
        for p, lines in self.parts.items():
            u[f"dio-{p}"] = {"label": lines[0].title(), "kind": "heading", "text": "\n".join(lines) + "\n"}
        for (p, c), t in self.chapters.items():
            u[f"dio-{p}-poglavlje-{c}"] = {"label": t, "kind": "heading", "text": t + "\n"}
        for n, a in self.arts.items():
            lines = [f"# Члан {n}"] + ([f"## {a['caption']}"] if a["caption"] else [])
            lines += [l for s in a["stavs"] for l in s]
            u[f"clan-{n:03d}"] = {"label": f"Члан {n}", "kind": "art", "text": "\n".join(lines) + "\n"}
        return u


def apply(state, roman, am, log):
    op = OPS[roman]
    stavs = ustav.group_stavs(am["paras"])
    if op[0] == "chapter":
        state.chapters[op[1]] = am["caption"]
        return [f"dio-{op[1][0]}-poglavlje-{op[1][1]}"]
    art = state.arts[op[1]]
    if op[0] in ("article", "article+caption"):
        art["stavs"] = stavs
        if op[0] == "article+caption":
            art["caption"] = am["caption"]
        else:
            assert am["caption"] is None, roman
    elif op[0] in ("stavs", "stavs+caption"):
        ns = op[2]
        assert ns == list(range(ns[0], ns[-1] + 1)) and ns[-1] <= len(art["stavs"]), (roman, ns)
        log.append(f"Amandman {roman}: čl. {op[1]} st. {ns} were: {art['stavs'][ns[0] - 1:ns[-1]]}")
        art["stavs"][ns[0] - 1:ns[-1]] = stavs
        if op[0] == "stavs+caption":
            art["caption"] = am["caption"]
    elif op[0] == "points":
        for want, new in zip(op[2], am["paras"]):
            assert new.startswith(f"{want}) "), (roman, new)
            hits = [(si, li) for si, s in enumerate(art["stavs"]) for li, l in enumerate(s) if l.startswith(f"{want}) ")]
            assert len(hits) == 1, (roman, want, hits)
            si, li = hits[0]
            log.append(f"Amandman {roman}: čl. {op[1]} tačka {want} was: {art['stavs'][si][li]}")
            art["stavs"][si][li] = new
        assert len(op[2]) == len(am["paras"]), roman
    elif op[0] == "append":
        art["stavs"] += stavs
    elif op[0] == "delete":
        for n in sorted(op[2], reverse=True):
            log.append(f"Amandman {roman}: čl. {op[1]} st. {n} deleted: {art['stavs'][n - 1]}")
            del art["stavs"][n - 1]
        assert not am["paras"], roman
    return [f"clan-{op[1]:03d}"]


def replay():
    """-> list of (from, act id, {unit key: [law keys]}, units dict, log lines), first = the 2007 text."""
    st = State()
    out = [("2007-10-22", ustav.USTAV, {}, copy.deepcopy(st.units()), [])]
    texts = {}
    for day, act, (ind, cont), romans in BATCHES:
        ams, order = ustav.read_amendments(act, ind, cont)
        assert order == romans, (order, romans)
        credits, log = {}, []
        for r in romans:
            assert ams[r]["instruction"] == INSTR[r], (r, ams[r]["instruction"])
            texts[r] = ams[r]
            for k in apply(st, r, ams[r], log):
                credits.setdefault(k, []).append(f"amandman-{ustav.ROMAN.index(r) + 1:02d}")
        out.append((day, act, credits, copy.deepcopy(st.units()), log))
    return out, texts


def checks(versions, texts):
    """Cross-references the 2026 amendments make to the 2013 ones: each named provision holds what we built."""
    res = []
    v2013 = versions[1][3]
    a91 = v2013["clan-091"]["text"].split("\n")
    res.append(("XVII: čl. 91 st. 3 after 2013 = Amandman IV para 2", a91[4] == texts["IV"]["paras"][1]))
    a128 = v2013["clan-128"]["text"].split("\n")
    res.append(("XIX: čl. 128 st. 3 after 2013 = Amandman IX last para", a128[-2] == texts["IX"]["paras"][-1]))
    a136 = v2013["clan-136"]["text"].split("\n")
    res.append(("XX: čl. 136 st. 3 after 2013 = Amandman XI para 3", a136[4] == texts["XI"]["paras"][2]))
    res.append(("XX: čl. 136 caption before 2026 is 'Тужилачки савјет' (named „Tužilački savjet”)",
                a136[1] == "## Тужилачки савјет"))
    res.append(("VI: chapter 5 of part 3 was '5. СУД' (named „SUD“)",
                versions[0][3]["dio-3-poglavlje-5"]["text"] == "5. СУД\n"))
    return res
