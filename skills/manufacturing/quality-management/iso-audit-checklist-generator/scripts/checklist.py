#!/usr/bin/env python3
"""Generate an ISO 9001 audit checklist for a process or a set of clauses.

Questions come from references/question-bank.md (open "show me" questions with evidence to sample).
Choose clauses directly, or name a common process to get its usual clause set. --turtle adds the six
turtle-diagram questions (inputs, outputs, who, with what, how, measures) for the named process.

Usage:
    python checklist.py --clauses 8.4 8.5.1 7.1.5
    python checklist.py --process purchasing --turtle
    python checklist.py --process production --csv > checklist.csv
    python checklist.py --list-processes

Exit codes: 0 printed, 1 no questions for the selection, 2 usage error.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

BANK = Path(__file__).resolve().parent.parent / "references" / "question-bank.md"
ALWAYS = ["6.1", "6.2", "7.2", "7.5", "9.1", "10.2"]   # asked in every process audit
PROCESSES = {
    "leadership": ["4.1", "4.2", "4.3", "4.4", "5.1", "5.2", "5.3", "6.3", "9.3", "10.3"],
    "sales": ["8.2", "7.4"],
    "design": ["8.3", "7.1.6"],
    "purchasing": ["8.4"],
    "production": ["8.1", "8.5.1", "8.5.2", "8.5.6", "7.1.3", "7.1.5", "7.3"],
    "inspection": ["8.6", "8.7", "7.1.5", "8.5.2"],
    "warehouse": ["8.5.4", "8.5.2", "8.6"],
    "maintenance": ["7.1.3"],
    "hr": ["7.2", "7.3", "7.1.6"],
    "quality": ["9.1", "9.2", "10.2", "8.7", "7.5"],
}
TURTLE = [
    ("Inputs", "What triggers this process and what do you receive? What happens if an input is wrong?"),
    ("Outputs", "What does this process deliver, to whom, and how do you know it is right?"),
    ("With what", "What equipment, software and materials are used? Are they maintained and fit for purpose?"),
    ("With whom", "Who does the work, what competence do they need and how is it confirmed?"),
    ("How", "Which procedures, instructions and criteria control the work? Are they current and followed?"),
    ("Measures", "Which KPIs and targets apply? Show the trend and the actions taken."),
]


def load_bank():
    bank, cur = {}, None
    for line in BANK.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^### (\d+(?:\.\d+)*) (.+)$", line)
        if m:
            cur = m.group(1)
            bank[cur] = {"title": m.group(2), "q": []}
        elif cur and line.startswith("- ") and "|" in line:
            q, ev = line[2:].rsplit("|", 1)
            bank[cur]["q"].append((q.strip(), ev.strip()))
    return bank


def pick(bank, clause):
    if clause in bank:
        return [clause]
    kids = [c for c in bank if c.startswith(clause + ".")]
    if kids:
        return kids
    parent = clause.rsplit(".", 1)[0]
    return [parent] if "." in clause and parent in bank else []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clauses", nargs="*", default=[], help="clause numbers, e.g. 8.4 8.5.1")
    ap.add_argument("--process", help="process name: " + ", ".join(PROCESSES))
    ap.add_argument("--turtle", action="store_true", help="add turtle-diagram questions for the process")
    ap.add_argument("--no-common", action="store_true", help="skip the clauses asked in every process audit")
    ap.add_argument("--csv", action="store_true", help="CSV with result and notes columns to fill in")
    ap.add_argument("--list-processes", action="store_true")
    a = ap.parse_args()
    if a.list_processes:
        for p, cl in PROCESSES.items():
            print(f"{p:<12}{' '.join(cl)}")
        return 0
    clauses = list(a.clauses)
    if a.process:
        key = a.process.strip().lower()
        if key not in PROCESSES:
            print(f"error: unknown process {a.process!r}; choose from {', '.join(PROCESSES)} or use --clauses", file=sys.stderr)
            return 2
        clauses += PROCESSES[key]
        if not a.no_common:
            clauses += ALWAYS
    if not clauses:
        print("error: give --clauses or --process", file=sys.stderr)
        return 2
    bank = load_bank()
    selected = []
    for c in clauses:
        for k in pick(bank, c):
            if k not in selected:
                selected.append(k)
    selected.sort(key=lambda c: [int(x) for x in c.split(".")])
    items = [("turtle", t, q, "Process description, observation") for t, q in TURTLE] if a.turtle else []
    for c in selected:
        items += [(c, bank[c]["title"], q, ev) for q, ev in bank[c]["q"]]
    if not items:
        print("no questions match that selection", file=sys.stderr)
        return 1
    if a.csv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["no", "clause", "topic", "question", "evidence_to_sample", "result", "notes"])
        for i, (c, t, q, ev) in enumerate(items, 1):
            w.writerow([i, c, t, q, ev, "", ""])
        return 0
    title = f"process: {a.process}" if a.process else "clauses: " + ", ".join(a.clauses)
    print(f"# Audit checklist - {title}\n")
    print("Result key: C = conforms, NC = nonconformity, OFI = opportunity for improvement\n")
    print("| # | Clause | Question | Evidence to sample | Result | Notes |")
    print("|---|--------|----------|--------------------|--------|-------|")
    for i, (c, t, q, ev) in enumerate(items, 1):
        label = t if c == "turtle" else f"{c} {t}"
        print(f"| {i} | {label} | {q} | {ev} |  |  |")
    print(f"\n{len(items)} questions. Sample at least 3 records per question where records exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
