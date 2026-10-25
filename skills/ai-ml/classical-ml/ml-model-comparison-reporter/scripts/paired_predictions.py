#!/usr/bin/env python3
"""Compare two models on the SAME test rows: paired tests that use the row-level pairing.

Binary targets (y_true 0/1, two score columns):
  DeLong test        difference in ROC-AUC with its standard error (DeLong et al. 1988, fast midrank form)
  McNemar test       on hard predictions at --threshold (or each model's own top-K with --k):
                     exact binomial on the discordant pairs (< 50), chi-square with continuity otherwise
  paired bootstrap   CI of the difference in ROC-AUC, PR-AUC, log loss and Brier (same resampled rows
                     for both models; stratified by class)
Regression (--regression, two prediction columns):
  paired bootstrap   CI of the difference in MAE and RMSE; sign test on |error_a| < |error_b|

Usage:
    python paired_predictions.py preds_ab.csv --a model_a --b model_b
    python paired_predictions.py preds_ab.csv --a lgbm --b logreg --k 50 --n-boot 2000
    python paired_predictions.py reg_ab.csv --regression --a new --b old

Exit codes: 0 report printed, 2 usage or data error.
"""

import argparse
import csv
import json
import math
import random
import sys


def midranks(xs):
    order = sorted(range(len(xs)), key=xs.__getitem__)
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def delong(y, sa, sb):
    """Return (auc_a, auc_b, diff, se, z, p) with the fast DeLong covariance."""
    pos = [i for i, t in enumerate(y) if t]
    neg = [i for i, t in enumerate(y) if not t]
    m, n = len(pos), len(neg)
    res = []
    for s in (sa, sb):
        tx = midranks([s[i] for i in pos])
        ty = midranks([s[i] for i in neg])
        tz = midranks([s[i] for i in pos] + [s[i] for i in neg])
        auc = (sum(tz[:m]) - m * (m + 1) / 2) / (m * n)
        v01 = [(tz[i] - tx[i]) / n for i in range(m)]          # per-positive structural components
        v10 = [1 - (tz[m + j] - ty[j]) / m for j in range(n)]  # per-negative
        res.append((auc, v01, v10))
    (a1, x1, y1), (a2, x2, y2) = res

    def cov(u, v):
        mu, mv = sum(u) / len(u), sum(v) / len(v)
        return sum((p - mu) * (q - mv) for p, q in zip(u, v)) / (len(u) - 1)
    var = (cov(x1, x1) + cov(x2, x2) - 2 * cov(x1, x2)) / m + (cov(y1, y1) + cov(y2, y2) - 2 * cov(y1, y2)) / n
    se = math.sqrt(max(var, 1e-18))
    z = (a1 - a2) / se
    return a1, a2, a1 - a2, se, z, math.erfc(abs(z) / math.sqrt(2))


def mcnemar(y, pa, pb):
    b = sum(1 for t, x, z in zip(y, pa, pb) if x == t and z != t)     # a right, b wrong
    c = sum(1 for t, x, z in zip(y, pa, pb) if x != t and z == t)
    n = b + c
    if n == 0:
        return b, c, 1.0, "no discordant pairs"
    if n < 50:
        k = min(b, c)
        p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)
        return b, c, p, "exact binomial"
    chi = (abs(b - c) - 1) ** 2 / n
    return b, c, math.erfc(math.sqrt(chi / 2)), "chi-square (continuity corrected)"


def auc_fast(y, s):
    pos = sum(y)
    r = midranks(s)
    return (sum(ri for ri, t in zip(r, y) if t) - pos * (pos + 1) / 2) / (pos * (len(y) - pos))


def ap(y, s):
    pairs = sorted(zip(s, y), key=lambda p: -p[0])
    P = sum(y)
    tp = seen = 0
    tot = 0.0
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        hits = sum(t for _, t in pairs[i:j + 1])
        tp += hits
        seen += j - i + 1
        tot += hits / P * tp / seen
        i = j + 1
    return tot


def logloss(y, s):
    e = 1e-15
    return -sum(t * math.log(min(1 - e, max(e, p))) + (1 - t) * math.log(min(1 - e, max(e, 1 - p))) for t, p in zip(y, s)) / len(y)


def brier(y, s):
    return sum((p - t) ** 2 for t, p in zip(y, s)) / len(y)


def boot_ci(diffs):
    d = sorted(diffs)
    return d[int(0.025 * len(d))], d[min(len(d) - 1, int(0.975 * len(d)))]


