#!/usr/bin/env python3
"""Run common hypothesis tests on CSV data and state the conclusion in plain words.

Subcommands (CSV input with --col VALUE and --group GROUP, or two columns --a/--b):
  t1           1-sample t-test vs --mu
  t2           2-sample Welch t-test (two groups)
  paired       paired t-test (--a before --b after)
  var2         F-test for two variances (normal data) plus Levene (Brown-Forsythe) test
  anova        one-way ANOVA (k groups)
  mannwhitney  Mann-Whitney U (normal approximation with tie correction)
  prop2        2-proportion z-test from counts: --x1 --n1 --x2 --n2 (no CSV)
  chi2         chi-square test of association on a contingency CSV (first column = row label)

Usage:
    python run_test.py t2 data.csv --col diameter --group machine
    python run_test.py paired data.csv --a before --b after
    python run_test.py anova data.csv --col strength --group supplier
    python run_test.py prop2 --x1 12 --n1 400 --x2 4 --n2 380
    python run_test.py chi2 table.csv

Exit codes: 0 not significant, 1 significant at --alpha, 2 usage or data error.
"""

import argparse
import csv
import math
import statistics as st
import sys
from collections import OrderedDict

from _stats import NORMAL, chi2_sf, f_sf, t_ppf, t_sf2


