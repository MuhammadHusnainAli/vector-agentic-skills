#!/usr/bin/env python3
"""Map curriculum units to ACTFL's three modes of communication and check each unit's performance assessment.

CSV columns: unit, interpretive, interpersonal, presentational, assessment
(each mode cell describes the unit's main task in that mode; assessment describes the unit's summative task,
ideally an Integrated Performance Assessment covering all three modes)

Checks:
  AC001 high    unit without a performance assessment
  AC002 medium  unit with no task in a mode
  AC003 medium  'interpersonal' task is scripted or rehearsed (skit, memorised dialogue, presentation): that is
                presentational; interpersonal means spontaneous two-way negotiation of meaning
  AC004 low     interpretive task is translation or word lists rather than understanding a text
  AC005 low     assessment does not cover all three modes

Usage:
    python mode_coverage.py units.csv

Exit codes: 0 no high findings, 1 high findings, 2 read error or bad CSV.
"""

import argparse
import csv
import re
import sys

MODES = ["interpretive", "interpersonal", "presentational"]
SCRIPTED = re.compile(r"\b(skit|memori[sz]e|script(ed)?|rehears|present(ation)?|perform|recite|read aloud)", re.I)
LOW_INTERP = re.compile(r"\b(translat\w*|vocab(ulary)? list|word list|define words|flashcards?)\b", re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            units = list(csv.DictReader(fh))
        if not units or not set(MODES) <= set(units[0]):
            raise ValueError("needs unit, interpretive, interpersonal, presentational and assessment columns")
    except (OSError, csv.Error, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f = []
    print("| Unit | Interpretive | Interpersonal | Presentational | Assessment |")
    print("|------|--------------|---------------|----------------|------------|")
    for u in units:
        uid = u.get("unit", "?")
        cells = {m: (u.get(m) or "").strip() for m in MODES}
        assess = (u.get("assessment") or "").strip()
        print(f"| {uid} | " + " | ".join("x" if cells[m] else "-" for m in MODES) + f" | {'x' if assess else '-'} |")
        for m in MODES:
            if not cells[m]:
                f.append(("AC002", "medium", f"unit {uid}: no {m} task"))
        if SCRIPTED.search(cells["interpersonal"]):
            f.append(("AC003", "medium", f"unit {uid}: interpersonal task '{cells['interpersonal'][:40]}' is rehearsed - that is presentational"))
        if LOW_INTERP.search(cells["interpretive"]):
            f.append(("AC004", "low", f"unit {uid}: interpretive task '{cells['interpretive'][:40]}' is not text comprehension"))
        if not assess:
            f.append(("AC001", "high", f"unit {uid}: no performance assessment"))
        elif not (re.search(r"\bipa\b|integrated", assess, re.I) or all(m[:6] in assess.lower() for m in MODES)):
            f.append(("AC005", "low", f"unit {uid}: assessment does not cover all three modes (consider an IPA)"))
    print()
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: every unit works in all three modes with an integrated assessment")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
