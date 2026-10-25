#!/usr/bin/env python3
"""Analyse hyperparameter search results: what mattered, whether the range was right, and what to pick.

Reads scikit-learn `cv_results_` exported to CSV (param_* columns, mean_test_score, std_test_score)
or an Optuna `study.trials_dataframe()` CSV (params_* columns, value, state). Reports:
  best        top configurations with mean ± std
  boundary    numeric parameters whose best values sit in the lowest/highest 15% of the searched
              range: the optimum may lie outside - widen the range
  sensitivity score range across quartile bins of each numeric parameter (catches peaked effects)
              plus Spearman for direction (log scale when values span > 1 decade); mean score per
              level for categorical parameters
  1-SE set    configurations within one standard error of the best (sklearn: std / sqrt(folds));
              among them the "simplest" by --simpler rules (e.g. smaller max_leaf_nodes, larger C)
  progress    best-so-far curve by trial order (Optuna number or row order): flat for the last half
              means more trials are unlikely to help
Use --lower-better for losses (Optuna minimise studies are detected from negative improvements
only when you pass it).

Usage:
    python analyze_search.py cv_results.csv --folds 5
    python analyze_search.py trials.csv --simpler "max_leaf_nodes:low" "min_samples_leaf:high"
    python analyze_search.py trials.csv --lower-better --json

Exit codes: 0 analysed, 2 usage or read error.
"""

import argparse
import csv
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


def spearman(a, b):
    def rk(v):
        o = sorted(range(len(v)), key=v.__getitem__)
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    ra, rb = rk(a), rk(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((x - mb) ** 2 for x in rb))
    return 0.0 if not va or not vb else sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (va * vb)


