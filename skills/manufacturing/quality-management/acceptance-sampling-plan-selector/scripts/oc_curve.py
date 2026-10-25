#!/usr/bin/env python3
"""Operating characteristic of a single sampling plan, or design a plan from producer and consumer risk.

Subcommands:
  oc      probability of acceptance Pa(p) for plan (n, c); the p at Pa = 0.95 (producer's quality level),
          at Pa = 0.10 (LTPD / consumer's quality level), and AOQ / AOQL under rectifying inspection.
          Binomial model, or hypergeometric with --lot (small lots, sampling without replacement).
  design  smallest (n, c) with Pa(AQL) >= 1 - alpha and Pa(LTPD) <= beta (binomial).
  c0      zero-acceptance plan: smallest n with Pa(LTPD) <= beta at c = 0 (n = ln(beta) / ln(1 - LTPD)).

Usage:
    python oc_curve.py oc --n 80 --c 2
    python oc_curve.py oc --n 80 --c 2 --lot 1000 --svg > oc.svg
    python oc_curve.py design --aql 0.01 --ltpd 0.05 [--alpha 0.05 --beta 0.10]
    python oc_curve.py c0 --ltpd 0.05 --beta 0.10

Exit codes: 0 computed, 1 no plan found within limits, 2 usage error.
"""

import argparse
import math
import sys


def binom_cdf(c, n, p):
    if p <= 0:
        return 1.0
    if p >= 1:
        return 0.0 if c < n else 1.0
    lp, lq = math.log(p), math.log1p(-p)
    return min(1.0, sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * lp + (n - i) * lq)
                        for i in range(0, min(c, n) + 1)))


def hyper_cdf(c, n, N, p):
    D = round(p * N)
    tot = math.comb(N, n)
    return sum(math.comb(D, i) * math.comb(N - D, n - i) for i in range(0, min(c, D, n) + 1)) / tot


def pa(c, n, p, N=None):
    return hyper_cdf(c, n, N, p) if N else binom_cdf(c, n, p)


