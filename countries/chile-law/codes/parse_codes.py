"""Phase 2 of Chile (gitlaw-CL-codes): reads the LeyChile cache and writes scripts/chile-law/corpus.d/50-codes.json
(--part codes, the default), corpus.d/60-more.json (--part more), corpus.d/70-batch3.json (--part batch3) or
corpus.d/80-batch4.json (--part batch4), corpus.d/90-batch5.json (--part batch5), corpus.d/95-batch6.json
(--part batch6), corpus.d/97-batch7.json, 98-batch8.json or 99-batch9.json (--part batch7|batch8|batch9), or
corpus.d/99a-batch10.json (--part batch10).

    python -X utf8 scripts/chile-law/codes/parse_codes.py [--part codes|more|batch3|...|batch9] [--acts a,b,...] [--out PATH]

It reuses the main agent's parse.py unchanged (read_version, the credit rules, the law key scheme): it only adds the
verified idNorma chains (codes/fetch_codes.py) and the act metadata of the codes, then runs parse.act_versions on
each. No network. The part is written atomically (.tmp, then rename). Law keys shared with corpus.json must name the
same LeyChile norm; the script stops if one does not.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
import fetch  # noqa: E402
import parse  # noqa: E402
from fetch_codes import CHAINS  # noqa: E402
import anachronism  # noqa: E402

L = parse.LEYCHILE
META = {
    'codigo-penal': {'short': 'CP', 'title': 'Código Penal', 'url': L + '1984', 'first_law': True},
    'codigo-comercio': {'short': 'CCom', 'title': 'Código de Comercio', 'url': L + '1974', 'first_law': True},
    'codigo-trabajo': {'short': 'CT', 'title': 'Código del Trabajo', 'url': L + '207436', 'first_law': False},
    'codigo-procedimiento-civil': {'short': 'CPC', 'title': 'Código de Procedimiento Civil', 'url': L + '22740',
                                   'first_law': True},
    'codigo-procesal-penal': {
        'short': 'CPP', 'title': 'Código Procesal Penal', 'url': L + '176595', 'first_law': True,
        'first': ('2000-12-16', 'The Código Procesal Penal (Ley 19.696, published in the Diario Oficial on 12 October '
                  '2000) says in its own art. 484 when it takes effect: "regirá para las Regiones de Coquimbo y de la '
                  'Araucanía desde el 16 de diciembre de 2000", and for the other regions from 16 October 2001, 2002 '
                  'and 2003 (dates later changed by amendment; today\'s text has the Región Metropolitana from 16 '
                  'June 2005). Its first '
                  'version is dated 2000-12-16, the first day it was in force anywhere, not the publication day '
                  'LeyChile shows; the regional phases are in the text of art. 484, not in the dates.')},
}
META.update({
    'codigo-tributario': {'short': 'CTrib', 'title': 'Código Tributario', 'url': L + '6374', 'first_law': True},
    'codigo-sanitario': {'short': 'CSan', 'title': 'Código Sanitario', 'url': L + '5595', 'first_law': True},
    'codigo-aguas': {'short': 'CAguas', 'title': 'Código de Aguas', 'url': L + '5605', 'first_law': True},
    'ley-18046': {'short': 'Ley 18.046', 'title': 'Ley 18.046 sobre sociedades anónimas', 'url': L + '29473',
                  'first_law': True},
    'ley-19496': {'short': 'Ley 19.496', 'title': 'Ley 19.496 sobre protección de los derechos de los consumidores',
                  'url': L + '1160403', 'first_law': True},
})
META.update({
    'codigo-organico-tribunales': {'short': 'COT', 'title': 'Código Orgánico de Tribunales', 'url': L + '25563',
                                   'first_law': True},
    'codigo-mineria': {'short': 'CMin', 'title': 'Código de Minería', 'url': L + '29668', 'first_law': True},
    'codigo-aeronautico': {'short': 'CAer', 'title': 'Código Aeronáutico', 'url': L + '30287', 'first_law': True},
    'codigo-justicia-militar': {'short': 'CJM', 'title': 'Código de Justicia Militar', 'url': L + '18914',
                                'first_law': False},
    'ley-20393': {'short': 'Ley 20.393', 'title': 'Ley 20.393 sobre responsabilidad penal de las personas jurídicas',
                  'url': L + '1008668', 'first_law': True},
    'ley-19880': {'short': 'Ley 19.880', 'title': 'Ley 19.880 de bases de los procedimientos administrativos',
                  'url': L + '210676', 'first_law': True},
    'ley-18010': {'short': 'Ley 18.010', 'title': 'Ley 18.010 sobre operaciones de crédito de dinero',
                  'url': L + '29438', 'first_law': True},
})
META.update({
    'ley-18695': {'short': 'Ley 18.695', 'title': 'Ley 18.695 orgánica constitucional de municipalidades',
                  'url': L + '251693', 'first_law': True},
    'ley-18575': {'short': 'Ley 18.575', 'title': 'Ley 18.575 orgánica constitucional de bases generales de la '
                  'administración del Estado', 'url': L + '191865', 'first_law': True},
    'ley-20000': {'short': 'Ley 20.000', 'title': 'Ley 20.000 sobre tráfico ilícito de estupefacientes y sustancias '
                  'sicotrópicas', 'url': L + '235507', 'first_law': True},
    'ley-17336': {'short': 'Ley 17.336', 'title': 'Ley 17.336 sobre propiedad intelectual', 'url': L + '28933',
                  'first_law': True},
    'ley-19039': {'short': 'Ley 19.039', 'title': 'Ley 19.039 de propiedad industrial', 'url': L + '1179684',
                  'first_law': True},
    'ley-18045': {'short': 'Ley 18.045', 'title': 'Ley 18.045 de mercado de valores', 'url': L + '29472',
                  'first_law': True},
    'ley-20720': {'short': 'Ley 20.720', 'title': 'Ley 20.720 de reorganización y liquidación de empresas y personas',
                  'url': L + '1058072', 'first_law': True},
    'dfl-1-2005-salud': {'short': 'DFL 1 2005 (Salud)', 'title': 'DFL 1 de 2005 del Ministerio de Salud (texto '
                         'refundido del DL 2.763 de 1979 y de las leyes 18.933 y 18.469)', 'url': L + '249177',
                         'first_law': False},
    'ley-16744': {'short': 'Ley 16.744', 'title': 'Ley 16.744 sobre accidentes del trabajo y enfermedades '
                  'profesionales', 'url': L + '28650', 'first_law': True},
})
META.update({
    'ley-19300': {'short': 'Ley 19.300', 'title': 'Ley 19.300 sobre bases generales del medio ambiente',
                  'url': L + '30667', 'first_law': True},
    'ley-18834': {'short': 'Ley 18.834', 'title': 'Ley 18.834 sobre Estatuto Administrativo', 'url': L + '236392',
                  'first_law': True},
    'dl-3500': {'short': 'DL 3.500', 'title': 'DL 3.500 que establece el nuevo sistema de pensiones',
                'url': L + '7147', 'first_law': True},
    'ley-21595': {'short': 'Ley 21.595', 'title': 'Ley 21.595 de delitos económicos', 'url': L + '1195119',
                  'first_law': True},
    'ley-19913': {'short': 'Ley 19.913', 'title': 'Ley 19.913 que crea la Unidad de Análisis Financiero',
                  'url': L + '219119', 'first_law': True},
    'ley-18290': {'short': 'Ley 18.290', 'title': 'Ley 18.290 de Tránsito', 'url': L + '1007469', 'first_law': True},
    'ley-19968': {'short': 'Ley 19.968', 'title': 'Ley 19.968 que crea los Tribunales de Familia',
                  'url': L + '229557', 'first_law': True},
    'ley-20084': {'short': 'Ley 20.084', 'title': 'Ley 20.084 sobre responsabilidad penal de los adolescentes',
                  'url': L + '244803', 'first_law': True},
    'ley-19947': {'short': 'Ley 19.947', 'title': 'Ley 19.947 de Matrimonio Civil', 'url': L + '225128',
                  'first_law': True},
    'ley-14908': {'short': 'Ley 14.908', 'title': 'Ley 14.908 sobre abandono de familia y pago de pensiones '
                  'alimenticias', 'url': L + '172986', 'first_law': True},
})
META.update({
    'ley-19537': {'short': 'Ley 19.537', 'title': 'Ley 19.537 sobre copropiedad inmobiliaria', 'url': L + '81505',
                  'first_law': True},
    'ley-18101': {'short': 'Ley 18.101', 'title': 'Ley 18.101 sobre arrendamiento de predios urbanos',
                  'url': L + '29526', 'first_law': True},
    'ley-20285': {'short': 'Ley 20.285', 'title': 'Ley 20.285 sobre acceso a la información pública',
                  'url': L + '276363', 'first_law': True},
    'ley-18700': {'short': 'Ley 18.700', 'title': 'Ley 18.700 orgánica constitucional sobre votaciones populares y '
                  'escrutinios', 'url': L + '1108229', 'first_law': True},
    'ley-20584': {'short': 'Ley 20.584', 'title': 'Ley 20.584 sobre derechos y deberes de las personas en relación '
                  'con su atención de salud', 'url': L + '1039348', 'first_law': True},
    'ley-19733': {'short': 'Ley 19.733', 'title': 'Ley 19.733 sobre libertades de opinión e información y ejercicio '
                  'del periodismo', 'url': L + '186049', 'first_law': True},
    'ley-20529': {'short': 'Ley 20.529', 'title': 'Ley 20.529 sobre el sistema nacional de aseguramiento de la '
                  'calidad de la educación', 'url': L + '1028635', 'first_law': True},
    'ley-21091': {'short': 'Ley 21.091', 'title': 'Ley 21.091 sobre educación superior', 'url': L + '1118991',
                  'first_law': True},
})
META.update({   # part 97-batch7 (gitlaw-CL-2, 2026-10-29)
    'dl-824': {'short': 'DL 824', 'title': 'DL 824 que aprueba la Ley sobre Impuesto a la Renta', 'url': L + '6368',
               'first_law': True},
    'dl-825': {'short': 'DL 825', 'title': 'DL 825 sobre Impuesto a las Ventas y Servicios', 'url': L + '6369',
               'first_law': True},
    'ley-21325': {'short': 'Ley 21.325', 'title': 'Ley 21.325 de Migración y Extranjería', 'url': L + '1158549',
                  'first_law': True},
    'ley-19886': {'short': 'Ley 19.886', 'title': 'Ley 19.886 de bases sobre contratos administrativos de suministro '
                  'y prestación de servicios', 'url': L + '213004', 'first_law': True},
    'ley-18840': {'short': 'Ley 18.840', 'title': 'Ley 18.840 orgánica constitucional del Banco Central de Chile',
                  'url': L + '30216', 'first_law': True},
    'ley-20066': {'short': 'Ley 20.066', 'title': 'Ley 20.066 de violencia intrafamiliar', 'url': L + '242648',
                  'first_law': True},
    'ley-18314': {'short': 'Ley 18.314', 'title': 'Ley 18.314 que determina conductas terroristas y fija su penalidad',
                  'url': L + '29731', 'first_law': True},
    'ley-17798': {'short': 'Ley 17.798', 'title': 'Ley 17.798 sobre control de armas', 'url': L + '13031',
                  'first_law': True},
    'ley-20609': {'short': 'Ley 20.609', 'title': 'Ley 20.609 que establece medidas contra la discriminación',
                  'url': L + '1042092', 'first_law': True},
    'ley-19799': {'short': 'Ley 19.799', 'title': 'Ley 19.799 sobre documentos electrónicos, firma electrónica y '
                  'servicios de certificación de dicha firma', 'url': L + '196640', 'first_law': True},
})
META.update({   # part 98-batch8 (gitlaw-CL-2, 2026-10-29)
    'ley-20370': {'short': 'Ley 20.370', 'title': 'Ley 20.370 General de Educación', 'url': L + '1014974',
                  'first_law': True},
    'ley-20730': {'short': 'Ley 20.730', 'title': 'Ley 20.730 que regula el lobby y las gestiones que representen '
                  'intereses particulares ante las autoridades y funcionarios', 'url': L + '1060115', 'first_law': True},
    'ley-21430': {'short': 'Ley 21.430', 'title': 'Ley 21.430 sobre garantías y protección integral de los derechos de '
                  'la niñez y adolescencia', 'url': L + '1173643', 'first_law': True},
    'ley-19253': {'short': 'Ley 19.253', 'title': 'Ley 19.253 sobre protección, fomento y desarrollo de los indígenas',
                  'url': L + '30620', 'first_law': True},
    'ley-20422': {'short': 'Ley 20.422', 'title': 'Ley 20.422 sobre igualdad de oportunidades e inclusión social de '
                  'personas con discapacidad', 'url': L + '1010903', 'first_law': True},
    'ley-10336': {'short': 'Ley 10.336', 'title': 'Ley 10.336 de organización y atribuciones de la Contraloría General '
                  'de la República', 'url': L + '18995', 'first_law': True},
    'ley-17997': {'short': 'Ley 17.997', 'title': 'Ley 17.997 orgánica constitucional del Tribunal Constitucional',
                  'url': L + '1016103', 'first_law': True},
    'ley-19640': {'short': 'Ley 19.640', 'title': 'Ley 19.640 orgánica constitucional del Ministerio Público',
                  'url': L + '145437', 'first_law': True},
    'ley-18918': {'short': 'Ley 18.918', 'title': 'Ley 18.918 orgánica constitucional del Congreso Nacional',
                  'url': L + '30289', 'first_law': True},
    'ley-21442': {'short': 'Ley 21.442', 'title': 'Ley 21.442 que aprueba nueva ley de copropiedad inmobiliaria',
                  'url': L + '1174663', 'first_law': True},
    'ley-19418': {'short': 'Ley 19.418', 'title': 'Ley 19.418 sobre juntas de vecinos y demás organizaciones '
                  'comunitarias', 'url': L + '70040', 'first_law': True},
    'ley-3918': {'short': 'Ley 3.918', 'title': 'Ley 3.918 sobre sociedades de responsabilidad limitada',
                 'url': L + '24349', 'first_law': True},
    'ley-19857': {'short': 'Ley 19.857', 'title': 'Ley 19.857 que autoriza el establecimiento de empresas individuales '
                  'de responsabilidad limitada', 'url': L + '207588', 'first_law': True},
    'ley-21521': {'short': 'Ley 21.521', 'title': 'Ley 21.521 que promueve la competencia e inclusión financiera a '
                  'través de la innovación y tecnología en la prestación de servicios financieros (Ley Fintec)',
                  'url': L + '1187323', 'first_law': True},
    'ley-20500': {'short': 'Ley 20.500', 'title': 'Ley 20.500 sobre asociaciones y participación ciudadana en la '
                  'gestión pública', 'url': L + '1023143', 'first_law': True},
})
META.update({   # part 99-batch9 (gitlaw-CL-2, 2026-10-29); from 2000-05-30 each is an article of DFL 1 of 2000
    'ley-4808': {'short': 'Ley 4.808', 'title': 'Ley 4.808 sobre Registro Civil', 'url': L + '172986',
                 'first_law': True},
    'ley-17344': {'short': 'Ley 17.344', 'title': 'Ley 17.344 que autoriza el cambio de nombres y apellidos',
                  'url': L + '172986', 'first_law': True},
    'ley-16618': {'short': 'Ley 16.618', 'title': 'Ley 16.618 de Menores', 'url': L + '172986', 'first_law': True},
    'ley-16271': {'short': 'Ley 16.271', 'title': 'Ley 16.271 de impuesto a las herencias, asignaciones y donaciones',
                  'url': L + '172986', 'first_law': True},
})
META.update({   # part 99a-batch10 (gitlaw-CL-3, 2026-10-29)
    'dfl-458': {'short': 'DFL 458', 'title': 'DFL 458 que aprueba la Ley General de Urbanismo y Construcciones',
                'url': L + '13560', 'first_law': True},
    'ley-general-bancos': {'short': 'LGB', 'title': 'Ley General de Bancos', 'url': L + '83135', 'first_law': True},
    'dl-211': {'short': 'DL 211', 'title': 'DL 211 que fija normas para la defensa de la libre competencia',
               'url': L + '236106', 'first_law': True},
    'ley-18892': {'short': 'Ley 18.892', 'title': 'Ley 18.892 General de Pesca y Acuicultura', 'url': L + '13315',
                  'first_law': True},
    'ley-18168': {'short': 'Ley 18.168', 'title': 'Ley 18.168 General de Telecomunicaciones', 'url': L + '29591',
                  'first_law': True},
    'ley-19175': {'short': 'Ley 19.175', 'title': 'Ley 19.175 orgánica constitucional sobre gobierno y administración '
                  'regional', 'url': L + '243771', 'first_law': True},
    'ley-19070': {'short': 'Ley 19.070', 'title': 'Ley 19.070 que aprueba el Estatuto de los Profesionales de la '
                  'Educación', 'url': L + '60439', 'first_law': True},
    'ley-20600': {'short': 'Ley 20.600', 'title': 'Ley 20.600 que crea los Tribunales Ambientales', 'url': L + '1041361',
                  'first_law': True},
    'ley-18287': {'short': 'Ley 18.287', 'title': 'Ley 18.287 que establece el procedimiento ante los juzgados de '
                  'policía local', 'url': L + '29705', 'first_law': True},
    'ley-15231': {'short': 'Ley 15.231', 'title': 'Ley 15.231 sobre organización y atribuciones de los juzgados de '
                  'policía local', 'url': L + '12193', 'first_law': True},
    'ley-19728': {'short': 'Ley 19.728', 'title': 'Ley 19.728 que establece un seguro de desempleo', 'url': L + '184979',
                  'first_law': True},
    'ley-20880': {'short': 'Ley 20.880', 'title': 'Ley 20.880 sobre probidad en la función pública y prevención de los '
                  'conflictos de intereses', 'url': L + '1086062', 'first_law': True},
    'ley-19983': {'short': 'Ley 19.983', 'title': 'Ley 19.983 que regula la transferencia y otorga mérito ejecutivo a '
                  'copia de la factura', 'url': L + '233421', 'first_law': True},
    'ley-18603': {'short': 'Ley 18.603', 'title': 'Ley 18.603 orgánica constitucional de los partidos políticos',
                  'url': L + '1107684', 'first_law': True},
    'ley-17322': {'short': 'Ley 17.322', 'title': 'Ley 17.322 sobre cobranza judicial de cotizaciones, aportes y multas '
                  'de las instituciones de seguridad social', 'url': L + '28919', 'first_law': True},
    'ley-18097': {'short': 'Ley 18.097', 'title': 'Ley 18.097 orgánica constitucional sobre concesiones mineras',
                  'url': L + '29522', 'first_law': True},
    'ley-19378': {'short': 'Ley 19.378', 'title': 'Ley 19.378 que establece el estatuto de atención primaria de salud '
                  'municipal', 'url': L + '30745', 'first_law': True},
    'ley-21040': {'short': 'Ley 21.040', 'title': 'Ley 21.040 que crea el Sistema de Educación Pública',
                  'url': L + '1111237', 'first_law': True},
    'ley-20712': {'short': 'Ley 20.712', 'title': 'Ley 20.712 sobre administración de fondos de terceros y carteras '
                  'individuales', 'url': L + '1057895', 'first_law': True},
    'ley-20659': {'short': 'Ley 20.659', 'title': 'Ley 20.659 que simplifica el régimen de constitución, modificación y '
                  'disolución de las sociedades comerciales', 'url': L + '1048718', 'first_law': True},
})
# Each part file this script writes: its acts, its path, and the decisions that are its own.
PARTS = {
    'codes': {
        'acts': 'codigo-penal,codigo-comercio,codigo-trabajo,codigo-procedimiento-civil,codigo-procesal-penal',
        'out': ROOT / 'corpus.d' / '50-codes.json',
        'decisions': [
            'Código Penal, Código de Comercio, Código del Trabajo, Código de Procedimiento Civil and Código Procesal '
            'Penal (corpus.d/50-codes.json) are parsed by the same parse.py rules as the Constitution, from the LeyChile '
            'norms verified on 2026-10-28 with get_cadena_refundidos and get_versiones: CP 1984, CCom 1974, CT 3471 '
            '(DFL 1 of 1994) then 207436 (DFL 1 of 2003), CPC 22740 (Ley 1.552), CPP 176595 (Ley 19.696).',
            'Código del Trabajo: LeyChile keeps the Código del Trabajo of 1987 (Ley 18.620, idNorma 30011) in one '
            'undated version only, so its history from 1987 to 1994 is not available; the act starts with the texto '
            'refundido of DFL 1 of 1994 as the oldest version available, and DFL 1 of 2003 is its next text.',
        ],
    },
    'batch3': {
        'acts': 'codigo-organico-tribunales,codigo-mineria,codigo-aeronautico,codigo-justicia-militar,ley-20393,'
                'ley-19880,ley-18010',
        'out': ROOT / 'corpus.d' / '70-batch3.json',
        'decisions': [
            'Código Orgánico de Tribunales, Código de Minería, Código Aeronáutico, Código de Justicia Militar, Ley '
            '20.393, Ley 19.880 and Ley 18.010 (corpus.d/70-batch3.json) are parsed by the same parse.py rules as the '
            'Constitution, from the LeyChile norms verified on 2026-10-28 with get_cadena_refundidos and get_versiones: '
            'Ley 7.421 of 1943 (25563), Ley 18.248 (29668), Ley 18.916 (30287), Decreto 2.226 of 1944 (18914), Ley '
            '20.393 (1008668), Ley 19.880 (210676) and Ley 18.010 (29438).',
            'Código de Justicia Militar: LeyChile keeps DL 806 of 1925 (idNorma 6363), which approved the code, in one '
            'version only (1926-03-01), so the act starts with Decreto 2.226 of 1944, which fixed the text of the code, '
            'as the oldest version available.',
        ],
    },
    'batch4': {
        'acts': 'ley-18695,ley-18575,ley-20000,ley-17336,ley-19039,ley-18045,ley-20720,dfl-1-2005-salud,ley-16744',
        'out': ROOT / 'corpus.d' / '80-batch4.json',
        'decisions': [
            'Leyes 18.695, 18.575, 20.000, 17.336, 19.039, 18.045, 20.720 and 16.744 and DFL 1 de 2005 (Salud) '
            '(corpus.d/80-batch4.json) are parsed by the same parse.py rules as the Constitution, from the LeyChile '
            'norms verified on 2026-10-28 with get_cadena_refundidos and get_versiones. Where a law was re-enacted as '
            'a texto refundido, LeyChile continues it under the new norm and so do we: Ley 18.695 = 30077, then '
            'Decreto 662 of 1992 (14962), DFL 2 of 2000 (150973), DFL 1 of 2002 (197482) and DFL 1 of 2006 (251693); '
            'Ley 18.575 = 29967, then DFL 1 of 2001 (191865); Ley 19.039 = 30406, then DFL 3 of 2006 (250708) and DFL 4 '
            'of 2022 (1179684). The others are one norm each: 235507, 28933, 29472, 1058072, 249177, 28650.',
            'DFL 1 de 2005 (Salud) fixes in one text DL 2.763 of 1979, Ley 18.933 and Ley 18.469, whose own histories '
            'are separate LeyChile norms; the act starts with the DFL as the oldest version available.',
        ],
    },
    'batch5': {
        'acts': 'ley-19300,ley-18834,dl-3500,ley-21595,ley-19913,ley-18290,ley-19968,ley-20084,ley-19947,ley-14908',
        'out': ROOT / 'corpus.d' / '90-batch5.json',
        'decisions': [
            'Leyes 19.300, 18.834, 21.595, 19.913, 18.290, 19.968, 20.084, 19.947 and 14.908 and DL 3.500 '
            '(corpus.d/90-batch5.json) are parsed by the same parse.py rules as the Constitution, from the LeyChile '
            'norms verified on 2026-10-28 with get_cadena_refundidos and get_versiones: 30667; Ley 18.834 = 30210, then '
            'DFL 29 of 2005 (236392); DL 3.500 = 7147; 1195119; 219119; Ley 18.290 = 29708, then DFL 1 of 2009 '
            '(1007469); 229557; 244803; Ley 19.947 = 225128; Ley 14.908 = 27977, then DFL 1 of 2000 (172986).',
            'Ley 14.908: from 2000-05-30 its text is article 7 of DFL 1 of 2000 (LeyChile idNorma 172986), which also '
            'fixes the Código Civil (its art. 2) and four other laws; only article 7 is read, and versions of the DFL '
            'in which only its other articles changed are left out as identical.',
            'Ley 20.084: its own art. 1 transitorio defers its entry into force ("La presente ley entrará en vigencia '
            'dieciocho meses después de su publicación", today\'s text), and it was amended before that day; the '
            'corpus keeps the days LeyChile gives its versions, from publication, so the deferral is in the text, '
            'not in the dates. LeyChile\'s unversioned page for it shows the version waiting for an event '
            '(2222-02-02), which is left out; the text in force on 2026-10-28 is the version of 2026-01-13.',
        ],
    },
    'batch6': {
        'acts': 'ley-19537,ley-18101,ley-20285,ley-18700,ley-20584,ley-19733,ley-20529,ley-21091',
        'out': ROOT / 'corpus.d' / '95-batch6.json',
        'decisions': [
            'Leyes 19.537, 18.101, 20.285, 18.700, 20.584, 19.733, 20.529 and 21.091 (corpus.d/95-batch6.json) are '
            'parsed by the same parse.py rules as the Constitution, from the LeyChile norms found with '
            'get_norma_json?idLey=<number> (metadatos.id_norma) and verified on 2026-10-28 with get_cadena_refundidos '
            'and get_versiones: 81505, 29526, 276363, Ley 18.700 = 30082 then DFL 2 of 2017 (1108229), 1039348, '
            '186049, 1028635 and 1118991.',
        ],
    },
    'batch7': {
        'acts': 'dl-824,dl-825,ley-21325,ley-19886,ley-18840,ley-20066,ley-18314,ley-17798,ley-20609,ley-19799',
        'out': ROOT / 'corpus.d' / '97-batch7.json',
        'decisions': [
            'DL 824 and DL 825 of 1974 and Leyes 21.325, 19.886, 18.840, 20.066, 18.314, 17.798, 20.609 and 19.799 '
            '(corpus.d/97-batch7.json) are parsed by the same parse.py rules as the Constitution, from the LeyChile '
            'norms found with get_norma_json?idLey=<number> (metadatos.id_norma) or get_cadena_refundidos and '
            'verified on 2026-10-29 with get_cadena_refundidos and get_versiones: 6368, 6369, 1158549, 213004, 30216, '
            '242648, 29731, Ley 17.798 = 29291 then Decreto 400 of 1978 (13031, texto refundido), 1042092 and '
            '196640. Retrieved from LeyChile on 2026-10-29; the repository\'s docs date stays 2026-10-28, the day the '
            'other acts were retrieved.',
            'Ley 20.066: its art. 25 says "La presente ley comenzará a regir el 1 de Octubre de 2005", a day before its '
            'publication in the Diario Oficial (2005-10-07); a law cannot bind before it is published (Código Civil '
            'arts. 7 and 9), so its first version keeps LeyChile\'s day, 2005-10-07.',
            'Ley 21.325: "Esta ley entrará en vigencia una vez publicado su reglamento" (art. 11 transitorio); '
            'LeyChile already dates its first version from that day, 2022-02-12, not from publication (2021-04-20).',
        ],
    },
    'batch8': {
        'acts': 'ley-20370,ley-20730,ley-21430,ley-19253,ley-20422,ley-10336,ley-17997,ley-19640,ley-18918,ley-21442,'
                'ley-19418,ley-3918,ley-19857,ley-21521,ley-20500',
        'out': ROOT / 'corpus.d' / '98-batch8.json',
        'decisions': [
            'Leyes 20.370, 20.730, 21.430, 19.253, 20.422, 10.336, 17.997, 19.640, 18.918, 21.442, 19.418, 3.918, '
            '19.857, 21.521 and 20.500 (corpus.d/98-batch8.json) are parsed by the same parse.py rules as the '
            'Constitution, from the LeyChile norms found with get_norma_json?idLey=<number> (metadatos.id_norma) and '
            'verified on 2026-10-29 with get_cadena_refundidos and get_versiones. Where a law was re-enacted as a '
            'texto refundido, LeyChile continues it under the new norm and so do we: Ley 20.370 = 1006043, then DFL 2 '
            'of 2009, published 2010-07-02 (1014974); Ley 10.336 = 26356, then Decreto 2.421 of 1964 (18995); Ley 17.997 = 29427, then DFL 5 '
            'of 2010 (1016103); Ley 19.418 = 30785, then Decreto 58 of 1997 (70040). The others are one norm each: '
            '1060115, 1173643, 30620, 1010903, 145437, 30289, 1174663, 24349, 207588, 1187323, 1023143. Retrieved '
            'from LeyChile on 2026-10-29; the repository\'s docs date stays 2026-10-28.',
            'Ley 20.370 (Ley General de Educación): LeyChile\'s chain of textos refundidos starts with Ley 18.962 '
            '(LOCE, 1990) and DFL 1 of 2005, whose remaining rules DFL 2 of 2009 took in; the LOCE is a different law, '
            'so the act starts with Ley 20.370 as enacted (2009-09-12).',
        ],
    },
    'batch9': {
        'acts': 'ley-4808,ley-17344,ley-16618,ley-16271',
        'out': ROOT / 'corpus.d' / '99-batch9.json',
        'decisions': [
            'Leyes 4.808, 17.344, 16.618 and 16.271 (corpus.d/99-batch9.json) are parsed by the same parse.py rules as '
            'the Constitution, from the LeyChile norms found with get_norma_json?idLey=<number> (metadatos.id_norma) '
            'and verified on 2026-10-29 with get_cadena_refundidos and get_versiones: 24928, 28940, 28581 and 28367, '
            'each continued from 2000-05-30 by DFL 1 of 2000 (172986), which fixes their texts in its arts. 3, 4, 6 '
            'and 8 (as it fixes the Código Civil in art. 2 and Ley 14.908 in art. 7). Only the act\'s own article of '
            'the DFL is read, and versions of the DFL in which only its other articles changed are left out as '
            'identical. Retrieved from LeyChile on 2026-10-29; the repository\'s docs date stays 2026-10-28.',
        ],
    },
    'batch10': {
        'acts': 'dfl-458,ley-general-bancos,dl-211,ley-18892,ley-18168,ley-19175,ley-19070,ley-20600,ley-18287,'
                'ley-15231,ley-19728,ley-20880,ley-19983,ley-18603,ley-17322,ley-18097,ley-19378,ley-21040,ley-20712,'
                'ley-20659',
        'out': ROOT / 'corpus.d' / '99a-batch10.json',
        'decisions': [
            'DFL 458, the Ley General de Bancos, DL 211 and Leyes 18.892, 18.168, 19.175, 19.070, 20.600, 18.287, '
            '15.231, 19.728, 20.880, 19.983, 18.603, 17.322, 18.097, 19.378, 21.040, 20.712 and 20.659 '
            '(corpus.d/99a-batch10.json) are parsed by the same parse.py rules as the Constitution, from the LeyChile '
            'norms found with get_norma_json?idLey=<number> (metadatos.id_norma) or get_cadena_refundidos and '
            'verified on 2026-10-29 with get_cadena_refundidos and get_versiones. Where a law was re-enacted as a '
            'texto refundido, LeyChile continues it under the new norm and so do we: Ley General de Bancos = DFL 252 '
            'of 1960 (5205), then DFL 3 of 1997 (83135); DL 211 = 5872, then Decreto 511 of 1980 (74808) and DFL 1 '
            'of 2004, published 2005 (236106); Ley 18.892 = 30265, then Decreto 430 of 1991, published 1992 (13315); '
            'Ley 19.175 = 30542, then DFL 1 of 2005 (243771); Ley 19.070 = 30437, then DFL 1 of 1996, published 1997 '
            '(60439); Ley 15.231 = 28104, then Decreto 307 of 1978 (12193); Ley 18.603 = 29994, then DFL 4 of 2017 '
            '(1107684). The others are one norm each: DFL 458 (13560), 29591, 1041361, 29705, 184979, 1086062, '
            '233421, 28919, 29522, 30745, 1111237, 1057895, 1048718. Retrieved from LeyChile on 2026-10-29; the '
            'repository\'s docs date stays 2026-10-28.',
            'Ley General de Bancos: LeyChile\'s chain of textos refundidos also lists DL 1.097 of 1975 (6484, the '
            'Superintendencia de Bancos), which DFL 3 of 1997 took into the same text; it is a different law, so the '
            'act follows DFL 252 and then DFL 3, and the DL 1.097 rules arrive with DFL 3.',
        ],
    },
    'more': {
        'acts': 'codigo-tributario,codigo-sanitario,codigo-aguas,ley-18046,ley-19496',
        'out': ROOT / 'corpus.d' / '60-more.json',
        'decisions': [
            'Código Tributario, Código Sanitario, Código de Aguas, Ley 18.046 and Ley 19.496 (corpus.d/60-more.json) '
            'are parsed by the same parse.py rules as the Constitution, from the LeyChile norms verified on 2026-10-28 '
            'with get_cadena_refundidos and get_versiones: DL 830 of 1974 (6374), DFL 725 of 1968 (5595), DFL 1.122 of '
            '1981 (5605), Ley 18.046 (29473), and Ley 19.496 (61438) followed by its texto refundido, DFL 3 of 2021 '
            '(1160403).',
        ],
    },
}
DEFAULT_ACTS = PARTS['codes']['acts']
OUT = PARTS['codes']['out']


STARTS: dict[str, tuple[str, list[str]]] = {}
EVENT_DROPPED: set[tuple[int, str, str]] = set()
# Part 99a-batch10: acts added after 76 acts were published whose LeyChile history starts before 1970. Git cannot date
# a commit before 1970, so the builder dates such commits 1970-01-01 plus one second per commit, in order; a new
# pre-1970 commit would move the placeholder second of every published pre-1970 commit after it. These acts start at
# their first LeyChile version from 1970 on (oldest version available), so the published commits keep their dates.
FROM_1970 = {'ley-general-bancos', 'ley-15231'}
LATE: dict[str, str] = {}
ORIGINAL_VERSIONS: list = []


def setup(slugs: list[str]) -> None:
    """Registers the chains and metadata, and cuts each code's history where LeyChile's versions stop being anachronistic
    (codes/anachronism.py): the versions before that day are left out, and the act's first version is then the oldest
    version available (first_law null), not the act as enacted."""
    fetch.ACTS.update(CHAINS)
    parse.ACT_META.update(META)
    if not getattr(parse.read_version, 'rekeyed', False):
        parse.read_version = rekeyed(parse.read_version)
        parse.width_for = part_width(parse.width_for)
    for s in slugs:
        CURRENT['act'] = s
        day, ev = anachronism.start_day(s)
        if day:
            STARTS[s] = (day, ev)
            parse.ACT_META[s] = dict(parse.ACT_META[s], first_law=False)
            norms = [n for n in CHAINS[s] if fetch.versions(n, offline=True)[-1]['@vigenteDesde'] >= day]
            fetch.ACTS[s] = norms
        elif s in FROM_1970:
            day = min(v['@vigenteDesde'] for n in CHAINS[s] for v in fetch.versions(n, offline=True)
                      if v['@vigenteDesde'] >= '1970-01-01')
            LATE[s] = day
            parse.ACT_META[s] = dict(parse.ACT_META[s], first_law=False)
            fetch.ACTS[s] = [n for n in CHAINS[s] if fetch.versions(n, offline=True)[-1]['@vigenteDesde'] >= day]
    cut = {n: STARTS[s][0] for s in STARTS for n in fetch.ACTS[s]}
    cut.update({n: LATE[s] for s in LATE for n in fetch.ACTS[s]})
    original = fetch.versions
    ORIGINAL_VERSIONS[:] = [original]

    def versions(id_norma: int, offline: bool = False) -> list[dict]:
        vs = original(id_norma, offline)
        out = []
        for v in vs:
            t = v.get('@tipoVersion') or ''
            if t != 'Con Vigencia Diferida por Evento' and ('Diferida por Evento' in t
                                                           or v['@vigenteDesde'] >= '2222'):
                # parse.py leaves out only the exact "Con Vigencia Diferida por Evento"; a version waiting for an
                # event under another wording, or under none (Ley 20.084's is typed "Última Versión"), is dated
                # 2222-02-02 by LeyChile and cannot be dated either.
                EVENT_DROPPED.add((id_norma, v['@vigenteDesde'], t))
                continue
            out.append(v)
        return [v for v in out if v['@vigenteDesde'] >= cut[id_norma]] if id_norma in cut else out
    fetch.versions = versions


ART_LINE = re.compile(r'(?i)^(art[íi]culo\s+\d+\s*(?:' + parse.SUFFIX + r')?(?:\s+[A-Z])?)\b')


def rekeyed(read_version):
    """LeyChile's table of contents of some old texts names several leaves alike (DFL 1 of 1994 calls the leaves of
    arts. 40 bis A to 40 bis D all "Artículo 40"), so parse.py keys them art-040-2, art-040-3... Such a collision key
    is replaced by the key of the article name the leaf's own text starts with ("Artículo 40 bis A.-"), when that key
    is free, so the file of each article stays the same across versions."""
    def wrapped(raw, width, part=None):
        if part is None and norm_part(norm_of(raw)) is not None:
            part = norm_part(norm_of(raw))
        if part is None:
            raw = unwrap(raw)
        r = read_version(raw, width, part)
        if part is None and norm_of(raw) in OWN_ARTICLES:
            r['units'] = own_articles(r['units'], OWN_ARTICLES[norm_of(raw)])
        units = r['units']
        out = {}
        for k, u in units.items():
            if re.search(r'-\d+$', k) and re.sub(r'-\d+$', '', k) in units:
                for line in u['text'].splitlines():
                    m = ART_LINE.match(line)
                    if m:
                        nk, label, kind = parse.unit_key(m.group(1), width)
                        if (nk == re.sub(r'-\d+$', '', k) or nk in units) and lettered(line, width):
                            nk, label, kind = lettered(line, width)
                        if nk != re.sub(r'-\d+$', '', k) and nk not in units and nk not in out:
                            u = dict(u, label=label, kind=kind)
                            k = nk
                        break
            out[k] = u
        r['units'] = out
        return r
    wrapped.rekeyed = True
    return wrapped


LETTERED = re.compile(r'(?i)^art[íi]culo\s+(\d+)\s*(?:(bis|ter|quater|quáter)\s+)?([a-zñ])\s*[.°º-]')


def lettered(line: str, width: int) -> tuple[str, str, str] | None:
    """(key, label, kind) for an article named with a capital letter ("Artículo 54 O.-", "Artículo 54 Ñ.-"), which
    parse.unit_key reads as a degree sign (O) or folds into another letter (Ñ to N); Ñ is keyed "nn", between n and o."""
    m = LETTERED.match(line)
    if not m:
        return None
    num, word, letter = int(m.group(1)), (m.group(2) or '').lower(), m.group(3)
    suf = word.replace('á', 'a')
    key = f'art-{num:0{width}d}' + (f'-{suf}' if suf else '') + '-' + ('nn' if letter.lower() == 'ñ' else letter.lower())
    return key, f'Art. {num}' + (f' {word}' if word else '') + f' {letter.upper()}', 'art'


# A norm that fixes the text of several laws, one per article: when one of our acts continues as such an article, the
# act reads only that article of the norm (parse.py's `part`, here per norm instead of per act). DFL 1 of 2000 (172986)
# fixes Ley 14.908 in its art. 7 ("LEY SOBRE ABANDONO DE FAMILIA Y PAGO DE PENSIONES ALIMENTICIAS").
NORM_PART = {172986: 7}
# The same norm read for another act: (act slug, idNorma) -> article. DFL 1 of 2000 fixes Ley 4.808 (Registro Civil) in
# its art. 3, Ley 17.344 (cambio de nombres) in art. 4, Ley 16.618 (Menores) in art. 6 and Ley 16.271 (herencias) in
# art. 8 (part 99-batch9). CURRENT names the act being read; it is set wherever an act's versions are read.
ACT_NORM_PART = {('ley-4808', 172986): 3, ('ley-17344', 172986): 4, ('ley-16618', 172986): 6, ('ley-16271', 172986): 8}
CURRENT = {'act': None}


def norm_part(norm: int | None) -> int | None:
    return ACT_NORM_PART.get((CURRENT['act'], norm), NORM_PART.get(norm))


NORM_ID = re.compile(rb'"id_norma":\s*"?(\d+)')


def norm_of(raw: bytes) -> int | None:
    m = NORM_ID.search(raw)
    return int(m.group(1)) if m else None


def part_width(width_for):
    """parse.width_for, reading only the article NORM_PART names of such a norm (its other parts have the Código
    Civil's four-digit article numbers)."""
    def wrapped(raws, part=None):
        if part is not None or not any(norm_part(norm_of(r)) is not None for r in raws):
            return width_for(raws, part)
        return max(width_for([r], norm_part(norm_of(r))) for r in raws)
    return wrapped


DEL_ART = re.compile(r'(?i)\s*\(DEL ART(?:[ÍI]CULO)?\.?\s*(?:\d+|[ÚU]NICO)\s*\)')
# Also dropped "(DEL ART. PRIMERO)" in these norms only (Ley 18.840, part 97-batch7); Ley 20.285 (part 95-batch6,
# published) keeps its art-NNN-del-art-primero keys, so its files do not move.
DEL_ART_WORD = re.compile(r'(?i)\s*\(DEL ART(?:[ÍI]CULO)?\.?\s*PRIMERO\s*\)')
STRIP_WORD = {30216}

# Norms whose own numbered articles sit beside the text they enact in their article 1 (DL 824: "Artículo 1°.-
# Apruébase el siguiente texto de la Ley sobre Impuesto a la Renta", then the decree law's own arts. 2 to 18 and its
# transitorios). Once unwrap lifts the enacted text, the decree law's own "Artículo 2" ... "Artículo 18" would share
# the keys of the enacted text's arts. 2 to 18; they are marked in unwrap and keyed decreto-ley-art-NNN, labelled
# "Art. N del decreto ley", so each file holds one article in every version. {idNorma: marker}.
OWN_ARTICLES = {6368: 'DEL DECRETO LEY'}
OWN_KEY = re.compile(r'^art-(\d+)-del-decreto-ley$')


def own_articles(units: dict, _marker: str) -> dict:
    out = {}
    for k, u in units.items():
        m = OWN_KEY.match(k)
        if m:
            k = f'decreto-ley-art-{m.group(1)}'
            u = dict(u, label=f'Art. {int(m.group(1))} del decreto ley')
        out[k] = u
    return out


def unwrap(raw: bytes) -> bytes:
    """A norm that enacts a whole text in one article ("doble articulado": DL 830's "Artículo 1°.- Apruébase el
    siguiente texto del Código Tributario", DFL 3 of 2021's "Artículo único.- Fíjase el siguiente texto refundido...
    de la ley N° 19.496") is read as the text it enacts: that article's tree takes its place among the norm's top-level
    nodes (heading and closing formula kept), and the "(DEL ART. 1)" LeyChile adds to the names inside is dropped. The
    enacting sentence itself is not part of the act's text. Other norms are returned unchanged."""
    d = json.loads(raw)
    if not (d.get('metadatos') or {}).get('doble_articulado'):
        return raw
    html = d.get('html') or []
    boxes = [i for i, x in enumerate(html) if x.get('h')]
    if len(boxes) != 1:
        return raw
    node = html[boxes[0]]
    while len(node['h']) == 1 and node['h'][0].get('h'):
        node = node['h'][0]
    d['html'] = html[:boxes[0]] + node['h'] + html[boxes[0] + 1:]
    marker = OWN_ARTICLES.get(norm_of(raw))
    if marker:
        box_id = html[boxes[0]].get('i')
        for x in d.get('estructura') or []:
            if (x.get('i') != box_id and re.match(r'(?i)^\s*art[íi]culo\s+\d+', x.get('n') or '')
                    and 'transitori' not in parse.plain(x['n']).lower()):
                x['n'] = x['n'].rstrip() + ' ' + marker

    word = norm_of(raw) in STRIP_WORD

    def strip(nodes):
        for x in nodes:
            if 'n' in x:
                x['n'] = DEL_ART.sub('', x['n'])
                if word:
                    x['n'] = DEL_ART_WORD.sub('', x['n'])
            strip(x.get('h') or [])
    strip(d.get('estructura') or [])
    return json.dumps(d, ensure_ascii=False).encode('utf-8')


def cut_note(slug: str) -> str:
    day, ev = STARTS[slug]
    return (f'Oldest version available: LeyChile lists older versions of this code, but each of them, up to the version '
            f'before {day}, carries amendment notes naming norms published after the day it is dated (for example '
            f'{ev[-1]}), so their text is not the text in force on those days. History here starts on {day}.')


def late_reason(slug: str) -> str:
    older = sorted({v['@vigenteDesde'] for n in CHAINS[slug] for v in ORIGINAL_VERSIONS[0](n, True)
                    if v['@vigenteDesde'] < '1970-01-01'})
    return (f'LeyChile also has {len(older)} older version(s) ({", ".join(older)}), left out because git cannot date a '
            'commit before 1970: the builder would date them 1970-01-01 plus one second per commit, and adding them '
            'would move the placeholder second of every commit before 1970 already published for other acts.')


def late_note(slug: str) -> str:
    return (f'Oldest version available here: history starts on {LATE[slug]}. ' + late_reason(slug))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--part', default='codes', choices=sorted(PARTS))
    ap.add_argument('--acts', help='default: the acts of --part')
    ap.add_argument('--out', help='default: the file of --part')
    ap.add_argument('--main-corpus', default=str(ROOT / 'corpus.json'),
                    help='checked for law keys that name a different norm')
    args = ap.parse_args()
    spec = PARTS[args.part]
    args.acts = args.acts or spec['acts']
    args.out = args.out or str(spec['out'])
    slugs = args.acts.split(',')
    if args.part != 'batch10':
        # Parts published before batch 10 read the Ley dates of the acts known then (anachronism.EXCLUDE).
        anachronism.EXCLUDE.update(PARTS['batch10']['acts'].split(','))
    setup(slugs)
    laws = parse.Laws()
    log: list[str] = []
    acts = []
    for s in slugs:
        CURRENT['act'] = s
        acts.append(parse.act_versions(s, laws, log))
    disclosed = []
    for a in acts:
        CURRENT['act'] = a['slug']
        if a['slug'] in STARTS:
            v0 = a['versions'][0]
            v0['note'] = cut_note(a['slug']) + (' ' + v0['note'] if v0.get('note') else '')
        if a['slug'] in LATE:
            v0 = a['versions'][0]
            v0['note'] = late_note(a['slug']) + (' ' + v0['note'] if v0.get('note') else '')
            disclosed.append(f'{a["short"]}: starts at {LATE[a["slug"]]}, its first LeyChile version from 1970 on, as the '
                             'oldest version available; ' + late_reason(a['slug']))
        disclosed += correct(a, laws)
        disclosed += fold_vigencia(a, laws)
    out_laws = {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in sorted(laws.laws.items())}
    main_laws = json.loads(Path(args.main_corpus).read_text(encoding='utf-8')).get('laws', {})
    for other in sorted((ROOT / 'corpus.d').glob('*.json')):
        if other.resolve() != Path(spec['out']).resolve():
            for k, v in json.loads(other.read_text(encoding='utf-8')).get('laws', {}).items():
                main_laws.setdefault(k, v)
    clash = [k for k, v in out_laws.items() if k in main_laws and (
        main_laws[k]['label'] != v['label'] or (main_laws[k].get('url') and v.get('url')
                                                and main_laws[k]['url'] != v['url']))]
    for k in clash:
        # parse.law_key gives numberless norms of the same type and year one key (e.g. "SEN S/N de 2009"); another
        # part already uses this key for a different LeyChile norm, so this part's norm takes its idNorma as well.
        nid = re.search(r'idNorma=(\d+)', out_laws[k].get('url') or '')
        nk = f'{k}-{nid.group(1)}' if nid else None
        if not nk or nk in out_laws or nk in main_laws:
            continue
        out_laws[nk] = out_laws.pop(k)
        for a in acts:
            a['earlier_laws'] = [nk if x == k else x for x in a['earlier_laws']]
            a['first_law'] = nk if a['first_law'] == k else a['first_law']
            for v in a['versions']:
                v['credits'] = {u: [nk if x == k else x for x in ls] for u, ls in v['credits'].items()}
    out_laws = dict(sorted(out_laws.items()))
    clash = [k for k, v in out_laws.items() if k in main_laws and (
        main_laws[k]['label'] != v['label'] or (main_laws[k].get('url') and v.get('url')
                                                and main_laws[k]['url'] != v['url']))]
    if clash:
        raise SystemExit('law keys naming a different norm than corpus.json: ' + ', '.join(
            f'{k} ({out_laws[k]["label"]} {out_laws[k]["url"]} vs {main_laws[k]["label"]} {main_laws[k]["url"]})'
            for k in clash))
    decisions = spec['decisions'] + [
        'A version dated D is anachronistic when its amendment notes name a norm published after D (by Diario Oficial '
        'date, or by a Ley number at least that of a Ley published after D). Where LeyChile\'s "Texto Original" of a '
        'code holds no article text (only a PDF link), its later old versions are reconstructions, and the code starts '
        'at the oldest version from which no version is anachronistic: ' + ('; '.join(f'{parse.ACT_META[s]["short"]} from {STARTS[s][0]} ({len(STARTS[s][1])} older versions '
                            'affected)' for s in STARTS) or 'none') + '. The first version is then the oldest '
        'version available, credited to the publisher. (codes/anachronism.py)',
    ] + [d for d in extra_decisions(acts)] + disclosed + [
        f'LeyChile version of idNorma {n} dated {d} ("{t}") left out: it waits for an event, not a day.'
        for n, d, t in sorted(EVENT_DROPPED) if any(n in CHAINS[x] for x in slugs)]
    part = {
        'laws': out_laws,
        'acts': acts,
        'decisions': decisions,
        'ai_use': ['Phase 2 codes: none at data-build time; codes/*.py are deterministic code written with Claude '
                   'Code (claude-opus-5-5), reusing parse.py; no model reads, writes or summarises legal text.'],
    }
    parse.stats(part)
    for a in acts:
        to_changes(a)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + '.tmp')
    tmp.write_text(json.dumps(part, ensure_ascii=False, indent=1) + '\n', encoding='utf-8', newline='\n')
    tmp.replace(out)
    (HERE / 'parse.log').write_text('\n'.join(log) + '\n', encoding='utf-8', newline='\n')


