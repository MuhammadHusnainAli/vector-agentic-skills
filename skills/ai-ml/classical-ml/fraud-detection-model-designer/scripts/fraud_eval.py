#!/usr/bin/env python3
"""Evaluate a fraud score the way fraud operations use it: alert budgets, money saved, and cost-optimal thresholds.

Input: CSV with the fraud label (1/0), the model score (higher = riskier), the transaction amount and,
optionally, a timestamp.

Reports:
  overview        transactions, frauds, fraud rate, fraud amount and its share of volume
  ranking         ROC AUC, average precision (PR AUC; the random baseline equals the fraud rate)
  alert rates     for the top 0.5% / 1% / 2% / 5% of scores (--alert-rates): threshold, precision, recall
                  (count), value detection rate (share of fraud AMOUNT caught), false-positive rate and
                  alerts per day
  recall at FPR   recall and value detection rate at FPR 0.1% and 1%
  cost            expected cost per threshold with
                    missed fraud     = amount x --loss-rate (default 1.0: the whole amount is lost)
                    each alert       = --review-cost (analyst time, default 3.0)
                    each false alert = --friction-cost extra (customer friction / lost sales, default 2.0)
                  and the threshold that minimises it, compared with "no model" (lose all fraud) and with
                  reviewing everything
  capacity        with --alerts-per-day N (needs a timestamp), the best threshold that stays within it
  by week         average precision and fraud rate per ISO week (drift and label maturity check)

Usage:
    python fraud_eval.py transactions.csv --label-col is_fraud --score-col score --amount-col amount
    python fraud_eval.py scored.csv --label-col fraud --score-col p --amount-col amt --time-col ts --alerts-per-day 20
    python fraud_eval.py scored.csv --review-cost 5 --friction-cost 10 --loss-rate 0.8 --json

Exit codes: 0 evaluated, 2 usage or read error.
"""

import argparse
import csv
import datetime as dt
import json
import math
import sys
from collections import defaultdict


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def roc_auc(y, s):
    pairs = sorted(zip(s, y))
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return None
    rank_sum, i = 0.0, 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        rank_sum += ((i + j) / 2 + 1) * sum(lab for _, lab in pairs[i:j + 1])
        i = j + 1
    return (rank_sum - pos * (pos + 1) / 2) / (pos * neg)


def avg_precision(y, s):
    pos = sum(y)
    if not pos:
        return None
    order = sorted(range(len(s)), key=lambda i: -s[i])
    tp = fp = 0
    ap, prev, k = 0.0, 0.0, 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and s[order[j + 1]] == s[order[k]]:
            j += 1
        for i in order[k:j + 1]:
            tp += y[i]
            fp += 1 - y[i]
        rec = tp / pos
        ap += (rec - prev) * tp / (tp + fp)
        prev = rec
        k = j + 1
    return ap


def at_threshold(y, s, amt, thr):
    tp = fp = 0
    caught = 0.0
    for yi, si, ai in zip(y, s, amt):
        if si >= thr:
            if yi:
                tp += 1
                caught += ai
            else:
                fp += 1
    pos = sum(y)
    neg = len(y) - pos
    fraud_amt = sum(a for a, yi in zip(amt, y) if yi)
    return {"threshold": thr, "alerts": tp + fp, "tp": tp, "fp": fp, "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / pos if pos else None, "value_detection": caught / fraud_amt if fraud_amt else None,
            "fpr": fp / neg if neg else None, "caught_amount": caught}


def cost(m, y, amt, a):
    fraud_amt = sum(x for x, yi in zip(amt, y) if yi)
    missed = (fraud_amt - m["caught_amount"]) * a.loss_rate
    return missed + m["alerts"] * a.review_cost + m["fp"] * a.friction_cost