def solve(c, n, target, N=None):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = (lo + hi) / 2
        if pa(c, n, mid, N) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def svg(points, n, c):
    W, H, M = 520, 320, 50
    pmax = points[-1][0]
    X = lambda p: M + (W - 2 * M) * p / pmax
    Y = lambda v: H - M - (H - 2 * M) * v
    path = " ".join(f"{X(p):.1f},{Y(v):.1f}" for p, v in points)
    ticks = "".join(f'<text x="{X(pmax * i / 5):.1f}" y="{H - M + 16}" font-size="11" text-anchor="middle">{100 * pmax * i / 5:.1f}%</text>' for i in range(6))
    yt = "".join(f'<text x="{M - 8}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end">{v:.1f}</text>' for v in (0, 0.25, 0.5, 0.75, 1.0))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"><rect width="{W}" height="{H}" fill="#fff"/>'
            f'<text x="{M}" y="22" font-size="13" font-weight="600">OC curve n = {n}, c = {c}</text>'
            f'<rect x="{M}" y="{M}" width="{W - 2 * M}" height="{H - 2 * M}" fill="none" stroke="#ccc"/>'
            f'<polyline points="{path}" fill="none" stroke="#3a6ea5" stroke-width="2"/>{ticks}{yt}'
            f'<text x="{W / 2}" y="{H - 10}" font-size="11" text-anchor="middle">lot fraction nonconforming</text></svg>')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("oc")
    o.add_argument("--n", type=int, required=True)
    o.add_argument("--c", type=int, required=True)
    o.add_argument("--lot", type=int, help="lot size for the hypergeometric model and AOQ")
    o.add_argument("--svg", action="store_true", help="print the OC curve as SVG instead of a table")
    d = sub.add_parser("design")
    d.add_argument("--aql", type=float, required=True, help="producer's quality level as a fraction, e.g. 0.01")
    d.add_argument("--ltpd", type=float, required=True, help="consumer's quality level as a fraction, e.g. 0.05")
    d.add_argument("--alpha", type=float, default=0.05)
    d.add_argument("--beta", type=float, default=0.10)
    z = sub.add_parser("c0")
    z.add_argument("--ltpd", type=float, required=True)
    z.add_argument("--beta", type=float, default=0.10)
    a = ap.parse_args()

    if a.cmd == "oc":
        if a.n < 1 or a.c < 0 or a.c >= a.n or (a.lot and a.lot < a.n):
            print("error: need n >= 1, 0 <= c < n and lot >= n", file=sys.stderr)
            return 2
        p95, p10, p50 = solve(a.c, a.n, 0.95, a.lot), solve(a.c, a.n, 0.10, a.lot), solve(a.c, a.n, 0.50, a.lot)
        grid = [p10 * 1.6 * i / 40 for i in range(41)]
        if a.svg:
            print(svg([(p, pa(a.c, a.n, p, a.lot)) for p in grid], a.n, a.c))
            return 0
        print(f"Plan n = {a.n}, c = {a.c}" + (f", lot {a.lot} (hypergeometric)" if a.lot else " (binomial)"))
        print(f"  Pa = 0.95 at p = {p95:.4%}   (producer's quality level)")
        print(f"  Pa = 0.50 at p = {p50:.4%}   (indifference quality)")
        print(f"  Pa = 0.10 at p = {p10:.4%}   (LTPD / consumer's quality level)\n")
        print(f"{'p':>9}{'Pa':>9}" + (f"{'AOQ':>10}" if a.lot else ""))
        aoqs = []
        for p in grid[::4]:
            v = pa(a.c, a.n, p, a.lot)
            aoq = p * v * (a.lot - a.n) / a.lot if a.lot else None
            aoqs.append(aoq or 0)
            print(f"{p:>9.3%}{v:>9.3f}" + (f"{aoq:>10.3%}" if a.lot else ""))
        if a.lot:
            fine = [p * pa(a.c, a.n, p, a.lot) * (a.lot - a.n) / a.lot for p in grid]
            print(f"\nAOQL (worst average outgoing quality with rejected lots 100% sorted): {max(fine):.3%}")
        return 0

    if a.cmd == "design":
        if not 0 < a.aql < a.ltpd < 1:
            print("error: need 0 < aql < ltpd < 1 (fractions)", file=sys.stderr)
            return 2
        for c in range(0, 60):
            # smallest n that meets the consumer risk at this c
            n = c + 1
            while binom_cdf(c, n, a.ltpd) > a.beta:
                n += 1 if n < 200 else max(1, n // 50)
                if n > 50000:
                    break
            if n > 50000:
                break
            if binom_cdf(c, n, a.aql) >= 1 - a.alpha:
                print(f"Plan: n = {n}, c = {c}")
                print(f"  Pa at AQL {a.aql:.3%} = {binom_cdf(c, n, a.aql):.3f} (needs >= {1 - a.alpha:.2f})")
                print(f"  Pa at LTPD {a.ltpd:.3%} = {binom_cdf(c, n, a.ltpd):.3f} (needs <= {a.beta:.2f})")
                return 0
        print("No plan with n <= 50000 meets both risks; widen the gap between AQL and LTPD.", file=sys.stderr)
        return 1

    if not 0 < a.ltpd < 1 or not 0 < a.beta < 1:
        print("error: --ltpd and --beta must be fractions between 0 and 1", file=sys.stderr)
        return 2
    n = math.ceil(math.log(a.beta) / math.log(1 - a.ltpd))
    print(f"c = 0 plan: n = {n}; accept the lot only if no nonconforming unit is found.")
    print(f"  Lots at {a.ltpd:.2%} nonconforming are accepted with probability {binom_cdf(0, n, a.ltpd):.3f}")
    print(f"  A lot at {a.ltpd / 10:.2%} is still rejected {1 - binom_cdf(0, n, a.ltpd / 10):.1%} of the time: c = 0 plans are strict on producers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