def to_changes(act: dict) -> None:
    """SCHEMA.md "Large acts": every version after the first gives only `changes` ({unit key: unit, or null to remove
    it}) against the version before it, instead of all its units. expand() is the inverse, as the builder reads it."""
    full = [v['units'] for v in act['versions']]
    for prev, cur, v in zip(full, full[1:], act['versions'][1:]):
        ch = {k: cur.get(k) for k in sorted(set(prev) | set(cur)) if prev.get(k) != cur.get(k)}
        items = [(k, ch if k == 'units' else x) for k, x in v.items()]
        v.clear()
        v.update((('changes' if k == 'units' else k), x) for k, x in items)


def expand(part: dict) -> dict:
    """The part with every version's full `units`, rebuilt from `changes` exactly as gitlaw_common/build.py does."""
    for act in part.get('acts', []):
        for prev, v in zip(act['versions'], act['versions'][1:]):
            if 'units' in v:
                continue
            units = dict(prev['units'])
            for k, u in (v.get('changes') or {}).items():
                if u is None:
                    units.pop(k, None)
                else:
                    units[k] = u
            v['units'] = units
    return part


PLACEHOLDER = '[La fuente no da el texto vigente en esta fecha.]\n'


def zkey(k: str) -> str:
    return re.sub(r'(?<=-)0+(?=\d)', '', k)


