#!/usr/bin/env python3
"""Plan an ISO 9001 certification timeline from start to certificate, plus the 3-year audit cycle.

Phase lengths scale with headcount and starting maturity; the records period before stage 2 is fixed at
12 weeks minimum because certification bodies want to see the system operating (one internal audit cycle and
one management review). Audit days follow the IAF MD 5 QMS table (initial = stage 1 + stage 2; surveillance
about 1/3 and recertification about 2/3 of initial); certification bodies adjust by up to +/-30% for
complexity, design responsibility and sites.

Usage:
    python roadmap.py --start 2026-11-02 --employees 40
    python roadmap.py --start 2026-11-02 --employees 180 --maturity partial --target 2027-06-30
    python roadmap.py --start 2026-11-02 --employees 12 --maturity basic --json

Maturity: none (no QMS), basic (some procedures/records exist), partial (another ISO system or a lapsed QMS).
Exit codes: 0 plan printed (target met if given), 1 target date not achievable, 2 usage error.
"""

import argparse
import datetime as dt
import json
import sys

# IAF MD 5 QMS table: (max effective personnel, initial audit days for stage 1 + stage 2)
MD5 = [(5, 1.5), (10, 2), (15, 2.5), (25, 3), (45, 4), (65, 5), (85, 6), (125, 7), (175, 8), (275, 9),
       (425, 10), (625, 11), (875, 12), (1175, 13), (1550, 14), (2025, 15), (2675, 16), (3450, 17),
       (4350, 18), (5450, 19), (6800, 20), (8500, 21), (10700, 22)]
MATURITY = {"none": 1.0, "basic": 0.75, "partial": 0.5}

# (phase, base weeks, scales with size/maturity, starts after phase index or None = previous, deliverable)
PHASES = [
    ("Gap analysis and project set-up", 3, True, "Gap report, project plan, steering group, budget"),
    ("Context, scope, processes, policy, objectives", 4, True, "Issue and party registers, scope, process map, policy, objectives"),
    ("Document and implement processes", 10, True, "Procedures, WIs, forms, registers in use; risk register"),
    ("Train staff and internal auditors", 3, True, "Awareness for all; 2+ trained internal auditors"),
    ("Operate the QMS and build records", 12, False, "At least 3 months of records for every process"),
    ("Full internal audit cycle", 4, True, "Audit of every process and clause; corrective actions raised"),
    ("Management review", 1, False, "Minutes covering all 9.3.2 inputs and decisions"),
    ("Stage 1 audit (readiness)", 1, False, "Stage 1 report: concerns to close before stage 2"),
    ("Close stage 1 concerns", 3, False, "Evidence for every stage 1 concern"),
    ("Stage 2 audit (certification)", 1, False, "Stage 2 report: recommendation or nonconformities"),
    ("Close nonconformities and certificate", 6, False, "Corrective action plans accepted; certificate issued"),
]


def audit_days(n):
    for cap, days in MD5:
        if n <= cap:
            return days
    return 22 + 0.5 * ((n - 10700) // 2000 + 1)  # approximate progression above the table


def size_factor(n):
    return 1.0 if n <= 25 else 1.25 if n <= 100 else 1.5 if n <= 500 else 2.0


def plan(start, n, maturity):
    f = size_factor(n) * MATURITY[maturity]
    rows, cur = [], start
    audit_start = None
    for i, (name, weeks, scales, deliverable) in enumerate(PHASES):
        w = max(1, round(weeks * f)) if scales else weeks
        if i == 3:      # training runs alongside implementation: starts 2 weeks before it ends
            s = rows[2][2] - dt.timedelta(weeks=min(2, rows[2][3]))
        elif i == 5:    # internal audit happens in the last part of the records period
            s = rows[4][2] - dt.timedelta(weeks=w + 1)
            audit_start = s
        elif i == 6:
            s = max(cur, audit_start + dt.timedelta(weeks=rows[5][3]))
        else:
            s = cur
        e = s + dt.timedelta(weeks=w)
        rows.append((name, s, e, w, deliverable))
        cur = max(cur, e) if i not in (3, 5) else cur
        if i == 3:
            cur = max(rows[2][2], e)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=dt.date.fromisoformat, required=True, help="project start YYYY-MM-DD")
    ap.add_argument("--employees", type=int, required=True, help="effective number of personnel in scope")
    ap.add_argument("--maturity", choices=MATURITY, default="none")
    ap.add_argument("--target", type=dt.date.fromisoformat, help="desired certificate date")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.employees < 1:
        print("error: --employees must be at least 1", file=sys.stderr)
        return 2
    rows = plan(a.start, a.employees, a.maturity)
    cert = rows[-1][2]
    days = audit_days(a.employees)
    # surveillance within 12 months of the certification decision, then yearly; recertification before expiry
    cycle = [("Surveillance audit 1", cert + dt.timedelta(days=365), round(days / 3, 1)),
             ("Surveillance audit 2", cert + dt.timedelta(days=730), round(days / 3, 1)),
             ("Recertification audit", cert + dt.timedelta(days=1095 - 90), round(days * 2 / 3, 1))]
    ok = a.target is None or cert <= a.target
    if a.json:
        print(json.dumps({"phases": [{"phase": r[0], "start": str(r[1]), "end": str(r[2]), "weeks": r[3],
                                      "deliverable": r[4]} for r in rows],
                          "initial_audit_days": days, "certificate": str(cert),
                          "cycle": [{"audit": c[0], "by": str(c[1]), "days": c[2]} for c in cycle],
                          "target_met": ok}, indent=2))
    else:
        print(f"ISO 9001 roadmap: {a.employees} people, maturity '{a.maturity}', start {a.start}\n")
        print(f"{'Phase':<48}{'Start':<12}{'End':<12}{'Wks':>4}  Deliverable")
        for name, s, e, w, d in rows:
            print(f"{name:<48}{s!s:<12}{e!s:<12}{w:>4}  {d}")
        months = (cert - a.start).days / 30.4
        print(f"\nCertificate expected: {cert} (~{months:.0f} months)")
        print(f"Audit days (IAF MD 5, before CB adjustments): initial {days:g} (stage 1 + stage 2)")
        for name, by, d in cycle:
            print(f"  {name:<24} by {by}  ~{d:g} days")
        print("Book the certification body by "
              f"{rows[7][1] - dt.timedelta(weeks=8)} (8 weeks' lead time before stage 1).")
        if a.target:
            gap = (a.target - cert).days
            print(f"Target {a.target}: " + (f"achievable with {gap} days' slack" if ok else
                  f"NOT achievable - {-gap} days short; raise maturity (consultant, existing system) or move the date"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
