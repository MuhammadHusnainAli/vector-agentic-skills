#!/usr/bin/env python3
"""Check a control chart series against the Western Electric rules (and optionally the Nelson rules).

Zones are measured in sigma from the centre line. Centre and sigma come from --center/--sigma, from --ucl/--lcl
(sigma = (UCL - LCL) / 6), or are estimated from the data (mean, MR-bar / 1.128) - estimate only from a Phase I
baseline, not from the data being judged.

Western Electric (default):
  WE1  1 point beyond 3 sigma
  WE2  2 of 3 consecutive points beyond 2 sigma on the same side
  WE3  4 of 5 consecutive points beyond 1 sigma on the same side
  WE4  8 consecutive points on the same side of the centre
Nelson additions (--nelson; Nelson uses 9 points for the same-side rule):
  N2   9 consecutive points on the same side
  N3   6 consecutive points steadily increasing or decreasing (trend)
  N4   14 consecutive points alternating up and down (over-adjustment, two streams)
  N7   15 consecutive points within 1 sigma (stratification: limits too wide, mixed subgroups)
  N8   8 consecutive points beyond 1 sigma on both sides, none within (mixture)

Usage:
    python we_rules.py xbar.csv --value xbar --center 12.0092 --sigma 0.00097
    python we_rules.py xbar.csv --value xbar --ucl 12.0121 --lcl 12.0063 --nelson
    python we_rules.py data.csv --value x --baseline 25

Exit codes: 0 no signals, 1 signals found, 2 usage or data error.
"""

import argparse
import csv
import sys
from statistics import mean

CAUSES = {
    "WE1": "a sudden special cause: wrong setting, broken tool, measurement error, material change",
    "WE2": "a shift starting: offset moved, new material lot, new operator",
    "WE3": "a small sustained shift: tool wear, temperature, gradual change",
    "WE4": "a sustained shift in the mean: new setting, new lot, maintenance",
    "N2": "a sustained shift in the mean",
    "N3": "a trend: tool wear, heating, chemical depletion",
    "N4": "over-adjustment (tampering) or two alternating streams (spindles, cavities)",
    "N7": "stratification: subgroups mix streams, or limits were computed from too wide a baseline",
    "N8": "a mixture of two distributions (two machines, two operators)",
}


def runs(z, rule_set):
    hits = []
    n = len(z)
    for i in range(n):
        if abs(z[i]) > 3:
            hits.append(("WE1", i, [i]))
        for k, need, lim, code in ((3, 2, 2, "WE2"), (5, 4, 1, "WE3")):
            if i >= k - 1:
                w = range(i - k + 1, i + 1)
                for side in (1, -1):
                    pts = [j for j in w if side * z[j] > lim]
                    if len(pts) >= need and side * z[i] > lim:
                        hits.append((code, i, pts))
        same = 9 if "nelson" in rule_set else 8
        code = "N2" if "nelson" in rule_set else "WE4"
        if i >= same - 1:
            w = z[i - same + 1:i + 1]
            if all(v > 0 for v in w) or all(v < 0 for v in w):
                hits.append((code, i, list(range(i - same + 1, i + 1))))
        if "nelson" in rule_set:
            if i >= 5:
                d = [z[j + 1] - z[j] for j in range(i - 5, i)]
                if all(x > 0 for x in d) or all(x < 0 for x in d):
                    hits.append(("N3", i, list(range(i - 5, i + 1))))
            if i >= 13:
                d = [z[j + 1] - z[j] for j in range(i - 13, i)]
                if all(d[j] * d[j + 1] < 0 for j in range(len(d) - 1)):
                    hits.append(("N4", i, list(range(i - 13, i + 1))))
            if i >= 14 and all(abs(v) < 1 for v in z[i - 14:i + 1]):
                hits.append(("N7", i, list(range(i - 14, i + 1))))
            if i >= 7 and all(abs(v) > 1 for v in z[i - 7:i + 1]) and \
                    any(v > 0 for v in z[i - 7:i + 1]) and any(v < 0 for v in z[i - 7:i + 1]):
                hits.append(("N8", i, list(range(i - 7, i + 1))))
    return hits


def collapse(hits):
    """Merge overlapping hits of the same rule into one signal spanning all their points."""
    merged = {}
    order = []
    for code, i, pts in sorted(hits, key=lambda h: (h[0], h[2][0])):
        prev = merged.get(code)
        if prev and pts[0] <= prev[-1][2][-1] + 1:
            last = prev[-1]
            prev[-1] = (code, last[1], sorted(set(last[2]) | set(pts)))
        else:
            merged.setdefault(code, []).append((code, i, pts))
    for v in merged.values():
        order.extend(v)
    return sorted(order, key=lambda h: (h[1], h[0]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--value", required=True)
    ap.add_argument("--label", help="column to name points (default: row number)")
    ap.add_argument("--center", type=float)
    ap.add_argument("--sigma", type=float, help="sigma of the plotted statistic")
    ap.add_argument("--ucl", type=float)
    ap.add_argument("--lcl", type=float)
    ap.add_argument("--baseline", type=int, help="estimate centre and sigma from the first N points only")
    ap.add_argument("--nelson", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = [r for r in csv.DictReader(fh) if (r.get(a.value) or "").strip()]
        x = [float(r[a.value]) for r in rows]
    except (OSError, KeyError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(x) < 8:
        print("error: need at least 8 points", file=sys.stderr)
        return 2
    labels = [r[a.label] for r in rows] if a.label else [str(i + 1) for i in range(len(x))]
    if a.ucl is not None and a.lcl is not None:
        center, sigma, src = (a.ucl + a.lcl) / 2 if a.center is None else a.center, (a.ucl - a.lcl) / 6, "control limits"
    elif a.center is not None and a.sigma:
        center, sigma, src = a.center, a.sigma, "given"
    else:
        base = x[:a.baseline] if a.baseline else x
        center = mean(base)
        sigma = mean(abs(b - c) for c, b in zip(base, base[1:])) / 1.128
        src = f"estimated from {'first ' + str(a.baseline) if a.baseline else 'all'} points (MR-bar/1.128)"
    if sigma <= 0:
        print("error: sigma must be positive", file=sys.stderr)
        return 2
    z = [(v - center) / sigma for v in x]
    hits = collapse(runs(z, {"nelson"} if a.nelson else set()))
    print(f"{len(x)} points, centre {center:.6g}, sigma {sigma:.4g} ({src}); rules: {'Nelson' if a.nelson else 'Western Electric'}\n")
    if not hits:
        print("No run-rule signals.")
        return 0
    for code, i, pts in hits:
        span = f"points {labels[pts[0]]}-{labels[pts[-1]]}" if len(pts) > 1 else f"point {labels[i]}"
        print(f"{code} at {labels[i]} ({span}): {CAUSES[code]}")
    print(f"\n{len(hits)} signal(s): investigate in time order; mark the cause and action on the chart.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
