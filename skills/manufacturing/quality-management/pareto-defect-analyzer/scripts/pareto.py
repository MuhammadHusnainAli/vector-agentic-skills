#!/usr/bin/env python3
"""Pareto analysis of defects: counts or cost/severity-weighted, vital few, 'Other' grouping, stratification,
before/after comparison and an optional SVG chart.

Input: a defect log CSV with a category column (--category, default 'defect'), and optionally a quantity
column (--count) and a cost column (--cost). Each row is one record; without --count each row counts as 1.

Usage:
    python pareto.py defects.csv
    python pareto.py defects.csv --count qty --cost unit_cost --weight cost
    python pareto.py defects.csv --by line                       # one Pareto per line (stratified)
    python pareto.py defects.csv --period month --compare 2026-08 2026-10
    python pareto.py defects.csv --other 0.03 --svg > pareto.svg

Warnings:
  PA001  'Other' is bigger than the top category: categories are too fine or too vague
  PA002  flat Pareto (top 20% of categories < 50% of the total): stratify by another factor
  PA003  count and cost Paretos disagree on the top category: decide which matters to the business

Exit codes: 0 printed, 2 usage or data error.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from html import escape


def tally(rows, cat, count, cost, weight):
    t = Counter()
    for r in rows:
        k = (r.get(cat) or "").strip() or "(blank)"
        q = float(r[count]) if count and (r.get(count) or "").strip() else 1.0
        if weight == "cost":
            q *= float(r[cost]) if (r.get(cost) or "").strip() else 0.0
        t[k] += q
    return t


def group_other(t, frac):
    total = sum(t.values()) or 1
    keep = Counter({k: v for k, v in t.items() if v / total >= frac})
    rest = sum(v for k, v in t.items() if k not in keep)
    return keep, rest


def show(t, frac, cut, unit):
    keep, other = group_other(t, frac)
    total = sum(t.values()) or 1
    items = keep.most_common() + ([("Other", other)] if other else [])
    print(f"{'Category':<30}{unit:>12}{'%':>7}{'Cum %':>8}")
    cum, vital = 0.0, []
    for k, v in items:
        prev = cum
        cum += v
        if k != "Other" and prev < cut * total:
            vital.append(k)
        print(f"{k[:29]:<30}{v:>12,.0f}{100 * v / total:>6.1f}%{100 * cum / total:>7.1f}%" + ("  *" if k in vital else ""))
    print(f"\nVital few (* up to {cut:.0%}): {', '.join(vital)} = {len(vital)} of {len(t)} categories")
    warn = []
    if other and keep and other > keep.most_common(1)[0][1]:
        warn.append("PA001 'Other' is bigger than the top category: split vague categories or lower --other")
    n20 = max(1, round(0.2 * len(t)))
    if len(t) >= 5 and sum(v for _, v in t.most_common(n20)) < 0.5 * total:
        warn.append("PA002 flat Pareto: no vital few by this category - stratify by line, shift, supplier or part")
    return items, warn


def svg(items, title, unit):
    W, H, M = 760, 380, 60
    total = sum(v for _, v in items) or 1
    bw = (W - 2 * M) / max(1, len(items))
    top = max(v for _, v in items) or 1
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>',
           f'<text x="{M}" y="24" font-size="14" font-weight="600">{escape(title)}</text>']
    cum, pts = 0, []
    for i, (k, v) in enumerate(items):
        h = (H - 2 * M - 30) * v / top
        x = M + i * bw
        out.append(f'<rect x="{x + 4:.1f}" y="{H - M - h:.1f}" width="{bw - 8:.1f}" height="{h:.1f}" fill="#3a6ea5"><title>{escape(k)}: {v:,.0f}</title></rect>')
        out.append(f'<text x="{x + bw / 2:.1f}" y="{H - M + 14}" font-size="10" text-anchor="middle">{escape(k[:12])}</text>')
        cum += v
        pts.append(f"{x + bw / 2:.1f},{H - M - (H - 2 * M - 30) * cum / total:.1f}")
    y80 = H - M - (H - 2 * M - 30) * 0.8
    out.append(f'<line x1="{M}" x2="{W - M}" y1="{y80:.1f}" y2="{y80:.1f}" stroke="#c0392b" stroke-dasharray="5 4"/>')
    out.append(f'<text x="{W - M + 4}" y="{y80 + 4:.1f}" font-size="10">80%</text>')
    out.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="#e67e22" stroke-width="2"/>')
    out.append(f'<text x="{M}" y="{H - 12}" font-size="11">{escape(unit)}; line = cumulative %</text></svg>')
    return "".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--category", default="defect")
    ap.add_argument("--count", help="quantity column (default: each row = 1)")
    ap.add_argument("--cost", help="cost per unit column (for --weight cost)")
    ap.add_argument("--weight", choices=["count", "cost"], default="count")
    ap.add_argument("--by", help="stratify: one Pareto per value of this column")
    ap.add_argument("--period", help="period column for --compare")
    ap.add_argument("--compare", nargs=2, metavar=("BEFORE", "AFTER"))
    ap.add_argument("--other", type=float, default=0.0, help="group categories below this share into Other, e.g. 0.03")
    ap.add_argument("--cut", type=float, default=0.8)
    ap.add_argument("--svg", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or a.category not in rows[0]:
            raise ValueError(f"no '{a.category}' column (use --category)")
        if a.weight == "cost" and not a.cost:
            raise ValueError("--weight cost needs --cost")
        t = tally(rows, a.category, a.count, a.cost, a.weight)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    unit = "Cost" if a.weight == "cost" else "Count"
    if a.svg:
        keep, other = group_other(t, a.other)
        print(svg(keep.most_common() + ([("Other", other)] if other else []), f"Pareto of {a.category}", unit))
        return 0
    if a.compare:
        if not a.period:
            print("error: --compare needs --period", file=sys.stderr)
            return 2
        b = tally([r for r in rows if r.get(a.period) == a.compare[0]], a.category, a.count, a.cost, a.weight)
        f = tally([r for r in rows if r.get(a.period) == a.compare[1]], a.category, a.count, a.cost, a.weight)
        tb, tf = sum(b.values()) or 1, sum(f.values()) or 1
        print(f"{'Category':<30}{a.compare[0]:>12}{a.compare[1]:>12}{'Change':>9}")
        for k in sorted(set(b) | set(f), key=lambda k: -(b[k] + f[k])):
            ch = (f[k] - b[k]) / b[k] if b[k] else float("inf")
            print(f"{k[:29]:<30}{b[k]:>12,.0f}{f[k]:>12,.0f}{('new' if b[k] == 0 else f'{ch:+.0%}'):>9}")
        print(f"{'Total':<30}{tb:>12,.0f}{tf:>12,.0f}{(tf - tb) / tb:>+9.0%}")
        return 0
    print(f"Pareto of {a.category} by {unit.lower()} ({len(rows)} records)\n")
    items, warn = show(t, a.other, a.cut, unit)
    if a.cost and a.weight == "count":
        tc = tally(rows, a.category, a.count, a.cost, "cost")
        if tc and tc.most_common(1)[0][0] != t.most_common(1)[0][0]:
            warn.append(f"PA003 top by count is '{t.most_common(1)[0][0]}' but top by cost is '{tc.most_common(1)[0][0]}'")
    if a.by:
        strata = defaultdict(list)
        for r in rows:
            strata[(r.get(a.by) or "(blank)").strip()].append(r)
        for s, rs in sorted(strata.items()):
            ts = tally(rs, a.category, a.count, a.cost, a.weight)
            top = ts.most_common(3)
            tot = sum(ts.values()) or 1
            print(f"  {a.by} {s}: total {tot:,.0f}; top " + ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in top))
    for w in warn:
        print(w)
    return 0


if __name__ == "__main__":
    sys.exit(main())
