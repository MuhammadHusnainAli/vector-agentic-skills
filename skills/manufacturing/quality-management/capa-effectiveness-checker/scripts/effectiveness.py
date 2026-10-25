#!/usr/bin/env python3
"""Decide with statistics whether a corrective action worked.

Subcommands:
  rate    compare the defect rate before and after the action (exact conditional binomial test for
          Poisson counts: given k = k1 + k2 defects, k2 ~ Binomial(k, n2 / (n1 + n2)) when nothing changed)
  zero    units that must run with zero defects to show the rate is below a target at a confidence
          (n = ln(1 - C) / ln(1 - p)), and the upper bound reached so far
  upper   exact (Clopper-Pearson) upper confidence bound on the defect rate after the action

Verdicts:
  EFFECTIVE               rate fell significantly (p < alpha) and by at least --min-reduction
  NOT YET DEMONSTRATED    rate fell but not significantly - collect more data (zero shows how much)
  NOT EFFECTIVE           rate did not fall

Usage:
    python effectiveness.py rate --before 12 --before-units 4000 --after 1 --after-units 3500
    python effectiveness.py zero --target 0.001 --confidence 0.95 --so-far 1200
    python effectiveness.py upper --defects 1 --units 3500 --confidence 0.95

Exit codes: 0 effective / requirement met, 1 not effective or not yet demonstrated, 2 usage error.
"""

import argparse
import math
import sys


def binom_cdf(k, n, p):
    """P(X <= k) for X ~ Binomial(n, p), summed in log space for stability."""
    if p <= 0:
        return 1.0
    if p >= 1:
        return 1.0 if k >= n else 0.0
    total, lp, lq = 0.0, math.log(p), math.log1p(-p)
    for i in range(0, k + 1):
        total += math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
    return min(total, 1.0)


def upper_bound(k, n, conf):
    """Clopper-Pearson one-sided upper bound: smallest p with P(X <= k | p) <= 1 - conf."""
    if k >= n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > 1 - conf:
            lo = mid
        else:
            hi = mid
    return hi


def usage(msg):
    print(f"error: {msg}", file=sys.stderr)
    return 2


def fmt_rate(r):
    return f"{r * 1e6:,.0f} ppm ({r:.4%})"


def cmd_rate(a):
    if a.before_units <= 0 or a.after_units <= 0 or a.before < 0 or a.after < 0:
        return usage("units must be > 0 and defects >= 0")
    r1, r2 = a.before / a.before_units, a.after / a.after_units
    k = a.before + a.after
    share = a.after_units / (a.before_units + a.after_units)
    p = binom_cdf(a.after, k, share) if k else 1.0
    red = 1 - r2 / r1 if r1 else 0.0
    print(f"Before: {a.before} defects in {a.before_units} units = {fmt_rate(r1)}")
    print(f"After:  {a.after} defects in {a.after_units} units = {fmt_rate(r2)}")
    print(f"Reduction: {red:.0%}   one-sided p-value (after < before): {p:.4f}")
    ub = upper_bound(a.after, a.after_units, 1 - a.alpha)
    print(f"After-rate upper {1 - a.alpha:.0%} bound: {fmt_rate(ub)}")
    if r2 >= r1:
        print("Verdict: NOT EFFECTIVE - the defect rate did not fall; re-open the root cause analysis")
        return 1
    if p < a.alpha and red >= a.min_reduction:
        print(f"Verdict: EFFECTIVE - significant at alpha {a.alpha:g} with {red:.0%} reduction (>= {a.min_reduction:.0%})")
        return 0
    if p < a.alpha:
        print(f"Verdict: NOT YET DEMONSTRATED - significant but reduction {red:.0%} < required {a.min_reduction:.0%}")
        return 1
    # units needed after the action, at the current after-rate pattern, to reach significance with 0 further defects
    extra = max(1, a.after_units // 20)
    while extra < 100 * a.after_units:
        s = (a.after_units + extra) / (a.before_units + a.after_units + extra)
        if binom_cdf(a.after, k, s) < a.alpha:
            break
        extra = int(extra * 1.1) + 1
    print(f"Verdict: NOT YET DEMONSTRATED - p {p:.3f} >= {a.alpha:g}; about {extra} more units with no further "
          "defects would show it")
    return 1


def cmd_zero(a):
    if not 0 < a.target < 1 or not 0 < a.confidence < 1:
        return usage("--target and --confidence must be between 0 and 1")
    n = math.ceil(math.log(1 - a.confidence) / math.log(1 - a.target))
    print(f"To show the defect rate is below {fmt_rate(a.target)} with {a.confidence:.0%} confidence: "
          f"{n} consecutive units with zero defects")
    if a.so_far is not None:
        ub = 1 - (1 - a.confidence) ** (1 / a.so_far) if a.so_far else 1.0
        left = max(0, n - a.so_far)
        print(f"So far {a.so_far} defect-free units: rate below {fmt_rate(ub)} at {a.confidence:.0%}; "
              + ("requirement met" if not left else f"{left} more units needed"))
        return 0 if not left else 1
    return 0


def cmd_upper(a):
    if a.units <= 0 or not 0 <= a.defects <= a.units:
        return usage("need 0 <= defects <= units and units > 0")
    ub = upper_bound(a.defects, a.units, a.confidence)
    print(f"{a.defects} defects in {a.units} units: observed {fmt_rate(a.defects / a.units)}; "
          f"{a.confidence:.0%} upper bound {fmt_rate(ub)}")
    if a.target is not None:
        ok = ub <= a.target
        print(f"Target {fmt_rate(a.target)}: " + ("demonstrated" if ok else "not demonstrated yet"))
        return 0 if ok else 1
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("rate", help="before/after defect rate comparison")
    r.add_argument("--before", type=int, required=True)
    r.add_argument("--before-units", type=int, required=True)
    r.add_argument("--after", type=int, required=True)
    r.add_argument("--after-units", type=int, required=True)
    r.add_argument("--alpha", type=float, default=0.05)
    r.add_argument("--min-reduction", type=float, default=0.5, help="required fractional reduction (default 0.5)")
    z = sub.add_parser("zero", help="zero-defect demonstration size")
    z.add_argument("--target", type=float, required=True, help="maximum acceptable defect rate, e.g. 0.001")
    z.add_argument("--confidence", type=float, default=0.95)
    z.add_argument("--so-far", type=int, help="defect-free units already run")
    u = sub.add_parser("upper", help="upper confidence bound on the defect rate")
    u.add_argument("--defects", type=int, required=True)
    u.add_argument("--units", type=int, required=True)
    u.add_argument("--confidence", type=float, default=0.95)
    u.add_argument("--target", type=float)
    a = ap.parse_args()
    return {"rate": cmd_rate, "zero": cmd_zero, "upper": cmd_upper}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
