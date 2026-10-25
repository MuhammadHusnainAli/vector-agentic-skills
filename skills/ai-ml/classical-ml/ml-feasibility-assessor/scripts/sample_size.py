#!/usr/bin/env python3
"""Back-of-envelope sample sizes for ML feasibility: how many rows and positives you need.

Subcommands:
  metric   rows needed to measure a proportion metric (precision, recall, accuracy, positive rate)
           to +/- margin:            n = z^2 p(1-p) / margin^2
  auc      standard error and 95% CI of an AUC given positives/negatives (Hanley & McNeil 1982),
           or the positives needed for a target CI half-width
  compare  test-set size to tell two classifiers apart by an accuracy difference (McNemar,
           paired, needs the expected disagreement rate)
  epv      events-per-variable check: max candidate features for the minority count
           (10 EPV rule for regression-type models; ~ guidance only for tree models)
  rate     how long data collection takes: positives needed / (rows per period x positive rate)

Usage:
    python sample_size.py metric --p 0.7 --margin 0.03
    python sample_size.py auc --auc 0.80 --pos 82 --neg 318
    python sample_size.py auc --auc 0.80 --half-width 0.03 --neg-per-pos 4
    python sample_size.py compare --p-disagree 0.10 --diff 0.03
    python sample_size.py epv --events 82 --features 25
    python sample_size.py rate --needed 500 --rows-per-period 4000 --positive-rate 0.02 --period week

Exit codes: 0 computed (and requirement met for epv), 1 epv requirement not met, 2 usage error.
"""

import argparse
import math
import sys

Z = {0.80: 1.2816, 0.90: 1.6449, 0.95: 1.9600, 0.99: 2.5758}


def z_of(conf):
    if conf not in Z:
        raise SystemExit(f"error: --confidence must be one of {sorted(Z)}")
    return Z[conf]


def hanley_mcneil_se(a, n_pos, n_neg):
    q1 = a / (2 - a)
    q2 = 2 * a * a / (1 + a)
    var = (a * (1 - a) + (n_pos - 1) * (q1 - a * a) + (n_neg - 1) * (q2 - a * a)) / (n_pos * n_neg)
    return math.sqrt(max(var, 0.0))


def cmd_metric(a):
    z = z_of(a.confidence)
    n = math.ceil(z * z * a.p * (1 - a.p) / (a.margin ** 2))
    print(f"To measure a proportion near {a.p:g} to +/-{a.margin:g} at {a.confidence:.0%} confidence you need "
          f"n = {n} evaluated cases.")
    print("Read n as the denominator of the metric:")
    print(f"  precision -> {n} predicted positives;  recall -> {n} actual positives;  accuracy -> {n} rows")
    if a.base_rate:
        print(f"  for recall at base rate {a.base_rate:g}: about {math.ceil(n / a.base_rate)} rows in the test set")
    return 0


def cmd_auc(a):
    if a.pos and a.neg:
        se = hanley_mcneil_se(a.auc, a.pos, a.neg)
        z = z_of(a.confidence)
        lo, hi = max(0.0, a.auc - z * se), min(1.0, a.auc + z * se)
        print(f"AUC {a.auc:.3f} with {a.pos} positives / {a.neg} negatives: SE {se:.4f}, "
              f"{a.confidence:.0%} CI [{lo:.3f}, {hi:.3f}] (half-width {z * se:.3f})")
        if z * se > 0.05:
            print(f"The interval is wide: AUC differences smaller than about {z * se:.2f} are hard to distinguish on this data.")
        return 0
    if not a.half_width:
        raise SystemExit("error: give --pos and --neg, or --half-width (with --neg-per-pos)")
    z = z_of(a.confidence)

    def wide(n_pos):
        return z * hanley_mcneil_se(a.auc, n_pos, max(1, round(n_pos * a.neg_per_pos))) > a.half_width

    lo, hi = 2, 4
    while wide(hi):                      # half-width shrinks as positives grow: double, then bisect
        lo, hi = hi, hi * 2
        if hi > 100_000_000:
            print("no solution found below 100M positives", file=sys.stderr)
            return 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        lo, hi = (mid, hi) if wide(mid) else (lo, mid)
    n_neg = round(hi * a.neg_per_pos)
    print(f"For AUC ~{a.auc:.2f} +/-{a.half_width:g} at {a.confidence:.0%} with {a.neg_per_pos:g} negatives per "
          f"positive you need about {hi} positives and {n_neg} negatives ({hi + n_neg} rows).")
    return 0


