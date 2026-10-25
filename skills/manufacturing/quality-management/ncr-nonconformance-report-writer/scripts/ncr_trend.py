#!/usr/bin/env python3
"""Trend an NCR log: Pareto by defect/part/supplier, repeats, open-NCR aging, escapes and monthly counts.

CSV columns: ncr_id, date, part, defect, supplier (blank for internal), detection_point, qty, cost, status
(open/closed), closed_date

Findings:
  NT001 high    repeat: same part + defect >= --repeat times in the log window -> systemic, needs CAPA
  NT002 medium  NCR open longer than --max-open days
  NT003 medium  escape rate (customer-detected share) above --escape-limit %
  NT004 low     NCRs with no cost recorded (cost of poor quality understated)

Usage:
    python ncr_trend.py ncr_log.csv --today 2026-10-24
    python ncr_trend.py ncr_log.csv --by supplier --weight cost

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import csv
import datetime as dt
import sys
from collections import Counter, defaultdict


def num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--by", choices=["defect", "part", "supplier", "detection_point"], default="defect")
    ap.add_argument("--weight", choices=["count", "qty", "cost"], default="count")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--max-open", type=int, default=30)
    ap.add_argument("--escape-limit", type=float, default=10.0)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"date", "defect", "part"} <= set(rows[0]):
        print("error: log needs date, part and defect columns", file=sys.stderr)
        return 2
    tally = Counter()
    for r in rows:
        key = (r.get(a.by) or "").strip() or ("(internal)" if a.by == "supplier" else "(blank)")
        w = 1 if a.weight == "count" else (num(r.get(a.weight)) or 0)
        tally[key] += w
    total = sum(tally.values()) or 1
    print(f"Pareto by {a.by} ({a.weight}), {len(rows)} NCRs\n")
    print(f"{a.by.title():<28}{a.weight.title():>10}{'%':>7}{'Cum %':>8}")
    cum = 0
    for key, v in tally.most_common():
        cum += v
        mark = "  <- vital few" if cum - v < 0.8 * total else ""
        print(f"{key:<28}{v:>10.0f}{100 * v / total:>6.1f}%{100 * cum / total:>7.1f}%{mark}")
    months = Counter(r["date"][:7] for r in rows if r.get("date"))
    print("\nBy month: " + "  ".join(f"{m}:{n}" for m, n in sorted(months.items())))
    findings = []
    combos = Counter((r["part"].strip(), r["defect"].strip()) for r in rows)
    for (part, defect), n in combos.most_common():
        if n >= a.repeat:
            findings.append(("NT001", "high", f"{part} / {defect}: {n} NCRs - systemic; one CAPA for all, not {n} corrections"))
    for r in rows:
        if (r.get("status") or "").strip().lower() == "open" and r.get("date"):
            age = (a.today - dt.date.fromisoformat(r["date"][:10])).days
            if age > a.max_open:
                findings.append(("NT002", "medium", f"{r.get('ncr_id')}: open {age} days (> {a.max_open})"))
    esc = sum((r.get("detection_point") or "").strip().lower() == "customer" for r in rows)
    rate = 100 * esc / len(rows)
    print(f"Escapes (customer-detected): {esc} of {len(rows)} = {rate:.1f}%")
    if rate > a.escape_limit:
        findings.append(("NT003", "medium", f"escape rate {rate:.1f}% > {a.escape_limit:g}%: review detection controls (PFMEA detection, final inspection)"))
    no_cost = sum(num(r.get("cost")) is None for r in rows)
    if "cost" in rows[0] and no_cost:
        findings.append(("NT004", "low", f"{no_cost} NCR(s) without cost; COPQ is understated"))
    known = [num(r.get("cost")) for r in rows if num(r.get("cost")) is not None]
    if known:
        print(f"Recorded cost of nonconformance: {sum(known):,.0f}")
    print()
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, msg in sorted(findings, key=lambda x: (order[x[1]], x[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(x[1] == "high" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
