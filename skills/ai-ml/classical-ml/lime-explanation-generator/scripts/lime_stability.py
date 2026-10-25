#!/usr/bin/env python3
"""Check whether a LIME explanation is stable across repeated runs (different sampling seeds).

LIME fits a weighted linear surrogate on random perturbations around one row; a different seed gives
different perturbations and can give a different explanation. Run LIME several times for the same row
(gen_lime_script.py does this) and pass the long CSV:
    run,feature,weight[,score,local_pred,model_pred]
Feature names are LIME's labels (e.g. "support_calls > 3", "plan=basic"); features missing from a run count
as weight 0 for that run.

Reports per feature: mean weight, std, coefficient of variation (std / |mean|), sign consistency (share of
runs agreeing with the majority sign among non-zero weights) and how often it appears in the top --top-k.
Then:
  stable       sign consistency >= 0.9 and CV <= 0.5 and in the top-k in >= 80% of runs
  noisy        sign consistent but CV > 0.5 or unstable top-k membership: the size is not reliable
  unstable     sign consistency < 0.9: do not report this feature's direction
  negligible   mean |weight| < 10% of the largest feature's: ignored for the verdict
  top-k Jaccard  mean pairwise overlap of the top-k sets between runs, ignoring negligible features
               (1 = always the same features)
  fidelity     if a `score` column (the surrogate's weighted R^2) is present: its mean; < 0.5 means the linear
               surrogate fits the model poorly around this row
  local gap    if local_pred and model_pred are present: mean |surrogate prediction - model prediction|
With --compare (CSV: feature,value, e.g. SHAP values for the same row; names matched by prefix), the sign
agreement with that method is reported for features both explain.

Usage:
    python lime_stability.py lime_runs.csv
    python lime_stability.py lime_runs.csv --top-k 3 --compare shap_row.csv --json

Exit codes: 0 stable (top-k Jaccard >= --min-jaccard, default 0.7, and no unstable top feature; low fidelity
is reported but does not change the exit code), 1 unstable, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys
from collections import defaultdict


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def base_name(label):
    """'support_calls > 3.00' / '1.00 < tenure <= 5.00' / 'plan=basic' -> the feature name."""
    s = label.strip()
    m = re.match(r"^[-\d.eE+]+\s*<=?\s*([^<>=]+?)\s*<=?\s*[-\d.eE+]+$", s)
    if m:
        return m.group(1).strip()
    return re.split(r"\s*(<=|>=|<|>|=)\s*", s, maxsplit=1)[0].strip()


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    for c in ("run", "feature", "weight"):
        if c not in rows[0]:
            raise ValueError(f"column {c!r} not found (have: {', '.join(rows[0])})")
    runs = defaultdict(dict)
    meta = defaultdict(dict)
    for r in rows:
        w = num(r["weight"])
        if w is None:
            continue
        runs[r["run"]][r["feature"]] = w
        for c in ("score", "local_pred", "model_pred"):
            if c in r and num(r[c]) is not None:
                meta[r["run"]][c] = num(r[c])
    if len(runs) < 2:
        raise ValueError("need at least two runs of the same explanation")
    return runs, meta


def analyse(runs, meta, top_k):
    names = sorted({f for r in runs.values() for f in r})
    R = list(runs)
    out = []
    tops = {}
    for r in R:
        ranked = sorted(runs[r].items(), key=lambda kv: -abs(kv[1]))
        tops[r] = {f for f, _ in ranked[:top_k]}
    for f in names:
        ws = [runs[r].get(f, 0.0) for r in R]
        m = sum(ws) / len(ws)
        sd = math.sqrt(sum((w - m) ** 2 for w in ws) / (len(ws) - 1))
        nz = [w for w in ws if w != 0]
        pos = sum(1 for w in nz if w > 0)
        sign_cons = max(pos, len(nz) - pos) / len(nz) if nz else 0.0
        in_top = sum(1 for r in R if f in tops[r]) / len(R)
        cv = sd / abs(m) if m else float("inf")
        if sign_cons < 0.9:
            status = "unstable"
        elif cv <= 0.5 and in_top >= 0.8:
            status = "stable"
        elif in_top == 0 and abs(m) < 1e-12:
            status = "absent"
        else:
            status = "noisy"
        out.append({"feature": f, "mean": m, "mean_abs": sum(abs(w) for w in ws) / len(ws), "std": sd, "cv": cv, "sign_consistency": sign_cons,
                    "top_k_share": in_top, "present_share": len(nz) / len(R), "status": status})
    out.sort(key=lambda d: -d["mean_abs"])                  # by size regardless of sign flips
    biggest = out[0]["mean_abs"] if out else 0.0
    negligible = set()
    for d in out:
        if d["mean_abs"] < 0.1 * biggest and d["status"] != "absent":
            d["status"] = "negligible"                  # too small to matter, whatever its stability
            negligible.add(d["feature"])
    pairs = [(a, b) for i, a in enumerate(R) for b in R[i + 1:]]
    def jacc(a, b):
        sa, sb = tops[a] - negligible, tops[b] - negligible
        return len(sa & sb) / len(sa | sb) if sa | sb else 1.0
    jac = sum(jacc(a, b) for a, b in pairs) / len(pairs)
    res = {"runs": len(R), "top_k": top_k, "features": out, "top_k_jaccard": jac}
    scores = [m["score"] for m in meta.values() if "score" in m]
    if scores:
        res["fidelity_mean"] = sum(scores) / len(scores)
    gaps = [abs(m["local_pred"] - m["model_pred"]) for m in meta.values() if "local_pred" in m and "model_pred" in m]
    if gaps:
        res["local_gap_mean"] = sum(gaps) / len(gaps)
    return res


def compare(res, path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows or "feature" not in rows[0] or "value" not in rows[0]:
        raise ValueError("compare file needs feature,value columns")
    other = {r["feature"]: num(r["value"]) for r in rows if num(r["value"]) is not None}
    agree, total, detail = 0, 0, []
    for d in res["features"]:
        if d["status"] == "absent":
            continue
        b = base_name(d["feature"])
        key = b if b in other else next((k for k in other if b.startswith(k) or k.startswith(b)), None)
        if key is None or other[key] == 0 or d["mean"] == 0:
            continue
        same = (other[key] > 0) == (d["mean"] > 0)
        agree += same
        total += 1
        detail.append({"lime": d["feature"], "other": key, "same_sign": same})
    return {"matched": total, "sign_agreement": agree / total if total else None, "pairs": detail}


def verdict_ok(res, min_j):
    unstable_top = [d for d in res["features"][:res["top_k"]] if d["status"] == "unstable"]
    return res["top_k_jaccard"] >= min_j and not unstable_top


def report(res, min_j):
    lines = [f"runs: {res['runs']}   top-k: {res['top_k']}", "",
             f"{'feature':<32} {'mean':>8} {'std':>7} {'cv':>6} {'sign':>5} {'top-k':>6}  status"]
    for d in res["features"]:
        if d["status"] == "absent":
            continue
        cv = "inf" if d["cv"] == float("inf") else f"{d['cv']:.2f}"
        lines.append(f"{d['feature'][:32]:<32} {d['mean']:>+8.4f} {d['std']:>7.4f} {cv:>6} "
                     f"{d['sign_consistency']:>5.0%} {d['top_k_share']:>6.0%}  {d['status']}")
    lines.append("")
    lines.append(f"top-{res['top_k']} Jaccard across runs: {res['top_k_jaccard']:.2f} (>= {min_j} wanted)")
    if "fidelity_mean" in res:
        f = res["fidelity_mean"]
        lines.append(f"surrogate fidelity (weighted R^2): {f:.2f}" + ("  LOW: the linear surrogate fits poorly here"
                                                                     if f < 0.5 else ""))
    if "local_gap_mean" in res:
        lines.append(f"|surrogate - model| prediction at the row: {res['local_gap_mean']:.4f}")
    c = res.get("compare")
    if c and c["matched"]:
        lines.append(f"sign agreement with the comparison method: {c['sign_agreement']:.0%} of {c['matched']} features")
        for p in c["pairs"]:
            if not p["same_sign"]:
                lines.append(f"  DISAGREES: {p['lime']} vs {p['other']}")
    lines.append("")
    if verdict_ok(res, min_j) and res.get("fidelity_mean", 1.0) < 0.5:
        lines.append("VERDICT: STABLE BUT LOW FIDELITY - reproducible, but the surrogate explains little of the model "
                     "around this row; try --no-discretize, a smaller kernel width, or SHAP")
    elif verdict_ok(res, min_j):
        lines.append("VERDICT: STABLE - report the stable features with their mean weights")
    else:
        lines.append("VERDICT: UNSTABLE - raise num_samples, tune kernel_width, fix the seed, or prefer SHAP; "
                     "report only features marked stable")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Check LIME explanation stability.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--min-jaccard", type=float, default=0.7)
    ap.add_argument("--compare", help="CSV feature,value from another method for the same row (e.g. SHAP)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        runs, meta = load(a.csv)
        res = analyse(runs, meta, a.top_k)
        if a.compare:
            res["compare"] = compare(res, a.compare)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2) if a.json else report(res, a.min_jaccard))
    return 0 if verdict_ok(res, a.min_jaccard) else 1


if __name__ == "__main__":
    sys.exit(main())
