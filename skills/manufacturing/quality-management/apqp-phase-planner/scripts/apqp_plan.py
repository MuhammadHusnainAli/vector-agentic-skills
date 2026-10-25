#!/usr/bin/env python3
"""Back-schedule the five APQP phases from start of production (SOP) and track deliverables.

Phases (AIAG APQP): 1 Plan and define, 2 Product design and development, 3 Process design and development,
4 Product and process validation, 5 Launch, feedback, assessment and corrective action.
Phase 4 ends --ppap-lead weeks before SOP (PPAP approval); phase 3 overlaps the second half of phase 2;
phase 5 starts at SOP with a --safe-launch period of early-production containment.

Durations (weeks: P1, P2, P3, P4) by complexity: low 4/8/8/6, medium 6/16/14/10, high 8/26/20/14.
Build-to-print suppliers (--no-design) shorten phase 2 to design-input review and feasibility (1/3 of the time).

Usage:
    python apqp_plan.py --sop 2027-09-06 --complexity medium --today 2026-10-26
    python apqp_plan.py --sop 2027-09-06 --complexity high --no-design --status deliverables.csv --today 2027-03-01

Status CSV columns: deliverable, phase (1-5), status (done/in-progress/not-started)
Exit codes: 0 schedule feasible and nothing late, 1 compressed schedule or late deliverables, 2 usage error.
"""

import argparse
import csv
import datetime as dt
import sys

DUR = {"low": (4, 8, 8, 6), "medium": (6, 16, 14, 10), "high": (8, 26, 20, 14)}
NAMES = ["Plan and define", "Product design and development", "Process design and development",
         "Product and process validation", "Launch, feedback and corrective action"]
DELIVERABLES = {
    1: ["Design goals", "Reliability and quality goals", "Preliminary bill of materials", "Preliminary process flow chart",
        "Preliminary special characteristics", "Product assurance plan", "Management support (gate 1)"],
    2: ["DFMEA", "Design for manufacturing and assembly", "Design verification plan and report (DVP&R)",
        "Design reviews", "Prototype control plan", "Engineering drawings and specifications", "Material specifications",
        "Team feasibility commitment", "Equipment, tooling and gauge requirements", "Special characteristics list"],
    3: ["Packaging standards", "Process flow chart", "Floor plan layout", "Characteristics matrix", "PFMEA",
        "Pre-launch control plan", "Process instructions", "MSA plan", "Preliminary process capability plan"],
    4: ["Significant production run", "MSA evaluation", "Preliminary process capability (Ppk)", "PPAP submission and approval",
        "Production validation testing", "Packaging evaluation", "Production control plan", "Quality planning sign-off"],
    5: ["Safe-launch containment and exit", "Reduced variation (Cpk tracking)", "Customer satisfaction and delivery review",
        "Lessons learned"],
}


def wk(d, n):
    return d + dt.timedelta(weeks=n)


def schedule(sop, comp, design, ppap_lead, safe):
    d1, d2, d3, d4 = DUR[comp]
    if not design:
        d2 = max(2, round(d2 / 3))
    p4e = wk(sop, -ppap_lead)
    p4s = wk(p4e, -d4)
    p3e, p3s = p4s, wk(p4s, -d3)
    p2s = wk(p3s, -d2 / 2)          # phase 3 starts halfway through phase 2
    p2e = wk(p2s, d2)
    p1e, p1s = p2s, wk(p2s, -d1)
    return [(1, p1s, p1e), (2, p2s, p2e), (3, p3s, p3e), (4, p4s, p4e), (5, sop, wk(sop, safe))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sop", type=dt.date.fromisoformat, required=True, help="start of production YYYY-MM-DD")
    ap.add_argument("--complexity", choices=DUR, default="medium")
    ap.add_argument("--no-design", action="store_true", help="build-to-print: no product design responsibility")
    ap.add_argument("--ppap-lead", type=int, default=4, help="weeks between PPAP approval and SOP (default 4)")
    ap.add_argument("--safe-launch", type=int, default=13, help="weeks of early-production containment (default 13)")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--status", help="deliverable status CSV")
    a = ap.parse_args()
    plan = schedule(a.sop, a.complexity, not a.no_design, a.ppap_lead, a.safe_launch)
    rc = 0
    print(f"APQP plan: SOP {a.sop}, {a.complexity} complexity" + (", build-to-print" if a.no_design else "") + "\n")
    print(f"{'Phase':<44}{'Start':<12}{'End':<12}Gate")
    for n, s, e in plan:
        gate = {1: "Program approval", 2: "Design freeze", 3: "Process sign-off", 4: "PPAP approved", 5: "Safe-launch exit"}[n]
        print(f"{n} {NAMES[n - 1]:<42}{s!s:<12}{e!s:<12}{gate}")
    start = plan[0][1]
    if start < a.today and not a.status:   # planning a new program: is there still time?
        short = (a.today - start).days / 7
        print(f"\nCOMPRESSED: phase 1 should have started {start}, {short:.0f} weeks ago. Options: run phases in "
              "parallel with extra resources, reuse carry-over designs/processes, negotiate SOP or a staged PPAP.")
        rc = 1
    if a.status:
        try:
            with open(a.status, newline="", encoding="utf-8-sig") as fh:
                rows = list(csv.DictReader(fh))
        except (OSError, csv.Error) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        ends = {n: e for n, _, e in plan}
        late, done, total = [], 0, 0
        listed = set()
        for r in rows:
            ph = int(r.get("phase") or 0)
            st = (r.get("status") or "").strip().lower()
            listed.add((r.get("deliverable") or "").strip().lower())
            total += 1
            done += st == "done"
            if ph in ends and st != "done" and ends[ph] < a.today:
                late.append(f"phase {ph} '{r['deliverable']}' is {st or 'not started'}; phase ended {ends[ph]}")
        print(f"\nDeliverables: {done}/{total} done")
        for msg in late:
            print(f"LATE  {msg}")
        current = [n for n, s, e in plan if s <= a.today <= e]
        for n in current:
            missing = [d for d in DELIVERABLES[n] if d.lower() not in listed]
            if missing:
                print(f"Phase {n} deliverables not tracked: {', '.join(missing)}")
        rc = 1 if late or rc else 0
    else:
        print("\nDeliverables by phase:")
        for n in range(1, 6):
            print(f"  {n}: " + "; ".join(DELIVERABLES[n]))
    return rc


if __name__ == "__main__":
    sys.exit(main())
