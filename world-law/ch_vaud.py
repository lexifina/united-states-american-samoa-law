"""Vaud (BLV: Akoma Ntoso HTML, every consolidated version) for switzerland-vaud-law. Private: scripts/world-law.

    python -X utf8 scripts/world-law/ch_vaud.py constitution <docs-date>
    python -X utf8 scripts/world-law/ch_vaud.py laws <docs-date> [max]     # parts of 50 LOIs in BLV order
    python -X utf8 scripts/world-law/ch_vaud.py publish <part> <docs-date>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ch_cantons as C  # noqa: E402
import ch_romandy as R  # noqa: E402

SLUG = 'vaud'
VD_API = 'https://prestations.vd.ch/pub/blv-publication/api/'
VD_SKIP = ('akn-modifiants-container', 'akn-modifiant-number', 'akn-commentaires', 'akn-collapsible-icon',
           'popper', 'nav')
clean = C.clean
letters = C.letters
art_key = R.art_key
_iso = C.iso


def vd_root(raw: bytes):
    from lxml import html
    t = raw.decode('utf-8')
    t = re.sub(r'(?is)<script.*?</script>|<style.*?</style>', ' ', t)
    t = re.sub(r'(?is)<sup>\s*<a [^>]*akn-commentaire[^>]*>.*?</a>\s*</sup>', '', t)  # commentary refs [A]
    r = html.fromstring(t)
    ak = r.xpath('//*[@id="akomaNtoso"]')
    root = ak[0]
    for el in list(root.iter()):
        if not isinstance(el.tag, str):
            continue
        c = (el.get('class') or '').split()
        if el.getparent() is not None and any(x in c for x in VD_SKIP):
            el.drop_tree()
    return root


HEADS = {'akn-book': 2, 'akn-part': 2, 'akn-title': 2, 'akn-subtitle': 3, 'akn-chapter': 3,
         'akn-subchapter': 4, 'akn-section': 4, 'akn-subsection': 5}


def parse_vd_doc(raw: bytes):
    root = vd_root(raw)
    units, order, outline, ingress = {}, [], [], []
    cur = [None]

    def add(line):
        line = clean(line)
        if line:
            (units[cur[0]]['lines'] if cur[0] else ingress).append(line)

    def walk(el):
        if not isinstance(el.tag, str):
            return
        c = (el.get('class') or '').split()
        if 'akn-preface' in c:
            parts = [clean(x.text_content()) for x in el.iter() if isinstance(x.tag, str) and set((x.get('class') or '').split()) &
                     {'akn-docType', 'akn-docNumber', 'akn-docTitle', 'akn-docAbreviation', 'akn-docDate'}]
            parts = [x for x in parts if x]
            if parts:
                ingress.append('# ' + ' '.join(parts))
            return
        if 'akn-preamble' in c:
            ps = [x for x in el.iter('p')]
            for x in ps or [el]:
                add(x.text_content())
            return
        if el.tag == 'table' and set(c) & set(HEADS):
            lv = min(HEADS[x] for x in c if x in HEADS)
            outline.append('#' * lv + ' ' + clean(el.text_content()))
            return
        if el.tag == 'table' and 'akn-article' in c:
            num = el.find_class('akn-num')
            ntxt = clean(num[0].text_content()) if num else ''
            head = el.find_class('akn-heading')
            htxt = clean(' '.join(h.text_content() for h in head)) if head else ''
            n = re.sub(r'^Art\.?\s*', '', ntxt).replace(' ', '')
            key = art_key(n or ntxt)
            b, i = key, 2
            while key in units:
                key = f'{b}-{i}'
                i += 1
            cur[0] = key
            subs = [clean(x.text_content()) for x in el.find_class('akn-subheading')]
            units[key] = {'label': ntxt or 'Art.', 'lines': ['# ' + clean(f'{ntxt} {htxt}')] + [x for x in subs if x]}
            order.append(key)
            return
        if 'akn-alinea' in c or (el.tag == 'tr' and 'akn-point' in c) or el.tag == 'p':
            add(el.text_content())
            return
        if el.tag == 'tr':
            cells = [clean(td.text_content()) for td in el if isinstance(td.tag, str)]
            cells = [x for x in cells if x]
            if cells:
                add(' | '.join(cells))
            return
        if el.text and el.text.strip() and len(el) == 0:
            add(el.text)
            return
        for ch in el:
            walk(ch)
    walk(root)
    out = {}
    if ingress:
        out['ingress'] = {'label': 'Titre et préambule', 'kind': 'preamble', 'text': '\n'.join(ingress) + '\n'}
    for k in order:
        out[k] = {'label': units[k]['label'], 'kind': 'art', 'text': '\n'.join(units[k]['lines']) + '\n'}
    if outline:
        out['gliederung'] = {'label': 'Structure', 'kind': 'heading', 'text': '\n'.join(outline) + '\n'}
    return out


def vd_source_letters(raw: bytes) -> str:
    """All text inside <akomaNtoso>, less the hidden modification lists, the commentary notes and their [A]
    markers, read from the whole tree without the parser's unit logic."""
    return letters(vd_root(raw).text_content())


