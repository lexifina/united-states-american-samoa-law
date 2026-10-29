"""Show the bridges for one provision, or for a concept, from bridges.json.

    python query.py "de|Art. 4"
    python query.py setoff
"""
import json
import sys
from pathlib import Path

ORDER = ["equivalent", "analogous", "related"]


def main(term):
    bridges = json.loads(Path("bridges.json").read_text(encoding="utf-8"))["bridges"]
    t = term.lower()
    hits = [b for b in bridges if t in (b["a"].lower(), b["b"].lower())] or \
        [b for b in bridges if t in " ".join([b["a"], b["b"], b["concept"], b["note"]]).lower()]
    for b in sorted(hits, key=lambda b: (ORDER.index(b["relation"]), -b["sim"])):
        print(f"{b['relation']:10s} {b['sim']:.2f}  {b['a']}  <->  {b['b']}  [{b['concept']}]")
        print(f"           {b['note']}")
    if not hits:
        print("No bridges match", repr(term))


if __name__ == "__main__":
    main(" ".join(sys.argv[1:]))
