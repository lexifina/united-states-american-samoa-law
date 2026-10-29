"""Hand-written replay data for the Código Civil (no legal text here: only anchors into official sources).

INTERMEDIATE[unit][law] lists, line by line, the unit's wording in force after `law` and before the next
change, for the units that two or more laws changed after the MINJUS 14th edition (Aug 2014). Each item:
  ("C", prefix)            the line of the Editora Perú 2024 text starting with prefix
  ("T14", prefix)          the line of the MINJUS 14th edition text starting with prefix
  ("L", law, start, end)   the law's own text from `start` up to (not including) `end`, joined into one line
"""

INTERMEDIATE = {
    "art-0042": {"dleg-1384": [
        ("L", "dleg-1384", "Artículo 42.- Capacidad de ejercicio plena", "Toda persona mayor de dieciocho"),
        ("C", "Toda persona mayor de dieciocho años"),
        ("L", "dleg-1384", "Excepcionalmente tienen plena capacidad", "”"),
    ]},
    "art-0046": {"dleg-1377": [
        ("L", "dleg-1377", "Artículo 46.- Capacidad adquirida", "La incapacidad de las personas mayores"),
        ("L", "dleg-1377", "La incapacidad de las personas mayores", "La capacidad adquirida por matrimonio no"),
        ("L", "dleg-1377", "La capacidad adquirida por matrimonio no", "Tratándose de mayores"),
        ("L", "dleg-1377", "Tratándose de mayores", "1. Inscribir"),
        ("L", "dleg-1377", "1. Inscribir", "2. Demandar por gastos"),
        ("L", "dleg-1377", "2. Demandar por gastos", "3. Demandar y ser parte"),
        ("L", "dleg-1377", "3. Demandar y ser parte", "4. Demandar y ser parte"),
        ("L", "dleg-1377", "4. Demandar y ser parte", "Ordenanza N° 011-2017"),
        ("L", "dleg-1377", "5. Celebrar conciliaciones", "6. Solicitar su inscripción"),
        ("L", "dleg-1377", "6. Solicitar su inscripción", "7. Impugnar"),
        ("L", "dleg-1377", "7. Impugnar judicialmente la paternidad", "»"),
    ]},
    "art-0241": {"dleg-1384": [
        ("C", "Impedimentos Absolutos"),
        ("C", "Artículo 241.-"),
        ("T14", "1. Los adolescentes"),
        ("C", "2.- Las personas con capacidad de ejercicio restringida"),
        ("C", "5.- Los casados"),
    ]},
    "art-0243": {"dleg-1384": [
        ("C", "Prohibiciones especiales"),
        ("C", "Artículo 243.-"),
        ("L", "dleg-1384", "1.- Del tutor o del curador con el menor o con la", "El tutor que infrinja"),
        ("L", "dleg-1384", "El tutor que infrinja", "”"),
        ("C", "2. Del viudo"),
        ("C", "La infracción de esta norma"),
        ("C", "Esta disposición es aplicable al cónyuge"),
        ("C", "3. De la viuda"),
        ("C", "Se dispensa el plazo"),
        ("C", "La viuda que contravenga"),
        ("C", "No rige la prohibición"),
        ("C", "Es de aplicación a los casos"),
    ]},
    "art-0248": {"ley-31643": [
        ("C", "Diligencias para matrimonio civil"),
        ("L", "ley-31643", "Artículo 248.- Diligencias para matrimonio civil", "Quienes pretendan contraer"),
        ("L", "ley-31643", "Quienes pretendan contraer", "Acompañarán copia certificada"),
        ("L", "ley-31643", "Acompañarán copia certificada", "Acompañarán también"),
        ("L", "ley-31643", "Acompañarán también", "Cada pretendiente presentará"),
        ("L", "ley-31643", "Cada pretendiente presentará", "Cuando la declaración sea oral"),
        ("L", "ley-31643", "Cuando la declaración sea oral", "Artículo 250.-"),
    ]},
    "art-0274": {"dleg-1384": [
        ("C", "Causales de nulidad del matrimonio"),
        ("C", "Artículo 274.-"),
        ("C", "3. Del casado"),
        ("C", "Tratándose del nuevo matrimonio"),
        ("C", "En el caso del matrimonio contraído"),
        ("C", "4. De los consanguíneos o afines"),
        ("C", "5. De los consanguíneos en segundo"),
        ("C", "Sin embargo, tratándose del tercer grado"),
        ("C", "6. De los afines"),
        ("C", "7. Del condenado"),
        ("C", "8. De quienes lo celebren"),
        ("C", "9. De los contrayentes"),
    ]},
    "art-0481": {"ley-30550": [
        ("C", "Artículo 481.-"),
        ("C", "Los alimentos se regulan"),
        ("C", "El juez considera como un aporte"),
        ("L", "ley-30550", "No es necesario investigar rigurosamente", "”"),
    ]},
    "art-0667": {"ley-30364": [
        ("C", "Exclusión de la sucesión por indignidad"),
        ("C", "Artículo 667.-"),
        ("C", "1. Los autores y cómplices"),
        ("C", "2. Los que hubieran sido condenados"),
        ("C", "3. Los que hubieran denunciado"),
        ("C", "4. Los que hubieran empleado"),
        ("C", "5. Los que destruyan"),
        ("L", "ley-30364", "6.\nLos que hubieran sido sancionados", "7.\nEs indigno"),
        ("C", "7. Es indigno de suceder"),
    ]},
    "art-0696": {"dleg-1384": [
        ("C", "Formalidades del testamento por escritura pública"),
        ("L", "dleg-1384", "Artículo 696.- Formalidades del testamento", "Las formalidades esenciales"),
        ("C", "Las formalidades esenciales"),
        ("T14", "1.- Que estén reunidos"),
        ("C", "2.- Que el testador exprese"),
        ("T14", "3.- Que el notario escriba"),
        ("C", "4.- Que cada una de las páginas"),
        ("C", "5.- Que el testamento sea leído"),
        ("C", "6.- Que, durante la lectura"),
        ("C", "7.- Que el notario deje constancia"),
        ("C", "8.- Que el testador, los testigos"),
        ("C", "9.- Que, en los casos en que el apoyo"),
    ]},
}

# Laws the NLA notes do not name for a unit, but whose own text changes it (the NLA notes name only the
# latest law per provision).
HIDDEN = {
    "art-0042": ["dleg-1384"],
    "art-0046": ["dleg-1377"],
    "art-0243": ["dleg-1384"],
    "art-0248": ["ley-31643"],
}

# Units incorporated by a note that sits on another unit ("Capítulo Cuarto incorporado ... D.Leg. 1384").
INCORPORATED_WITH = {k: "dleg-1384" for k in ["art-0659-a", "art-0659-b", "art-0659-c", "art-0659-d",
                                                "art-0659-e", "art-0659-f", "art-0659-g", "art-0659-h"]}
