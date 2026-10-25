#!/usr/bin/env python3
"""Build a supplier audit / self-assessment questionnaire for a supplier type and risk level.

Sections and questions come from references/question-sets.md. Low risk gets the core sections, medium adds
planning, sub-tier and traceability sections, high adds the process-specific section. Knockout (KO) questions
are marked: a KO scored 0 or 1 blocks approval in score_questionnaire.py.

Scoring scale written into the output: 0 = not in place, 1 = partly, 2 = mostly, 3 = fully, na = not applicable.

Usage:
    python questionnaire.py --type machining --risk high
    python questionnaire.py --type distributor --risk low --csv > sa.csv

Exit codes: 0 printed, 2 usage error.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

SETS = Path(__file__).resolve().parent.parent / "references" / "question-sets.md"
TYPES = ["machining", "electronics", "chemical", "distributor", "service"]
RISK = {"low": 0, "medium": 1, "high": 2}


def load():
    sections, cur = [], None
    for line in SETS.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (.+?) \| weight (\d+) \| ([\w,]+) \| (\w+)$", line)
        if m:
            cur = {"name": m.group(1), "weight": int(m.group(2)), "types": m.group(3).split(","),
                   "risk": m.group(4), "q": []}
            sections.append(cur)
        elif cur and line.startswith("- ") and "|" in line:
            body, ev = line[2:].rsplit("|", 1)
            ko = body.startswith("[KO]")
            cur["q"].append((body.replace("[KO]", "", 1).strip(), ev.strip(), ko))
    return sections


def select(sections, kind, risk):
    return [s for s in sections if ("all" in s["types"] or kind in s["types"]) and RISK[s["risk"]] <= RISK[risk]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--type", required=True, choices=TYPES, dest="kind")
    ap.add_argument("--risk", required=True, choices=RISK)
    ap.add_argument("--csv", action="store_true", help="CSV with a score column, for score_questionnaire.py")
    a = ap.parse_args()
    secs = select(load(), a.kind, a.risk)
    total_w = sum(s["weight"] for s in secs)
    rows = []
    for si, s in enumerate(secs, 1):
        w = round(100 * s["weight"] / total_w, 1)
        for qi, (q, ev, ko) in enumerate(s["q"], 1):
            rows.append((f"{si}.{qi}", s["name"], w, "yes" if ko else "", q, ev))
    if a.csv:
        out = csv.writer(sys.stdout, lineterminator="\n")
        out.writerow(["id", "section", "section_weight", "knockout", "question", "evidence", "score", "comment"])
        for r in rows:
            out.writerow(list(r) + ["", ""])
        return 0
    print(f"# Supplier questionnaire - {a.kind}, {a.risk} risk\n")
    print("Score each question: 0 not in place, 1 partly, 2 mostly, 3 fully, na not applicable.")
    print("KO = knockout question: 0 or 1 blocks approval.\n")
    for s in secs:
        w = round(100 * s["weight"] / total_w, 1)
        print(f"## {s['name']} (weight {w:g}%)\n")
        print("| # | Question | Evidence | Score |\n|---|----------|----------|-------|")
        for r in (r for r in rows if r[1] == s["name"]):
            print(f"| {r[0]} | {'**KO** ' if r[3] else ''}{r[4]} | {r[5]} |  |")
        print()
    print(f"{len(rows)} questions in {len(secs)} sections, {sum(1 for r in rows if r[3])} knockout.")
    if a.risk == "high":
        print("High risk: verify on site; do not rely on self-assessment answers alone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