def main():
    ap = argparse.ArgumentParser(description="Evaluate a fraud score for operations.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--label-col", default="is_fraud")
    ap.add_argument("--score-col", default="score")
    ap.add_argument("--amount-col", default="amount")
    ap.add_argument("--time-col", default="timestamp")
    ap.add_argument("--alert-rates", type=float, nargs="+", default=[0.005, 0.01, 0.02, 0.05])
    ap.add_argument("--loss-rate", type=float, default=1.0)
    ap.add_argument("--review-cost", type=float, default=3.0)
    ap.add_argument("--friction-cost", type=float, default=2.0)
    ap.add_argument("--alerts-per-day", type=float)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        for c in (a.label_col, a.score_col, a.amount_col):
            if c not in rows[0]:
                raise ValueError(f"column {c!r} not found (have: {', '.join(rows[0])})")
        data = []
        for r in rows:
            yv, sv, av = num(r[a.label_col]), num(r[a.score_col]), num(r[a.amount_col])
            if None in (yv, sv, av):
                continue
            if yv not in (0, 1):
                raise ValueError("labels must be 0/1")
            t = None
            if a.time_col in r and r[a.time_col]:
                try:
                    t = dt.datetime.fromisoformat(r[a.time_col].replace("Z", "+00:00"))
                except ValueError:
                    t = None
            data.append((int(yv), sv, av, t))
        if sum(d[0] for d in data) == 0:
            raise ValueError("no fraud labels in the data")
        if a.alerts_per_day and not all(d[3] for d in data):
            raise ValueError("--alerts-per-day needs a parseable --time-col")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    y = [d[0] for d in data]
    s = [d[1] for d in data]
    amt = [d[2] for d in data]
    times = [d[3] for d in data]
    n, pos = len(y), sum(y)
    days = None
    if all(times):
        span = (max(times) - min(times)).total_seconds() / 86400
        days = max(1.0, span)
    fraud_amt = sum(x for x, yi in zip(amt, y) if yi)
    res = {"n": n, "frauds": pos, "fraud_rate": pos / n, "fraud_amount": fraud_amt, "fraud_amount_share": fraud_amt / sum(amt),
           "roc_auc": roc_auc(y, s), "average_precision": avg_precision(y, s), "days": days}
    srt = sorted(s, reverse=True)
    res["alert_rates"] = []
    for rate in a.alert_rates:
        thr = srt[max(0, min(n - 1, int(math.ceil(rate * n)) - 1))]
        m = at_threshold(y, s, amt, thr)
        m["rate"] = rate
        m["alerts_per_day"] = m["alerts"] / days if days else None
        res["alert_rates"].append(m)
    negs = sorted((si for si, yi in zip(s, y) if not yi), reverse=True)
    res["at_fpr"] = []
    for fpr in (0.001, 0.01):
        k = int(fpr * len(negs))
        thr = negs[k] if k < len(negs) else negs[-1]
        thr = math.nextafter(thr, math.inf)                 # strictly above the k-th negative score
        m = at_threshold(y, s, amt, thr)
        m["target_fpr"] = fpr
        res["at_fpr"].append(m)
    cands = sorted(set(s), reverse=True)
    best, best_cap = None, None
    for thr in cands:
        m = at_threshold(y, s, amt, thr)
        c = cost(m, y, amt, a)
        if best is None or c < best[0]:
            best = (c, m)
        if a.alerts_per_day and days and m["alerts"] / days <= a.alerts_per_day:
            if best_cap is None or c < best_cap[0]:
                best_cap = (c, m)
    no_model = fraud_amt * a.loss_rate
    review_all = n * a.review_cost + (n - pos) * a.friction_cost
    res["cost"] = {"optimal_threshold": best[1]["threshold"], "optimal_cost": best[0], "at_optimum": best[1],
                   "no_model_cost": no_model, "review_all_cost": review_all, "savings_vs_no_model": no_model - best[0]}
    if best_cap:
        res["capacity"] = {"alerts_per_day": a.alerts_per_day, "threshold": best_cap[1]["threshold"],
                           "cost": best_cap[0], "metrics": best_cap[1]}
    if all(times):
        wk = defaultdict(lambda: ([], []))
        for yi, si, _, t in data:
            key = f"{t.isocalendar()[0]}-W{t.isocalendar()[1]:02d}"
            wk[key][0].append(yi)
            wk[key][1].append(si)
        res["by_week"] = {k: {"n": len(v[0]), "fraud_rate": sum(v[0]) / len(v[0]), "ap": avg_precision(v[0], v[1])}
                          for k, v in sorted(wk.items())}
    if a.json:
        print(json.dumps(res, indent=2, default=str))
        return 0
    print(f"transactions {n}   frauds {pos} ({pos / n:.2%})   fraud amount {fraud_amt:,.2f} "
          f"({res['fraud_amount_share']:.1%} of volume)" + (f"   period {days:.1f} days" if days else ""))
    print(f"ROC AUC {res['roc_auc']:.4f}   average precision {res['average_precision']:.4f} "
          f"(random = {pos / n:.4f})")
    print("")
    print(f"{'alert rate':>10} {'threshold':>10} {'alerts':>7} {'/day':>6} {'precision':>10} {'recall':>7} "
          f"{'value det.':>10} {'FPR':>7}")
    for m in res["alert_rates"]:
        pd_ = f"{m['alerts_per_day']:.1f}" if m["alerts_per_day"] is not None else ""
        print(f"{m['rate']:>10.1%} {m['threshold']:>10.4g} {m['alerts']:>7} {pd_:>6} {m['precision'] or 0:>10.1%} "
              f"{m['recall']:>7.1%} {m['value_detection']:>10.1%} {m['fpr']:>7.2%}")
    for m in res["at_fpr"]:
        print(f"at FPR {m['target_fpr']:.1%}: recall {m['recall']:.1%}, value detection {m['value_detection']:.1%} "
              f"(threshold {m['threshold']:.4g}, {m['alerts']} alerts)")
    c = res["cost"]
    o = c["at_optimum"]
    print("")
    print(f"cost model: missed fraud x {a.loss_rate:g}, {a.review_cost:g} per alert, +{a.friction_cost:g} per false alert")
    print(f"cost-optimal threshold {c['optimal_threshold']:.4g}: {o['alerts']} alerts, precision {o['precision'] or 0:.1%}, "
          f"value detection {o['value_detection']:.1%}; cost {c['optimal_cost']:,.2f} vs no model {c['no_model_cost']:,.2f} "
          f"(saves {c['savings_vs_no_model']:,.2f}) vs review all {c['review_all_cost']:,.2f}")
    if "capacity" in res:
        k = res["capacity"]
        mm = k["metrics"]
        print(f"within {k['alerts_per_day']:g} alerts/day: threshold {k['threshold']:.4g}, recall {mm['recall']:.1%}, "
              f"value detection {mm['value_detection']:.1%}, cost {k['cost']:,.2f}")
    if "by_week" in res:
        print("")
        print("by week: " + "; ".join(f"{k} n={v['n']} fraud {v['fraud_rate']:.1%} AP "
                                      + (f"{v['ap']:.3f}" if v["ap"] is not None else "n/a")
                                      for k, v in res["by_week"].items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