def main():
    ap = argparse.ArgumentParser(description="Analyse hyperparameter search results.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--folds", type=int, default=5, help="CV folds behind std_test_score (for the standard error)")
    ap.add_argument("--lower-better", action="store_true")
    ap.add_argument("--simpler", nargs="*", default=[], help="param:low|high - which direction is simpler")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rd = csv.DictReader(fh)
            cols = rd.fieldnames or []
            rows = list(rd)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if "mean_test_score" in cols:
        fmt, pcols, score_col, std_col = "sklearn", [c for c in cols if c.startswith("param_")], "mean_test_score", "std_test_score"
    elif "value" in cols:
        fmt, pcols, score_col, std_col = "optuna", [c for c in cols if c.startswith("params_")], "value", None
        if "state" in cols:
            rows = [r for r in rows if r["state"] == "COMPLETE"]
        if "number" in cols:
            rows.sort(key=lambda r: int(r["number"]))
    else:
        print("error: expected scikit-learn cv_results (mean_test_score) or Optuna trials (value)", file=sys.stderr)
        return 2
    rows = [r for r in rows if num(r[score_col]) is not None]
    if len(rows) < 3 or not pcols:
        print("error: need >= 3 completed trials with parameter columns", file=sys.stderr)
        return 2
    sign = -1 if a.lower_better else 1
    scores = [num(r[score_col]) for r in rows]
    best_i = max(range(len(rows)), key=lambda i: sign * scores[i])
    best = scores[best_i]
    name = lambda c: c.split("_", 1)[1] if c.startswith(("param_", "params_")) else c
    params = {}
    for c in pcols:
        vals = [r[c] for r in rows]
        nums = [num(v) for v in vals]
        params[c] = {"numeric": all(x is not None for x in nums) and len(set(nums)) > 2, "values": vals, "nums": nums}
    report = {"format": fmt, "trials": len(rows), "best_score": best,
              "best_params": {name(c): rows[best_i][c] for c in pcols}, "boundary": [], "sensitivity": [], "levels": {}}
    order = sorted(range(len(rows)), key=lambda i: -sign * scores[i])
    report["top"] = [{"score": scores[i], "std": num(rows[i][std_col]) if std_col else None,
                      "params": {name(c): rows[i][c] for c in pcols}} for i in order[:a.top]]
    for c, p in params.items():
        if p["numeric"]:
            xs = p["nums"]
            lo, hi = min(xs), max(xs)
            logscale = lo > 0 and hi / lo > 10
            tx = [math.log10(x) for x in xs] if logscale else xs
            tlo, thi = min(tx), max(tx)
            bx = tx[best_i]
            pos = (bx - tlo) / (thi - tlo) if thi > tlo else 0.5
            if pos <= 0.15 or pos >= 0.85:
                report["boundary"].append({"param": name(c), "best": xs[best_i], "range": [lo, hi],
                                           "side": "low" if pos <= 0.15 else "high"})
            # binned effect: catches non-monotonic (peaked) effects that a rank correlation misses
            idx = sorted(range(len(tx)), key=tx.__getitem__)
            q = max(1, len(idx) // 4)
            bins = [idx[k:k + q] for k in range(0, len(idx), q)]
            means = [sum(scores[i] for i in b) / len(b) for b in bins if b]
            report["sensitivity"].append({"param": name(c), "spearman": round(spearman(tx, [sign * s for s in scores]), 3),
                                          "effect_range": round(max(means) - min(means), 4),
                                          # peaked only if the best middle bin clearly beats both ends
                                          "peaked": len(means) >= 3 and max(means[1:-1]) - max(means[0], means[-1])
                                          > 0.5 * (max(means) - min(means)),
                                          "scale": "log" if logscale else "linear"})
        else:
            agg = defaultdict(list)
            for v, s in zip(p["values"], scores):
                agg[v].append(s)
            report["levels"][name(c)] = {k: round(sum(v) / len(v), 4) for k, v in agg.items()}
    report["sensitivity"].sort(key=lambda d: -d["effect_range"])
    if std_col:
        se = (num(rows[best_i][std_col]) or 0) / math.sqrt(a.folds)
        within = [i for i in range(len(rows)) if sign * (best - scores[i]) <= se]
        rules = [s.split(":") for s in a.simpler if ":" in s]
        def simplicity(i):
            key = []
            for prm, direction in rules:
                c = next((pc for pc in pcols if name(pc) == prm), None)
                v = num(rows[i][c]) if c else None
                key.append((v if direction == "low" else -v) if v is not None else 0)
            return key
        pick = min(within, key=simplicity) if rules else best_i
        report["one_se"] = {"se": se, "count": len(within), "pick": {name(c): rows[pick][c] for c in pcols},
                            "pick_score": scores[pick]}
    running, curve = None, []
    for s in scores:
        running = s if running is None or sign * s > sign * running else running
        curve.append(running)
    half = len(curve) // 2
    report["progress"] = {"best_at_half": curve[half - 1] if half else curve[-1], "best_at_end": curve[-1],
                          "improved_in_second_half": sign * (curve[-1] - curve[half - 1]) > 1e-9 if half else True}
    if a.json:
        print(json.dumps(report, indent=2, default=str))
        return 0
    print(f"{fmt} search: {len(rows)} trials; best {best:.4f} with " +
          ", ".join(f"{k}={v}" for k, v in report["best_params"].items()))
    print("\ntop configurations:")
    for t in report["top"]:
        sd = f" ± {t['std']:.4f}" if t["std"] is not None else ""
        print(f"  {t['score']:.4f}{sd}  " + ", ".join(f"{k}={v}" for k, v in t["params"].items()))
    print("\nsensitivity (score range across quartile bins of the parameter; Spearman for direction):")
    for s in report["sensitivity"]:
        shape = "peaked: optimum inside the range" if s["peaked"] else ("higher is better" if s["spearman"] > 0.2 else
                                                                         "lower is better" if s["spearman"] < -0.2 else "")
        print(f"  {s['param']:<22} effect {s['effect_range']:.4f}  spearman {s['spearman']:+.3f}  ({s['scale']} scale)"
              + (f"  {shape}" if shape else ""))
    for p, lv in report["levels"].items():
        print(f"  {p:<22} " + ", ".join(f"{k}: {v}" for k, v in lv.items()))
    for b in report["boundary"]:
        print(f"BOUNDARY: best {b['param']}={b['best']:g} sits at the {b['side']} end of [{b['range'][0]:g}, "
              f"{b['range'][1]:g}] - extend the range on that side")
    if "one_se" in report:
        o = report["one_se"]
        print(f"\n{o['count']} configuration(s) within 1 SE ({o['se']:.4f}) of the best; pick: " +
              ", ".join(f"{k}={v}" for k, v in o["pick"].items()) + f" (score {o['pick_score']:.4f})")
    pr = report["progress"]
    print(f"best after half the trials {pr['best_at_half']:.4f}, at the end {pr['best_at_end']:.4f}" +
          ("" if pr["improved_in_second_half"] else " - no gain in the second half: more trials will not help much"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
