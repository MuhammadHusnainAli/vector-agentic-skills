#!/usr/bin/env python3
"""Look up ISO 9001:2015 clauses: intent, requirements, evidence, pitfalls and related clauses.

Reads references/clause-guide.md (single source of truth for this skill).

Usage:
    python clause_lookup.py 8.7                 # one clause (sub-clauses like 8.3.4 resolve to 8.3)
    python clause_lookup.py 8.5                 # every 8.5.x clause
    python clause_lookup.py --search calibration
    python clause_lookup.py --from-2008 7.6     # where an ISO 9001:2008 clause went
    python clause_lookup.py --list

Exit codes: 0 found, 1 nothing matched, 2 usage error.
"""

import argparse
import re
import sys
from pathlib import Path

GUIDE = Path(__file__).resolve().parent.parent / "references" / "clause-guide.md"
FIELDS = ("Intent", "Requires", "Evidence", "Pitfalls", "Related")
FROM_2008 = {
    "4.1": ["4.4"], "4.2.1": ["7.5.1"], "4.2.2": ["4.3", "4.4", "7.5.1"], "4.2.3": ["7.5"], "4.2.4": ["7.5"],
    "5.1": ["5.1"], "5.2": ["5.1"], "5.3": ["5.2"], "5.4.1": ["6.2"], "5.4.2": ["6.1", "6.3"], "5.5.1": ["5.3"],
    "5.5.2": ["5.3"], "5.5.3": ["7.4"], "5.6": ["9.3"], "6.1": ["7.1.1"], "6.2": ["7.2", "7.3"], "6.3": ["7.1.3"],
    "6.4": ["7.1.4"], "7.1": ["8.1"], "7.2.1": ["8.2.2"], "7.2.2": ["8.2.3"], "7.2.3": ["8.2.1"], "7.3": ["8.3"],
    "7.4": ["8.4"], "7.5.1": ["8.5.1"], "7.5.2": ["8.5.1"], "7.5.3": ["8.5.2"], "7.5.4": ["8.5.3"],
    "7.5.5": ["8.5.4"], "7.6": ["7.1.5"], "8.1": ["9.1.1"], "8.2.1": ["9.1.2"], "8.2.2": ["9.2"],
    "8.2.3": ["9.1.1"], "8.2.4": ["8.6"], "8.3": ["8.7", "10.2"], "8.4": ["9.1.3"], "8.5.1": ["10.3"],
    "8.5.2": ["10.2"], "8.5.3": ["6.1"],
}
NOTES_2008 = {"4.2.2": "the quality manual is no longer mandatory; the scope (4.3) and process description (4.4) remain",
              "5.5.2": "the management representative role was removed; assign its duties under 5.3",
              "8.5.3": "preventive action became risk-based thinking (6.1)"}


def load():
    clauses, cur = {}, None
    for line in GUIDE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (\d+(?:\.\d+)*) (.+)$", line)
        if m:
            cur = m.group(1)
            clauses[cur] = {"title": m.group(2)}
            continue
        m = re.match(r"^- \*\*(\w+):\*\* (.+)$", line)
        if m and cur:
            clauses[cur][m.group(1)] = m.group(2)
    return clauses


def resolve(num, clauses):
    if num in clauses:
        return [num]
    kids = [c for c in clauses if c.startswith(num + ".")]
    if kids:
        return kids
    parts = num.split(".")
    while len(parts) > 1:
        parts.pop()
        if ".".join(parts) in clauses:
            return [".".join(parts)]
    return []


def show(num, c):
    print(f"{num} {c['title']}")
    for f in FIELDS:
        if f in c:
            print(f"  {f + ':':<10}{c[f]}")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clause", nargs="?", help="clause number, e.g. 8.7 or 8.5")
    ap.add_argument("--search", help="keyword search across all fields")
    ap.add_argument("--from-2008", dest="old", help="ISO 9001:2008 clause number to map to 2015")
    ap.add_argument("--list", action="store_true", help="list all clause numbers and titles")
    a = ap.parse_args()
    clauses = load()
    if a.list:
        for n, c in clauses.items():
            print(f"{n:<7}{c['title']}")
        return 0
    if a.old:
        new = FROM_2008.get(a.old)
        if not new:
            print(f"no ISO 9001:2008 mapping for {a.old!r}", file=sys.stderr)
            return 1
        print(f"ISO 9001:2008 {a.old} -> ISO 9001:2015 {', '.join(new)}"
              + (f"  ({NOTES_2008[a.old]})" if a.old in NOTES_2008 else "") + "\n")
        for n in new:
            for r in resolve(n, clauses):
                show(r, clauses[r])
        return 0
    if a.search:
        q = a.search.lower()
        hits = [n for n, c in clauses.items() if any(q in v.lower() for v in c.values())]
        for n in hits:
            show(n, clauses[n])
        if not hits:
            print(f"no clause mentions {a.search!r}", file=sys.stderr)
        return 0 if hits else 1
    if not a.clause:
        ap.print_usage(sys.stderr)
        return 2
    hits = resolve(a.clause.strip(), clauses)
    if not hits:
        print(f"no clause {a.clause!r}; auditable clauses run from 4.1 to 10.3 (use --list)", file=sys.stderr)
        return 1
    for n in hits:
        show(n, clauses[n])
    return 0


if __name__ == "__main__":
    sys.exit(main())
