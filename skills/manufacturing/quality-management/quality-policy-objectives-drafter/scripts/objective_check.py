#!/usr/bin/env python3
"""Check a quality objectives register against ISO 9001:2015 clause 6.2 (and SMART practice).

CSV columns (header names, any order; missing columns count as blank):
  objective, function, metric, baseline, target, due, owner, resources, evaluation, policy_link

Checks per objective:
  OB001 high    target has no number (not measurable)
  OB002 high    no owner (6.2.2 c: who will be responsible)
  OB003 medium  no due date, unreadable date, or already past --today (6.2.2 d: when)
  OB004 medium  no baseline, so improvement cannot be shown
  OB005 medium  no resources / action plan (6.2.2 a, b)
  OB006 medium  no evaluation method or frequency (6.2.2 e)
  OB007 low     not linked to a policy commitment (6.2.1 a)
  OB008 medium  target is not better than the baseline ('<' targets must be below it, '>' above)
Register-level:
  OB009 medium  a function listed in --functions has no objective (6.2.1: relevant functions and levels)

Usage:
    python objective_check.py objectives.csv
    python objective_check.py objectives.csv --today 2026-10-24 --functions Production Quality Sales Purchasing

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import csv
import datetime as dt
import re
import sys

NUM = re.compile(r"-?\d+(?:\.\d+)?")


def first_num(s):
    m = NUM.search(s or "")
    return float(m.group()) if m else None


def lower_is_better(target, metric):
    t = (target or "").strip().lower()
    if t.startswith(("<", "≤", "below", "under", "max", "reduce")):
        return True
    if t.startswith((">", "≥", "above", "over", "min", "increase", "at least")):
        return False
    return bool(re.search(r"scrap|defect|ppm|complaint|reject|cost of poor|copq|lead time|downtime|rework|returns",
                          (metric or "").lower())) or None


def check_row(r, today):
    out = []
    get = lambda k: (r.get(k) or "").strip()
    target, base = get("target"), get("baseline")
    tv, bv = first_num(target), first_num(base)
    if tv is None:
        out.append(("OB001", "high", f"target '{target or 'blank'}' has no number; make it measurable"))
    if not get("owner"):
        out.append(("OB002", "high", "no owner"))
    due = get("due")
    if not due:
        out.append(("OB003", "medium", "no due date"))
    else:
        try:
            d = dt.date.fromisoformat(due[:10])
            if today and d < today:
                out.append(("OB003", "medium", f"due {d} has passed; record the result and set the next target"))
        except ValueError:
            out.append(("OB003", "medium", f"due date '{due}' is not YYYY-MM-DD"))
    if bv is None:
        out.append(("OB004", "medium", "no baseline; improvement cannot be demonstrated"))
    if not get("resources"):
        out.append(("OB005", "medium", "no resources or action plan (what will be done, with what)"))
    if not get("evaluation"):
        out.append(("OB006", "medium", "no evaluation method/frequency (e.g. 'monthly KPI review, MR quarterly')"))
    if not get("policy_link"):
        out.append(("OB007", "low", "not linked to a policy commitment"))
    if tv is not None and bv is not None:
        lib = lower_is_better(target, get("metric"))
        if lib is True and tv >= bv:
            out.append(("OB008", "medium", f"lower is better but target {tv:g} is not below baseline {bv:g}"))
        elif lib is False and tv <= bv:
            out.append(("OB008", "medium", f"higher is better but target {tv:g} is not above baseline {bv:g}"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="objectives register CSV, or - for stdin")
    ap.add_argument("--today", type=dt.date.fromisoformat, help="date for overdue checks (YYYY-MM-DD)")
    ap.add_argument("--functions", nargs="*", default=[], help="functions that must each have an objective")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or "objective" not in rows[0]:
        print("error: CSV needs an 'objective' column and at least one row", file=sys.stderr)
        return 2
    high = total = 0
    for i, r in enumerate(rows, 1):
        f = check_row(r, a.today)
        score = 7 - len({c for c, _, _ in f if c in ("OB001", "OB002", "OB003", "OB004", "OB005", "OB006", "OB007")})
        print(f"[{i}] {r['objective'].strip()}  ({r.get('function') or 'no function'})  SMART {score}/7")
        for code, sev, msg in f:
            print(f"    {code} [{sev}] {msg}")
        high += sum(s == "high" for _, s, _ in f)
        total += len(f)
    covered = {(r.get("function") or "").strip().lower() for r in rows}
    for fn in a.functions:
        if fn.lower() not in covered:
            print(f"OB009 [medium] function '{fn}' has no quality objective")
            total += 1
    print(f"\n{len(rows)} objective(s), {total} finding(s), {high} high")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