def vd_elem_units(pos: str) -> set:
    out = set()
    m = re.search(r'Art\.\s*([0-9]+[a-zA-Z]*(?:\s?(?:bis|ter|quater|quinquies|sexies))?)', pos)
    if m:
        out.add(art_key(m.group(1).replace(' ', '')))
    if not m and re.search(r'Titre|Chapitre|Section|Partie|Livre', pos):
        out.add('gliederung')
    if re.search(r'Intitul|Préambule|Preambule', pos):
        out.add('ingress')
    return out


def _nn(x):
    return None if x in (None, 'None', '') else x


def vd_act(cote, acte_id):
    vers = json.loads(R.get(SLUG, f'{VD_API}actes/CONSOLIDE?id={acte_id}&cote={cote}'))
    hist = json.loads(R.get(SLUG, f'{VD_API}actes/{acte_id}/historique'))
    orig = hist['original']
    dedup = {}
    for v in sorted(vers, key=lambda v: _iso(v.get('versionDateMiseEnVigueur')) or ''):
        frm = _iso(v.get('versionDateMiseEnVigueur'))
        if frm and v.get('type') == 'HTML_RENDU':
            dedup[frm] = v
    if not dedup:
        return None
    laws, mods = {}, []
    for m in hist.get('modifiants', []):
        key = 'vd-' + m['id'][:12]
        label = clean(re.sub(r'\s*\(BLV [^)]*\)\s*$', '', m.get('titreComplet') or m.get('titre') or key))[:110]
        laws[key] = {'label': f'{label} [{m["id"][:8]}]', 'title': clean(m.get('titreComplet') or label),
                     'kind': 'law', 'enacted': _iso(_nn(m.get('dateAdoption'))),
                     'published': _iso(_nn(m.get('datePublicationFAO'))), 'url': None, 'temporary_until': None,
                     'restores': None, 'note': None}
        for x in m.get('modifications') or []:
            mods.append({'law': key, 'pos': x.get('position') or '',
                         'inforce': _iso(_nn(x.get('dateMiseEnVigueur'))) or _iso(_nn(m.get('dateMiseEnVigueur')))})
        if not m.get('modifications'):
            mods.append({'law': key, 'pos': '', 'inforce': _iso(_nn(m.get('dateMiseEnVigueur')))})
    versions, prev_units, prev_from, first_v = [], None, None, None
    for frm in sorted(dedup):
        v = dedup[frm]
        url = f'{VD_API}actes/{v["htmlId"]}/html'
        raw = R.get(SLUG, url)
        units = parse_vd_doc(raw)
        ver = {'from': frm, 'source_url': url, 'sha256': hashlib.sha256(raw).hexdigest()}
        if prev_units is None:
            ver['units'], ver['credits'], first_v = units, {}, v
        else:
            changed = sorted(k for k in set(prev_units) | set(units)
                             if prev_units.get(k, {}).get('text') != units.get(k, {}).get('text'))
            if not changed:
                continue
            ver['changes'] = {k: units.get(k) for k in changed}
            window = [m for m in mods if m['inforce'] and prev_from < m['inforce'] <= frm]
            day = sorted({m['law'] for m in window})
            cr = {}
            for k in changed:
                ls = sorted({m['law'] for m in window if k in vd_elem_units(m['pos'])}) or day
                if ls:
                    cr[k] = ls
            ver['credits'] = cr
        versions.append(ver)
        prev_units, prev_from = units, frm
    title = clean(orig.get('titreComplet') or (first_v or {}).get('titre') or cote)
    okey = 'vd-orig-' + acte_id[:12]
    laws[okey] = {'label': clean(re.sub(r'\s*\(BLV [^)]*\)\s*$', '', title))[:110] + f' [{acte_id[:8]}]',
                  'title': title, 'kind': 'law', 'enacted': _iso(_nn(orig.get('dateAdoption'))),
                  'published': _iso(_nn(orig.get('datePublicationFAO'))), 'url': None,
                  'temporary_until': None, 'restores': None, 'note': None}
    first_law, earlier = None, []
    if first_v and first_v.get('origine') == 'acte original':
        first_law = okey
    else:
        earlier = [okey] + sorted({m['law'] for m in mods if m['inforce'] and m['inforce'] <= versions[0]['from']})
    used = {first_law} if first_law else set(earlier)
    for v in versions:
        for ls in v.get('credits', {}).values():
            used.update(ls)
    abbr = clean(_nn(orig.get('abreviation')) or '')
    act = {'slug': C.ascii_key(f'{cote}-{abbr}') if abbr else C.ascii_key(cote), 'short': abbr or f'BLV {cote}',
           'title': clean((first_v or {}).get('titre') or title),
           'url': f'https://prestations.vd.ch/pub/blv-publication/actes/consolide/{cote}?id={acte_id}',
           'first_law': first_law, 'earlier_laws': earlier, 'systematic_number': cote, 'versions': versions}
    return act, {k: laws[k] for k in sorted(used)}


