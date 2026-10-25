#!/usr/bin/env python3
"""Per-slice evaluation for a model card: metrics with bootstrap CIs and fairness gaps.

Input: a predictions CSV with the true label, the model score and one or more slice columns, e.g.
    y_true,y_score,group,age_band,region
Binary classification (labels 0/1, scores in [0, 1]) by default; --regression for numeric targets with a
y_pred column.

For the overall data and every level of each --slices column it reports n, positives, and:
  classification   ROC AUC, average precision, positive rate at --threshold, TPR (recall), FPR, precision,
                   Brier score; 95% bootstrap CI (--boot resamples, seeded) for AUC and TPR
  regression       MAE, RMSE, bias (mean error), R^2; CI for MAE
Then per slice column:
  gaps         max - min across levels of AUC, TPR, FPR and positive rate (equal opportunity difference =
               TPR gap, false-positive-rate gap, demographic parity difference = positive-rate gap); the
               positive-rate ratio (min / max: the "four-fifths rule" flags < 0.8)
  flags        LOW-N slices (< --min-n rows or < 10 positives: their metrics are not reliable),
               UNDERPERFORMS: a slice whose AUC CI lies entirely below the overall AUC
Output is a readable report, --markdown (tables to paste into a model card) or --json (input for
model_card.py's "slices" field).

Usage:
    python slice_metrics.py preds.csv --slices group age_band --threshold 0.5
    python slice_metrics.py preds.csv --slices region --markdown
    python slice_metrics.py preds.csv --regression --pred-col y_pred --slices segment --json

Exit codes: 0 no flags, 1 a slice underperforms or a gap exceeds --max-gap (default 0.1) / ratio < 0.8,
2 usage or read error.
"""

import argparse
import csv
import json
import math
import random
import sys
from collections import defaultdict


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def auc(y, s):
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return None
    pairs = sorted(zip(s, y))
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        r = (i + j) / 2 + 1
        rank_sum += r * sum(lab for _, lab in pairs[i:j + 1])
        i = j + 1
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def avg_precision(y, s):
    pos = sum(y)
    if not pos:
        return None
    order = sorted(range(len(s)), key=lambda i: -s[i])
    tp = fp = 0
    ap, prev_recall, k = 0.0, 0.0, 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and s[order[j + 1]] == s[order[k]]:
            j += 1
        for idx in order[k:j + 1]:
            tp += y[idx]
            fp += 1 - y[idx]
        recall = tp / pos
        ap += (recall - prev_recall) * tp / (tp + fp)
        prev_recall = recall
        k = j + 1
    return ap


def clf_metrics(y, s, thr):
    pred = [1 if v >= thr else 0 for v in s]
    tp = sum(1 for a, b in zip(y, pred) if a and b)
    fp = sum(1 for a, b in zip(y, pred) if not a and b)
    pos = sum(y)
    neg = len(y) - pos
    return {"n": len(y), "positives": pos, "auc": auc(y, s), "avg_precision": avg_precision(y, s),
            "positive_rate": sum(pred) / len(y), "tpr": tp / pos if pos else None, "fpr": fp / neg if neg else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "brier": sum((v - a) ** 2 for a, v in zip(y, s)) / len(y)}


def reg_metrics(y, p):
    n = len(y)
    err = [b - a for a, b in zip(y, p)]
    mae = sum(abs(e) for e in err) / n
    rmse = math.sqrt(sum(e * e for e in err) / n)
    my = sum(y) / n
    sst = sum((a - my) ** 2 for a in y)
    return {"n": n, "mae": mae, "rmse": rmse, "bias": sum(err) / n,
            "r2": 1 - sum(e * e for e in err) / sst if sst else None}


def bootstrap(y, s, fn, boot, seed):
    rng = random.Random(seed)
    n = len(y)
    vals = []
    for _ in range(boot):
        idx = [rng.randrange(n) for _ in range(n)]
        v = fn([y[i] for i in idx], [s[i] for i in idx])
        if v is not None:
            vals.append(v)
    if len(vals) < boot * 0.5:
        return None
    vals.sort()
    return vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]


def tpr_fn(thr):
    def f(y, s):
        pos = sum(y)
        return sum(1 for a, b in zip(y, s) if a and b >= thr) / pos if pos else None
    return f


