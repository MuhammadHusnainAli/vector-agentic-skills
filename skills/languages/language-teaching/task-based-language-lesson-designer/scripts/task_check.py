#!/usr/bin/env python3
"""Check a task-based lesson against Ellis's task criteria and the Willis TBL framework.

JSON:
  {
    "title": "Plan a class trip",
    "instructions": "In groups, agree on one day trip for the class within a 30 euro budget per person",
    "gap": "opinion",                       # information / opinion / reasoning
    "outcome": "One trip plan per group, presented to the class, then a class vote",
    "stages": [
      {"name": "Pre-task", "minutes": 8, "procedure": "Topic intro, brainstorm places, model recording"},
      {"name": "Task", "minutes": 12}, {"name": "Planning", "minutes": 8}, {"name": "Report", "minutes": 10},
      {"name": "Language focus", "minutes": 15, "procedure": "Ss find suggestion phrases in the transcript"}
    ]
  }

Checks:
  TB001 high    instructions focus on form ('use the present perfect', 'make sentences with'): an exercise, not a task
  TB002 high    no information, opinion or reasoning gap
  TB003 high    no non-linguistic outcome (decision, list, plan, solution, ranking, product)
  TB004 medium  pre-task pre-teaches the target structure: learners should draw on their own resources first
  TB005 medium  Willis stage missing (pre-task, task, planning, report, language focus)
  TB006 medium  language focus comes before the task
  TB007 low     no task repetition or planning time before the report
  TB008 low     a stage has no time limit

Usage:
    python task_check.py tbl.json

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import re
import sys

FORM = re.compile(r"\b(use|using|practi[cs]e|make sentences with|with the|correct form of)\s+(the\s+)?"
                  r"(present|past|future|perfect|continuous|passive|conditional|modal|comparative|superlative|"
                  r"going to|used to|will future|tense|grammar|structure|target language)", re.I)
GAP_WORDS = re.compile(r"\b(agree|decide|choose|rank|find out|find the differences|compare|solve|plan|negotiate|"
                       r"persuade|guess|predict|missing information|information gap|discuss and)\b", re.I)
OUTCOME = re.compile(r"\b(list|plan|decision|ranking|ranked|solution|answer|map|poster|vote|choice|product|"
                     r"itinerary|recommendation|agreement|order|winner|report|timetable|menu|budget)\b", re.I)
PRETEACH = re.compile(r"\b(pre-?teach|present|drill|explain)\b.*\b(grammar|structure|tense|form|target language)\b", re.I)
STAGES = [("pre-task", r"pre-?task|intro"), ("task", r"^\s*task\b|task cycle"), ("planning", r"plan"),
          ("report", r"report|present"), ("language focus", r"language focus|analysis|focus on form|practice")]


def kind(name):
    for k, pat in STAGES:
        if re.search(pat, name, re.I):
            return k
    return None


def check(t):
    f = []
    ins = str(t.get("instructions", ""))
    if FORM.search(ins):
        f.append(("TB001", "high", f"instructions ask for '{FORM.search(ins).group(0)}': give a goal, not a structure"))
    if not (t.get("gap") or GAP_WORDS.search(ins)):
        f.append(("TB002", "high", "no gap: learners need to share information, opinions or reasoning to finish"))
    if not (t.get("outcome") and OUTCOME.search(str(t["outcome"]))):
        f.append(("TB003", "high", "no clear outcome: say what learners produce (a decision, list, plan, solution)"))
    stages = t.get("stages") or []
    kinds = [kind(str(s.get("name", ""))) for s in stages]
    for s, k in zip(stages, kinds):
        if k == "pre-task" and PRETEACH.search(str(s.get("procedure", ""))):
            f.append(("TB004", "medium", "pre-task teaches the structure: introduce topic and task, not the grammar"))
        if not s.get("minutes"):
            f.append(("TB008", "low", f"'{s.get('name')}' has no time limit"))
    missing = [k for k, _ in STAGES if k not in kinds]
    if missing:
        f.append(("TB005", "medium", f"Willis stage(s) missing: {', '.join(missing)}"))
    if "language focus" in kinds and "task" in kinds and kinds.index("language focus") < kinds.index("task"):
        f.append(("TB006", "medium", "language focus is before the task: put it after, built on what learners needed"))
    if "planning" not in kinds and not re.search(r"repeat|again|second time", " ".join(str(s) for s in stages), re.I):
        f.append(("TB007", "low", "no planning time or task repetition: learners have no chance to improve accuracy"))
    return f, kinds


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tbl", help="task lesson JSON, or - for stdin")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.tbl == "-" else open(a.tbl, encoding="utf-8")
        with fh:
            t = json.load(fh)
        if not isinstance(t, dict):
            raise ValueError("JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f, kinds = check(t)
    crit = {c: not any(x[0] == c for x in f) for c in ("TB001", "TB002", "TB003")}
    print(f"{t.get('title', '(untitled)')}")
    print(f"Ellis criteria: meaning focus {'yes' if crit['TB001'] else 'NO'} | gap {'yes' if crit['TB002'] else 'NO'} | "
          f"outcome {'yes' if crit['TB003'] else 'NO'}")
    print("Stages: " + " -> ".join(k or "?" for k in kinds))
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    if not f:
        print("OK: a real task in a complete Willis cycle")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