def note_laws(laws: parse.Laws, notes: list[str]) -> list[str]:
    """The law keys the amendment notes name (registering a law known only from a note, as parse.py does)."""
    dated = dict(anachronism.ley_dates())
    keys = set()
    for n in notes:
        refs, dates = parse.note_refs([n])
        day = max(dates) if dates else None
        for t, num in sorted(refs):
            pub = day or (dated.get(num) if t == 'ley' else None)
            if t == 'ley' or pub:
                keys.add(laws.from_note(t, num, pub, n))
        if not refs and day and re.match(r'(?i)RECTIFICA', n):
            keys.add(laws.from_note('rec', None, day, n))
    return sorted(keys)


# Acts whose own text defers their entry into force while LeyChile dates their first version from publication
# (found with codes/vigencia_scan.py). The day follows Código Civil art. 48: periods are complete and run to midnight
# of their last day; a period of months ends on the day with the same number (the last day of the month when there
# is none); a period of days counts from the day after publication; the act applies from the next day.
VIGENCIA = {
    'ley-19496': ('1997-06-06', '"La presente ley entrará en vigencia noventa días después de su publicación en el '
                  'Diario Oficial" (art. 1 transitorio; published 1997-03-07)'),
    'codigo-mineria': ('1983-12-14', '"El presente Código empezará a regir sesenta días después de su publicación" '
                       '(artículo final; published 1983-10-14)'),
    'codigo-aeronautico': ('1990-08-09', '"Esta ley entrará en vigencia seis meses después de su publicación en el '
                           'Diario Oficial" (art. 203; published 1990-02-08)'),
    'ley-18695': ('1988-05-01', '"Esta ley entrará en vigencia un mes después de su publicación" (artículo final; '
                  'published 1988-03-31; there is no 31 April, so the month ends on 30 April)'),
    'ley-20084': ('2007-06-08', '"La presente ley entrará en vigencia dieciocho meses después de su publicación, con '
                  'excepción de lo dispuesto en las letras a) y c) del artículo 68" (art. 1 transitorio, in the words '
                  'Ley 20.110 gave it; published 2005-12-07)'),
    'ley-20285': ('2009-04-21', '"La presente ley entrará en vigencia ocho meses después de publicada en el Diario '
                  'Oficial, salvo el artículo 2º transitorio [...], que regirá desde su publicación" (artículo '
                  'transitorio; published 2008-08-20)'),
    'ley-19947': ('2004-11-18', '"Esta ley entrará en vigencia seis meses después de su publicación en el Diario '
                  'Oficial" (artículo final; published 2004-05-17)'),
    # part 97-batch7 (gitlaw-CL-2, 2026-10-29; codes/vigencia_scan.py)
    'dl-824': ('1975-01-01', '"El nuevo texto de la Ley sobre Impuesto a la Renta que se establece en el artículo 1° '
               'del presente decreto ley regirá a contar del 1° de Enero de 1975" (art. 2; published 1974-12-31)'),
    'ley-19886': ('2003-08-30', '"La presente ley entrará en vigencia 30 días después de la fecha de su publicación" '
                  '(art. 39; published 2003-07-30; for municipalities from 1 January 2004 and for the armed forces '
                  'and police from 1 January 2005, which stays in the text)'),
    'ley-18840': ('1989-12-10', '"Esta ley entrará en vigencia sesenta días después de su publicación en el Diario '
                  'Oficial" (artículo cuarto; published 1989-10-10)'),
    # part 98-batch8 (gitlaw-CL-2, 2026-10-29)
    'ley-18918': ('1990-03-11', '"Esta ley entrará en vigencia el 11 de marzo de 1990" (artículo final; published '
                  '1990-02-05)'),
    'ley-21521': ('2023-02-04', '"Esta ley entrará en vigencia treinta días después de su publicación en el Diario '
                  'Oficial, con excepción de los títulos II y III, de los artículos 32, 35, y del N°2 del artículo 37", '
                  'which apply from the rules the Comisión para el Mercado Financiero issues (artículo primero '
                  'transitorio; published 2023-01-04; LeyChile dates it 2023-02-03, the thirtieth day)'),
    # part 99a-batch10 (gitlaw-CL-3, 2026-10-29; codes/vigencia_scan.py)
    'ley-19983': ('2005-04-16', '"Esta ley entrará en vigencia en el plazo de cuatro meses contados desde su '
                  'publicación en el Diario Oficial" (art. 11; published 2004-12-15)'),
    'ley-18603': ('1987-04-03', '"Esta ley entrará en vigencia diez días después de su publicación en el Diario '
                  'Oficial" (artículo final; published 1987-03-23)'),
}


