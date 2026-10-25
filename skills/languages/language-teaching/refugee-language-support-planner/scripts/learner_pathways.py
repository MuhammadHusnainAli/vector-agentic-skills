#!/usr/bin/env python3
"""Suggest a learning pathway for each refugee or migrant learner and group them into classes by pathway and time.

CSV columns: name, english (pre-A1, A1, A2, B1, B2), l1_literacy (none, basic, fluent), l1_script (roman / other),
schooling_years, goal (work, school-children, health, study, daily-life), availability (mornings, evenings,
weekends), childcare (y/n)

Pathways:
  Foundation literacy   little or no L1 literacy or under 4 years of schooling, English pre-A1/A1
  Script transition     literate in a non-Roman script, English pre-A1/A1
  Settlement ESOL       English A1-A2 (or literate beginners in a Roman script)
  Work / study          English B1+; vocational or academic depending on the goal

Only learning information is used; do not record trauma, asylum status or other sensitive details in this file.

Usage:
    python learner_pathways.py intake.csv [--max-class 12]

Exit codes: 0 printed, 2 read error or missing columns.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict

HOURS = {"Foundation literacy": "6-10 h/week, small class (max 10), oral English + phonics + functional literacy",
         "Script transition": "6-8 h/week, Roman alphabet, sound-letter links, then settlement topics",
         "Settlement ESOL": "4-8 h/week, settlement topics (health, housing, transport, school, work)",
         "Work / study": "4-6 h/week, vocational English or academic preparation; link to training providers"}


def pathway(r):
    eng = r["english"].strip().upper()
    lit = r.get("l1_literacy", "").strip().lower()
    school = float(r.get("schooling_years") or 0)
    beginner = eng in ("PRE-A1", "A1")
    if beginner and (lit in ("none", "basic") or school < 4):
        return "Foundation literacy"
    if beginner and r.get("l1_script", "").strip().lower() not in ("roman", "latin"):
        return "Script transition"
    if eng in ("PRE-A1", "A1", "A2"):
        return "Settlement ESOL"
    return "Work / study"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--max-class", type=int, default=12)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or not {"name", "english"} <= set(rows[0]):
            raise ValueError("needs at least name and english columns")
        groups = defaultdict(list)
        for r in rows:
            r["pathway"] = pathway(r)
            groups[(r["pathway"], (r.get("availability") or "any").strip().lower())].append(r)
    except (OSError, csv.Error, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"{len(rows)} learners\n")
    print("| Learner | English | L1 literacy | Schooling | Pathway | Goal |\n|---------|---------|-------------|-----------|---------|------|")
    for r in rows:
        print(f"| {r['name']} | {r['english']} | {r.get('l1_literacy', '')} | {r.get('schooling_years', '')} | "
              f"{r['pathway']} | {r.get('goal', '')} |")
    print("\nClasses:")
    for (path, when), members in sorted(groups.items()):
        cap = 10 if path == "Foundation literacy" else a.max_class
        for i in range(0, len(members), cap):
            chunk = members[i:i + cap]
            print(f"  {path} ({when}), {len(chunk)} learner{'s' if len(chunk) > 1 else ''}: " + ", ".join(m["name"] for m in chunk))
    print("\nPathway guidance:")
    for path in sorted({r["pathway"] for r in rows}):
        print(f"  {path}: {HOURS[path]}")
    care = sum((r.get("childcare") or "").strip().lower() in ("y", "yes") for r in rows)
    goals = Counter((r.get("goal") or "").strip().lower() for r in rows if r.get("goal"))
    if care:
        print(f"\nChildcare needed by {care} learner(s): arrange a creche or schedule in school hours")
    if goals:
        print("Goals: " + ", ".join(f"{g} {n}" for g, n in goals.most_common()) + " - weight settlement topics accordingly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
