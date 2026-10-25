#!/usr/bin/env python3
"""Report on a CAPA log: open actions by stage, aging, overdue items, stuck stages and cycle times.

CSV columns: capa_id, source, owner, opened, stage (containment/root-cause/action/verification/closed),
stage_since, due, closed

Findings:
  CA001 high    overdue: past its due date and not closed
  CA002 medium  stuck: in the same stage longer than its limit (containment 7, root-cause 30, action 60,
                verification 120 days)
  CA003 low     closed with no time for effectiveness (closed within 14 days of opening)

Usage:
    python capa_aging.py capa_log.csv --today 2026-10-24

Exit codes: 0 nothing overdue, 1 overdue CAPAs, 2 read error.
"""

import argparse
import csv
import datetime as dt
import statistics
import sys
from collections import Counter, defaultdict

STAGES = ["containment", "root-cause", "action", "verification", "closed"]
LIMIT = {"containment": 7, "root-cause": 30, "action": 60, "verification": 120}
BUCKETS = [(30, "0-30"), (60, "31-60"), (90, "61-90"), (10 ** 6, ">90")]


def d(s):
    try:
        return dt.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"capa_id", "opened", "stage"} <= set(rows[0]):
        print("error: log needs capa_id, opened and stage columns", file=sys.stderr)
        return 2
    findings, stage_n, buckets, owners, cycle = [], Counter(), Counter(), defaultdict(int), []
    for r in rows:
        stage = (r["stage"] or "").strip().lower()
        opened = d(r["opened"])
        if stage == "closed":
            closed = d(r.get("closed"))
            if opened and closed:
                cycle.append((closed - opened).days)
                if (closed - opened).days < 14:
                    findings.append(("CA003", "low", f"{r['capa_id']}: closed {(closed - opened).days} days after opening; was effectiveness verified?"))
            continue
        stage_n[stage] += 1
        owners[r.get("owner", "").strip() or "(no owner)"] += 1
        age = (a.today - opened).days if opened else 0
        buckets[next(lbl for lim, lbl in BUCKETS if age <= lim)] += 1
        due = d(r.get("due"))
        if due and due < a.today:
            findings.append(("CA001", "high", f"{r['capa_id']} ({r.get('owner', '')}): {(a.today - due).days} days overdue in {stage}"))
        since = d(r.get("stage_since")) or opened
        if since and stage in LIMIT and (a.today - since).days > LIMIT[stage]:
            findings.append(("CA002", "medium", f"{r['capa_id']}: {(a.today - since).days} days in {stage} (limit {LIMIT[stage]})"))
    open_n = sum(stage_n.values())
    print(f"{len(rows)} CAPAs, {open_n} open\n")
    print("Open by stage:  " + "  ".join(f"{s}:{stage_n[s]}" for s in STAGES[:-1]))
    print("Open by age:    " + "  ".join(f"{lbl}:{buckets[lbl]}" for _, lbl in BUCKETS))
    print("Open by owner:  " + "  ".join(f"{o}:{n}" for o, n in sorted(owners.items(), key=lambda kv: -kv[1])))
    if cycle:
        print(f"Closed cycle time: median {statistics.median(cycle):.0f} days, max {max(cycle)} days ({len(cycle)} closed)")
    overdue = sum(f[0] == "CA001" for f in findings)
    print(f"On-time: {100 * (open_n - overdue) / open_n:.0f}% of open CAPAs within due date\n" if open_n else "")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(findings, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if overdue else 0


if __name__ == "__main__":
    sys.exit(main())
