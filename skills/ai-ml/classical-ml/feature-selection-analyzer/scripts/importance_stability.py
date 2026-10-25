#!/usr/bin/env python3
"""Check whether a feature selection is stable across CV folds, bootstraps or seeds.

Input: a long CSV with one row per (run, feature): columns `run`, `feature`, `importance`
(names configurable). A run is one fold / bootstrap / seed; importance is anything where larger
means more important (gain, |SHAP| mean, permutation drop, |coefficient|, 1/0 selected flag).

Reports per feature: mean importance, mean rank, rank standard deviation, and the share of runs in
which it is in the top K (selection frequency, as in stability selection). Then:
  stable core   features selected in >= --stable (default 0.8) of runs
  unstable      selected in 0.2 .. 0.8 of runs: often members of correlated groups that swap
  never         selected in < 0.2 of runs
and the mean pairwise Spearman correlation of the importance vectors between runs (1 = identical
ordering). Low agreement with a high CV score usually means redundant features: the model is
stable, the attribution is not.

Usage:
    python importance_stability.py importances.csv --top-k 5
    python importance_stability.py imp.csv --run-col fold --feature-col name --importance-col gain --json

Exit codes: 0 stable enough (mean Spearman >= --min-agreement, default 0.6), 1 unstable, 2 usage error.
"""

import argparse
import csv
import json
import math
import sys
from collections import defaultdict


def ranks_desc(values):
    order = sorted(range(len(values)), key=lambda i: -values[i])
    r = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks_desc(a), ranks_desc(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((x - mb) ** 2 for x in rb))
    return 1.0 if not va or not vb else sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (va * vb)


def main():
    ap = argparse.ArgumentParser(description="Feature-importance stability across runs.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--run-col", default="run")
    ap.add_argument("--feature-col", default="feature")
    ap.add_argument("--importance-col", default="importance")
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--stable", type=float, default=0.8)
    ap.add_argument("--min-agreement", type=float, default=0.6)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
            missing = [c for c in (a.run_col, a.feature_col, a.importance_col) if c not in cols]
            if missing:
                raise ValueError(f"missing column(s) {missing}; found {cols}")
            data = defaultdict(dict)
            for r in reader:
                data[r[a.run_col]][r[a.feature_col]] = abs(float(r[a.importance_col]))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    runs = sorted(data)
    feats = sorted({f for d in data.values() for f in d})
    if len(runs) < 2 or not feats:
        print("error: need at least 2 runs", file=sys.stderr)
        return 2
    k = min(a.top_k, len(feats))
    mat = [[data[r].get(f, 0.0) for f in feats] for r in runs]
    rank_mat = [ranks_desc(v) for v in mat]
    stats = []
    for j, f in enumerate(feats):
        imp = [m[j] for m in mat]
        rk = [rm[j] for rm in rank_mat]
        mr = sum(rk) / len(rk)
        stats.append({"feature": f, "mean_importance": sum(imp) / len(imp), "mean_rank": mr,
                      "rank_std": math.sqrt(sum((x - mr) ** 2 for x in rk) / len(rk)),
                      "selected_share": sum(1 for x in rk if x <= k) / len(rk)})
    stats.sort(key=lambda s: s["mean_rank"])
    for s in stats:
        s["group"] = ("stable" if s["selected_share"] >= a.stable else
                      "unstable" if s["selected_share"] >= 0.2 else "never")
    pair = [spearman(mat[i], mat[j]) for i in range(len(runs)) for j in range(i + 1, len(runs))]
    agreement = sum(pair) / len(pair)
    ok = agreement >= a.min_agreement
    if a.json:
        print(json.dumps({"runs": len(runs), "top_k": k, "mean_spearman": round(agreement, 4), "stable": ok,
                          "features": stats}, indent=2))
        return 0 if ok else 1
    print(f"{len(runs)} runs, {len(feats)} features, top-{k} selection; mean pairwise Spearman of importances "
          f"{agreement:.3f} ({'stable' if ok else 'UNSTABLE'})")
    print(f"{'feature':<24} {'mean imp':>10} {'mean rank':>9} {'rank sd':>8} {'in top-k':>8}  group")
    for s in stats:
        print(f"{s['feature']:<24} {s['mean_importance']:>10.4g} {s['mean_rank']:>9.1f} {s['rank_std']:>8.2f} "
              f"{s['selected_share']:>8.0%}  {s['group']}")
    core = [s["feature"] for s in stats if s["group"] == "stable"]
    shaky = [s["feature"] for s in stats if s["group"] == "unstable"]
    print(f"\nstable core ({len(core)}): {', '.join(core) or '-'}")
    if shaky:
        print(f"unstable ({len(shaky)}): {', '.join(shaky)} - check correlations among them; keep one per group or "
              "report the group, not the individual feature")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
