#!/usr/bin/env python3
"""Plan a layered process audit (LPA) calendar with rotation and workload (AIAG CQI-8 style).

Layers (defaults): L1 supervisors audit their own area every shift-day; L2 managers audit weekly and rotate
across areas; L3 plant leadership audits monthly and rotates. People CSV columns: name, layer (1/2/3), area
(home area, required for layer 1). L2/L3 auditors rotate through every area,
with their home area last in the rotation.

Usage:
    python lpa_plan.py --people people.csv --weeks 4
    python lpa_plan.py --people people.csv --weeks 4 --questions 10 --minutes-per-question 1.5 --days 5

Exit codes: 0 plan printed, 1 an area has no layer-1 auditor, 2 read/usage error.
"""

import argparse
import csv
import sys
from collections import defaultdict

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--people", required=True, help="CSV with name, layer, area")
    ap.add_argument("--weeks", type=int, default=4)
    ap.add_argument("--days", type=int, default=5, choices=range(1, 8), help="production days per week")
    ap.add_argument("--questions", type=int, default=10, help="questions per audit (CQI-8: keep it short)")
    ap.add_argument("--minutes-per-question", type=float, default=1.5)
    a = ap.parse_args()
    try:
        with open(a.people, newline="", encoding="utf-8-sig") as fh:
            people = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not people or not {"name", "layer"} <= set(people[0]):
        print("error: people CSV needs name, layer and area columns", file=sys.stderr)
        return 2
    layers = defaultdict(list)
    for p in people:
        layers[p["layer"].strip()].append(p)
    areas = sorted({p["area"].strip() for p in people if p.get("area", "").strip()})
    l1_areas = {p["area"].strip() for p in layers["1"]}
    missing = [x for x in areas if x not in l1_areas]
    audit_min = a.questions * a.minutes_per_question + 5   # 5 min walk and close-out
    load = defaultdict(float)
    print(f"LPA plan: {len(areas)} areas, {a.weeks} weeks, {a.questions} questions/audit (~{audit_min:g} min)\n")
    print("Layer 1 (daily, own area): " + ", ".join(f"{p['name']} -> {p['area']}" for p in layers["1"]))
    for p in layers["1"]:
        load[p["name"]] += audit_min * a.days
    for layer, label, per_week in (("2", "Layer 2 (weekly, rotating)", 1), ("3", "Layer 3 (monthly, rotating)", 0)):
        auditors = layers[layer]
        if not auditors:
            continue
        print(f"\n{label}")
        print(f"{'Week':<6}" + "".join(f"{p['name']:<22}" for p in auditors))
        visits = defaultdict(lambda: defaultdict(int))
        for w in range(a.weeks):
            if layer == "3" and w % 4:
                continue
            cells, used = [], set()
            for i, p in enumerate(auditors):
                home = p.get("area", "").strip()
                # least-visited area first, avoid doubling up this week, home area last
                area = min(areas, key=lambda x: (visits[i][x], x in used, x == home, (areas.index(x) - i) % len(areas)))
                visits[i][area] += 1
                used.add(area)
                day = DAYS[(i + w) % a.days]
                cells.append(f"{day} {area}")
                load[p["name"]] += audit_min / (4 if layer == "3" else 1)
            print(f"W{w + 1:<5}" + "".join(f"{c:<22}" for c in cells))
    print("\nWorkload (minutes per week):")
    for name, m in sorted(load.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<24}{m:>6.0f}")
    total_audits = len(layers["1"]) * a.days * a.weeks + len(layers["2"]) * a.weeks + len(layers["3"]) * -(-a.weeks // 4)
    print(f"\nAudits in plan: {total_audits}")
    for x in missing:
        print(f"LP001 [high] area '{x}' has no layer-1 auditor; assign its supervisor or team leader")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
