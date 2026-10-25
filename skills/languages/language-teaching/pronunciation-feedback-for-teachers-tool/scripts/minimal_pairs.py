#!/usr/bin/env python3
"""Print minimal pairs for a sound contrast, with a discrimination sentence and a numbered listening drill.

Reads references/minimal-pairs.md. Contrasts can be given in IPA ("/ɪ/-/iː/") or by alias ("i-ee", "l-r", "th-s").
--drill N prints N items (seeded) where the teacher says one word and learners answer 1 or 2, with a key.

Usage:
    python minimal_pairs.py l-r
    python minimal_pairs.py "/ɪ/-/iː/" --drill 8 --seed 2
    python minimal_pairs.py --list

Exit codes: 0 printed, 2 unknown contrast or unreadable table.
"""

import argparse
import random
import re
import sys
from pathlib import Path

TABLE = Path(__file__).resolve().parent.parent / "references" / "minimal-pairs.md"


def read(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == 4 and "/" in cells[2] and cells[0] != "Contrast":
            rows.append({"contrast": cells[0], "aliases": [x.strip().lower() for x in cells[1].split(",")],
                         "pairs": [tuple(p.strip().split("/")) for p in cells[2].split(",")], "sentence": cells[3]})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contrast", nargs="?")
    ap.add_argument("--drill", type=int, default=0, help="number of listening items")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--table", default=TABLE)
    a = ap.parse_args()
    try:
        rows = read(a.table)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.list or not a.contrast:
        for r in rows:
            print(f"{r['contrast']:<16} {', '.join(r['aliases'])}")
        return 0 if a.list else 2
    key = a.contrast.strip().lower()
    hit = next((r for r in rows if key == r["contrast"].lower() or key in r["aliases"]), None)
    if not hit:
        print(f"error: unknown contrast '{a.contrast}'; use --list", file=sys.stderr)
        return 2
    print(f"{hit['contrast']}\n")
    print("| 1 | 2 |\n|---|---|")
    for p in hit["pairs"]:
        print(f"| {p[0]} | {p[1] if len(p) > 1 else ''} |")
    print(f"\nIn context: {hit['sentence']}")
    if a.drill:
        rng = random.Random(a.seed)
        items = [(rng.choice(hit["pairs"]), rng.randint(1, 2)) for _ in range(a.drill)]
        print("\nListening drill - say the word; learners answer 1 or 2:")
        print("  " + "  ".join(f"{i}. {p[n - 1]}" for i, (p, n) in enumerate(items, 1)))
        print("Key: " + " ".join(f"{i}-{n}" for i, (_, n) in enumerate(items, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
