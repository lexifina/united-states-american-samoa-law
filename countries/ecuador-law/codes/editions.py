"""Locate the Registro Oficial editions of the COGEP and the Código del Trabajo and their amending acts, download
them (cached) and test their text layer; results in codes/editions.json. Same machinery as coip/find_editions.py.

    python -X utf8 codes/editions.py [TARGET ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "coip"))
sys.path.insert(0, str(HERE.parent))
import find_editions  # noqa: E402

# from the reading-only indexes (codes/index_docx.py: LegalCloud/Lexis notes to II-2023; codes/screen.py after)
TARGETS = {
    # COGEP
    "s506-2015": ("suplemento", "2015-05-22", 506),
    "ro539-2015": ("ro", "2015-07-09", 539),
    "s584-2015": ("suplemento", "2015-09-10", 584),
    "ro636-2015": ("ro", "2015-11-26", 636),
    "s652-2015": ("suplemento", "2015-12-18", 652),
    "s899-2016": ("suplemento", "2016-12-09", 899),
    "s1-2017": ("suplemento", "2017-05-31", 1),
    "ec1-2017": ("constitucional", "2017-05-31", 1),
    "s31-2017": ("suplemento", "2017-07-07", 31),
    "s104-2017": ("suplemento", "2017-10-20", 104),
    "ec19-2017": ("constitucional", "2017-11-14", 19),
    "s19-2017": ("suplemento", "2017-11-14", 19),
    "s309-2018": ("suplemento", "2018-08-21", 309),
    "s517-2019": ("suplemento", "2019-06-26", 517),
    "s345-2020": ("suplemento", "2020-12-08", 345),
    "s137-2021": ("suplemento", "2021-02-23", 137),
    "ec137-2021": ("constitucional", "2021-02-23", 137),
    "s156-2021": ("suplemento", "2021-04-09", 156),
    "ec156-2021": ("constitucional", "2021-04-09", 156),
    "s452-2021": ("suplemento", "2021-05-14", 452),
    "s587-2021": ("suplemento", "2021-11-29", 587),
    "s53-2022": ("suplemento", "2022-07-15", 53),
    "ec53-2022": ("constitucional", "2022-07-15", 53),
    "s245-2023": ("suplemento", "2023-02-07", 245),
}


def main(argv: list[str]) -> None:
    find_editions.TARGETS = TARGETS
    find_editions.OUT = HERE / "editions.json"
    find_editions.main(argv)


if __name__ == "__main__":
    main(sys.argv[1:])
