#!/usr/bin/env python3
"""Prioritise suppliers for development and draft a 90-day development plan for each selected supplier.

CSV columns: supplier, spend (annual), score (scorecard 0-100), ppm, otd (%), risk (high/medium/low),
strategic (yes/no), single_source (yes/no), gaps (';'-separated: process control, msa, capability,
problem solving, delivery, planning, apqp/ppap, quality system, special processes, sub-tier control)

Priority index = spend share x risk factor (high 3, medium 2, low 1) x (100 - score) x 1.5 if single source.
Decision per supplier:
  DEVELOP   gap and (strategic, single source or high spend share): invest in a plan
  REPLACE   gap, not strategic, not single source, small spend: resource instead of developing
  MONITOR   score >= 85: scorecard only

Usage:
    python dev_plan.py suppliers.csv --top 3 --start 2026-11-02
    python dev_plan.py suppliers.csv --ppm-target 500 --otd-target 95

Exit codes: 0 plan printed, 2 usage or data error.
"""

import argparse
import csv
import datetime as dt
import sys

RISK = {"high": 3, "medium": 2, "low": 1}
LEVERS = {
    "process control": "Control plan review on key characteristics; SPC with reaction plans; LPA at the supplier",
    "msa": "Gage R&R on gauges for key characteristics; calibration system review",
    "capability": "Capability studies on key characteristics; DOE or variation reduction project to reach Cpk >= 1.33",
    "problem solving": "8D / 5 Why training with a coached live case; SCAR quality reviewed jointly",
    "delivery": "Capacity and S&OP review; firm forecast window; safety stock; OTD daily tracking",
    "planning": "Production planning and changeover (SMED) review; frozen schedule window",
    "apqp/ppap": "APQP checklist and PPAP coaching for the next launch; joint gate reviews",
    "quality system": "Gap analysis to ISO 9001 / IATF 16949; certification roadmap with milestones",
    "special processes": "Process validation and parameter monitoring; NADCAP / CQI special process assessment",
    "sub-tier control": "Sub-supplier approval, flow-down audit, incoming inspection at the supplier",
}


def yes(v):
    return (v or "").strip().lower() in ("yes", "y", "true")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--top", type=int, default=3, help="number of suppliers to develop")
    ap.add_argument("--start", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--ppm-target", type=float, default=500)
    ap.add_argument("--otd-target", type=float, default=95)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or not {"supplier", "spend", "score"} <= set(rows[0]):
            raise ValueError("CSV needs supplier, spend and score columns (see --help)")
        total = sum(float(r["spend"] or 0) for r in rows) or 1
        items = []
        for r in rows:
            share = float(r["spend"] or 0) / total
            score = float(r["score"])
            idx = share * RISK.get((r.get("risk") or "medium").strip().lower(), 2) * max(0, 100 - score) * (1.5 if yes(r.get("single_source")) else 1)
            if score >= 85:
                decision = "MONITOR"
            elif yes(r.get("strategic")) or yes(r.get("single_source")) or share >= 0.10:
                decision = "DEVELOP"
            else:
                decision = "REPLACE"
            items.append((idx, r, share, score, decision))
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    items.sort(key=lambda x: -x[0])
    print(f"{'Supplier':<18}{'Spend %':>8}{'Score':>7}{'Risk':>8}{'Index':>8}  Decision")
    for idx, r, share, score, dec in items:
        print(f"{r['supplier'][:17]:<18}{100 * share:>7.1f}%{score:>7.0f}{(r.get('risk') or '-'):>8}{idx:>8.2f}  {dec}")
    chosen = [x for x in items if x[4] == "DEVELOP"][:a.top]
    for idx, r, share, score, dec in chosen:
        gaps = [g.strip().lower() for g in (r.get("gaps") or "").split(";") if g.strip()]
        ppm, otd = float(r.get("ppm") or 0), float(r.get("otd") or 100)
        print(f"\n## Development plan: {r['supplier']}  (score {score:.0f}, PPM {ppm:,.0f}, OTD {otd:.0f}%)")
        tq = max(a.ppm_target, ppm / 2) if ppm > a.ppm_target else ppm
        print(f"Targets at day 90: PPM <= {tq:,.0f} (then <= {a.ppm_target:g}), OTD >= {max(a.otd_target, otd):.0f}%, score >= 80")
        steps = [(0, "Kick-off with supplier management: data, targets, team, commitment"),
                 (14, "Joint on-site assessment of the gap areas; agree root causes"),
                 (21, "Action plan signed by both parties: owners, dates, evidence")]
        for i, g in enumerate(gaps or ["process control"]):
            steps.append((30 + 15 * i, f"{g}: {LEVERS.get(g, 'define the lever with the supplier')}"))
        steps += [(75, "Verify actions on site; review scorecard trend"), (90, "Close-out review: targets met -> monitor; not met -> escalate or resource")]
        for day, text in sorted(steps):
            print(f"  {a.start + dt.timedelta(days=day)}  day {day:>2}  {text}")
        unknown = [g for g in gaps if g not in LEVERS]
        if unknown:
            print(f"  note: no standard lever for {', '.join(unknown)}; define it with the supplier")
    replace = [r["supplier"] for _, r, *_x, dec in items if dec == "REPLACE"]
    if replace:
        print(f"\nResource instead of developing: {', '.join(replace)} (small spend, not strategic, not single source)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