def fold_vigencia(act: dict, laws: parse.Laws) -> list[str]:
    """Coordinator rule: commits are dated by when the text took effect. The act's first version is dated the day
    its own vigencia clause gives (VIGENCIA); LeyChile's versions dated before that day (amendments made before the
    act applied) are folded into it: it holds the text in force on that day, and its note names, per folded version,
    the laws LeyChile credits and the provisions they changed. Returns the decision line."""
    if act['slug'] not in VIGENCIA:
        return []
    day, quote = VIGENCIA[act['slug']]
    vs = act['versions']
    before = [v for v in vs if v['from'] < day]
    if not before:
        return []
    at = [v for v in vs if v['from'] == day]
    base = dict(at[0] if at else before[-1])
    steps = before[1:] + at
    parts = []
    for v in steps:
        by: dict[str, list[str]] = {}
        for k, ls in sorted(v['credits'].items()):
            lab = v['units'].get(k, {}).get('label', k)
            for l in ls:
                by.setdefault(l, []).append(lab)
        prev = vs[vs.index(v) - 1]['units']
        changed = [k for k in set(prev) | set(v['units']) if prev.get(k) != v['units'].get(k)]
        loose = len([k for k in changed if not v['credits'].get(k)])
        desc = '; '.join(f'{laws.laws[l]["label"]}: ' + ', '.join(us[:12]) + (', …' if len(us) > 12 else '')
                         for l, us in by.items())
        parts.append(f'{v["from"]}: ' + (desc or 'no law named') + (f' (and {loose} provisions no law explains)'
                                                                       if loose else ''))
    note = (f'In force from {day} by the words of the act itself: {quote}. LeyChile dates the text from its publication '
            f'({before[0]["from"]}); this first version is the text in force on {day}.')
    if parts:
        note += (' It includes the changes LeyChile records before that day, made before the act applied: '
                 + ' | '.join(parts) + '.')
    base.update({'from': day, 'credits': {}, 'note': note})
    act['versions'] = [base] + [v for v in vs if v['from'] > day]
    return [f'{act["short"]}: first version dated {day}, the day its own vigencia clause gives ({quote}), not the '
            f'publication day LeyChile uses; the {len(before)} LeyChile '
            f'version(s) dated before it are folded into it (Código Civil art. 48 for the count).']


