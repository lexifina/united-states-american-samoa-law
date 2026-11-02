from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'ch_cities.py'
s = p.read_text(encoding='utf-8')

old = """            'restriction on reproducing the content of the website.'),
}
"""
new = """            'restriction on reproducing the content of the website.'),
    # Stadt Kloten: Impressum (www.kloten.ch/impressum, i-web) has no copyright or reproduction clause; its only
    # permission rule is for the coat of arms (Wappenschutzgesetz Art. 8). Datenschutz page: none either.
    'kloten': ('ZH-KLOTEN', 'Kloten', 'Stadt Kloten', 'kloten.tlex.ch', 'de', '', 'zurich', 'Zurich',
               'https://www.kloten.ch/impressum',
               'NOCLAUSE:The city\\'s own legal notice (https://www.kloten.ch/impressum) places no restriction on '
               'reproducing the content of the website; its only permission rule concerns the city\\'s coat of arms.'),
    # Gemeinden of the canton of Zug on the shared zg.ch platform: their Impressum and the shared "Nutzungsregelung
    # und Datenschutz" (which names "Internetauftritte ... von Zuger Gemeinden") have no reproduction clause.
    'steinhausen': ('ZG-STEINHAUSEN', 'Steinhausen', 'Gemeinde Steinhausen', 'steinhausen.tlex.ch', 'de', '', 'zug',
                    'Zug', 'https://www.zg.ch/behoerden/gemeinden/steinhausen/verwaltung/kontakt/impressum',
                    'NOCLAUSE:The municipality\\'s own legal notice '
                    '(https://www.zg.ch/behoerden/gemeinden/steinhausen/verwaltung/kontakt/impressum) and the usage '
                    'rules of the shared Zug web platform it is published on '
                    '(https://zg.ch/de/nutzungsregelung-datenschutz) place no restriction on reproducing the content '
                    'of the website.'),
    'huenenberg': ('ZG-HUENENBERG', 'Hünenberg', 'Gemeinde Hünenberg', 'huenenberg.tlex.ch', 'de', '', 'zug', 'Zug',
                   'https://zg.ch/de/impressumtwo',
                   'NOCLAUSE:The legal notice of the shared Zug web platform the municipality publishes on '
                   '(https://zg.ch/de/impressumtwo) and its usage rules (https://zg.ch/de/nutzungsregelung-datenschutz) '
                   'place no restriction on reproducing the content of the website.'),
    # Gemeinde Oberägeri (i-web): Impressum has no copyright or reproduction clause; its only consent rule is the
    # social-media netiquette (posts marked with the Oberägeri brand). "Disclaimer" leads to the Datenschutz page.
    'oberaegeri': ('ZG-OBERAEGERI', 'Oberägeri', 'Gemeinde Oberägeri', 'oberaegeri.tlex.ch', 'de', '', 'zug', 'Zug',
                   'https://www.oberaegeri.ch/impressum',
                   'NOCLAUSE:The municipality\\'s own legal notice (https://www.oberaegeri.ch/impressum) places no '
                   'restriction on reproducing the content of the website.'),
}

CHARTER = re.compile(r'^(Gemeindeordnung|Gemeindeverfassung|Organisationsreglement|R[èe]glement d.organisation)', re.I)
_orig_constitution_sn = C.constitution_sn


def constitution_sn(h):
    \"\"\"A city whose Gemeindeordnung number is not given: the first in-force act whose title names the charter.\"\"\"
    if h.host in {CITIES[c][3] for c in CITIES} and not h.const:
        for x in C.index_entries(h):
            if CHARTER.search(x['title']) and not x.get('abrogated'):
                h.const = x['systematic_number']
                return h.const
        raise RuntimeError(f'{h.slug}: no Gemeindeordnung in the index')
    return _orig_constitution_sn(h)


C.constitution_sn = constitution_sn
"""
assert s.count(old) == 1, 'old1'
s = s.replace(old, new)

old2 = """    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\\n')"""
new2 = """    if not native.startswith(('Stadt ', 'Ville ', 'Città ')):
        readme, lic = (re.sub(r'(?<![-(])\\bcity\\b(?![)-])', 'municipality', x) for x in (readme, lic))
    (repo / 'README.md').write_text(readme, encoding='utf-8', newline='\\n')"""
assert s.count(old2) == 1, 'old2'
s = s.replace(old2, new2)
p.write_bytes(s.encode('utf-8'))
print('patched')
