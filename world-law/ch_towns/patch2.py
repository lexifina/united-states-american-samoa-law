from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'ch_cities.py'
s = p.read_text(encoding='utf-8')

old = """                   'restriction on reproducing the content of the website.'),
}
"""
new = """                   'restriction on reproducing the content of the website.'),
    # Gemeinde Unterägeri (i-web): Impressum has no copyright or reproduction clause; "Disclaimer" leads to Datenschutz.
    'unteraegeri': ('ZG-UNTERAEGERI', 'Unterägeri', 'Gemeinde Unterägeri', 'unteraegeri.tlex.ch', 'de', '', 'zug',
                    'Zug', 'https://www.unteraegeri.ch/impressum',
                    'NOCLAUSE:The municipality\\'s own legal notice (https://www.unteraegeri.ch/impressum) places no '
                    'restriction on reproducing the content of the website.'),
    'menzingen': ('ZG-MENZINGEN', 'Menzingen', 'Gemeinde Menzingen', 'menzingen.tlex.ch', 'de', '', 'zug', 'Zug',
                  'https://zg.ch/de/impressumtwo',
                  'NOCLAUSE:The legal notice of the shared Zug web platform the municipality publishes on '
                  '(https://zg.ch/de/impressumtwo) and its usage rules (https://zg.ch/de/nutzungsregelung-datenschutz) '
                  'place no restriction on reproducing the content of the website.'),
    # Gemeinde Weesen (i-web): Impressum has no copyright or reproduction clause.
    'weesen': ('SG-WEESEN', 'Weesen', 'Gemeinde Weesen', 'weesen.tlex.ch', 'de', '', 'st-gallen', 'St. Gallen',
               'https://www.weesen.ch/impressum',
               'NOCLAUSE:The municipality\\'s own legal notice (https://www.weesen.ch/impressum) places no '
               'restriction on reproducing the content of the website.'),
    # Ville de Delémont: Mentions légales hold only a social-media charter; footer "Tous droits réservés", no consent
    # clause.
    'delemont': ('JU-DELEMONT', 'Delémont', 'Ville de Delémont', 'delemont.tlex.ch', 'fr', '', 'jura', 'Jura',
                 'https://www.delemont.ch/fr/Votre-commune/Mentions-legales/Mentions-legales.html',
                 'NOCLAUSE:The city\\'s own legal notice '
                 '(https://www.delemont.ch/fr/Votre-commune/Mentions-legales/Mentions-legales.html) places no '
                 'restriction on reproducing the content of the website; the site footer reads "© 2026 Municipalité '
                 'de Delémont. Tous droits réservés", which the copyright exclusion above qualifies for law texts.'),
}
"""
assert s.count(old) == 1, 'old1'
s = s.replace(old, new)

old2 = """    if not native.startswith(('Stadt ', 'Ville ', 'Città ')):"""
new2 = """    if lang == 'fr':
        readme = readme.replace("the Gemeindeordnung (the city's charter)",
                                "the city's charter (its règlement d'organisation)").replace(
            '("in Kraft seit / von")', '("en vigueur")')
        juris['build'] = juris['build'].replace('Gemeindeordnung', "règlement d'organisation")
    if not native.startswith(('Stadt ', 'Ville ', 'Città ')):"""
assert s.count(old2) == 1, 'old2'
s = s.replace(old2, new2)
p.write_bytes(s.encode('utf-8'))
print('patched')
