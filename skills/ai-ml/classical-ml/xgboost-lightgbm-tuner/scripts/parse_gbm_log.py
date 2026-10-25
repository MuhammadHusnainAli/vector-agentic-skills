#!/usr/bin/env python3
"""Read a gradient-boosting training log and say what the learning curve means.

Accepted inputs (auto-detected):
  LightGBM log   [100]  training's auc: 0.93  valid_1's auc: 0.81
  XGBoost log    [99]   validation_0-logloss:0.31  validation_1-logloss:0.42   (or train-/eval- names)
  CatBoost log   99:    learn: 0.31  test: 0.42  best: 0.41 (87)  total: 1.2s ...
  CSV            iteration, <train metric>, <valid metric> columns (names containing train / valid)

For the validation curve it reports the best iteration, best value, train/valid gap at the best
iteration, how many rounds ran after it, whether the curve is still improving at the end, and
the overfitting slope after the best. Then recommends: more rounds or a higher learning rate,
a lower learning rate (best found in very few rounds), stronger regularisation (large gap,
rising validation loss), or early stopping patience.

When the training data is the first eval_set entry (logged as validation_0 / valid_0) and a
validation_1 / valid_1 series exists, the better-scoring of the two is treated as the training
curve; --train-name NAME sets it explicitly.

Metric direction is inferred from the name (auc, ndcg, map, accuracy, r2 -> higher is better;
loss, error, rmse, mae, mape, deviance -> lower) and can be forced with --higher-better.

Usage:
    python parse_gbm_log.py train.log
    python parse_gbm_log.py history.csv --json
    lightgbm_script.py 2>&1 | python parse_gbm_log.py -

Exit codes: 0 parsed, 2 nothing parseable or usage error.
"""

import argparse
import csv
import io
import json
import re
import sys

HIGHER = re.compile(r"(auc|ndcg|map|accuracy|acc\b|r2|precision|recall|f1|gini)", re.I)
LGB = re.compile(r"^\[(\d+)\]\s+(.*)$")
LGB_PART = re.compile(r"([\w.]+)'s ([\w@.:-]+):\s*(-?[\d.eE+-]+)")
XGB_PART = re.compile(r"([\w.]+)-([\w@.:-]+):\s*(-?[\d.eE+-]+)")
CB = re.compile(r"^(\d+):\s+learn:\s*(-?[\d.eE+-]+)\s+test:\s*(-?[\d.eE+-]+)")


def parse(text):
    """Return {(dataset, metric): {iteration: value}}."""
    series = {}
    lines = text.splitlines()
    head = lines[0] if lines else ""
    if "," in head and re.search(r"iter|round|epoch", head, re.I):
        rows = list(csv.DictReader(io.StringIO(text)))
        it_col = next(c for c in rows[0] if re.search(r"iter|round|epoch", c, re.I))
        for c in rows[0]:
            if c == it_col:
                continue
            ds = "train" if re.search(r"train|learn", c, re.I) else ("valid" if re.search(r"valid|val|test|eval", c, re.I) else c)
            metric = re.sub(r"^(train|training|valid|validation|val|test|eval|learn)_?", "", c, flags=re.I) or c
            series[(ds, metric)] = {int(float(r[it_col])): float(r[c]) for r in rows if r[c] not in ("", None)}
        return series
    for ln in lines:
        ln = ln.strip()
        m = CB.match(ln)
        if m:
            it = int(m.group(1))
            series.setdefault(("train", "loss"), {})[it] = float(m.group(2))
            series.setdefault(("valid", "loss"), {})[it] = float(m.group(3))
            continue
        m = LGB.match(ln)
        if not m:
            continue
        it, rest = int(m.group(1)), m.group(2)
        parts = LGB_PART.findall(rest) or XGB_PART.findall(rest)
        for ds, metric, val in parts:
            series.setdefault((ds, metric), {})[it] = float(val)
    return series


def classify(ds):
    if re.search(r"train|learn", ds, re.I):
        return "train"
    return "valid"