def cmd_compare(a):
    # McNemar: p_disagree = P(models disagree); diff = accuracy difference = p10 - p01.
    # n = (z_a * sqrt(pd) + z_b * sqrt(pd - diff^2))^2 / diff^2   (Connor 1987)
    if a.diff >= a.p_disagree:
        raise SystemExit("error: --diff must be smaller than --p-disagree")
    za, zb = z_of(a.confidence), {0.8: 0.8416, 0.9: 1.2816}.get(a.power)
    if zb is None:
        raise SystemExit("error: --power must be 0.8 or 0.9")
    pd, d = a.p_disagree, a.diff
    n = math.ceil((za * math.sqrt(pd) + zb * math.sqrt(pd - d * d)) ** 2 / (d * d))
    print(f"To detect an accuracy difference of {d:g} when the models disagree on {pd:.0%} of cases "
          f"({a.confidence:.0%} confidence, {a.power:.0%} power) the paired test set needs about {n} rows.")
    print("Measure p-disagree from a pilot: share of rows where the two models predict different labels.")
    return 0


def cmd_epv(a):
    limit = int(a.events // a.epv)
    ok = a.features <= limit
    print(f"{a.events} minority events / {a.features} candidate features = {a.events / max(1, a.features):.1f} EPV "
          f"(rule of thumb >= {a.epv:g}).")
    print(f"Max features at {a.epv:g} EPV: {limit}. " + ("OK." if ok else
          "Too many: use strong regularisation (L1/L2), fewer features, or more data. Counts one-hot levels and "
          "spline terms as separate features."))
    return 0 if ok else 1


def cmd_rate(a):
    per_period = a.rows_per_period * a.positive_rate
    periods = math.ceil(a.needed / per_period) if per_period else float("inf")
    print(f"{a.rows_per_period} rows per {a.period} x {a.positive_rate:g} positive rate = {per_period:.1f} positives "
          f"per {a.period}; {a.needed} positives take about {periods} {a.period}(s), plus the label delay.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Sample-size arithmetic for ML feasibility (usage below).",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    m = sub.add_parser("metric", help="rows to measure a proportion metric")
    m.add_argument("--p", type=float, required=True, help="expected metric value, e.g. 0.7")
    m.add_argument("--margin", type=float, required=True, help="desired +/- margin, e.g. 0.03")
    m.add_argument("--base-rate", type=float, help="positive rate, to convert recall needs into test rows")
    u = sub.add_parser("auc", help="AUC confidence interval or positives needed")
    u.add_argument("--auc", type=float, required=True)
    u.add_argument("--pos", type=int)
    u.add_argument("--neg", type=int)
    u.add_argument("--half-width", type=float)
    u.add_argument("--neg-per-pos", type=float, default=1.0)
    c = sub.add_parser("compare", help="paired test-set size to compare two classifiers")
    c.add_argument("--p-disagree", type=float, required=True)
    c.add_argument("--diff", type=float, required=True)
    c.add_argument("--power", type=float, default=0.8)
    e = sub.add_parser("epv", help="events-per-variable check")
    e.add_argument("--events", type=int, required=True, help="minority-class count")
    e.add_argument("--features", type=int, required=True, help="candidate features (count one-hot levels)")
    e.add_argument("--epv", type=float, default=10.0)
    r = sub.add_parser("rate", help="collection time for a number of positives")
    r.add_argument("--needed", type=int, required=True)
    r.add_argument("--rows-per-period", type=float, required=True)
    r.add_argument("--positive-rate", type=float, required=True)
    r.add_argument("--period", default="week")
    for p in (m, u, c):
        p.add_argument("--confidence", type=float, default=0.95)
    a = ap.parse_args()
    if not a.cmd:
        ap.print_help()
        return 2
    return {"metric": cmd_metric, "auc": cmd_auc, "compare": cmd_compare, "epv": cmd_epv, "rate": cmd_rate}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
