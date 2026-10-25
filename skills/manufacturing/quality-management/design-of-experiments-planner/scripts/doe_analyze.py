#!/usr/bin/env python3
"""Analyse a two-level factorial experiment: effects, significance, curvature and the coded model.

Input: the CSV from doe_design.py with the response column filled (or any CSV with *_coded columns of -1/+1,
0 for centre points). Effects = mean(+1) - mean(-1) for main effects and two-factor interactions; columns that
are identical (aliased in a fraction) are reported together.

Significance:
  replicated factorial runs -> t-test of each effect against pure error from replicates
  unreplicated              -> Lenth's pseudo standard error (PSE) and margin of error (ME) at 95%
Centre points             -> curvature test: factorial mean vs centre mean

Usage:
    python doe_analyze.py runs.csv --response yield
    python doe_analyze.py runs.csv --response ra --goal min

Exit codes: 0 analysed, 2 usage or data error.
"""

import argparse
import csv
import itertools
import math
import statistics
import sys


def betacf(a, b, x):
    c, d = 1.0, 1 - (a + b) * x / (a + 1)
    d = 1 / (d or 1e-300)
    h = d
    for m in range(1, 300):
        for aa in (m * (b - m) * x / ((a - 1 + 2 * m) * (a + 2 * m)), -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 1 + 2 * m))):
            d = 1 / ((1 + aa * d) or 1e-300)
            c = (1 + aa / c) or 1e-300
            h *= d * c
        if abs(d * c - 1) < 1e-12:
            break
    return h


def betainc(a, b, x):
    if x <= 0 or x >= 1:
        return 0.0 if x <= 0 else 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    return math.exp(lbt) * betacf(a, b, x) / a if x < (a + 1) / (a + b + 2) else 1 - math.exp(lbt) * betacf(b, a, 1 - x) / b


def t_two_sided_p(t, df):
    return betainc(df / 2, 0.5, df / (df + t * t))


def t_quantile(q, df):
    lo, hi = 0.0, 100.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if 1 - t_two_sided_p(mid, df) / 2 < q:
            lo = mid
        else:
            hi = mid
    return mid


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--response", default="response")
    ap.add_argument("--goal", choices=["max", "min"], default="max", help="direction for the recommended settings")
    ap.add_argument("--alpha", type=float, default=0.05)
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = [r for r in csv.DictReader(fh) if (r.get(a.response) or "").strip()]
        coded = [c for c in (rows[0].keys() if rows else []) if c.endswith("_coded")]
        if not coded:
            raise ValueError("no *_coded factor columns (use the CSV from doe_design.py)")
        X = [[float(r[c]) for c in coded] for r in rows]
        y = [float(r[a.response]) for r in rows]
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    names = [c[:-6] for c in coded]
    fact = [i for i, x in enumerate(X) if all(v != 0 for v in x)]
    centre = [i for i, x in enumerate(X) if all(v == 0 for v in x)]
    if len(fact) < 4:
        print("error: need at least 4 factorial runs with responses", file=sys.stderr)
        return 2
    terms = [((j,), names[j]) for j in range(len(names))] + \
            [((i, j), f"{names[i]}*{names[j]}") for i, j in itertools.combinations(range(len(names)), 2)]
    cols, effects = {}, []
    for idx, label in terms:
        col = tuple(math.prod(X[r][j] for j in idx) for r in fact)
        if col in cols:
            cols[col].append(label)
            continue
        cols[col] = [label]
        plus = [y[r] for r, s in zip(fact, col) if s > 0]
        minus = [y[r] for r, s in zip(fact, col) if s < 0]
        if plus and minus:
            effects.append((col, statistics.mean(plus) - statistics.mean(minus)))
    # pure error from replicated factorial points
    groups = {}
    for r in fact:
        groups.setdefault(tuple(X[r]), []).append(y[r])
    dfe = sum(len(g) - 1 for g in groups.values())
    ss = sum(sum((v - statistics.mean(g)) ** 2 for v in g) for g in groups.values())
    n = len(fact)
    print(f"{n} factorial runs, {len(centre)} centre points, response '{a.response}' (goal: {a.goal})\n")
    rows_out = []
    if dfe >= 2:
        s = math.sqrt(ss / dfe)
        se = 2 * s / math.sqrt(n)
        method = f"pure error from replicates (s = {s:.4g}, df = {dfe})"
        for col, e in effects:
            p = t_two_sided_p(abs(e) / se, dfe)
            rows_out.append((col, e, p, p < a.alpha))
    else:
        abs_e = [abs(e) for _, e in effects]
        s0 = 1.5 * statistics.median(abs_e)
        pse = 1.5 * statistics.median([v for v in abs_e if v < 2.5 * s0] or abs_e)
        me = t_quantile(0.975, max(1, len(effects) / 3)) * pse
        method = f"Lenth: PSE {pse:.4g}, margin of error {me:.4g} (unreplicated)"
        for col, e in effects:
            rows_out.append((col, e, None, abs(e) > me))
    print(f"Significance: {method}\n")
    print(f"{'Term':<34}{'Effect':>10}{'p':>9}  Sig")
    for col, e, p, sig in sorted(rows_out, key=lambda r: -abs(r[1])):
        print(f"{' = '.join(cols[col])[:33]:<34}{e:>10.4g}{('-' if p is None else f'{p:.3f}'):>9}  {'*' if sig else ''}")
    ybar = statistics.mean(y[r] for r in fact)
    model = " ".join(f"{'+' if e >= 0 else '-'} {abs(e) / 2:.4g}*{cols[col][0]}" for col, e, _, sig in rows_out if sig)
    print(f"\nCoded model (significant terms): y = {ybar:.4g} {model}" if model else f"\nNo significant effects at alpha {a.alpha}.")
    if centre:
        yc = statistics.mean(y[i] for i in centre)
        msg = f"Curvature: factorial mean {ybar:.4g} vs centre mean {yc:.4g} (difference {yc - ybar:+.4g})"
        if len(centre) >= 2:
            sc = statistics.stdev(y[i] for i in centre)
            se_c = sc * math.sqrt(1 / n + 1 / len(centre)) if sc else 0
            if se_c:
                pc = t_two_sided_p(abs(yc - ybar) / se_c, len(centre) - 1)
                msg += f", p = {pc:.3f}" + ("  -> curvature: add axial points (response surface)" if pc < a.alpha else "")
        print(msg)
    best = []
    for j, nm in enumerate(names):
        col = next((c for c in cols if cols[c][0] == nm), None)
        e = next((e for c, e, _, s in rows_out if c == col and s), None)
        if e is not None:
            best.append(f"{nm} {'high' if (e > 0) == (a.goal == 'max') else 'low'}")
    if best:
        print("Recommended settings (main effects only; check interactions): " + ", ".join(best))
    print("Confirm with verification runs at the recommended settings before changing the process.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
