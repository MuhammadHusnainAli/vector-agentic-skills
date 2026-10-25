#!/usr/bin/env python3
"""Choose the right control chart and compute its centre line and control limits (Phase I).

Variables data: --value COL with --subgroup COL (rows grouped by that column) or --size N (consecutive
values chunked); subgroup size 1 -> I-MR, 2-9 -> X-bar/R, 10+ -> X-bar/S (override with --chart).
Attribute data: --defectives COL or --defects COL with --n COL (inspected per sample); constant n -> np / c,
varying n -> p / u.

Points beyond the limits are listed; --exclude-ooc recomputes the limits without them (only after the special
causes have been found and removed). The within-subgroup sigma printed is the estimate to use for Cp/Cpk.

Usage:
    python control_limits.py bore.csv --value diameter --size 5
    python control_limits.py bore.csv --value diameter --subgroup hour --chart xbar-s
    python control_limits.py defects.csv --defectives rejects --n inspected
    python control_limits.py data.csv --value x --size 1 --exclude-ooc --json

Exit codes: 0 limits computed and process in control, 1 points beyond limits, 2 usage or data error.
"""

import argparse
import json
import sys

from _spc import attributes, beyond, choose, read_rows, subgroups, to_float, variables


def compute(a, rows):
    if a.defectives or a.defects:
        col = a.defectives or a.defects
        if not a.n:
            raise ValueError("attribute charts need --n (sample size column)")
        counts = [to_float(r[col], col) for r in rows]
        sizes = [to_float(r[a.n], a.n) for r in rows]
        chart = a.chart or choose(None, "defectives" if a.defectives else "defects", len(set(sizes)) > 1)
        return chart, attributes(counts, sizes, chart), [str(i + 1) for i in range(len(rows))]
    groups, labels = subgroups(rows, a.value, a.subgroup, a.size)
    if len(groups) < 2:
        raise ValueError("need at least 2 subgroups (20-25 recommended)")
    chart = a.chart or choose(len(groups[0]))
    return chart, variables(groups, chart), labels


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--value", help="measurement column (variables data)")
    ap.add_argument("--subgroup", help="column identifying subgroups")
    ap.add_argument("--size", type=int, help="subgroup size for consecutive values")
    ap.add_argument("--defectives", help="column of defective units per sample (p / np)")
    ap.add_argument("--defects", help="column of defect counts per sample (c / u)")
    ap.add_argument("--n", help="column with units inspected per sample")
    ap.add_argument("--chart", choices=["imr", "xbar-r", "xbar-s", "p", "np", "c", "u"])
    ap.add_argument("--exclude-ooc", action="store_true", help="recompute limits without out-of-control points")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if not (a.value or a.defectives or a.defects):
        print("error: give --value (variables) or --defectives/--defects with --n (attributes)", file=sys.stderr)
        return 2
    try:
        rows = read_rows(a.csv)
        chart, res, labels = compute(a, rows)
        excluded = []
        if a.exclude_ooc and not (a.defectives or a.defects):
            ooc = sorted(set(beyond(res["main"])) | set(beyond(res["second"])))
            if ooc:
                groups, labels = subgroups(rows, a.value, a.subgroup, a.size)
                excluded = [labels[i] for i in ooc]
                keep = [g for i, g in enumerate(groups) if i not in ooc]
                labels = [l for i, l in enumerate(labels) if i not in ooc]
                res = variables(keep, chart)
    except (OSError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    series = [res["main"]] + ([res["second"]] if "second" in res else [])
    out = {"chart": chart, "points": len(labels), "excluded": excluded, "series": []}
    for s in series:
        name, pts, cl, ucl, lcl = s
        ooc = [labels[i] for i in beyond(s)]
        lim = lambda v: v if not isinstance(v, list) else (v[0] if len(set(round(x, 9) for x in v)) == 1 else "varies")
        out["series"].append({"name": name, "cl": cl, "ucl": lim(ucl), "lcl": lim(lcl), "beyond_limits": ooc})
    if "sigma" in res:
        out["sigma_within"] = res["sigma"]
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Chart: {chart.upper()}  ({len(labels)} {'subgroups' if res.get('n', 1) > 1 else 'points'}"
              + (f", n = {res['n']}" if res.get("n", 1) > 1 else "") + ")")
        if excluded:
            print(f"Recomputed without out-of-control subgroups: {', '.join(excluded)}")
        for s in out["series"]:
            fmt = lambda v: v if isinstance(v, str) else f"{v:.7g}"
            print(f"  {s['name']:<24} CL {fmt(s['cl']):<10} UCL {fmt(s['ucl']):<10} LCL {fmt(s['lcl'])}")
            if s["beyond_limits"]:
                print(f"    beyond limits at: {', '.join(s['beyond_limits'])}")
        if "sigma_within" in out:
            print(f"  Within-subgroup sigma estimate: {out["sigma_within"]:.5g}")
        bad = any(s["beyond_limits"] for s in out["series"])
        print("\nProcess shows special-cause signals: find and remove the causes before using these limits."
              if bad else "\nNo points beyond limits; check run rules (western-electric-rules-checker) before declaring control.")
    return 1 if any(s["beyond_limits"] for s in out["series"]) else 0


if __name__ == "__main__":
    sys.exit(main())
