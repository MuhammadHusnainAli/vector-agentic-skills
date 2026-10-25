#!/usr/bin/env python3
"""Check the order and recycling of items in a course scope and sequence.

CSV columns: item, unit (number), requires (items it builds on, ';'-separated), recycled_in (units, ';'-separated)

Checks:
  SQ001 high    item taught before (or in a course without) an item it requires
  SQ002 high    circular prerequisites
  SQ003 medium  item never recycled after it is introduced
  SQ004 low     first recycling comes more than --gap units after introduction (default 3)

Prints a valid teaching order (prerequisites first, then by unit) after the findings.

Usage:
    python sequence_check.py scope.csv [--gap 3]

Exit codes: 0 no high findings, 1 high findings, 2 read error or bad CSV.
"""

import argparse
import csv
import sys


def split(cell):
    return [x.strip() for x in (cell or "").split(";") if x.strip()]


def topo(items, req):
    order, state = [], {}

    def visit(n, path):
        if state.get(n) == "done":
            return None
        if state.get(n) == "busy":
            return path[path.index(n):] + [n]
        state[n] = "busy"
        for r in sorted(req.get(n, []), key=lambda x: items.get(x, 10 ** 6)):
            cyc = visit(r, path + [n]) if r in items else None
            if cyc:
                return cyc
        state[n] = "done"
        order.append(n)
        return None

    for n in sorted(items, key=items.get):
        cyc = visit(n, [])
        if cyc:
            return None, cyc
    return order, None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--gap", type=int, default=3, help="max units before first recycling (default 3)")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        items = {r["item"].strip(): int(r["unit"]) for r in rows}
        req = {r["item"].strip(): split(r.get("requires")) for r in rows}
        rec = {r["item"].strip(): [int(u) for u in split(r.get("recycled_in"))] for r in rows}
    except (OSError, KeyError, ValueError, csv.Error) as e:
        print(f"error: needs item and numeric unit columns ({e})", file=sys.stderr)
        return 2
    f = []
    for it, unit in items.items():
        for r in req[it]:
            if r not in items:
                f.append(("SQ001", "high", f"'{it}' requires '{r}', which is not in the course"))
            elif items[r] > unit:
                f.append(("SQ001", "high", f"'{it}' (unit {unit}) comes before '{r}' (unit {items[r]}) that it requires"))
        later = sorted(u for u in rec[it] if u > unit)
        if not later:
            f.append(("SQ003", "medium", f"'{it}' (unit {unit}) is never recycled"))
        elif later[0] - unit > a.gap:
            f.append(("SQ004", "low", f"'{it}' first recycled in unit {later[0]}, {later[0] - unit} units after unit {unit}"))
    order, cycle = topo(items, req)
    if cycle:
        f.append(("SQ002", "high", "circular prerequisites: " + " -> ".join(cycle)))
    print(f"{len(items)} items in {len(set(items.values()))} units")
    sev = {"high": 0, "medium": 1, "low": 2}
    for code, s, msg in sorted(f, key=lambda x: (sev[x[1]], x[0])):
        print(f"{code} [{s}] {msg}")
    if order:
        print("\nTeaching order: " + " -> ".join(order))
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
