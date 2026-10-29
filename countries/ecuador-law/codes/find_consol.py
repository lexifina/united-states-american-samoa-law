"""Look for archived consolidations (indexes of amending acts) of a Code on known hosts, through archive.org CDX
(one request per host, filtered by a URL regex) via gitlaw_common/wayback.py. Reading only.

    python -X utf8 codes/find_consol.py "<url-regex>" [host-prefix ...]
"""
from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE.parent / ".cache"
sys.path.insert(0, r"C:/Users/alany/Documents/lexifina/scripts/gitlaw_common")
import wayback  # noqa: E402

HOSTS = ["aduana.gob.ec/wp-content/uploads/", "trabajo.gob.ec/wp-content/uploads/", "www.funcionjudicial.gob.ec/",
         "legalcloud.ec/wp-content/uploads/", "www.gob.ec/sites/default/files/regulations/",
         "derechoecuador.com/uploads/", "lotaip.bomberosquito.gob.ec/", "www.defensa.gob.ec/wp-content/uploads/",
         "faolex.fao.org/docs/pdf/ecu", "www.ces.gob.ec/", "www.cpccs.gob.ec/wp-content/uploads/",
         "www.planificacion.gob.ec/wp-content/uploads/", "www.igualdad.gob.ec/", "www.supercias.gob.ec/"]


def main(argv: list[str]) -> None:
    rx = argv[0]
    for host in argv[1:] or HOSTS:
        q = ["url=" + host, "output=json", "matchType=prefix", "fl=timestamp,original,statuscode,length",
             "filter=statuscode:200", "filter=original:" + urllib.parse.quote(rx), "collapse=urlkey", "limit=2000"]
        raw = wayback.fetch("https://web.archive.org/cdx/search/cdx?" + "&".join(q), CACHE)
        rows = json.loads(raw.decode("utf-8") or "[]") if raw else []
        print(f"== {host}: {max(len(rows) - 1, 0)}", flush=True)
        for r in rows[1:]:
            print("  ", r[0], r[3], r[1])


if __name__ == "__main__":
    main(sys.argv[1:])