DECISIONS = [
    'Each version is a consolidated version the BLV publishes, dated by its own in-force day; when two versions '
    'share a day only the last is kept, and a version whose text is unchanged is skipped.',
    'Changes are credited to the amending acts whose recorded modifications (provision and entry into force) fall '
    'after the previous version and on or before this one; a change whose provision none of them names is credited '
    'to every amending act of that window.',
    'An act\'s first version is credited to the act as adopted when the BLV marks it "acte original"; otherwise it '
    'is the oldest version available.',
    'Section headings are kept together in gliederung.md; the title, date and preamble in ingress.md. Commentary '
    'notes, their markers and the modification lists the BLV shows beside each article are left out.',
]


def part(name, acts_ids, docs_date, with_country=False):
    acts, laws = [], {}
    for cote, aid in acts_ids:
        r = vd_act(cote, aid)
        if not r:
            continue
        a, l = r
        acts.append(a)
        for k, v in l.items():
            laws.setdefault(k, v)
    p = {'laws': dict(sorted(laws.items())), 'acts': acts}
    if with_country:
        pub = 'Etat de Vaud, Base législative vaudoise (BLV)'
        p = {'country': R.country_block(SLUG, pub, 'https://prestations.vd.ch/pub/blv-publication/'),
             'sources': [{'name': 'Base législative vaudoise (BLV)',
                          'url': 'https://prestations.vd.ch/pub/blv-publication/', 'retrieved': docs_date,
                          'licence': 'Art. 5 para. 1 let. a URG (SR 231.1): no copyright in acts.',
                          'notes': 'Every consolidated version of each act (HTML), with each amending act and '
                                   'the provisions it changed.'}],
             **p, 'decisions': DECISIONS, 'ai_use': R.AI_USE}
    R.write_part(R.folder(SLUG) / 'corpus.d' / f'{name}.json', p)
    return acts


def law_list():
    """Every in-force LOI in BLV order, from the systematic tree (one request per volume)."""
    top = json.loads(R.get(SLUG, f'{VD_API}recueil-systematique'))
    out = []

    def walk(n):
        for x in n:
            if x.get('typeElement') == 'ACTE' and re.match(r'^LOI\b', x.get('libelle', '')) and x.get('atelierId'):
                out.append((x['code'], x['atelierId']))
            walk(x.get('children') or [])
    for vol in top:
        walk(json.loads(R.get(SLUG, f'{VD_API}recueil-systematique?code={vol["code"]}')))
    seen, res = set(), []
    for c, a in out:
        if a not in seen:
            seen.add(a)
            res.append((c, a))
    return res


R.SOURCE_DOCS[SLUG] = {
    'holds': 'Each act has every consolidated version the BLV publishes, from the act as adopted (where the BLV holds it) to today: the constitution first, then the cantonal laws (LOI) and the règlements (RÈGLEMENT) in force, each in the order of the systematic collection, added in parts. Arrêtés, decrees, agreements and repealed acts are not included yet.',
    'source': 'The Base législative vaudoise (BLV), published by the Etat de Vaud at <https://prestations.vd.ch/pub/blv-publication/>. For each act it gives every consolidated version with its in-force day, and the list of amending acts with the provisions each changed and when.',
    'dates': 'Each version is dated by the in-force day the BLV gives it. The adoption day of each amending act is the `Enacted:` trailer; its publication in the Feuille des avis officiels the `Published:` trailer.',
    'author': 'The author of each commit is the amending act (decree or law) the BLV records for the changed provisions, with an e-mail address that cannot exist. Where several amending acts take effect in one version and the BLV does not say which provision each one touched, the commit names them all.',
    'limits': 'The binding text is the one published in the Feuille des avis officiels and the Recueil annuel. Commentary notes are not included. Only the acts listed above are included.',
    'licence_src': 'Taken from the Base législative vaudoise (https://prestations.vd.ch/pub/blv-publication/), Etat de Vaud. The canton\'s legal notice (https://www.vd.ch/mentions-legales) forbids reuse of "contenu protégé par les droits d\'auteur" without permission; laws are not such content (Art. 5 URG).',
}

if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'constitution':
        acts = part('10-constitution', [('101.01', 'f79b6681-185b-42a1-946d-55fb19430277')], sys.argv[2], True)
        print([v['from'] for v in acts[0]['versions']], len(acts[0]['versions'][0]['units']))
    elif cmd == 'laws':
        lst = law_list()
        print(len(lst), 'LOIs')
        mx = int(sys.argv[3]) if len(sys.argv) > 3 else len(lst)
        for i in range(0, min(mx, len(lst)), 50):
            name = f'{20 + i // 50:02d}-lois-{i // 50 + 1}'
            if (R.folder(SLUG) / 'corpus.d' / f'{name}.PUBLISH').exists():
                continue
            acts = part(name, lst[i:i + 50], sys.argv[2])
            print(name, len(acts), 'acts', sum(len(a['versions']) for a in acts), 'versions', flush=True)
    elif cmd == 'publish':
        print(R.publish(SLUG, sys.argv[2], sys.argv[3]))
