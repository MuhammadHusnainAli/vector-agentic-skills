#!/usr/bin/env python3
"""Build a lesson observation form for language teachers from the criteria bank.

Choose areas by name or a word in the name (e.g. "classroom" matches Classroom management). --developmental drops the rating column and adds reflection questions for peer or coaching
observations; otherwise a 1-4 rating with n/o is used.

Usage:
    python observation_form.py --areas classroom "error correction" engagement
    python observation_form.py --areas all --teacher "J. Doe" --date 2026-11-02
    python observation_form.py --areas clarification --developmental

Exit codes: 0 printed, 2 bank unreadable or an area matches nothing.
"""

import argparse
import re
import sys
from collections import OrderedDict
from pathlib import Path

BANK = Path(__file__).resolve().parent.parent / "references" / "observation-criteria.md"


def read(path):
    """Rows of the first table, the one headed | Area | Criterion | Look-fors |."""
    rows, inside = [], False
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not inside:
            inside = line.startswith("|") and cells[:1] == ["Area"]
        elif not line.startswith("|"):
            break
        elif len(cells) == 3 and not re.fullmatch(r"-+", cells[0]):
            rows.append(cells)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--areas", nargs="+", required=True, help="area names or words, or 'all'")
    ap.add_argument("--developmental", action="store_true")
    ap.add_argument("--teacher", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--bank", default=BANK)
    a = ap.parse_args()
    try:
        rows = read(a.bank)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    areas = OrderedDict()
    for area, crit, look in rows:
        areas.setdefault(area, []).append((crit, look))
    if [x.lower() for x in a.areas] == ["all"]:
        chosen = list(areas)
    else:
        chosen = []
        for want in a.areas:
            hits = [ar for ar in areas if want.lower() in ar.lower()]
            if not hits:
                print(f"error: no area matches '{want}'; areas: {', '.join(areas)}", file=sys.stderr)
                return 2
            chosen += [h for h in hits if h not in chosen]
    kind = "Developmental" if a.developmental else "Evaluative"
    print(f"# Lesson Observation ({kind})\n")
    print("| Teacher | Observer | Date | Class / level | Lesson aim |\n|---------|----------|------|---------------|------------|")
    print(f"| {a.teacher} |  | {a.date} |  |  |\n")
    if a.developmental:
        print("Focus agreed with the teacher before the lesson: ______\n")
    for ar in chosen:
        print(f"## {ar}\n")
        if a.developmental:
            print("| Criterion | Look-fors | Evidence (time, what was said/done) |\n|---|---|---|")
        else:
            print("| Criterion | Look-fors | Evidence (time, what was said/done) | 4 3 2 1 n/o |\n|---|---|---|---|")
        for crit, look in areas[ar]:
            print(f"| {crit} | {look} |  |" + ("" if a.developmental else "  |"))
        print()
    if a.developmental:
        print("## Reflection questions\n")
        print("1. What went as planned? What surprised you?\n2. What evidence shows learners achieved the aim?\n"
              "3. What would you change, and why?\n4. What do you want to try next time?\n")
    print("## Strengths\n\n1.\n2.\n\n## Action points (1-2, specific, with a review date)\n\n1.\n2.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
