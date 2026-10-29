"""Registro Oficial month listings: which editions came out in a month, with their dates and PDF links.

The portal (registroficial.gob.ec, WordPress) shows each product (Registro Oficial, Suplemento, Edición Especial,
Edición Constitucional, Edición Jurídica) as a year/month tree; a month's list is a POST to admin-ajax.php with
action=get_term_post_kilur_con_imagen. Every response is cached by fetch.py (key = URL + form body).

    python -X utf8 ro_index.py <product> <year> <month 1-12>    print the editions of that month
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch  # noqa: E402

BASE = "https://www.registroficial.gob.ec"
AJAX = BASE + "/wp-admin/admin-ajax.php"
PRODUCTS = {
    "ro": BASE + "/245427-2/",
    "suplemento": BASE + "/255776-2/",
    "especial": BASE + "/261974-2/",
    "constitucional": BASE + "/267099-2/",
    "juridica": BASE + "/266381-2/",
}
MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
          "Noviembre", "Diciembre"]


def tree(product: str) -> dict[tuple[int, str], dict]:
    """(year, month name) -> the data-* attributes of that month's link."""
    p = fetch.get(PRODUCTS[product])
    t = p.read_bytes().decode("utf-8", "replace")
    out: dict[tuple[int, str], dict] = {}
    # Each year is <li class="kilur-primer-li">  YYYY<ul> ... month links ... </ul>
    for m in re.finditer(r'kilur-primer-li">\s*(\d{4})<ul>(.*?)</ul>', t, re.S):
        year = int(m.group(1))
        for a in re.finditer(r'<a href="#" class="post-imagen-link"([^>]*)>', m.group(2)):
            attrs = dict(re.findall(r'data-([a-z-]+)="([^"]*)"', a.group(1)))
            out[(year, attrs["name"])] = attrs
    return out


def month(product: str, year: int, mon: int, page: int = 1) -> str:
    attrs = tree(product)[(year, MONTHS[mon - 1])]
    form = urlencode({"action": "get_term_post_kilur_con_imagen", "year_id": attrs["year-id"],
                      "mes_id": attrs["mes-id"], "name_folder": attrs["name"], "page": page,
                      "id_carpeta": attrs["id-carpeta"]})
    p = fetch.get(AJAX, data=form)
    if p is None:
        raise RuntimeError(f"listing failed: {product} {year}-{mon:02d} p{page}")
    raw = p.read_bytes().decode("utf-8", "replace")
    try:
        return json.loads(raw).get("data") or ""
    except json.JSONDecodeError:
        return raw


def editions(product: str, year: int, mon: int) -> list[dict]:
    """Every edition listed for the month, following the listing's own pages."""
    out: list[dict] = []
    page = 1
    while True:
        h = month(product, year, mon, page)
        out.extend(parse_listing(h))
        pages = [int(x) for x in re.findall(r'button-post-imagen-link[^>]*data-page="(\d+)"', h)]
        if not pages or page >= max(pages):
            break
        page += 1
    return out


def parse_listing(h: str) -> list[dict]:
    """One card per edition: product title, 'Año I - Nº 458', 'viernes, 31 octubre 2008', pages, PDF link."""
    items = []
    for block in h.split("<div class='card__item_post_imagen'>")[1:]:
        def grab(cls: str) -> list[str]:
            return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()
                    for x in re.findall(rf"class='{cls}'>(.*?)</(?:h4|p)>", block, re.S)]
        title = grab("card__title_post_imagen")
        num = grab("card__title_numero_imagen")
        fecha = grab("txt_fecha_post_imagen")
        pdf = re.findall(r"href='([^']+)' class='cta_post_imagen'", block)
        nm = re.search(r"N[º°o]\.?\s*(\d+)", num[0] if num else "")
        dm = re.search(r"(\d{1,2}) (\w+) (\d{4})", fecha[0] if fecha else "")
        date = None
        if dm:
            mi = [x.lower() for x in MONTHS].index(dm.group(2).lower()) + 1 if dm.group(2).lower() in [x.lower() for x in MONTHS] else 0
            if mi:
                date = f"{int(dm.group(3)):04d}-{mi:02d}-{int(dm.group(1)):02d}"
        items.append({"title": title[0] if title else "", "number": int(nm.group(1)) if nm else None,
                      "numero": num[0] if num else "", "date": date, "fecha": fecha[0] if fecha else "",
                      "pages": fecha[1] if len(fecha) > 1 else "", "pdf": pdf[0] if pdf else None})
    return items


if __name__ == "__main__":
    prod, y, m = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    for e in editions(prod, y, m):
        print(e["date"], e["title"], "|", e["numero"], "|", e["pages"], "|", e["pdf"])
