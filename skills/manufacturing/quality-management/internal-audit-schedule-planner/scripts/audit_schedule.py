#!/usr/bin/env python3
"""Build a risk-based 12-month internal audit programme (ISO 9001 9.2 / ISO 19011 5.x).

Processes CSV columns: process, department, clauses (';'-separated, e.g. 8.4;8.5.1), risk (high/medium/low),
last_result (none/good/minor/major), changed (yes/no), last_audit (YYYY-MM-DD, optional)
Auditors CSV columns (optional): auditor, department

Frequency: high risk = 2 audits a year, medium and low = 1 (--biennial-low lets low-risk processes with a good
last result be audited every 2 years). A major last result or a significant change adds one audit.
Each audit is placed near its due month (overdue ones in the first quarter) in the least-loaded month; auditors are assigned round-robin, never to their own department (9.2.2 c).

Checks:
  AS001 high    an ISO 9001 clause family (4-10) is covered by no process in the programme
  AS002 high    no independent auditor available for a process
  AS003 medium  process overdue (last audit older than its interval) - scheduled in the first quarter
  AS004 low     process never audited

Usage:
    python audit_schedule.py processes.csv --start 2027-01 --auditors auditors.csv
    python audit_schedule.py processes.csv --start 2027-01 --biennial-low --csv > programme.csv

Exit codes: 0 programme complete, 1 coverage or independence problems, 2 read/usage error.
"""

import argparse
import csv
import datetime as dt
import sys

FAMILIES = ["4", "5", "6", "7", "8", "9", "10"]
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def frequency(p, biennial_low):
    risk = (p.get("risk") or "medium").strip().lower()
    result = (p.get("last_result") or "none").strip().lower()
    n = 2 if risk == "high" else 1
    if result == "major" or (p.get("changed") or "").strip().lower() in ("yes", "y", "true"):
        n += 1
    if biennial_low and risk == "low" and result == "good" and n == 1:
        return 0.5
    return min(n, 4)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("processes", help="processes CSV")
    ap.add_argument("--start", required=True, help="first month of the programme, YYYY-MM")
    ap.add_argument("--auditors", help="auditors CSV (auditor, department)")
    ap.add_argument("--biennial-low", action="store_true", help="audit good low-risk processes every 2 years")
    ap.add_argument("--csv", action="store_true", help="print the programme as CSV")
    a = ap.parse_args()
    try:
        start = dt.date.fromisoformat(a.start + "-01")
        procs = read_csv(a.processes)
        auditors = read_csv(a.auditors) if a.auditors else []
    except (OSError, ValueError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not procs or "process" not in procs[0]:
        print("error: processes CSV needs a 'process' column", file=sys.stderr)
        return 2

    findings, events, plans = [], [], []
    load = [0] * 12
    for p in procs:
        name = p["process"].strip()
        f = frequency(p, a.biennial_low)
        interval = 12 / f
        last = (p.get("last_audit") or "").strip()
        if not last:
            findings.append(("AS004", "low", f"{name}: never audited - scheduled in the first quarter"))
            due = 0
        else:
            age = (start - dt.date.fromisoformat(last)).days / 30.44
            due = max(0, round(interval - age))
            if age > interval:
                findings.append(("AS003", "medium", f"{name}: last audited {last} ({age:.0f} months ago, interval {interval:g})"))
        if f < 1:
            if due > 11:
                p["_note"] = "every 2 years: next cycle"
                continue
            f = 1
        plans.append((due, name, p, int(f)))
    # overdue and soonest-due first; each process goes to the least-loaded month near its due month
    for due, name, p, count in sorted(plans, key=lambda x: (x[0], x[1])):
        step = 12 // count
        due = min(due, step - 1)
        window = range(max(0, due - 1), min(step - 1, due + 1 if due else 2) + 1)
        first = min(window, key=lambda m: (sum(load[m + k * step] for k in range(count)), abs(m - due), m))
        for k in range(count):
            m = first + k * step
            load[m] += 1
            events.append((m, name, p))

    by_dept = {}
    for au in auditors:
        by_dept.setdefault(au["auditor"].strip(), au.get("department", "").strip().lower())
    pool = list(by_dept)
    assigned_load = {x: 0 for x in pool}
    rows = []
    for m, name, p in sorted(events, key=lambda e: (e[0], e[1])):
        dept = (p.get("department") or "").strip().lower()
        auditor = ""
        if pool:
            eligible = [x for x in pool if by_dept[x] != dept]
            if eligible:
                auditor = min(eligible, key=lambda x: (assigned_load[x], x))
                assigned_load[auditor] += 1
            else:
                findings.append(("AS002", "high", f"{name}: every auditor belongs to {dept}; train one from another area"))
        month = dt.date(start.year + (start.month - 1 + m) // 12, (start.month - 1 + m) % 12 + 1, 1)
        rows.append((month.strftime("%Y-%m"), name, p.get("department", ""), p.get("risk", ""), p.get("clauses", ""), auditor or "TBD"))

    covered = set()
    for _, name, p in events:
        for c in (p.get("clauses") or "").split(";"):
            if c.strip():
                covered.add(c.strip().split(".")[0])
    for fam in FAMILIES:
        if fam not in covered:
            findings.append(("AS001", "high", f"clause {fam} is not covered by any audit this cycle; add it to a process scope"))

    if a.csv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["month", "process", "department", "risk", "clauses", "auditor"])
        w.writerows(rows)
    else:
        print(f"Internal audit programme {rows[0][0] if rows else a.start} - 12 months, {len(rows)} audits\n")
        print(f"{'Month':<9}{'Process':<30}{'Risk':<8}{'Clauses':<22}Auditor")
        for r in rows:
            print(f"{r[0]:<9}{r[1]:<30}{r[3]:<8}{r[4]:<22}{r[5]}")
        for p in procs:
            if p.get("_note"):
                print(f"{'-':<9}{p['process'].strip():<30}{p.get('risk', ''):<8}{p.get('clauses', ''):<22}({p['_note']})")
        print("\nAudits per month: " + " ".join(f"{MONTHS[(start.month - 1 + i) % 12]}:{n}" for i, n in enumerate(load)))
        if pool:
            print("Auditor load: " + ", ".join(f"{x} {n}" for x, n in sorted(assigned_load.items())))
    for code, sev, msg in findings:
        print(f"{code} [{sev}] {msg}", file=sys.stderr if a.csv else sys.stdout)
    return 1 if any(s == "high" for _, s, _ in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