def main():
    ap_ = argparse.ArgumentParser(description="Paired comparison of two models on one test set.", epilog=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument("csv")
    ap_.add_argument("--true-col", default="y_true")
    ap_.add_argument("--a", required=True, help="column with model A scores/predictions")
    ap_.add_argument("--b", required=True, help="column with model B scores/predictions")
    ap_.add_argument("--regression", action="store_true")
    ap_.add_argument("--threshold", type=float, default=0.5)
    ap_.add_argument("--k", type=int, help="McNemar on each model's top-K instead of a threshold")
    ap_.add_argument("--n-boot", type=int, default=1000)
    ap_.add_argument("--seed", type=int, default=0)
    ap_.add_argument("--json", action="store_true")
    a = ap_.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            for c in (a.true_col, a.a, a.b):
                if c not in (rd.fieldnames or []):
                    raise ValueError(f"column {c!r} not found")
            rows = list(rd)
        y = [float(r[a.true_col]) for r in rows]
        sa = [float(r[a.a]) for r in rows]
        sb = [float(r[a.b]) for r in rows]
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    rng = random.Random(a.seed)
    n = len(y)
    out = {"rows": n, "a": a.a, "b": a.b}
    if a.regression:
        ea = [abs(p - t) for p, t in zip(sa, y)]
        eb = [abs(p - t) for p, t in zip(sb, y)]
        mae = lambda e: sum(e) / len(e)
        rmse = lambda e: math.sqrt(sum(x * x for x in e) / len(e))
        d_mae, d_rmse = [], []
        for _ in range(a.n_boot):
            idx = [rng.randrange(n) for _ in range(n)]
            xa, xb = [ea[i] for i in idx], [eb[i] for i in idx]
            d_mae.append(mae(xa) - mae(xb))
            d_rmse.append(rmse(xa) - rmse(xb))
        wins = sum(1 for x, z in zip(ea, eb) if x < z)
        ties = sum(1 for x, z in zip(ea, eb) if x == z)
        m = n - ties
        k = min(wins, m - wins)
        p_sign = min(1.0, 2 * sum(math.comb(m, i) for i in range(k + 1)) / 2 ** m) if m <= 1000 else \
            math.erfc(abs(wins - m / 2) / math.sqrt(m / 4) / math.sqrt(2))
        out.update(mae_a=mae(ea), mae_b=mae(eb), rmse_a=rmse(ea), rmse_b=rmse(eb), mae_diff_ci=boot_ci(d_mae),
                   rmse_diff_ci=boot_ci(d_rmse), a_closer_share=wins / n, sign_test_p=p_sign)
        if a.json:
            print(json.dumps(out, indent=2))
            return 0
        print(f"{n} rows; A = {a.a}, B = {a.b} (negative differences favour A)")
        print(f"MAE   A {out['mae_a']:.4g}  B {out['mae_b']:.4g}  diff 95% CI [{out['mae_diff_ci'][0]:+.4g}, {out['mae_diff_ci'][1]:+.4g}]")
        print(f"RMSE  A {out['rmse_a']:.4g}  B {out['rmse_b']:.4g}  diff 95% CI [{out['rmse_diff_ci'][0]:+.4g}, {out['rmse_diff_ci'][1]:+.4g}]")
        print(f"A has the smaller error on {wins / n:.1%} of rows; sign test p = {p_sign:.4f}")
        return 0
    yi = [int(t) for t in y]
    if set(yi) - {0, 1} or sum(yi) in (0, n):
        print("error: binary y_true with both classes required (or use --regression)", file=sys.stderr)
        return 2
    a1, a2, d, se, z, p = delong(yi, sa, sb)
    out["delong"] = {"auc_a": a1, "auc_b": a2, "diff": d, "se": se, "ci": (d - 1.96 * se, d + 1.96 * se), "z": z, "p": p}
    if a.k:
        ta = sorted(sa, reverse=True)[a.k - 1]
        tb = sorted(sb, reverse=True)[a.k - 1]
        pa, pb = [int(s >= ta) for s in sa], [int(s >= tb) for s in sb]
        how = f"top-{a.k} of each model"
    else:
        pa, pb = [int(s >= a.threshold) for s in sa], [int(s >= a.threshold) for s in sb]
        how = f"threshold {a.threshold:g}"
    b_, c_, pm, kind = mcnemar(yi, pa, pb)
    out["mcnemar"] = {"rule": how, "a_right_b_wrong": b_, "a_wrong_b_right": c_, "p": pm, "method": kind}
    pos = [i for i in range(n) if yi[i]]
    neg = [i for i in range(n) if not yi[i]]
    diffs = {"roc_auc": [], "pr_auc": [], "log_loss": [], "brier": []}
    probs = all(0 <= s <= 1 for s in sa + sb)
    for _ in range(a.n_boot):
        idx = [rng.choice(pos) for _ in pos] + [rng.choice(neg) for _ in neg]
        yy = [yi[i] for i in idx]
        xa, xb = [sa[i] for i in idx], [sb[i] for i in idx]
        diffs["roc_auc"].append(auc_fast(yy, xa) - auc_fast(yy, xb))
        diffs["pr_auc"].append(ap(yy, xa) - ap(yy, xb))
        if probs:
            diffs["log_loss"].append(logloss(yy, xa) - logloss(yy, xb))
            diffs["brier"].append(brier(yy, xa) - brier(yy, xb))
    out["bootstrap"] = {k: {"point": None, "ci": boot_ci(v)} for k, v in diffs.items() if v}
    out["bootstrap"]["roc_auc"]["point"] = a1 - a2
    out["bootstrap"]["pr_auc"]["point"] = ap(yi, sa) - ap(yi, sb)
    if probs:
        out["bootstrap"]["log_loss"]["point"] = logloss(yi, sa) - logloss(yi, sb)
        out["bootstrap"]["brier"]["point"] = brier(yi, sa) - brier(yi, sb)
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    dl = out["delong"]
    print(f"{n} rows, {sum(yi)} positives; A = {a.a}, B = {a.b}")
    print(f"DeLong: AUC A {dl['auc_a']:.4f}  B {dl['auc_b']:.4f}  diff {dl['diff']:+.4f} "
          f"(95% CI {dl['ci'][0]:+.4f} .. {dl['ci'][1]:+.4f}), z {dl['z']:.2f}, p {dl['p']:.4f}")
    mc = out["mcnemar"]
    print(f"McNemar ({mc['rule']}): A right/B wrong {mc['a_right_b_wrong']}, A wrong/B right {mc['a_wrong_b_right']}, "
          f"p {mc['p']:.4f} ({mc['method']})")
    print(f"Paired stratified bootstrap ({a.n_boot} resamples), A - B:")
    for k, v in out["bootstrap"].items():
        better = "lower" if k in ("log_loss", "brier") else "higher"
        print(f"  {k:<9} {v['point']:+.4f}  95% CI [{v['ci'][0]:+.4f}, {v['ci'][1]:+.4f}]  ({better} is better)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
