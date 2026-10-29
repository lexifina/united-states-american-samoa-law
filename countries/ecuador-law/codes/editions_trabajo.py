"""Locate the Registro Oficial editions of the Código del Trabajo (codificación 2005) and its amending acts, download
them (cached) and test their text layer; results in codes/editions_trabajo.json. Same machinery as
coip/find_editions.py.

    python -X utf8 codes/editions_trabajo.py [TARGET ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "coip"))
sys.path.insert(0, str(HERE.parent))
import find_editions  # noqa: E402

# from the reading-only indexes (codes/index_docx.py trabajo: LegalCloud/Lexis notes to II-2023; codes/screen.py after)
TARGETS = {
    "s167-2005": ("suplemento", "2005-12-16", 167),
    "ro198-2006": ("ro", "2006-01-30", 198),
    "ro223-2006": ("ro", "2006-03-07", 223),
    "ro250-2006": ("ro", "2006-04-13", 250),
    "ro259-2006": ("ro", "2006-04-27", 259),
    "s298-2006": ("suplemento", "2006-06-23", 298),
    "ro340-2006": ("ro", "2006-08-23", 340),
    "s387-2006": ("suplemento", "2006-10-30", 387),
    "ro75-2007": ("ro", "2007-05-02", 75),
    "s330-2008": ("suplemento", "2008-05-06", 330),
    "s528-2009": ("suplemento", "2009-02-13", 528),
    "s644-2009": ("suplemento", "2009-07-29", 644),
    "s351-2010": ("suplemento", "2010-12-29", 351),
    "s372-2011": ("suplemento", "2011-01-27", 372),
    "s797-2012": ("suplemento", "2012-09-26", 797),
    "s332-2014": ("suplemento", "2014-09-12", 332),
    "s483-2015": ("suplemento", "2015-04-20", 483),
    "s506-2015": ("suplemento", "2015-05-22", 506),
    "s720-2016": ("suplemento", "2016-03-28", 720),
    "s906-2016": ("suplemento", "2016-12-20", 906),
    "s1008-2017": ("suplemento", "2017-05-19", 1008),
    "s116-2017": ("suplemento", "2017-11-09", 116),
    "s175-2018": ("suplemento", "2018-02-05", 175),
    "ec40-2018": ("constitucional", "2018-04-06", 40),
    "s40-2018": ("suplemento", "2018-04-06", 40),
    "s309-2018": ("suplemento", "2018-08-21", 309),
    "s517-2019": ("suplemento", "2019-06-26", 517),
    "s229-2020": ("suplemento", "2020-06-22", 229),
    "ec231-2021": ("constitucional", "2021-11-04", 231),
    "ec259-2022": ("constitucional", "2022-01-03", 259),
    "s222-2023": ("suplemento", "2023-01-04", 222),
    "s234-2023": ("suplemento", "2023-01-20", 234),
    "s242-2023": ("suplemento", "2023-02-01", 242),
    "s309-2023": ("suplemento", "2023-05-12", 309),
    "s559-2024": ("suplemento", "2024-05-16", 559),
    "s588-2024": ("suplemento", "2024-06-27", 588),
    "s64-2025": ("suplemento", "2025-06-20", 64),
    "s94-2025": ("suplemento", "2025-08-01", 94),
}


def main(argv: list[str]) -> None:
    find_editions.TARGETS = TARGETS
    find_editions.OUT = HERE / "editions_trabajo.json"
    find_editions.main(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