def evaluate(rows, a):
    def metrics(sub):
        y = [r[0] for r in sub]
        s = [r[1] for r in sub]
        if a.regression:
            m = reg_metrics(y, s)
            m["mae_ci"] = bootstrap(y, s, lambda yy, ss: reg_metrics(yy, ss)["mae"], a.boot, a.seed)
        else:
            m = clf_metrics(y, s, a.threshold)
            m["auc_ci"] = bootstrap(y, s, auc, a.boot, a.seed)
            m["tpr_ci"] = bootstrap(y, s, tpr_fn(a.threshold), a.boot, a.seed)
        low = m["n"] < a.min_n or (not a.regression and (m["positives"] < 10 or m["n"] - m["positives"] < 10))
        m["low_n"] = low
        return m

    res = {"overall": metrics(rows), "slices": {}, "flags": []}
    for k, col in enumerate(a.slices):
        groups = defaultdict(list)
        for r in rows:
            groups[r[2][k]].append(r)
        levels = {}
        for lv in sorted(groups):
            levels[lv] = metrics(groups[lv])
        ok = {lv: m for lv, m in levels.items() if not m["low_n"]}
        gaps = {}
        keys = ("mae", "rmse", "bias") if a.regression else ("auc", "tpr", "fpr", "positive_rate")
        for key in keys:
            vals = [m[key] for m in ok.values() if m[key] is not None]
            if len(vals) >= 2:
                gaps[key] = max(vals) - min(vals)
        if not a.regression:
            pr = [m["positive_rate"] for m in ok.values()]
            if len(pr) >= 2 and max(pr) > 0:
                gaps["positive_rate_ratio"] = min(pr) / max(pr)
        res["slices"][col] = {"levels": levels, "gaps": gaps}
        for lv, m in levels.items():
            if m["low_n"]:
                res["flags"].append(("LOW-N", col, lv, f"n={m['n']}" + ("" if a.regression else
                                                                      f", positives={m['positives']}")))
            elif not a.regression and m["auc_ci"] and res["overall"]["auc"] and m["auc_ci"][1] < res["overall"]["auc"]:
                res["flags"].append(("UNDERPERFORMS", col, lv, f"AUC {m['auc']:.3f} (CI {m['auc_ci'][0]:.3f}-"
                                                              f"{m['auc_ci'][1]:.3f}) below overall {res['overall']['auc']:.3f}"))
        for key in ("tpr", "fpr", "positive_rate", "auc"):
            if gaps.get(key) is not None and gaps[key] > a.max_gap:
                res["flags"].append(("GAP", col, key, f"{key} differs by {gaps[key]:.3f} across levels (> {a.max_gap})"))
        if gaps.get("positive_rate_ratio") is not None and gaps["positive_rate_ratio"] < 0.8:
            res["flags"].append(("GAP", col, "positive_rate_ratio",
                                 f"positive-rate ratio {gaps['positive_rate_ratio']:.2f} < 0.8 (four-fifths rule)"))
    return res


def f3(v):
    return "n/a" if v is None else f"{v:.3f}"


def ci(c):
    return "" if not c else f" [{c[0]:.3f}, {c[1]:.3f}]"


def row_text(name, m, regression):
    if regression:
        return (f"| {name} | {m['n']} | {f3(m['mae'])}{ci(m.get('mae_ci'))} | {f3(m['rmse'])} | {f3(m['bias'])} | "
                f"{f3(m['r2'])} |")
    return (f"| {name} | {m['n']} | {m['positives']} | {f3(m['auc'])}{ci(m.get('auc_ci'))} | {f3(m['avg_precision'])} | "
            f"{f3(m['tpr'])}{ci(m.get('tpr_ci'))} | {f3(m['fpr'])} | {f3(m['positive_rate'])} | {f3(m['brier'])} |")


def markdown(res, a):
    if a.regression:
        hdr = "| slice | n | MAE [95% CI] | RMSE | bias | R^2 |\n|---|---|---|---|---|---|"
    else:
        hdr = ("| slice | n | positives | ROC AUC [95% CI] | avg precision | TPR [95% CI] | FPR | positive rate | Brier |\n"
               "|---|---|---|---|---|---|---|---|---|")
    out = [f"Threshold: {a.threshold}" if not a.regression else "Regression metrics", "", hdr,
           row_text("**overall**", res["overall"], a.regression)]
    for col, d in res["slices"].items():
        for lv, m in d["levels"].items():
            out.append(row_text(f"{col} = {lv}" + (" (low n)" if m["low_n"] else ""), m, a.regression))
    out.append("")
    for col, d in res["slices"].items():
        if d["gaps"]:
            out.append(f"- **{col}** gaps: " + ", ".join(f"{k} {v:.3f}" for k, v in d["gaps"].items()))
    for fl in res["flags"]:
        out.append(f"- {fl[0]}: {fl[1]} = {fl[2]}: {fl[3]}" if fl[0] != "GAP" else f"- GAP: {fl[1]}: {fl[3]}")
    return "\n".join(out)


def text(res, a):
    lines = [ln for ln in markdown(res, a).splitlines() if not ln.startswith("|---")]
    lines.append("")
    lines.append("Bootstrap CIs are 95% percentile intervals; LOW-N slices are excluded from the gaps.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Per-slice metrics and fairness gaps.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--slices", nargs="*", default=[])
    ap.add_argument("--label-col", default="y_true")
    ap.add_argument("--score-col", default="y_score")
    ap.add_argument("--pred-col", default="y_pred", help="prediction column with --regression")
    ap.add_argument("--regression", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--boot", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--min-n", type=int, default=50)
    ap.add_argument("--max-gap", type=float, default=0.1)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--markdown", action="store_true")
    g.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            raw = list(csv.DictReader(f))
        if not raw:
            raise ValueError("no rows")
        sc = a.pred_col if a.regression else a.score_col
        for c in [a.label_col, sc] + a.slices:
            if c not in raw[0]:
                raise ValueError(f"column {c!r} not found (have: {', '.join(raw[0])})")
        rows = []
        for r in raw:
            y, s = num(r[a.label_col]), num(r[sc])
            if y is None or s is None:
                continue
            if not a.regression and y not in (0, 1):
                raise ValueError("labels must be 0/1 for classification (use --regression for numeric targets)")
            rows.append((int(y) if not a.regression else y, s, [r[c] or "(missing)" for c in a.slices]))
        if len(rows) < 20:
            raise ValueError("need at least 20 rows")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    res = evaluate(rows, a)
    if a.json:
        print(json.dumps({**res, "flags": [dict(zip(("flag", "column", "level", "detail"), f)) for f in res["flags"]],
                          "threshold": a.threshold}, indent=2))
    elif a.markdown:
        print(markdown(res, a))
    else:
        print(text(res, a))
    bad = any(f[0] in ("UNDERPERFORMS", "GAP") for f in res["flags"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