def load(a):
    with open(a.csv, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def groups(rows, col, group):
    g = OrderedDict()
    for r in rows:
        if (r.get(col) or "").strip():
            g.setdefault(r[group].strip(), []).append(float(r[col]))
    return g


def two(a, rows):
    if a.a and a.b:
        x = [float(r[a.a]) for r in rows if (r.get(a.a) or "").strip()]
        y = [float(r[a.b]) for r in rows if (r.get(a.b) or "").strip()]
        return a.a, x, a.b, y
    g = groups(rows, a.col, a.group)
    if len(g) != 2:
        raise ValueError(f"need exactly 2 groups in '{a.group}', found {len(g)}")
    (n1, x), (n2, y) = g.items()
    return n1, x, n2, y


def verdict(p, alpha, h1):
    sig = p < alpha
    print(f"\np = {p:.4g} {'<' if sig else '>='} alpha {alpha:g}: " +
          (f"significant - {h1}." if sig else "not significant - the data do not show a difference (this is not proof of no difference)."))
    return 1 if sig else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("test", choices=["t1", "t2", "paired", "var2", "anova", "mannwhitney", "prop2", "chi2"])
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--col")
    ap.add_argument("--group")
    ap.add_argument("--a")
    ap.add_argument("--b")
    ap.add_argument("--mu", type=float)
    ap.add_argument("--x1", type=int)
    ap.add_argument("--n1", type=int)
    ap.add_argument("--x2", type=int)
    ap.add_argument("--n2", type=int)
    ap.add_argument("--alpha", type=float, default=0.05)
    a = ap.parse_args()
    try:
        if a.test == "prop2":
            if None in (a.x1, a.n1, a.x2, a.n2) or not (0 <= a.x1 <= a.n1 and 0 <= a.x2 <= a.n2 and a.n1 and a.n2):
                raise ValueError("prop2 needs 0 <= x <= n for --x1 --n1 --x2 --n2")
            p1, p2 = a.x1 / a.n1, a.x2 / a.n2
            pp = (a.x1 + a.x2) / (a.n1 + a.n2)
            se = math.sqrt(pp * (1 - pp) * (1 / a.n1 + 1 / a.n2))
            z = (p1 - p2) / se if se else 0.0
            p = 2 * (1 - NORMAL.cdf(abs(z)))
            print(f"2-proportion test: p1 = {p1:.4f} ({a.x1}/{a.n1}), p2 = {p2:.4f} ({a.x2}/{a.n2}), z = {z:.3f}")
            if min(a.x1, a.x2, a.n1 - a.x1, a.n2 - a.x2) < 5:
                print("  small counts: confirm with Fisher's exact test")
            return verdict(p, a.alpha, "the proportions differ")
        if not a.csv:
            raise ValueError("this test needs a CSV file")
        rows = load(a)
        if a.test == "chi2":
            labels = list(rows[0].keys())
            table = [[float(r[c]) for c in labels[1:]] for r in rows]
            R, C = len(table), len(table[0])
            tot = sum(map(sum, table))
            rs, cs = [sum(r) for r in table], [sum(table[i][j] for i in range(R)) for j in range(C)]
            exp = [[rs[i] * cs[j] / tot for j in range(C)] for i in range(R)]
            chi = sum((table[i][j] - exp[i][j]) ** 2 / exp[i][j] for i in range(R) for j in range(C))
            df = (R - 1) * (C - 1)
            low = sum(e < 5 for row in exp for e in row)
            print(f"Chi-square test of association: {R}x{C} table, chi2 = {chi:.3f}, df = {df}")
            if low > 0.2 * R * C:
                print(f"  {low} cells have expected count < 5: combine categories or use an exact test")
            return verdict(chi2_sf(chi, df), a.alpha, f"'{labels[0]}' and the column categories are associated")
        if a.test == "t1":
            if a.mu is None:
                raise ValueError("t1 needs --mu")
            x = [float(r[a.col]) for r in rows if (r.get(a.col) or "").strip()]
            n, m, s = len(x), st.mean(x), st.stdev(x)
            t = (m - a.mu) / (s / math.sqrt(n))
            h = t_ppf(1 - a.alpha / 2, n - 1) * s / math.sqrt(n)
            print(f"1-sample t: n = {n}, mean = {m:.7g}, s = {s:.4g}, t = {t:.3f}, df = {n - 1}")
            print(f"  {100 * (1 - a.alpha):.0f}% CI for the mean: {m - h:.7g} to {m + h:.7g}")
            return verdict(t_sf2(t, n - 1), a.alpha, f"the mean differs from {a.mu:g}")
        if a.test == "anova":
            g = groups(rows, a.col, a.group)
            k, allv = len(g), [v for vs in g.values() for v in vs]
            gm = st.mean(allv)
            ssb = sum(len(v) * (st.mean(v) - gm) ** 2 for v in g.values())
            ssw = sum((x - st.mean(v)) ** 2 for v in g.values() for x in v)
            dfb, dfw = k - 1, len(allv) - k
            f = (ssb / dfb) / (ssw / dfw)
            print(f"One-way ANOVA: {k} groups, F = {f:.3f}, df = {dfb}, {dfw}; R-sq = {ssb / (ssb + ssw):.1%}")
            for name, v in g.items():
                print(f"  {name:<14} n = {len(v):<4} mean = {st.mean(v):.7g}  s = {st.stdev(v):.4g}")
            return verdict(f_sf(f, dfb, dfw), a.alpha, "at least one group mean differs (follow up with Tukey comparisons)")
        n1, x, n2, y = two(a, rows)
        if a.test == "paired":
            if len(x) != len(y):
                raise ValueError("paired test needs the same number of values in --a and --b")
            d = [b - c for b, c in zip(y, x)]
            n, m, s = len(d), st.mean(d), st.stdev(d)
            t = m / (s / math.sqrt(n))
            h = t_ppf(1 - a.alpha / 2, n - 1) * s / math.sqrt(n)
            print(f"Paired t ({n2} - {n1}): n = {n}, mean difference = {m:.7g}, s = {s:.4g}, t = {t:.3f}")
            print(f"  {100 * (1 - a.alpha):.0f}% CI for the difference: {m - h:.7g} to {m + h:.7g}")
            return verdict(t_sf2(t, n - 1), a.alpha, "the mean difference is not zero")
        if a.test == "t2":
            m1, m2, v1, v2 = st.mean(x), st.mean(y), st.variance(x), st.variance(y)
            se = math.sqrt(v1 / len(x) + v2 / len(y))
            t = (m1 - m2) / se
            df = se ** 4 / ((v1 / len(x)) ** 2 / (len(x) - 1) + (v2 / len(y)) ** 2 / (len(y) - 1))
            h = t_ppf(1 - a.alpha / 2, df) * se
            print(f"2-sample Welch t: {n1} mean {m1:.7g} (n {len(x)}), {n2} mean {m2:.7g} (n {len(y)}); t = {t:.3f}, df = {df:.1f}")
            print(f"  {100 * (1 - a.alpha):.0f}% CI for {n1} - {n2}: {m1 - m2 - h:.7g} to {m1 - m2 + h:.7g}")
            return verdict(t_sf2(t, df), a.alpha, "the means differ")
        if a.test == "var2":
            v1, v2 = st.variance(x), st.variance(y)
            f = v1 / v2
            p = 2 * min(f_sf(f, len(x) - 1, len(y) - 1), 1 - f_sf(f, len(x) - 1, len(y) - 1))
            zx = [abs(v - st.median(x)) for v in x]
            zy = [abs(v - st.median(y)) for v in y]
            mz, n = st.mean(zx + zy), len(x) + len(y)
            fl = ((len(zx) * (st.mean(zx) - mz) ** 2 + len(zy) * (st.mean(zy) - mz) ** 2) /
                  ((sum((v - st.mean(zx)) ** 2 for v in zx) + sum((v - st.mean(zy)) ** 2 for v in zy)) / (n - 2)))
            pl = f_sf(fl, 1, n - 2)
            print(f"Two variances: s({n1}) = {math.sqrt(v1):.4g}, s({n2}) = {math.sqrt(v2):.4g}, ratio = {f:.3f}")
            print(f"  F-test p = {p:.4g} (normal data)   Levene/Brown-Forsythe p = {pl:.4g} (robust)")
            return verdict(pl, a.alpha, "the variances differ")
        allv = sorted((v, i) for i, v in enumerate(x + y))
        ranks, i = [0.0] * len(allv), 0
        ties = 0.0
        while i < len(allv):
            j = i
            while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
                j += 1
            for k in range(i, j + 1):
                ranks[allv[k][1]] = (i + j) / 2 + 1
            t_ = j - i + 1
            ties += t_ ** 3 - t_
            i = j + 1
        n1_, n2_ = len(x), len(y)
        u = sum(ranks[:n1_]) - n1_ * (n1_ + 1) / 2
        nn = n1_ + n2_
        sd = math.sqrt(n1_ * n2_ / 12 * ((nn + 1) - ties / (nn * (nn - 1))))
        z = (u - n1_ * n2_ / 2) / sd
        print(f"Mann-Whitney: median {n1} = {st.median(x):.7g}, median {n2} = {st.median(y):.7g}, U = {u:.1f}, z = {z:.3f}")
        return verdict(2 * (1 - NORMAL.cdf(abs(z))), a.alpha, "the distributions (medians) differ")
    except (OSError, KeyError, ValueError, ZeroDivisionError, st.StatisticsError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
