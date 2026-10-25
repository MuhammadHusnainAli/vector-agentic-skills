#!/usr/bin/env python3
"""Profile a candidate target column in a CSV and say which ML task it implies.

Reads the column, infers what kind of label it is and prints the task type,
the class balance or distribution, the metric family that fits, and warnings
that change the framing (too few positives, constant target, ID-like target,
heavy skew, many zeros, missing labels).

Kinds detected:
  binary        two distinct values (0/1, yes/no, true/false, any two labels)
  multiclass    3..50 distinct non-numeric values, or small-integer codes
  ordinal       3..10 consecutive integers (ratings, grades): consider ordinal or regression
  count         non-negative integers with many distinct values
  continuous    real numbers
  id_like       almost every value unique and non-numeric: not a target
  constant      one distinct value: nothing to learn

Usage:
    python target_profile.py data.csv --target churned
    python target_profile.py data.csv --target price --json
    python target_profile.py - --target label < data.csv

Exit codes: 0 usable target, 1 target has a blocking problem (constant, ID-like,
< 2 classes with enough rows, too few minority examples), 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import Counter

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def to_num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except ValueError:
        return None


def quantile(sorted_xs, q):
    if not sorted_xs:
        return float("nan")
    pos = (len(sorted_xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


def skewness(xs):
    n = len(xs)
    if n < 3:
        return 0.0
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / n)
    return 0.0 if sd == 0 else sum(((x - m) / sd) ** 3 for x in xs) / n


def profile(values):
    n_total = len(values)
    present = [v.strip() for v in values if v.strip().lower() not in MISSING]
    n = len(present)
    res = {"rows": n_total, "labelled": n, "missing": n_total - n, "warnings": [], "blocking": []}
    if n == 0:
        res["kind"] = "empty"
        res["blocking"].append("target column has no values")
        return res
    counts = Counter(present)
    nums = [to_num(v) for v in present]
    numeric = all(x is not None for x in nums)
    distinct = len(counts)
    res["distinct"] = distinct
    if res["missing"] / n_total > 0.05:
        res["warnings"].append(f"{res['missing']} rows ({res['missing'] / n_total:.0%}) have no label: find out why "
                               "(not yet observed? censored? filtered?) before dropping them")

    if distinct == 1:
        res["kind"] = "constant"
        res["blocking"].append(f"every labelled row is {present[0]!r}: nothing to learn; check the label query")
        return res
    if distinct == 2:
        res["kind"] = "binary"
    elif numeric and all(float(x).is_integer() for x in nums):
        ints = sorted({int(x) for x in nums})
        if distinct <= 10 and ints == list(range(ints[0], ints[0] + distinct)):
            res["kind"] = "ordinal"
        elif min(ints) >= 0 and distinct > 10:
            # counts repeat small values; integer prices or amounts are almost all distinct
            res["kind"] = "count" if distinct <= 0.5 * n or ints[-1] <= 1000 else "continuous"
        else:
            res["kind"] = "multiclass" if distinct <= 50 else "continuous"
    elif numeric:
        res["kind"] = "continuous"
    elif distinct > 0.9 * n and n > 20:
        res["kind"] = "id_like"
        res["blocking"].append("almost every value is unique text: this looks like an ID or free text, not a label")
        return res
    else:
        res["kind"] = "multiclass"

    if res["kind"] in ("binary", "multiclass", "ordinal"):
        dist = counts.most_common()
        if res["kind"] == "ordinal":
            dist.sort(key=lambda vc: float(vc[0]))
        res["classes"] = [{"value": v, "count": c, "share": round(c / n, 4)} for v, c in dist]
        minority = min(c for _, c in dist)
        res["minority_share"] = round(minority / n, 4)
        if res["kind"] == "binary":
            if minority < 30:
                res["blocking"].append(f"only {minority} minority examples: too few to train or to measure; "
                                       "widen the window, pool more history, or use rules/anomaly detection")
            elif minority < 200:
                res["warnings"].append(f"{minority} minority examples: metrics will be noisy; use repeated stratified CV "
                                       "and report confidence intervals")
            if minority / n < 0.05:
                res["warnings"].append(f"minority share {minority / n:.1%}: use PR-AUC / recall@capacity, not accuracy "
                                       "(see imbalanced-class-handler)")
        else:
            rare = [v for v, c in dist if c < 10]
            if rare:
                res["warnings"].append(f"{len(rare)} class(es) with < 10 rows ({', '.join(map(str, rare[:5]))}): "
                                       "merge them into 'other' or collect more")
            if distinct > 20:
                res["warnings"].append(f"{distinct} classes: consider a hierarchy or top-k accuracy")
    else:
        xs = sorted(x for x in nums if x is not None)
        mean = sum(xs) / len(xs)
        res["summary"] = {k: round(v, 4) for k, v in {
            "min": xs[0], "p01": quantile(xs, 0.01), "p25": quantile(xs, 0.25), "median": quantile(xs, 0.5),
            "mean": mean, "p75": quantile(xs, 0.75), "p99": quantile(xs, 0.99), "max": xs[-1]}.items()}
        sk = skewness(xs)
        res["skew"] = round(sk, 3)
        zeros = sum(1 for x in xs if x == 0) / len(xs)
        res["zero_share"] = round(zeros, 4)
        if zeros > 0.3:
            res["warnings"].append(f"{zeros:.0%} zeros: a two-part (hurdle) model or Tweedie/Poisson loss fits better "
                                   "than plain squared error")
        if sk > 1 and xs[0] >= 0:
            res["warnings"].append(f"right-skewed (skew {sk:.2f}): train on log1p(target) or use a Tweedie/Gamma "
                                   "objective; report errors in original units")
        if xs[0] < 0 and res["kind"] == "count":
            res["warnings"].append("negative values in a count-like target: check the definition")
        if len(xs) > 20 and xs[-1] > quantile(xs, 0.99) * 3:
            res["warnings"].append("extreme maximum (> 3x the 99th percentile): check for data errors; consider Huber "
                                   "loss or capping")
    return res


TASKS = {
    "binary": ("binary classification", "PR-AUC or recall@capacity for rare positives, ROC-AUC for ranking, log loss / "
               "Brier when probabilities are used"),
    "multiclass": ("multiclass classification", "macro-F1 when classes matter equally, weighted-F1 or accuracy when "
                   "frequency matters, top-k accuracy for routing"),
    "ordinal": ("ordinal classification or regression", "MAE on the ordinal scale, quadratic weighted kappa, "
                "Spearman correlation"),
    "count": ("count regression (Poisson / Tweedie)", "Poisson deviance, MAE; RMSE only if large errors are much worse"),
    "continuous": ("regression", "MAE (robust, in units), RMSE (penalises large errors), MAPE/WAPE for business "
                   "reporting when targets are far from 0"),
}


def main():
    ap = argparse.ArgumentParser(description="Profile a target column and infer the ML task type.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="CSV file with a header row, or - for stdin")
    ap.add_argument("--target", required=True, help="target column name")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        reader = csv.DictReader(fh)
        if a.target not in (reader.fieldnames or []):
            print(f"error: column {a.target!r} not found; columns: {', '.join(reader.fieldnames or [])}", file=sys.stderr)
            return 2
        values = [row[a.target] or "" for row in reader]
    except OSError as e:
        print(f"error: cannot read {a.csv}: {e}", file=sys.stderr)
        return 2

    res = profile(values)
    task, metrics = TASKS.get(res["kind"], ("none", "-"))
    res["task_type"], res["metric_family"] = task, metrics
    if a.json:
        print(json.dumps(res, indent=2))
        return 1 if res["blocking"] else 0

    print(f"Target {a.target!r}: {res['kind']}  ->  {task}")
    print(f"rows {res['rows']}, labelled {res['labelled']}, missing {res['missing']}, distinct {res.get('distinct', 0)}")
    for c in res.get("classes", [])[:12]:
        print(f"  {str(c['value']):<20} {c['count']:>7}  {c['share']:6.1%}")
    if "summary" in res:
        print("  " + "  ".join(f"{k}={v:g}" for k, v in res["summary"].items()))
        print(f"  skew={res['skew']:g}  zero_share={res['zero_share']:.1%}")
    print(f"metrics: {metrics}")
    for b in res["blocking"]:
        print(f"BLOCKING: {b}")
    for w in res["warnings"]:
        print(f"warning: {w}")
    return 1 if res["blocking"] else 0


if __name__ == "__main__":
    sys.exit(main())
