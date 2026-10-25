#!/usr/bin/env python3
"""Check a unit-by-unit syllabus against a CEFR level: core grammar coverage, items above level, can-dos, skills.

Syllabus CSV columns: unit, grammar, vocabulary, functions, can_do, skills (e.g. "reading; speaking")
The grammar inventory is references/core-inventory-by-level.md (Level | Item | Keywords).

Checks:
  SY001 high    unit without a can-do statement
  SY002 medium  core item for the course level not covered
  SY003 medium  grammar item above the course level
  SY004 medium  a skill (reading, listening, speaking, writing) in fewer than half the units
  SY005 low     unit with no vocabulary or functions

Usage:
    python syllabus_check.py syllabus.csv --level B1
    python syllabus_check.py syllabus.csv --level A2 --from A1     # course covers A1 and A2

Exit codes: 0 no high findings, 1 high findings, 2 read error or bad CSV.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
SKILLS = ["reading", "listening", "speaking", "writing"]
INVENTORY = Path(__file__).resolve().parent.parent / "references" / "core-inventory-by-level.md"


def load_inventory(path):
    items = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0] in LEVELS:
            items.append((cells[0], cells[1], [k.strip().lower() for k in cells[2].split(",") if k.strip()]))
    if not items:
        raise ValueError(f"no inventory rows in {path}")
    return items


def matches(keywords, text):
    return any(re.search(rf"(?<![\w-]){re.escape(k)}(s|es)?(?![\w-])", text) for k in keywords)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--level", type=str.upper, choices=LEVELS, required=True, help="exit level of the course")
    ap.add_argument("--from", dest="start", type=str.upper, choices=LEVELS, help="lowest level the course also covers")
    ap.add_argument("--inventory", default=INVENTORY)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            units = list(csv.DictReader(fh))
        inv = load_inventory(a.inventory)
        if not units or "grammar" not in units[0]:
            raise ValueError("syllabus needs at least unit and grammar columns")
    except (OSError, csv.Error, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    top = LEVELS.index(a.level)
    low = LEVELS.index(a.start) if a.start else top
    f = []
    grammar = [(u.get("unit", str(i)), (u.get("grammar") or "").lower()) for i, u in enumerate(units, 1)]
    covered = 0
    core = [it for it in inv if low <= LEVELS.index(it[0]) <= top]
    for lvl, item, keys in core:
        if any(matches(keys, g) for _, g in grammar):
            covered += 1
        else:
            f.append(("SY002", "medium", f"{lvl} core item not covered: {item}"))
    for lvl, item, keys in inv:
        if LEVELS.index(lvl) > top:
            for unit, g in grammar:
                if matches(keys, g):
                    f.append(("SY003", "medium", f"unit {unit}: '{item}' is {lvl}, above the {a.level} course"))
    for u in units:
        uid = u.get("unit", "?")
        if not (u.get("can_do") or "").strip():
            f.append(("SY001", "high", f"unit {uid} has no can-do statement"))
        if not ((u.get("vocabulary") or "").strip() or (u.get("functions") or "").strip()):
            f.append(("SY005", "low", f"unit {uid} has no vocabulary or functions"))
    for s in SKILLS:
        n = sum(s in (u.get("skills") or "").lower() for u in units)
        if n < len(units) / 2:
            f.append(("SY004", "medium", f"{s} appears in {n} of {len(units)} units"))
    print(f"{len(units)} units, {a.start + '-' if a.start else ''}{a.level}: {covered}/{len(core)} core grammar items covered")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
