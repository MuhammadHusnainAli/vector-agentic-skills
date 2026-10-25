#!/usr/bin/env python3
"""Diagnose a regression target and recommend the loss, transform and model family that fit its shape.

Reads one numeric column and reports: quantiles, mean vs median, skew, tail ratio (p99 / median),
share of zeros, negatives, integer-ness, bounded [0, 1] proportions, and robust outliers. Then
recommends one of:
  squared error            symmetric, light tails
  absolute / Huber         heavy-tailed noise or outliers you do not want to chase
  log1p target             positive, right-skewed, multiplicative effects (predicts the median-ish)
  Gamma                    strictly positive, skewed, variance grows with the mean^2 (claim size)
  Poisson                  counts, variance ~ mean
  Tweedie (1 < p < 2)      many exact zeros plus a positive skewed tail (insurance loss, spend)
  (two-part / hurdle)      suggested alongside Tweedie when zeros exceed half the rows, and for
                           counts with far more zeros than a Poisson with the same mean would give
  logit / beta             proportions in (0, 1)
  quantile (pinball)       when the business needs a percentile, not the mean
and the matching objective names for scikit-learn, LightGBM, XGBoost and CatBoost.

Usage:
    python target_diagnostics.py data.csv --target price
    python target_diagnostics.py data.csv --target claim_amount --need-quantile 0.9
    python target_diagnostics.py data.csv --target spend_90d --json

Exit codes: 0 diagnosed, 2 usage error or non-numeric target.
"""

