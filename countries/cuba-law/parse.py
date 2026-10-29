"""Reads only .cache/ and writes corpus.json (Cuba). First pass: Constitución 2019 as published, GOC-2019-406-EX5."""
import hashlib, json, os, re, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
URL = "https://www.gacetaoficial.gob.cu/sites/default/files/goc-2019-ex5_0.pdf"
def cache(u): return HERE / ".cache" / hashlib.sha256(u.encode()).hexdigest()
def text(u): return subprocess.run(["pdftotext", "-enc", "UTF-8", str(cache(u)), "-"], capture_output=True, text=True, encoding="utf-8").stdout
ORD = ["PRIMERA","SEGUNDA","TERCERA","CUARTA","QUINTA","SEXTA","SÉPTIMA","OCTAVA","NOVENA","DÉCIMA","DECIMOPRIMERA","DECIMOSEGUNDA","DECIMOTERCERA"]
def constitution():
    raw = text(URL).replace(" ", " ").replace("\f", "\n")
    lines = [re.sub(r"\s+", " ", l).strip() for l in raw.split("\n")]
    lines = [l for l in lines if l and not re.fullmatch(r"(\d+ )?Gaceta Oficial 10 de abril de 2019( \d+)?|\d+|GACETA OFICIAL|_+|ISSN 1682-7511", l)]
    start = next(i for i, l in enumerate(lines) if l == "PREÁMBULO")
    units, cur, kind, buf = {}, "preambulo", "preamble", []
    def flush():
        if buf: units[cur] = {"label": lab[cur], "kind": kind, "text": "\n".join(join(buf)) + "\n"}
    lab = {"preambulo": "Preámbulo"}; section = None
    for l in lines[start+1:]:
        m = re.match(r"ARTÍCULO (\d+)\. ?(.*)", l)
        if m and section is None:
            flush(); cur = f"art-{int(m.group(1)):03d}"; kind = "art"; lab[cur] = f"Artículo {m.group(1)}"; buf = [l]; continue
        if l in ("DISPOSICIONES ESPECIALES", "DISPOSICIONES TRANSITORIAS", "DISPOSICIONES FINALES"):
            flush(); buf = []; section = {"DISPOSICIONES ESPECIALES": "especial", "DISPOSICIONES TRANSITORIAS": "transitoria", "DISPOSICIONES FINALES": "final"}[l]; continue
        m = re.match(r"(" + "|".join(ORD) + r"): (.*)", l)
        if section and m:
            flush(); n = ORD.index(m.group(1)) + 1; cur = f"disp-{section}-{n:02d}"; kind = "transitional" if section == "transitoria" else "final"
            lab[cur] = f"Disposición {section} {m.group(1).lower()}"; buf = [l]; continue
        if re.match(r"(TÍTULO|CAPÍTULO|SECCIÓN) ", l) or (l.isupper() and len(l) < 80 and not re.match(r"[a-zñ]\)", l)):
            if section and l.startswith("DADA EN"): pass
            continue
        if section == "final" and re.match(r"(DADA|Dada) ", l): flush(); buf = []; break
        buf.append(l)
    flush()
    return units
def join(buf):
    out = []
    for l in buf:
        if out and not re.match(r"([a-zñ]\)|\d+\.|ARTÍCULO|[A-ZÁÉÍÓÚ]+:)", l) and not out[-1].endswith((".", ":", ";")):
            out[-1] = (out[-1][:-1] + l) if out[-1].endswith("-") else out[-1] + " " + l
        else: out.append(l)
    return out
units = constitution()
corpus = {"country": {"code": "CU", "name": "Cuba", "slug": "cuba", "lang": "es", "tz": "America/Havana", "future_branch": "futuro",
  "publisher": {"name": "Gaceta Oficial de la República de Cuba (Ministerio de Justicia)", "email": "gaceta@gacetaoficial.invalid"},
  "default_in_force_rule": {"text": "Constitución 2019, Disposición final segunda: in force once proclaimed, from its publication in the Gaceta Oficial; other laws state their own vigencia", "source": URL},
  "licence_note": "Text from the Gaceta Oficial de la República de Cuba, Ministerio de Justicia (gacetaoficial.gob.cu)."},
 "sources": [{"name": "Gaceta Oficial de la República de Cuba", "url": "https://www.gacetaoficial.gob.cu", "retrieved": "2026-10-28", "requests": 9, "licence": "Official text; no licence stated", "notes": "robots.txt Crawl-delay 10 respected"}],
 "laws": {"constitucion-2019": {"label": "Constitución 2019", "title": "Constitución de la República de Cuba, proclamada el 10 de abril de 2019", "kind": "referendum", "enacted": "2019-04-10", "published": "2019-04-10", "url": URL, "temporary_until": None, "restores": None, "note": None}},
 "acts": [{"slug": "constitucion", "short": "CRC", "title": "Constitución de la República de Cuba", "url": URL, "first_law": "constitucion-2019", "earlier_laws": [],
   "versions": [{"from": "2019-04-10", "source_url": URL, "sha256": hashlib.sha256(cache(URL).read_bytes()).hexdigest(), "units": units, "credits": {}}]}],
 "applies": [], "decisions": ["Constitution dated 2019-04-10: GOC-2019-406-EX5 publication day; Disposición final segunda puts it in force on publication.", "Headings (títulos, capítulos) dropped in this first pass; signatures dropped."],
 "ai_use": ["none"]}
tmp = HERE / "corpus.json.tmp"; tmp.write_text(json.dumps(corpus, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"); os.replace(tmp, HERE / "corpus.json")
print(len(units), "units")
