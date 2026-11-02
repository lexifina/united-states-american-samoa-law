from pathlib import Path
p = Path(__file__).resolve().parent.parent / 'ch_cities.py'
s = p.read_text(encoding='utf-8')
old = """                 'de Delémont. Tous droits réservés", which the copyright exclusion above qualifies for law texts.'),
}
"""
new = """                 'de Delémont. Tous droits réservés", which the copyright exclusion above qualifies for law texts.'),
    # Wave 3 (DNS sweep of every municipality above ~5,000, 2026-11-01 evening).
    # Gemeinde Ilanz/Glion: Impressum says only "Das Copyright für sämtliche Inhalte dieser Website liegt bei der
    # Gemeinde Ilanz/Glion." (no consent clause).
    'ilanz-glion': ('GR-ILANZ-GLION', 'Ilanz/Glion', 'Gemeinde Ilanz/Glion', 'ilanz-glion.tlex.ch', 'de', '',
                    'graubunden', 'Graubünden', 'https://www.ilanz-glion.ch/impressum',
                    'NOCLAUSE:The municipality\\'s own legal notice (https://www.ilanz-glion.ch/impressum) says only '
                    '"Das Copyright für sämtliche Inhalte dieser Website liegt bei der Gemeinde Ilanz/Glion." and '
                    'places no restriction on reproduction; the copyright exclusion above covers the law texts.'),
    # Gemeinde Ehrendingen (CommunityNet): Impressum, "Rechtliches" and its privacy statement have no clause.
    'ehrendingen': ('AG-EHRENDINGEN', 'Ehrendingen', 'Gemeinde Ehrendingen', 'ehrendingen.tlex.ch', 'de', '',
                    'aargau', 'Aargau', 'https://www.ehrendingen.ch/impressum/',
                    'NOCLAUSE:The municipality\\'s own legal notice (https://www.ehrendingen.ch/impressum/ and '
                    'https://www.ehrendingen.ch/rechtliches/) places no restriction on reproducing the content of '
                    'the website.'),
    # Gemeinde Bad Ragaz (i-web): Impressum without the copyright paragraph.
    'bad-ragaz': ('SG-BAD-RAGAZ', 'Bad Ragaz', 'Gemeinde Bad Ragaz', 'badragaz.tlex.ch', 'de', '', 'st-gallen',
                 'St. Gallen', 'https://www.badragaz.ch/impressum',
                 'NOCLAUSE:The municipality\\'s own legal notice (https://www.badragaz.ch/impressum) places no '
                 'restriction on reproducing the content of the website.'),
    # Gemeinde Ettingen: no Impressum on the site (/de/impressum 404); its Datenschutz page has no clause.
    'ettingen': ('BL-ETTINGEN', 'Ettingen', 'Gemeinde Ettingen', 'ettingen.tlex.ch', 'de', '', 'basel-landschaft',
                 'Basel-Landschaft', 'https://www.ettingen.ch/de/datenschutz',
                 'NOCLAUSE:The municipality\\'s website (https://www.ettingen.ch/) has no legal notice of its own; '
                 'its data-protection page places no restriction on reproducing the content of the website.'),
}
"""
assert s.count(old) == 1
s = s.replace(old, new)
p.write_bytes(s.encode('utf-8'))
print('patched')
