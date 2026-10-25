#!/usr/bin/env python3
"""Compare models from per-fold cross-validation scores with tests that respect fold dependence.

Input: long CSV with columns model, fold and one or more metric columns (the format written by
classification-model-selector's bakeoff script). For the chosen --metric it reports:
  summary      mean, standard deviation, mean rank across folds, wins vs the best model
  paired tests every model vs the best, on the per-fold differences:
               - corrected resampled t-test (Nadeau & Bengio 2003): variance inflated by
                 (1/k + n_test/n_train) because CV folds share training data; plain paired t-tests
                 are far too confident
               - Wilcoxon signed-rank test (exact for <= 20 folds)
               - Bayesian correlated t-test (Benavoli et al. 2017) with a region of practical
                 equivalence --rope: P(best better), P(equivalent), P(other better)
  omnibus      Friedman test across all models (needs >= 3 models) with average ranks
Scores where lower is better (log loss, RMSE, MAE...) are detected from the name or set with
--lower-better. Folds must be aligned (same fold ids for every model).

Usage:
    python compare_models.py bakeoff_folds.csv --metric average_precision
    python compare_models.py cv_scores.csv --metric roc_auc --rope 0.005 --test-train-ratio 0.25
    python compare_models.py folds.csv --metric log_loss --markdown

Exit codes: 0 report printed, 2 usage or data error (missing metric, unaligned folds, < 2 models).
"""

import argparse
import csv
import itertools
import json
import math
import re
import sys
from collections import defaultdict

LOWER = re.compile(r"(loss|error|rmse|mse|mae|mape|deviance|brier|seconds|ms_)", re.I)


# ---------------------------------------------------------------- distributions
def betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1) < 1e-12:
            break
    return h