def correct(act: dict, laws: parse.Laws) -> list[str]:
    """Coordinator rule for anachronistic versions (codes/anachronism.py): a provision whose LeyChile text, in a version
    dated D, carries an amendment note naming a norm published after D holds wording that is not yet in force. Only
    those provisions are corrected, in the run of versions in which the note is ahead of its day:
      - the provision did not exist before the run and no norm in force that day is credited with it: that norm
        inserted it, so it is left out of the run;
      - otherwise, where its text differs from the text before the run, it becomes the placeholder line (the source
        does not give the wording in force then), credited to the publisher (unexplained);
    and in the first version after the run, where LeyChile's wording arrives, the change is credited to the norm(s)
    the notes name. Returns the decision lines."""
    bad = anachronism.defects(act['slug'])
    vs = act['versions']
    keys = {zkey(k): k for v in vs for k in v['units']}
    flagged: dict[str, dict[int, list[str]]] = {}
    for i, v in enumerate(vs):
        for _why, k4, n in bad.get(v['from'], []):
            k = keys.get(zkey(k4))
            if k:
                flagged.setdefault(k, {}).setdefault(i, []).append(n)
    lines = []
    for k in sorted(flagged):
        idx = sorted(flagged[k])
        runs, start = [], idx[0]
        for a, b in zip(idx, idx[1:] + [None]):
            if b != a + 1:
                runs.append((start, a))
                start = b
        for i, j in runs:
            pre = vs[i - 1]['units'].get(k) if i else None
            # New in the run: inserted by the late norm, unless the versions list credits its arrival to a norm in
            # force that day (that norm inserted it; the late norm changed it later).
            inserted = pre is None and not vs[i]['credits'].get(k)
            pre = pre or {'text': None}
            label = next((vs[t]['units'][k]['label'] for t in range(i, j + 1) if k in vs[t]['units']), k)
            for t in range(i, j + 1):
                u = vs[t]['units'].get(k)
                if inserted:
                    vs[t]['units'].pop(k, None)
                elif u is not None and u['text'] != pre['text']:
                    vs[t]['units'][k] = dict(u, text=PLACEHOLDER)
                vs[t]['credits'].pop(k, None)
            names = sorted({n for t in range(i, j + 1) for n in flagged[k].get(t, [])})
            how = 'left out (the norm its note names inserted it)' if inserted else \
                'shown as the placeholder line where LeyChile gives a later wording'
            vs[i]['note'] = (vs[i]['note'] + ' ' if vs[i].get('note') else '') + (
                f'Corrected: LeyChile\'s text of {label} from this version to {vs[j]["from"]} carries amendment notes '
                f'naming norms published after those days ({"; ".join(names)[:300]}), so its wording there is not yet '
                f'in force: it is {how}.')
            arrive = ''
            if j + 1 < len(vs):
                nxt = vs[j + 1]
                if nxt['units'].get(k) != vs[j]['units'].get(k):
                    lk = note_laws(laws, flagged[k][j])
                    if lk:
                        nxt['credits'][k] = sorted(set(nxt['credits'].get(k, [])) | set(lk))
                        nxt['note'] = (nxt['note'] + ' ' if nxt.get('note') else '') + (
                            f'{label}: the wording LeyChile gives once '
                            + ', '.join(laws.laws[x]['label'] for x in lk)
                            + ' is in force; credited to it (see the correction noted on '
                            + vs[i]['from'] + ').')
                        arrive = f'; from {nxt["from"]} credited to ' + ', '.join(laws.laws[x]['label'] for x in lk)
            lines.append(f'{label} {vs[i]["from"]} to {vs[j]["from"]} {"left out" if inserted else "placeholder"}'
                         + arrive)
    if not lines:
        return []
    return [f'{act["short"]}: provisions whose LeyChile text in a version carries notes naming a norm published after '
            'that version (coordinator rule: correct only those provisions, never keep text in force before its law; '
            'placeholder "' + PLACEHOLDER.strip() + '" credited to the publisher): ' + '; '.join(lines) + '.']


def extra_decisions(acts: list[dict]) -> list[str]:
    out = []
    for a in acts:
        m = parse.ACT_META[a['slug']]
        if m.get('first'):
            out.append(f'{a["short"]}: ' + m['first'][1])
    return out


if __name__ == '__main__':
    main()
