#!/usr/bin/env python3
"""Evaluate uplift scores on randomised data: Qini, AUUC, uplift by decile, and the value of targeting.

Input: CSV with treatment (1/0), a binary or numeric outcome and one or more uplift score columns
(higher = larger expected effect of treatment). The data must come from a randomised test (or have known
propensities, --propensity-col); uplift cannot be evaluated on observational data without them.

Metrics per score column:
  Qini coefficient   area between the Qini curve and the random line, divided by the same area of the
                     perfect curve (matches scikit-uplift qini_auc_score, negative_effect=True); 1 = perfect,
                     0 = random, < 0 = worse than random
  AUUC (normalised)  the same for the uplift curve (matches scikit-uplift uplift_auc_score exactly)
  deciles            per score decile: treated and control outcome rates, uplift with a 95% CI; a good model
                     has falling uplift from top to bottom decile; significantly negative bottom deciles are
                     "sleeping dogs" (treatment hurts them)
  targeting          the expected outcome when treating only the top q% (--target-fracs) vs treating
                     everyone or no-one, estimated with inverse propensity weighting on the randomised data,
                     plus the best fraction; with --cost-per-treatment and --value-per-outcome, the profit
                     of each policy

Usage:
    python uplift_eval.py uplift.csv --treatment-col treatment --outcome-col converted --scores uplift_score
    python uplift_eval.py preds.csv --scores t_learner x_learner --target-fracs 0.1 0.2 0.3 0.5 --cost-per-treatment 1 --value-per-outcome 20

Exit codes: 0 evaluated, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _uplift_io import num  # noqa: E402


def curves(y, t, s):
    """Qini and uplift curve points at distinct score thresholds (scikit-uplift conventions)."""
    order = sorted(range(len(s)), key=lambda i: -s[i])
    xs, qini, upl = [0], [0.0], [0.0]
    nt = nc = yt = yc = 0.0
    for k, i in enumerate(order):
        nt += t[i]
        nc += 1 - t[i]
        yt += y[i] * t[i]
        yc += y[i] * (1 - t[i])
        last = k == len(order) - 1
        if last or s[order[k + 1]] != s[i]:
            n = k + 1
            xs.append(n)
            qini.append(yt - (yc * nt / nc if nc else 0.0))     # no controls yet: all treated responders count
            rt = yt / nt if nt else 0.0
            rc = yc / nc if nc else 0.0
            upl.append((rt - rc) * n)
    return xs, qini, upl


def auc(x, y):
    return sum((x[i + 1] - x[i]) * (y[i + 1] + y[i]) / 2 for i in range(len(x) - 1))


def normalised(y, t, s, kind):
    x, q, u = curves(y, t, s)
    actual = q if kind == "qini" else u
    n = len(y)
    base = auc([x[0], x[-1]], [0.0, actual[-1]])
    if kind == "qini":
        perfect_score = [yi * ti - yi * (1 - ti) for yi, ti in zip(y, t)]
        px, pq, _ = curves(y, t, perfect_score)
        perfect = auc(px, pq)
    else:
        cr = sum(1 for yi, ti in zip(y, t) if yi == 1 and ti == 0)
        tn = sum(1 for yi, ti in zip(y, t) if yi == 0 and ti == 1)
        summand = y if cr > tn else t
        perfect_score = [2 * (yi == ti) + sm for yi, ti, sm in zip(y, t, summand)]
        px, _, pu = curves(y, t, perfect_score)
        perfect = auc(px, pu)
    denom = perfect - base
    return (auc(x, actual) - base) / denom if denom else None


def deciles(y, t, s, k=10):
    order = sorted(range(len(s)), key=lambda i: -s[i])
    out = []
    n = len(order)
    for d in range(k):
        idx = order[d * n // k:(d + 1) * n // k]
        yt = [y[i] for i in idx if t[i] == 1]
        yc = [y[i] for i in idx if t[i] == 0]
        if len(yt) < 2 or len(yc) < 2:
            out.append(None)
            continue
        mt, mc = sum(yt) / len(yt), sum(yc) / len(yc)
        vt = sum((v - mt) ** 2 for v in yt) / (len(yt) - 1)
        vc = sum((v - mc) ** 2 for v in yc) / (len(yc) - 1)
        se = math.sqrt(vt / len(yt) + vc / len(yc))
        out.append({"decile": d + 1, "n": len(idx), "treated_rate": mt, "control_rate": mc, "uplift": mt - mc,
                    "ci": (mt - mc - 1.959964 * se, mt - mc + 1.959964 * se), "mean_score": sum(s[i] for i in idx) / len(idx)})
    return out


def policy_value(y, t, s, p, frac):
    """IPW estimate of the mean outcome when treating exactly the top `frac` by score."""
    n = len(y)
    k = int(round(frac * n))
    order = sorted(range(n), key=lambda i: -s[i])
    treat = [0] * n
    for i in order[:k]:
        treat[i] = 1
    v = 0.0
    for i in range(n):
        if treat[i] == t[i]:
            v += y[i] / (p[i] if t[i] else 1 - p[i])
    return v / n


def main():
    ap = argparse.ArgumentParser(description="Evaluate uplift scores.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--treatment-col", default="treatment")
    ap.add_argument("--outcome-col", default="converted")
    ap.add_argument("--scores", nargs="+", required=True)
    ap.add_argument("--propensity-col", help="treatment probability per row (default: the observed treated share)")
    ap.add_argument("--target-fracs", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.5, 0.7])
    ap.add_argument("--cost-per-treatment", type=float)
    ap.add_argument("--value-per-outcome", type=float)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError("no rows")
        need = [a.treatment_col, a.outcome_col] + a.scores + ([a.propensity_col] if a.propensity_col else [])
        miss = [c for c in need if c not in rows[0]]
        if miss:
            raise ValueError(f"columns not found: {', '.join(miss)}")
        rows = [r for r in rows if all(num(r[c]) is not None for c in need)]
        t = [int(num(r[a.treatment_col])) for r in rows]
        if set(t) - {0, 1}:
            raise ValueError("treatment must be 0/1")
        y = [num(r[a.outcome_col]) for r in rows]
        share = sum(t) / len(t)
        p = [num(r[a.propensity_col]) for r in rows] if a.propensity_col else [share] * len(t)
        if not 0 < share < 1:
            raise ValueError("need both treated and control rows")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    binary = set(y) <= {0.0, 1.0}
    res = {"n": len(y), "treated_share": share, "models": {}}
    all_t = policy_value(y, t, [1.0] * len(y), p, 1.0)
    none = policy_value(y, t, [1.0] * len(y), p, 0.0)
    res["treat_all"], res["treat_none"] = all_t, none
    for c in a.scores:
        s = [num(r[c]) for r in rows]
        m = {"qini": normalised(y, t, s, "qini") if binary else None,
             "auuc": normalised(y, t, s, "uplift") if binary else None,
             "deciles": deciles(y, t, s),
             "policies": [{"frac": f, "value": policy_value(y, t, s, p, f)} for f in a.target_fracs]}
        if a.cost_per_treatment is not None and a.value_per_outcome is not None:
            for pol in m["policies"] + [{"frac": 1.0, "value": all_t}, {"frac": 0.0, "value": none}]:
                pol["profit_per_person"] = pol["value"] * a.value_per_outcome - pol["frac"] * a.cost_per_treatment
        res["models"][c] = m
    if a.json:
        print(json.dumps(res, indent=2))
        return 0
    print(f"n {len(y)}   treated share {share:.1%}   outcome mean if everyone treated {all_t:.4f}, "
          f"if nobody treated {none:.4f} (IPW)")
    for c, m in res["models"].items():
        print(f"\n[{c}]" + (f"   Qini coefficient {m['qini']:.4f}   AUUC {m['auuc']:.4f}" if m["qini"] is not None else
                           "   (Qini/AUUC need a binary outcome)"))
        print(f"  {'decile':>6} {'n':>5} {'treated':>8} {'control':>8} {'uplift':>8}  95% CI")
        for d in m["deciles"]:
            if d is None:
                continue
            mark = "  sleeping dogs" if d["ci"][1] < 0 else ("  *" if d["ci"][0] > 0 else "")
            print(f"  {d['decile']:>6} {d['n']:>5} {d['treated_rate']:>8.4f} {d['control_rate']:>8.4f} "
                  f"{d['uplift']:>+8.4f}  [{d['ci'][0]:+.4f}, {d['ci'][1]:+.4f}]{mark}")
        profit = "profit_per_person" in m["policies"][0]
        best = max(m["policies"], key=lambda q: q["profit_per_person"] if profit else q["value"])
        print("  targeting (IPW): " + ", ".join(f"top {q['frac']:.0%} -> {q['value']:.4f}"
                                                + (f" (profit {q['profit_per_person']:+.3f})" if profit else "")
                                                for q in m["policies"]))
        if profit:
            print(f"  treat all: profit {all_t * a.value_per_outcome - a.cost_per_treatment:+.3f}   "
                  f"treat none: profit {none * a.value_per_outcome:+.3f}")
        print(f"  best: treat the top {best['frac']:.0%}" + (f" (profit {best['profit_per_person']:+.3f} per person)"
                                                             if profit else f" (outcome {best['value']:.4f})"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