def betainc(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lb = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log(1 - x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lb) * betacf(a, b, x) / a
    return 1 - math.exp(lb) * betacf(b, a, 1 - x) / b


def t_cdf(t, df):
    x = df / (df + t * t)
    p = 0.5 * betainc(df / 2, 0.5, x)
    return 1 - p if t > 0 else p


def chi2_sf(x, k):
    """Survival function of chi-square via the regularised upper incomplete gamma (series / continued fraction)."""
    a, x = k / 2, x / 2
    if x <= 0:
        return 1.0
    if x < a + 1:
        s, term, n = 1 / a, 1 / a, 0
        while abs(term) > 1e-14 and n < 1000:
            n += 1
            term *= x / (a + n)
            s += term
        return 1 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b, c, d = x + 1 - a, 1e300, 1 / (x + 1 - a)
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = b + an / c
        h *= d * c
        if abs(d * c - 1) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def wilcoxon_exact(d):
    """Two-sided exact p-value of the Wilcoxon signed-rank test (zeros dropped)."""
    d = [x for x in d if x != 0]
    n = len(d)
    if n == 0:
        return 1.0, 0.0
    order = sorted(range(n), key=lambda i: abs(d[i]))
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(d[order[j + 1]]) == abs(d[order[i]]):
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    w_plus = sum(r for r, x in zip(ranks, d) if x > 0)
    total = n * (n + 1) / 2
    if n > 20:   # normal approximation
        mu, sd = total / 2, math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
        z = (w_plus - mu) / sd
        return math.erfc(abs(z) / math.sqrt(2)), w_plus
    stat = min(w_plus, total - w_plus)
    count = sum(1 for signs in itertools.product((0, 1), repeat=n)
                if sum(r for r, s in zip(ranks, signs) if s) <= stat + 1e-9)
    return min(1.0, 2 * count / 2 ** n), w_plus


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="Statistical comparison of models from per-fold CV scores.",
                                 epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--metric", required=True)
    ap.add_argument("--model-col", default="model")
    ap.add_argument("--fold-col", default="fold")
    ap.add_argument("--lower-better", action="store_true")
    ap.add_argument("--rope", type=float, default=0.0, help="practical-equivalence half-width (metric units)")
    ap.add_argument("--test-train-ratio", type=float, help="n_test/n_train per fold (default 1/(k-1) for k-fold)")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            cols = rd.fieldnames or []
            for c in (a.model_col, a.fold_col, a.metric):
                if c not in cols:
                    raise ValueError(f"column {c!r} not found; columns: {cols}")
            scores = defaultdict(dict)
            for r in rd:
                scores[r[a.model_col]][r[a.fold_col]] = float(r[a.metric])
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    models = sorted(scores)
    folds = sorted(set.intersection(*(set(v) for v in scores.values())), key=lambda f: (len(f), f))
    if len(models) < 2 or len(folds) < 3:
        print("error: need >= 2 models with >= 3 shared folds", file=sys.stderr)
        return 2
    if any(set(v) != set(folds) for v in scores.values()):
        print(f"warning: using the {len(folds)} folds shared by all models", file=sys.stderr)
    lower = a.lower_better or bool(LOWER.search(a.metric))
    k = len(folds)
    ratio = a.test_train_ratio if a.test_train_ratio else 1 / (k - 1)
    mat = {m: [scores[m][f] for f in folds] for m in models}
    # ranks per fold (1 = best)
    rank_sum = defaultdict(float)
    for i in range(k):
        vals = sorted(((mat[m][i], m) for m in models), reverse=not lower)
        j = 0
        while j < len(vals):
            l = j
            while l + 1 < len(vals) and vals[l + 1][0] == vals[j][0]:
                l += 1
            for t in range(j, l + 1):
                rank_sum[vals[t][1]] += (j + l) / 2 + 1
            j = l + 1
    summary = []
    for m in models:
        v = mat[m]
        mu = sum(v) / k
        sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (k - 1))
        summary.append({"model": m, "mean": mu, "std": sd, "mean_rank": rank_sum[m] / k})
    summary.sort(key=lambda s: (s["mean"] if lower else -s["mean"]))
    best = summary[0]["model"]
    pairs = []
    for s in summary[1:]:
        m = s["model"]
        d = [(mat[best][i] - mat[m][i]) * (-1 if lower else 1) for i in range(k)]   # > 0: best is better
        dm = sum(d) / k
        var = sum((x - dm) ** 2 for x in d) / (k - 1)
        se_naive = math.sqrt(var / k) if var > 0 else 0.0
        se_corr = math.sqrt((1 / k + ratio) * var) if var > 0 else 0.0
        if se_corr > 0:
            t_naive, t_corr = dm / se_naive, dm / se_corr
            p_naive = 2 * (1 - t_cdf(abs(t_naive), k - 1))
            p_corr = 2 * (1 - t_cdf(abs(t_corr), k - 1))
            rope = a.rope
            p_better = 1 - t_cdf((rope - dm) / se_corr, k - 1)
            p_worse = t_cdf((-rope - dm) / se_corr, k - 1)
            p_equiv = max(0.0, 1 - p_better - p_worse)
        else:
            p_naive = p_corr = 0.0 if dm else 1.0
            p_better, p_equiv, p_worse = (1.0, 0.0, 0.0) if dm > a.rope else (0.0, 1.0, 0.0)
        p_w, _ = wilcoxon_exact(d)
        wins = sum(1 for x in d if x > 0)
        pairs.append({"model": m, "vs": best, "mean_diff": dm, "wins_of_best": wins, "folds": k,
                      "p_corrected_t": p_corr, "p_naive_t": p_naive, "p_wilcoxon": p_w,
                      "bayes_p_best_better": p_better, "bayes_p_equivalent": p_equiv, "bayes_p_other_better": p_worse})
    friedman = None
    if len(models) >= 3:
        r_means = [rank_sum[m] / k for m in models]
        K = len(models)
        chi = 12 * k / (K * (K + 1)) * sum((r - (K + 1) / 2) ** 2 for r in r_means)
        friedman = {"chi2": chi, "df": K - 1, "p": chi2_sf(chi, K - 1)}
    out = {"metric": a.metric, "lower_is_better": lower, "folds": k, "test_train_ratio": ratio, "rope": a.rope,
           "summary": summary, "best": best, "pairwise_vs_best": pairs, "friedman": friedman}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    arrow = "lower" if lower else "higher"
    if a.markdown:
        print(f"| model | {a.metric} mean ± sd | mean rank | Δ vs {best} | corrected-t p | Wilcoxon p | "
              f"P(best better) / P(equiv) |\n|---|---|---|---|---|---|---|")
        print(f"| **{best}** | {summary[0]['mean']:.4f} ± {summary[0]['std']:.4f} | {summary[0]['mean_rank']:.2f} | - | - | - | - |")
        for s, p in zip(summary[1:], pairs):
            print(f"| {s['model']} | {s['mean']:.4f} ± {s['std']:.4f} | {s['mean_rank']:.2f} | {-p['mean_diff']:+.4f} | "
                  f"{p['p_corrected_t']:.3f} | {p['p_wilcoxon']:.3f} | {p['bayes_p_best_better']:.2f} / {p['bayes_p_equivalent']:.2f} |")
        return 0
    print(f"{a.metric} ({arrow} is better), {k} aligned folds, test/train ratio {ratio:.3f}, ROPE ±{a.rope:g}")
    print(f"\n{'model':<16} {'mean':>9} {'std':>8} {'rank':>6}")
    for s in summary:
        print(f"{s['model']:<16} {s['mean']:>9.4f} {s['std']:>8.4f} {s['mean_rank']:>6.2f}")
    print(f"\nPaired comparisons vs the best ({best}); diff > 0 means {best} is better:")
    print(f"{'model':<16} {'diff':>8} {'wins':>6} {'p corr-t':>9} {'p naive-t':>10} {'p Wilcoxon':>11} {'P(best>)':>9} {'P(equiv)':>9}")
    for p in pairs:
        print(f"{p['model']:<16} {p['mean_diff']:>+8.4f} {p['wins_of_best']:>3}/{k:<2} {p['p_corrected_t']:>9.3f} "
              f"{p['p_naive_t']:>10.3f} {p['p_wilcoxon']:>11.3f} {p['bayes_p_best_better']:>9.2f} {p['bayes_p_equivalent']:>9.2f}")
    if friedman:
        print(f"\nFriedman test across {len(models)} models: chi2 = {friedman['chi2']:.2f} (df {friedman['df']}), "
              f"p = {friedman['p']:.4f}")
    close = [p["model"] for p in pairs if p["p_corrected_t"] > 0.05]
    if close:
        print(f"\nNot distinguishable from {best} at alpha 0.05 (corrected t): {', '.join(close)} - prefer the simplest / "
              "cheapest among them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
