"""Index parsing for the AGO 'Current Revised Edition by Title' pages (reads cache via fetch.get)."""
import html
import re

import fetch

INDEX = 'https://www.ago.gov.to/cms/legislation/current-revised-edition/by-title.html?view=acts_alpha'
POINT = '2026-10-28+00%3A00%3A00'
BASE = 'https://www.ago.gov.to'


def letter_page(letter):
    return fetch.get(INDEX, data=f'submit4={letter}&pointintime={POINT}').decode('utf-8', 'replace')


def history(letter, title_re):
    """Return [(title, [{version, pdf, commenced, details, superseded}])] for modals whose title matches."""
    b = letter_page(letter)
    out = []
    for m in re.finditer(r'<div id="myHistoryModal(\d+)".*?<h4[^>]*>(.*?) - Legislation History Table.*?<div class="modal-footer">', b, re.S):
        title = html.unescape(m.group(2)).strip()
        if not re.search(title_re, title):
            continue
        rows = []
        for r in re.finditer(r'<div class="rowHistory">(.*?)</div>\s*</div>', m.group(0) + '</div>', re.S):
            t = r.group(1)
            v = re.search(r'Version:</b>\s*(\d+)', t)
            pdf = re.search(r'href="([^"]+)"', t)
            com = re.search(r'Date Commenced:</b>\s*([^<]+)', t)
            det = re.search(r'Details:</b><br>(.*?)</div>', t, re.S)
            sup = re.search(r'Date Superseded:</b>\s*([^<]+)', t)
            rows.append({'version': int(v.group(1)) if v else None,
                         'pdf': BASE + pdf.group(1) if pdf else None,
                         'commenced': com.group(1).strip() if com else None,
                         'details': re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', det.group(1)))).strip() if det else '',
                         'superseded': sup.group(1).strip() if sup else None})
        out.append((title, m.group(1), rows))
    return out