def analyse(series, higher_override, train_name=None):
    if train_name:
        series = {(("train" if d == train_name else d), m): v for (d, m), v in series.items()}
    elif not any(classify(d) == "train" for d, _ in series):
        # eval_set=[(X_train, y_train), (X_valid, y_valid)] logs the training data as validation_0 / valid_0
        names = sorted({d for d, _ in series if re.search(r"_0$", d)})
        for d0 in names:
            d1 = d0[:-1] + "1"
            for (d, m), v in list(series.items()):
                if d == d0 and (d1, m) in series:
                    hb = higher_override if higher_override is not None else bool(HIGHER.search(m))
                    a, b = sum(v.values()) / len(v), sum(series[(d1, m)].values()) / len(series[(d1, m)])
                    if (a > b) if hb else (a < b):
                        series = {(("train" if dd == d0 else dd), mm): vv for (dd, mm), vv in series.items()}
                        break
    valid = {k: v for k, v in series.items() if classify(k[0]) == "valid"}
    if not valid:
        raise ValueError("no validation series found (need a validation set in the log)")
    key = sorted(valid, key=lambda k: (k[0] not in ("valid_1", "validation_1", "eval", "valid", "test"), k))[0]
    ds, metric = key
    curve = dict(sorted(valid[key].items()))
    higher = higher_override if higher_override is not None else bool(HIGHER.search(metric))
    its = list(curve)
    vals = [curve[i] for i in its]
    best_idx = max(range(len(vals)), key=lambda i: vals[i]) if higher else min(range(len(vals)), key=lambda i: vals[i])
    best_it, best_val = its[best_idx], vals[best_idx]
    last_it, last_val = its[-1], vals[-1]
    train = next((v for (d, m), v in series.items() if classify(d) == "train" and m == metric), None)
    gap = None
    if train and best_it in train:
        gap = (train[best_it] - best_val) if higher else (best_val - train[best_it])
    tail = vals[-max(3, len(vals) // 10):]
    improving = (tail[-1] > tail[0]) if higher else (tail[-1] < tail[0])
    after = len(its) - 1 - best_idx
    span = (max(vals) - min(vals)) or 1e-12
    degradation = ((best_val - last_val) if higher else (last_val - best_val)) / span
    advice = []
    if best_idx == len(its) - 1 or (improving and len(its) >= 10 and after < max(5, len(its) // 20)):
        advice.append("still improving at the last round: raise n_estimators (or the learning rate); you have not "
                      "reached the best model yet")
    if best_it < 100 and len(its) > best_it * 2:
        advice.append(f"best at iteration {best_it}: the learning rate is high for this data; lower it (x0.3-0.5) "
                      "for a smoother optimum and usually a slightly better score")
    if degradation > 0.2 and after > 0:
        advice.append(f"validation got {degradation:.0%} of its range worse after the best round: early stopping is "
                      f"essential; patience ~{max(20, min(300, after // 3))} rounds")
    if gap is not None:
        rel = gap / (abs(best_val) or 1)
        if rel > 0.3:
            advice.append(f"large train/valid gap at the best round ({gap:.4g}, {rel:.0%} of the valid value): "
                          "increase min_child_samples/min_child_weight, lower num_leaves/max_depth, raise "
                          "reg_lambda, use subsample/colsample < 1")
        elif rel < 0.02 and not improving:
            advice.append("train and valid are close and flat: the model may be under-fitting; allow more capacity "
                          "(num_leaves / max_depth) or add features")
    if not advice:
        advice.append("curve looks healthy: best round well inside the run, moderate gap; keep early stopping")
    return {"dataset": ds, "metric": metric, "higher_is_better": higher, "iterations": len(its),
            "best_iteration": best_it, "best_value": best_val, "last_iteration": last_it, "last_value": last_val,
            "rounds_after_best": after, "train_valid_gap_at_best": gap, "still_improving": improving,
            "degradation_after_best": round(degradation, 4), "advice": advice}


def main():
    ap = argparse.ArgumentParser(description="Interpret a GBM training log / history.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", help="log or CSV file, or - for stdin")
    ap.add_argument("--higher-better", choices=["yes", "no"], help="override metric direction")
    ap.add_argument("--train-name", help="dataset name that holds the training curve (e.g. validation_0)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.log == "-" else open(a.log, encoding="utf-8").read()
        series = parse(text)
        if not series:
            raise ValueError("no LightGBM / XGBoost / CatBoost / CSV training lines recognised")
        hb = None if a.higher_better is None else a.higher_better == "yes"
        r = analyse(series, hb, a.train_name)
    except (OSError, ValueError, StopIteration, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(r, indent=2))
        return 0
    gap = "-" if r["train_valid_gap_at_best"] is None else f"{r['train_valid_gap_at_best']:.4g}"
    print(f"{r['dataset']} {r['metric']} ({'higher' if r['higher_is_better'] else 'lower'} is better), "
          f"{r['iterations']} logged rounds")
    print(f"best {r['best_value']:.5g} at iteration {r['best_iteration']}; last {r['last_value']:.5g} at "
          f"{r['last_iteration']} ({r['rounds_after_best']} logged rounds after best); train/valid gap at best {gap}")
    for adv in r["advice"]:
        print(f"- {adv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
