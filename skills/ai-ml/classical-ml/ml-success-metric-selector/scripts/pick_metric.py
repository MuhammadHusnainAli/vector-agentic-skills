#!/usr/bin/env python3
"""Recommend a primary metric, secondary metrics and guardrails from the problem's traits.

Answers the question "which number do we optimise and report?" from facts about the
decision rather than habit. Every recommendation comes with the reason and the metric
it replaces when that one would mislead.

Traits (flags):
  --task           binary | multiclass | multilabel | regression | count | forecast | ranking |
                   recommendation | anomaly | survival | uplift
  --prevalence     positive rate (binary/anomaly), e.g. 0.02
  --capacity       cases acted on per period (top-K decisions); with --population gives K/N
  --cost-fp / --cost-fn   cost of a false positive / false negative (any unit)
  --probabilities  the probability itself is used (pricing, expected loss, risk tiers)
  --classes-equal  multiclass: rare classes matter as much as common ones
  --outliers       regression: large errors are rare but not to be chased (robust metric)
  --big-errors-worse  regression: a few large errors are much worse than many small ones
  --near-zero      regression/forecast: true values can be 0 or close to 0
  --many-series    forecast: metric must aggregate across series of different scales
  --quantiles      forecast/regression: intervals or a service level are needed

Usage:
    python pick_metric.py --task binary --prevalence 0.02 --capacity 400 --cost-fp 8 --cost-fn 600
    python pick_metric.py --task regression --outliers --near-zero
    python pick_metric.py --task forecast --many-series --near-zero --quantiles --json

Exit codes: 0 recommendation printed, 2 usage error.
"""

import argparse
import json
import sys


def rec(primary, why, secondary=(), guardrails=(), avoid=(), threshold=None):
    return {"primary": primary, "why": why, "secondary": list(secondary), "guardrails": list(guardrails),
            "avoid": list(avoid), "threshold": threshold}


def binary(a):
    avoid = []
    if a.prevalence is not None and a.prevalence < 0.2:
        avoid.append(("accuracy", f"at {a.prevalence:.1%} prevalence 'always negative' scores {1 - a.prevalence:.1%}"))
    avoid.append(("F1 at 0.5", "0.5 is rarely the operating point; F1 ignores true negatives and costs"))
    thr = None
    if a.cost_fp is not None and a.cost_fn is not None and a.cost_fp + a.cost_fn > 0:
        t = a.cost_fp / (a.cost_fp + a.cost_fn)
        thr = (f"with calibrated probabilities act when p > cost_fp / (cost_fp + cost_fn) = {t:.4f}; "
               "check calibration first")
    if a.capacity:
        k = f"top {a.capacity:g}" + (f" of {a.population:g} ({a.capacity / a.population:.1%})" if a.population else "")
        primary = f"precision@K and recall@K at K = {k}"
        why = "the action handles a fixed number of cases, so only the ranking of the top K matters"
        sec = ["PR-AUC (average precision)", "ROC-AUC for overall ranking", "lift@K vs random and vs the rule"]
    elif a.cost_fp is not None and a.cost_fn is not None:
        primary = "expected cost (or net value) at the cost-optimal threshold"
        why = f"errors have known, asymmetric costs (FP {a.cost_fp:g}, FN {a.cost_fn:g})"
        sec = ["PR-AUC", "recall and precision at the chosen threshold", "ROC-AUC"]
    elif a.prevalence is not None and a.prevalence < 0.1:
        primary = "PR-AUC (average precision)"
        why = "rare positives: PR-AUC focuses on how well positives are ranked above negatives near the top"
        sec = ["recall at a fixed precision (or precision at a fixed recall)", "ROC-AUC"]
        avoid.append(("ROC-AUC alone", "looks high on rare-event problems even when precision is poor"))
    else:
        primary = "ROC-AUC"
        why = "balanced-enough classes and no fixed operating point yet: measure ranking quality"
        sec = ["PR-AUC", "balanced accuracy at the chosen threshold"]
    if a.probabilities:
        sec = ["log loss", "Brier score", "calibration curve / ECE"] + sec
        why += "; probabilities feed a downstream calculation, so calibration is part of success"
    guard = ["metric by segment (fairness, key customer groups)", "score distribution drift (PSI)"]
    if a.capacity:
        guard.insert(0, "false positive load on the team per period")
    return rec(primary, why, sec, guard, avoid, thr)


def multiclass(a):
    if a.classes_equal:
        return rec("macro-F1", "every class counts equally, so small classes must not be drowned by big ones",
                   ["per-class recall and precision", "confusion matrix of costly swaps", "top-k accuracy"],
                   ["worst-class recall"], [("accuracy", "dominated by frequent classes")])
    return rec("accuracy (or weighted-F1)", "class frequency reflects importance",
               ["macro-F1", "log loss if probabilities route work", "top-k accuracy for human-in-the-loop routing"],
               ["per-class recall of critical classes"], [("macro-F1 as primary", "over-weights rare classes")])