import argparse
import csv
import json
import math
import sys

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def q(xs, p):
    pos = (len(xs) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def describe(xs):
    xs = sorted(xs)
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    sd = math.sqrt(var)
    med = q(xs, 0.5)
    mad = q(sorted(abs(x - med) for x in xs), 0.5) * 1.4826
    pos = [x for x in xs if x > 0]
    logs = [math.log(x) for x in pos]
    lmean = sum(logs) / len(logs) if logs else 0.0
    lsd = math.sqrt(sum((l - lmean) ** 2 for l in logs) / len(logs)) if len(logs) > 1 else 0.0
    return {
        "n": n, "min": xs[0], "p01": q(xs, 0.01), "p25": q(xs, 0.25), "median": med, "mean": mean,
        "p75": q(xs, 0.75), "p99": q(xs, 0.99), "max": xs[-1], "std": sd,
        "skew": 0.0 if sd == 0 else sum(((x - mean) / sd) ** 3 for x in xs) / n,
        "skew_of_log_positive": 0.0 if lsd == 0 else sum(((l - lmean) / lsd) ** 3 for l in logs) / len(logs),
        "zero_share": sum(1 for x in xs if x == 0) / n, "negative_share": sum(1 for x in xs if x < 0) / n,
        "integer": all(float(x).is_integer() for x in xs), "distinct": len(set(xs)),
        "tail_ratio": (q(xs, 0.99) / med) if med > 0 else None,
        "dispersion": var / mean if mean > 0 else None,
        "outlier_share": sum(1 for x in xs if mad and abs(x - med) / mad > 5) / n,
    }


OBJECTIVES = {
    "squared": ("squared error", "HistGradientBoostingRegressor(loss='squared_error') / Ridge",
                "objective='regression'", "objective='reg:squarederror'", "loss_function='RMSE'"),
    "huber": ("Huber / absolute error", "HistGradientBoostingRegressor(loss='absolute_error') / HuberRegressor",
              "objective='huber' (alpha=delta) or 'regression_l1'", "objective='reg:pseudohubererror' or 'reg:absoluteerror'",
              "loss_function='Huber:delta=...' or 'MAE'"),
    "log": ("log1p target + squared error", "TransformedTargetRegressor(func=np.log1p, inverse_func=np.expm1)",
            "train on log1p(y), objective='regression'", "train on log1p(y)", "train on log1p(y) or loss_function='RMSE'"),
    "gamma": ("Gamma deviance (log link)", "HistGradientBoostingRegressor(loss='gamma') / GammaRegressor",
              "objective='gamma'", "objective='reg:gamma'", "loss_function='Tweedie:variance_power=1.99' (Gamma-like)"),
    "poisson": ("Poisson deviance (log link)", "HistGradientBoostingRegressor(loss='poisson') / PoissonRegressor",
                "objective='poisson'", "objective='count:poisson'", "loss_function='Poisson'"),
    "tweedie": ("Tweedie deviance, power in (1, 2)", "TweedieRegressor(power=1.5, link='log') (HGB has no tweedie loss)",
                "objective='tweedie', tweedie_variance_power=1.5", "objective='reg:tweedie', tweedie_variance_power=1.5",
                "loss_function='Tweedie:variance_power=1.5'"),
    "hurdle": ("two-part model: P(y > 0) classifier x E[y | y > 0] regressor", "classifier + regressor on positives",
               "binary + gamma/regression on positives", "binary:logistic + reg:gamma on positives",
               "Logloss + RMSE/Tweedie on positives"),
    "logit": ("logit-transformed proportion or cross-entropy on [0,1] targets", "TransformedTargetRegressor(logit/expit)",
              "objective='cross_entropy' (xentropy) with y in [0, 1]", "objective='reg:logistic' with y in [0, 1]",
              "loss_function='CrossEntropy' (targets in [0,1]) or RMSE on logit"),
    "quantile": ("quantile (pinball) loss", "HistGradientBoostingRegressor(loss='quantile', quantile=q)",
                 "objective='quantile', alpha=q", "objective='reg:quantileerror', quantile_alpha=q",
                 "loss_function='Quantile:alpha=q'"),
}


def recommend(d, need_q):
    why = []
    if need_q:
        return "quantile", [f"the decision needs the {need_q:.0%} quantile (safety stock, upper bound), not the mean"]
    if 0 <= d["min"] and d["max"] <= 1 and not d["integer"]:
        return "logit", ["values lie in [0, 1]: a proportion; keep predictions inside the bounds"]
    if d["integer"] and d["min"] >= 0 and d["distinct"] <= max(50, 0.2 * d["n"]):
        disp = d["dispersion"]
        why.append(f"non-negative integer counts (variance/mean {disp:.2f})" if disp else "non-negative counts")
        p0 = math.exp(-d["mean"])                 # zero share a Poisson with this mean would produce
        if d["zero_share"] > p0 + 0.1:
            why.append(f"zeros {d['zero_share']:.0%} vs {p0:.0%} expected under Poisson: zero-inflated; consider a "
                       "hurdle model or Tweedie, or check for a missing exposure offset")
        elif disp and disp > 2:
            why.append("over-dispersed: the Poisson mean is fine for ranking, but intervals need negative binomial / Tweedie")
        return "poisson", why
    if d["min"] >= 0 and d["zero_share"] > 0.05 and d["skew"] > 1:
        why = [f"{d['zero_share']:.0%} exact zeros plus a right-skewed positive part (skew {d['skew']:.1f}): "
               "compound Poisson-Gamma (Tweedie) models both in one loss"]
        if d["zero_share"] > 0.5:
            why.append("alternative: a two-part model (P(y > 0) x E[y | y > 0]) when zeros come from a different process")
        return "tweedie", why
    if d["min"] > 0 and d["skew"] > 1:
        if abs(d["skew_of_log_positive"]) < 0.5:
            return "log", [f"right-skewed (skew {d['skew']:.1f}) and roughly log-normal (skew of log "
                           f"{d['skew_of_log_positive']:.2f}): log1p target or Gamma loss"]
        return "gamma", [f"strictly positive and right-skewed (skew {d['skew']:.1f}); log is not enough to symmetrise"]
    if d["outlier_share"] > 0.01 or abs(d["skew"]) > 2:
        return "huber", [f"{d['outlier_share']:.1%} extreme values / skew {d['skew']:.1f}: a robust loss stops them dominating"]
    return "squared", ["roughly symmetric with light tails: squared error estimates the mean well"]


def main():
    ap = argparse.ArgumentParser(description="Recommend loss / transform for a regression target.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--need-quantile", type=float, help="the decision needs this quantile (0-1), e.g. 0.9")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            if a.target not in (reader.fieldnames or []):
                raise ValueError(f"target {a.target!r} not found")
            raw = [(r[a.target] or "").strip() for r in reader]
        xs = [float(v) for v in raw if v.lower() not in MISSING]
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if len(xs) < 10:
        print("error: fewer than 10 numeric target values", file=sys.stderr)
        return 2
    d = describe(xs)
    d["missing"] = len(raw) - len(xs)
    choice, why = recommend(d, a.need_quantile)
    name, sk, lgb, xgb, cb = OBJECTIVES[choice]
    notes = []
    if choice == "log":
        notes.append("log-target predictions estimate the conditional median; for totals multiply by a smearing "
                     "factor mean(exp(residuals)) or use the Gamma/Tweedie objective")
    if d["tail_ratio"] and d["tail_ratio"] > 10:
        notes.append(f"p99 is {d['tail_ratio']:.0f}x the median: report errors by segment; RMSE will be dominated by the tail")
    if d["negative_share"] > 0 and choice in ("squared", "huber"):
        notes.append("negative values present: log, Gamma, Poisson and Tweedie are not applicable")
    if d["missing"]:
        notes.append(f"{d['missing']} rows without a target: check why before dropping them")
    metric = {"squared": "RMSE (+MAE)", "huber": "MAE (+RMSE)", "log": "MAE / WAPE in original units, RMSLE",
              "gamma": "mean Gamma deviance, MAE", "poisson": "mean Poisson deviance, MAE", "tweedie": "mean Tweedie deviance, MAE",
              "hurdle": "MAE, plus AUC of the zero/non-zero part", "logit": "MAE, cross-entropy", "quantile": "pinball loss at q, coverage"}[choice]
    out = {"target": a.target, "stats": {k: (round(v, 6) if isinstance(v, float) else v) for k, v in d.items()},
           "recommendation": choice, "loss": name, "why": why, "sklearn": sk, "lightgbm": lgb, "xgboost": xgb,
           "catboost": cb, "metric": metric, "notes": notes}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    s = out["stats"]
    print(f"Target {a.target!r}: n={s['n']}  min={s['min']:g}  median={s['median']:g}  mean={s['mean']:g}  "
          f"p99={s['p99']:g}  max={s['max']:g}")
    print(f"  skew {s['skew']:.2f} (of log: {s['skew_of_log_positive']:.2f})  zeros {s['zero_share']:.1%}  "
          f"negatives {s['negative_share']:.1%}  integer {s['integer']}  outliers {s['outlier_share']:.1%}")
    print(f"\nRECOMMENDED: {name}")
    for w in why:
        print(f"  why: {w}")
    print(f"  scikit-learn: {sk}\n  LightGBM:     {lgb}\n  XGBoost:      {xgb}\n  CatBoost:     {cb}\n  metric:       {metric}")
    for n_ in notes:
        print(f"  note: {n_}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
