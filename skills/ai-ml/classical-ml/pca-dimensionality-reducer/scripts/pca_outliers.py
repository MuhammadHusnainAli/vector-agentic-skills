#!/usr/bin/env python3
"""Flag unusual rows with a PCA model: Hotelling's T^2 (extreme inside the model) and Q / SPE residuals
(breaks the correlation structure), the standard multivariate process-monitoring pair.

Fits PCA on --train (standardised, k components from --k or --var), then scores --score rows
(default: the training rows):
  T^2 = sum_i t_i^2 / lambda_i      distance within the PCA subspace (unusually large but "normal-shaped")
  Q   = ||x - x_hat||^2             reconstruction error outside the subspace (new correlation pattern)
Control limits are the --alpha quantiles of T^2 and Q on the training rows (empirical, no distribution
assumption). For each flagged row the features contributing most to Q are listed. With --label, a
known anomaly flag column, precision/recall of the flags are reported.

Uses load() and pca() from pca_report.py in the same folder.

Usage:
    python pca_outliers.py --train sensors_jan.csv --score sensors_feb.csv --drop reading_id --k 2
    python pca_outliers.py --train sensors.csv --drop reading_id is_anomaly --var 0.9 --label is_anomaly
    python pca_outliers.py --train data.csv --drop id --alpha 0.995 --top 10 --json

Exit codes: 0 scored (no rows flagged above the limits is also 0), 2 usage or read error.
"""

import argparse
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pca_report import load, num, pca  # noqa: E402


def quantile(xs, p):
    s = sorted(xs)
    return s[min(len(s) - 1, int(math.ceil(p * len(s))) - 1)]


def main():
    ap = argparse.ArgumentParser(description="PCA-based outlier detection (T^2 and Q).", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train", required=True)
    ap.add_argument("--score", help="rows to score (default: the training rows)")
    ap.add_argument("--columns", nargs="*")
    ap.add_argument("--drop", nargs="*", default=[])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--k", type=int, help="number of components")
    g.add_argument("--var", type=float, default=0.9, help="keep components up to this variance share")
    ap.add_argument("--alpha", type=float, default=0.99, help="control-limit quantile on training rows")
    ap.add_argument("--label", help="known anomaly flag column in the scored file (for precision/recall)")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    drop = set(a.drop) | ({a.label} if a.label else set())
    try:
        cols, Xtr = load(a.train, a.columns, drop)
        if a.score:
            _, Xsc = load(a.score, cols, ())
        else:
            Xsc = Xtr
        labels = None
        if a.label:
            with open(a.score or a.train, newline="", encoding="utf-8-sig") as fh:
                rd = list(csv.DictReader(fh))
            labels = [int(float(r[a.label])) for r in rd if all(num(r[c]) is not None for c in cols)]
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(cols) < 2 or len(Xtr) <= len(cols):
        print("error: need >= 2 numeric columns and more training rows than columns", file=sys.stderr)
        return 2
    model = pca(Xtr, scale=True)
    ev, comps, mu, sd = model["eigenvalues"], model["components"], model["mean"], model["sd"]
    total = sum(ev)
    if a.k:
        k = max(1, min(a.k, len(cols) - 1))
    else:
        cum, k = 0.0, 0
        while k < len(cols) - 1 and cum < a.var:
            cum += ev[k] / total
            k += 1
    def score(x):
        z = [(x[j] - mu[j]) / sd[j] for j in range(len(cols))]
        t = [sum(z[j] * comps[i][j] for j in range(len(cols))) for i in range(k)]
        recon = [sum(t[i] * comps[i][j] for i in range(k)) for j in range(len(cols))]
        resid = [z[j] - recon[j] for j in range(len(cols))]
        t2 = sum(t[i] ** 2 / ev[i] for i in range(k) if ev[i] > 0)
        return t2, sum(r * r for r in resid), resid
    tr = [score(x) for x in Xtr]
    t2_lim = quantile([s[0] for s in tr], a.alpha)
    q_lim = quantile([s[1] for s in tr], a.alpha)
    sc = [score(x) for x in Xsc]
    flagged = []
    for i, (t2, q, resid) in enumerate(sc):
        reasons = []
        if t2 > t2_lim:
            reasons.append("T2")
        if q > q_lim:
            reasons.append("Q")
        if reasons:
            contrib = sorted(zip(cols, resid), key=lambda cr: -cr[1] ** 2)[:3]
            flagged.append({"row": i + 2, "t2": t2, "q": q, "why": "+".join(reasons),
                            "q_contributors": [{"feature": c, "residual_z": round(r, 3)} for c, r in contrib]})
    flagged.sort(key=lambda f: -(f["q"] / q_lim + f["t2"] / t2_lim))
    out = {"train_rows": len(Xtr), "scored_rows": len(Xsc), "components": k,
           "variance_kept": sum(ev[:k]) / total, "t2_limit": t2_lim, "q_limit": q_lim, "alpha": a.alpha,
           "flagged": len(flagged), "rows": flagged[:a.top]}
    if labels and len(labels) == len(Xsc):
        fl = {f["row"] - 2 for f in flagged}
        tp = sum(1 for i in fl if labels[i])
        out["vs_label"] = {"precision": tp / len(fl) if fl else 0.0, "recall": tp / max(1, sum(labels)),
                           "flagged": len(fl), "labelled_anomalies": sum(labels)}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"PCA with {k} components ({out['variance_kept']:.1%} variance) fitted on {len(Xtr)} rows; "
          f"limits at the {a.alpha:g} training quantile: T2 {t2_lim:.3g}, Q {q_lim:.3g}")
    print(f"{len(flagged)} of {len(Xsc)} scored rows flagged ({len(flagged) / len(Xsc):.1%})")
    for f in flagged[:a.top]:
        cs = ", ".join(f"{c['feature']} {c['residual_z']:+.2f}" for c in f["q_contributors"])
        print(f"  line {f['row']}: {f['why']:<4} T2 {f['t2']:.3g}  Q {f['q']:.3g}  top Q contributors: {cs}")
    if "vs_label" in out:
        v = out["vs_label"]
        print(f"against {a.label}: precision {v['precision']:.2f}, recall {v['recall']:.2f} "
              f"({v['flagged']} flagged, {v['labelled_anomalies']} labelled)")
    print("T2 = extreme along normal patterns; Q = a pattern the model has not seen (often sensor faults or new regimes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
