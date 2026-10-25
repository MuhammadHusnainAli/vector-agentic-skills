#!/usr/bin/env python3
"""List likely English pronunciation difficulties for learners' first languages, highest priority first.

Reads references/l1-pronunciation-issues.md. Give one or more L1s (a mixed class); features shared by several L1s
are listed once with all the L1s, so a teacher can pick whole-class priorities.

Usage:
    python l1_issues.py Spanish
    python l1_issues.py Arabic Japanese Spanish --priority high
    python l1_issues.py --list

Exit codes: 0 printed, 2 unknown L1 or unreadable table.
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

TABLE = Path(__file__).resolve().parent.parent / "references" / "l1-pronunciation-issues.md"
RANK = {"high": 0, "medium": 1, "low": 2}


def read(path):
    rows, head = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|[\s|:-]+\|$", line):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if head is None:
            head = [c.lower() for c in cells]
        elif len(cells) == len(head):
            rows.append(dict(zip(head, cells)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("l1", nargs="*", help="first language(s), e.g. Spanish Arabic")
    ap.add_argument("--priority", choices=RANK, help="show this priority and above")
    ap.add_argument("--list", action="store_true", help="list the L1s in the table")
    ap.add_argument("--table", default=TABLE)
    a = ap.parse_args()
    try:
        rows = read(a.table)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    langs = sorted({r["l1"] for r in rows})
    if a.list or not a.l1:
        print("L1s: " + ", ".join(langs))
        return 0 if a.list else 2
    wanted = {l.lower() for l in a.l1}
    unknown = wanted - {l.lower() for l in langs}
    if unknown:
        print(f"error: not in the table: {', '.join(sorted(unknown))}; use --list", file=sys.stderr)
        return 2
    feats = defaultdict(list)
    for r in rows:
        if r["l1"].lower() in wanted and (not a.priority or RANK[r["priority"]] <= RANK[a.priority]):
            feats[(r["feature"], r["priority"])].append(r)
    print(f"Likely difficulties for {', '.join(a.l1)} speakers (check with the learners before teaching)\n")
    for (feat, pri), rs in sorted(feats.items(), key=lambda kv: (RANK[kv[0][1]], -len(kv[1]), kv[0][0])):
        who = ", ".join(r["l1"] for r in rs)
        print(f"[{pri}] {feat}  ({who})")
        for r in rs:
            print(f"    {r['l1']}: {r['tendency']}" + (f" - e.g. {r['example']}" if r["example"] else ""))
        print(f"    Tip: {rs[0]['teaching tip']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