def regression(a, count=False):
    avoid, sec = [], []
    if count:
        return rec("Poisson deviance (or MAE)", "count target: errors scale with the mean, Poisson deviance "
                   "matches a Poisson/Tweedie objective",
                   ["MAE", "calibration by predicted decile (mean predicted vs mean actual)"],
                   ["total predicted vs actual (bias)"], [("RMSE alone", "dominated by the largest counts")])
    if a.big_errors_worse and not a.outliers:
        primary, why = "RMSE", "large errors are disproportionately costly; RMSE squares them"
        sec.append("MAE (typical error)")
    else:
        primary, why = "MAE", "robust, in the target's units, easy to explain"
        sec.append("RMSE (sensitivity to large errors)")
        if a.outliers:
            why += "; outliers should not dominate the metric"
    if a.near_zero:
        avoid.append(("MAPE", "explodes or is undefined when actuals are near 0"))
        sec.append("WAPE = sum|error| / sum|actual| for business reporting")
    else:
        sec.append("MAPE or WAPE for business reporting")
    sec += ["R2 for comparison across models only", "mean error (bias)"]
    if a.quantiles:
        sec.insert(0, "pinball loss at each quantile; interval coverage")
    return rec(primary, why, sec, ["error by segment", "bias over time"], avoid)


def forecast(a):
    avoid = []
    if a.many_series:
        primary = "MASE (or RMSSE) vs seasonal naive, averaged across series"
        why = "scale-free across series and anchored to the naive forecast (MASE < 1 beats it)"
    else:
        primary = "MAE / WAPE on the forecast horizon"
        why = "single series: errors in units are interpretable"
    sec = ["WAPE weighted by volume or margin", "bias (sum of forecast - actual) / sum of actual"]
    if a.near_zero:
        avoid.append(("MAPE / sMAPE", "unstable with zeros and intermittent demand"))
    if a.quantiles:
        sec.insert(0, "pinball loss / CRPS for quantile forecasts; coverage of prediction intervals")
    return rec(primary, why, sec, ["stock-out rate or service level", "error by horizon"], avoid)


SIMPLE = {
    "multilabel": rec("micro-F1 (or per-label PR-AUC averaged)", "many labels per item; micro-F1 weights by "
                      "label frequency", ["macro-F1", "Hamming loss", "per-label recall"], ["label cardinality drift"]),
    "ranking": rec("NDCG@k (k = what users see)", "graded relevance and position both matter",
                   ["MRR for single-answer tasks", "MAP / recall@k for binary relevance"],
                   ["zero-result rate", "online CTR / conversion"], [("accuracy/AUC per row", "ignores the query grouping")]),
    "recommendation": rec("recall@k (or NDCG@k) on a time-based holdout", "users see a short list; "
                          "measure whether future interactions appear in it",
                          ["coverage of the catalogue", "novelty / popularity bias", "MAP@k"],
                          ["online CTR, conversion, long-term retention"], [("RMSE on ratings", "does not measure top-k quality")]),
    "anomaly": rec("precision@k on a reviewed sample (alerts the team can handle)", "labels are scarce; alert "
                   "budget defines success", ["recall on known incidents", "time to detect", "PR-AUC when labels exist"],
                   ["alert volume per day"], [("accuracy", "anomalies are rare by definition")]),
    "survival": rec("concordance index (Harrell's C or Uno's C for heavy censoring)", "ranks who fails first "
                    "and uses censored rows", ["time-dependent AUC at the decision horizon", "integrated Brier score"],
                    ["calibration at key horizons"], [("accuracy on 'event yes/no'", "ignores censoring")]),
    "uplift": rec("Qini coefficient / AUUC on a randomised holdout", "the decision is who to treat; success is "
                  "incremental outcome, not response", ["uplift at top-K", "incremental conversions per treatment cost"],
                  ["treatment cost", "negative-effect segments"], [("AUC of response", "rewards targeting sure things")]),
}


def main():
    ap = argparse.ArgumentParser(description="Recommend ML success metrics from problem traits.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True, choices=["binary", "multiclass", "multilabel", "regression", "count",
                                                       "forecast", "ranking", "recommendation", "anomaly", "survival",
                                                       "uplift"])
    ap.add_argument("--prevalence", type=float)
    ap.add_argument("--capacity", type=float)
    ap.add_argument("--population", type=float)
    ap.add_argument("--cost-fp", type=float)
    ap.add_argument("--cost-fn", type=float)
    ap.add_argument("--probabilities", action="store_true")
    ap.add_argument("--classes-equal", action="store_true")
    ap.add_argument("--outliers", action="store_true")
    ap.add_argument("--big-errors-worse", action="store_true")
    ap.add_argument("--near-zero", action="store_true")
    ap.add_argument("--many-series", action="store_true")
    ap.add_argument("--quantiles", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.prevalence is not None and not 0 < a.prevalence < 1:
        print("error: --prevalence must be between 0 and 1", file=sys.stderr)
        return 2
    r = {"binary": binary, "multiclass": multiclass, "regression": regression, "forecast": forecast,
         "count": lambda x: regression(x, count=True)}.get(a.task, lambda x: SIMPLE[a.task])(a)
    if a.json:
        print(json.dumps({"task": a.task, **r, "avoid": [{"metric": m, "why": w} for m, w in r["avoid"]]}, indent=2))
        return 0
    print(f"Task: {a.task}")
    print(f"PRIMARY    {r['primary']}\n           why: {r['why']}")
    if r["threshold"]:
        print(f"THRESHOLD  {r['threshold']}")
    for s in r["secondary"]:
        print(f"secondary  {s}")
    for g in r["guardrails"]:
        print(f"guardrail  {g}")
    for m, w in r["avoid"]:
        print(f"avoid      {m}: {w}")
    print("\nReport the primary metric with a confidence interval, against the baseline, on a deployment-like split.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
