"""Read laws.gov.tt act pages (cached HTML) into plain data."""
import html as _html
import re


def _clean(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', _html.unescape(s)).strip()


def act_page(path):
    h = open(path, encoding='utf-8', errors='replace').read()
    out = {'versions': [], 'amendments': []}
    m = re.search(r'Year - (\d{4}).*?Act Number - (\d+).*?Commencement Date - ([^<]+)<', h, re.S)
    if m:
        out['year'], out['number'], out['commencement'] = m.group(1), m.group(2), m.group(3).strip()
    # versions tab: <li> with download?type=act, "as at ..." and edition label
    vt = h[h.find('id="activities"'):h.find('id="bio"')]
    for li in re.findall(r'<li class="list-group-item">(.*?)</li>', vt, re.S):
        href = re.search(r'href="(/ttdll-web/revision/download/\d+\?type=act)"', li)
        asat = re.search(r'<small class="pull-right">([^<]*)</small>', li)
        ed = re.search(r'<strong class="block">([^<]*)</strong>', li)
        if href:
            out['versions'].append({'href': href.group(1), 'as_at': _clean(asat.group(1)) if asat else '',
                                    'edition': _clean(ed.group(1)) if ed else ''})
    # amendments tab: rows with kind (Act / Ordinance / Legal Notice) and reference
    bt = h[h.find('id="bio"'):h.find('id="edit"')]
    for tr in re.findall(r'<tr>(.*?)</tr>', bt, re.S):
        href = re.search(r'href="(/ttdll-web/revision/download/\d+\?type=amendment)"', tr)
        strongs = [_clean(s) for s in re.findall(r'<strong[^>]*>(.*?)</strong>', tr, re.S)]
        if href and len(strongs) >= 2:
            out['amendments'].append({'href': href.group(1), 'kind': strongs[0], 'ref': strongs[1]})
    et = h[h.find('id="edit"'):]
    out['alerts'] = [_clean(a) for a in re.findall(r'<div class="alert[^"]*">(.*?)</div>', et, re.S)]
    return out
