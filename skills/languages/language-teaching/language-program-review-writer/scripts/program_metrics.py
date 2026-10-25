#!/usr/bin/env python3
"""Summarise language programme outcomes by course: retention, pass rate, level gain, attendance, satisfaction.

CSV columns: student, course, status (completed / withdrawn / continuing), start_level, end_level (CEFR, + allowed,
or blank), passed (yes/no), attendance (%), satisfaction (1-5); only student, course and status are required.

Level gain counts half-steps: A2 -> A2+ = 0.5, A2 -> B1 = 1.

Findings (thresholds can be changed):
  PM001 high    retention below --retention % (default 75): withdrawn / (completed + withdrawn)
  PM002 medium  pass rate below --pass % (default 75) among completers
  PM003 medium  median level gain of completers is zero
  PM004 low     mean attendance below --attendance % (default 80)
  PM005 low     mean satisfaction below 3.5 / 5
  PM006 info    fewer than 10 students: treat percentages with caution

Usage:
    python program_metrics.py students.csv [--retention 75] [--pass 75] [--attendance 80]

Exit codes: 0 no high findings, 1 high findings, 2 read error or bad CSV.
"""

import argparse
import csv
import statistics
import sys
from collections import defaultdict

LEVELS = {"PRE-A1": 0, "A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


def level(s):
    s = (s or "").strip().upper()
    if not s:
        return None
    return LEVELS[s.rstrip("+")] + (0.5 if s.endswith("+") else 0)


def num(s):
    try:
        return float(str(s).strip().rstrip("%"))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--retention", type=float, default=75)
    ap.add_argument("--pass", dest="pass_", type=float, default=75)
    ap.add_argument("--attendance", type=float, default=80)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or not {"student", "course", "status"} <= set(rows[0]):
            raise ValueError("needs student, course and status columns")
        by = defaultdict(list)
        for r in rows:
            r["_gain"] = (level(r.get("end_level")) - level(r.get("start_level"))
                          if level(r.get("end_level")) is not None and level(r.get("start_level")) is not None else None)
            by[r["course"].strip()].append(r)
    except (OSError, csv.Error, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f = []
    print("| Course | n | Retention | Pass | Median gain | Attendance | Satisfaction |")
    print("|--------|---|-----------|------|-------------|------------|--------------|")
    for course, rs in sorted(by.items()):
        st = [r["status"].strip().lower() for r in rs]
        done, gone = st.count("completed"), st.count("withdrawn")
        ret = 100 * done / (done + gone) if done + gone else None
        comp = [r for r in rs if r["status"].strip().lower() == "completed"]
        passed = [r for r in comp if (r.get("passed") or "").strip().lower() in ("yes", "y", "true", "1")]
        pas = 100 * len(passed) / len(comp) if comp and any(r.get("passed") for r in comp) else None
        gains = [r["_gain"] for r in comp if r["_gain"] is not None]
        gain = statistics.median(gains) if gains else None
        att = [x for x in (num(r.get("attendance")) for r in rs) if x is not None]
        sat = [x for x in (num(r.get("satisfaction")) for r in rs) if x is not None]
        att_m = statistics.mean(att) if att else None
        sat_m = statistics.mean(sat) if sat else None
        fmt = lambda v, s="": "-" if v is None else f"{v:.0f}{s}" if s == "%" else f"{v:g}{s}"
        print(f"| {course} | {len(rs)} | {fmt(ret, '%')} | {fmt(pas, '%')} | {fmt(gain)} | {fmt(att_m, '%')} | "
              f"{'-' if sat_m is None else f'{sat_m:.1f}'} |")
        if ret is not None and ret < a.retention:
            f.append(("PM001", "high", f"{course}: retention {ret:.0f}% ({gone} withdrew) is below {a.retention:g}%"))
        if pas is not None and pas < a.pass_:
            f.append(("PM002", "medium", f"{course}: pass rate {pas:.0f}% is below {a.pass_:g}%"))
        if gain is not None and gain <= 0:
            f.append(("PM003", "medium", f"{course}: median level gain of completers is {gain:g}"))
        if att_m is not None and att_m < a.attendance:
            f.append(("PM004", "low", f"{course}: mean attendance {att_m:.0f}% is below {a.attendance:g}%"))
        if sat_m is not None and sat_m < 3.5:
            f.append(("PM005", "low", f"{course}: mean satisfaction {sat_m:.1f}/5"))
        if len(rs) < 10:
            f.append(("PM006", "info", f"{course}: only {len(rs)} students; percentages are unstable"))
    print()
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    for code, sev, msg in sorted(f, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
