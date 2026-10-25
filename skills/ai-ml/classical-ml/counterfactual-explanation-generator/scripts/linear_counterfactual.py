#!/usr/bin/env python3
"""Minimal-cost counterfactuals (recourse) for linear and logistic models, with actionability constraints.

Model spec (JSON):
  {"model": "logistic" | "linear", "intercept": b, "coefficients": {feature: w},
   "features": {feature: {"mutable": true, "direction": "increase" | "decrease" | "any",
                          "min": .., "max": .., "integer": false, "binary": false,
                          "scale": MAD or std (cost unit), "cost_multiplier": 1.0}}}
Row (JSON object feature -> value). Features absent from "features" are treated as immutable.

Goal: reach --target-prob (logistic; default: just across --threshold 0.5 on the other side of the current
prediction) or --target-value (linear), with --side below|above (default: towards the other class).

Cost of a change: sum over features of |delta| / scale x cost_multiplier (L1 in MAD units: sparse,
interpretable changes; Wachter et al. 2017, Ustun et al. 2019). For a linear score the problem is a
fractional knapsack: features are used in order of score change per unit cost up to their bounds, which is
optimal for continuous features; binary features are searched exhaustively (2^b subsets); for integer
features both the rounded-down and rounded-up step are explored, so integer rounding stays optimal.

Reports:
  current      score and probability
  optimal      the minimal-cost counterfactual: changes, cost, sparsity, resulting probability
  alternatives the best counterfactual without each feature of the optimal one (diverse options) and the
               best single-feature changes
               (features without which no counterfactual exists are reported as essential)
  no recourse  when no allowed change reaches the target: the best reachable probability using every allowed
               change, and the immutable features (a fairness and recourse finding)

Usage:
    python linear_counterfactual.py cf_logreg.json cf_row.json --target-prob 0.3
    python linear_counterfactual.py model.json row.json --threshold 0.5 --json
    python linear_counterfactual.py linear.json row.json --target-value 250000 --side above

Exit codes: 0 counterfactual found, 1 no feasible recourse, 2 usage or read error.
"""

import argparse
import itertools
import json
import math
import sys


def logit(p):
    return math.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + math.exp(-z)) if z > -700 else 0.0


def bounds(name, x, cfg, want_sign, w):
    """Allowed delta range for a feature, restricted to the helpful direction."""
    if not cfg.get("mutable", True) or w == 0:
        return 0.0, 0.0
    lo = cfg.get("min", -math.inf) - x
    hi = cfg.get("max", math.inf) - x
    d = cfg.get("direction", "any")
    if d == "increase":
        lo = max(lo, 0.0)
    elif d == "decrease":
        hi = min(hi, 0.0)
    # only move in the direction that changes the score the way we want
    helpful_up = (w > 0) == (want_sign > 0)
    return (0.0, max(hi, 0.0)) if helpful_up else (min(lo, 0.0), 0.0)


def best_fill(opts, i, remaining, coefs, fcfg):
    """Cheapest way to cover `remaining` score with features opts[i:] (sorted by efficiency).

    Continuous features are taken greedily (optimal for a fractional knapsack); for an integer feature both
    the rounded-down and the rounded-up step are tried, so rounding never forces an unnecessary unit.
    Returns (cost, {feature: delta}) or None when infeasible."""
    if remaining <= 1e-12:
        return 0.0, {}
    if i >= len(opts):
        return None
    _, f, room = opts[i]
    cfg = fcfg.get(f, {})
    unit_cost = cfg.get("cost_multiplier", 1.0) / cfg.get("scale", 1.0)
    w = abs(coefs[f])
    exact = remaining / w
    steps = [min(abs(room), exact)]
    if cfg.get("integer"):
        steps = sorted({min(abs(room), math.floor(exact + 1e-9)), min(abs(room), math.ceil(exact - 1e-9))})
    best = None
    for step in steps:
        rest = best_fill(opts, i + 1, remaining - w * step, coefs, fcfg)
        if rest is None:
            continue
        c = step * unit_cost + rest[0]
        if best is None or c < best[0] - 1e-12:
            d = dict(rest[1])
            if step:
                d[f] = math.copysign(step, room)
            best = (c, d)
    return best


def solve(spec, row, need, want_sign, exclude=()):
    """Minimise cost s.t. sum w*delta moves the score by `need` (signed, in want_sign direction)."""
    coefs = spec["coefficients"]
    fcfg = spec.get("features", {})
    names = [f for f in coefs if f not in exclude]
    binaries = [f for f in names if fcfg.get(f, {}).get("binary")]
    conts = [f for f in names if f not in binaries]
    best = None
    for k in range(len(binaries) + 1):
        for subset in itertools.combinations(binaries, k):
            delta, cost, gain = {}, 0.0, 0.0
            ok = True
            for f in subset:
                cfg = fcfg.get(f, {})
                if not cfg.get("mutable", True):
                    ok = False
                    break
                x = row[f]
                nd = (1 - x) - x                          # flip 0 <-> 1
                d = cfg.get("direction", "any")
                if (d == "increase" and nd < 0) or (d == "decrease" and nd > 0):
                    ok = False
                    break
                g = coefs[f] * nd * want_sign
                if g <= 0:
                    ok = False
                    break
                delta[f] = nd
                gain += g
                cost += abs(nd) / cfg.get("scale", 1.0) * cfg.get("cost_multiplier", 1.0)
            if not ok:
                continue
            remaining = need - gain
            opts = []
            for f in conts:
                cfg = fcfg.get(f, {})
                lo, hi = bounds(f, row[f], cfg, want_sign, coefs[f])
                room = hi if hi > 0 else lo
                if room == 0:
                    continue
                per_unit_gain = abs(coefs[f])
                per_unit_cost = cfg.get("cost_multiplier", 1.0) / cfg.get("scale", 1.0)
                opts.append((per_unit_gain / per_unit_cost, f, room))
            opts.sort(reverse=True)
            fill = best_fill(opts, 0, remaining, coefs, fcfg)
            if fill is None:                              # infeasible: use every allowed move
                for _, f, room in opts:
                    delta[f] = room
                    remaining -= abs(coefs[f]) * abs(room)
                    cfg = fcfg.get(f, {})
                    cost += abs(room) / cfg.get("scale", 1.0) * cfg.get("cost_multiplier", 1.0)
            else:
                fcost, fdelta = fill
                delta.update(fdelta)
                cost += fcost
                remaining = 0.0
            feasible = remaining <= 1e-9
            cand = {"delta": {f: v for f, v in delta.items() if v != 0}, "cost": cost, "feasible": feasible,
                    "shortfall": max(0.0, remaining)}
            if best is None or (cand["feasible"], -cand["cost"]) > (best["feasible"], -best["cost"]) or \
                    (not best["feasible"] and not cand["feasible"] and cand["shortfall"] < best["shortfall"]):
                best = cand
    return best


def score(spec, values):
    return spec["intercept"] + sum(w * values[f] for f, w in spec["coefficients"].items())


def describe(spec, row, sol):
    new = dict(row)
    for f, d in sol["delta"].items():
        new[f] = row[f] + d
    z = score(spec, new)
    out = {"changes": [{"feature": f, "from": row[f], "to": round(new[f], 6), "delta": round(d, 6)}
                       for f, d in sorted(sol["delta"].items(), key=lambda kv: -abs(kv[1]))],
           "cost": sol["cost"], "sparsity": len(sol["delta"]), "feasible": sol["feasible"], "score": z}
    if spec.get("model", "logistic") == "logistic":
        out["prob"] = sigmoid(z)
    return out


def run(spec, row, a):
    for f in spec["coefficients"]:
        if f not in row:
            raise ValueError(f"row lacks feature {f!r}")
    logistic = spec.get("model", "logistic") == "logistic"
    z0 = score(spec, row)
    if logistic:
        p0 = sigmoid(z0)
        side = a.side or ("below" if p0 >= a.threshold else "above")
        target = a.target_prob if a.target_prob is not None else a.threshold
        if not 0 < target < 1:
            raise ValueError("--target-prob must be in (0, 1)")
        zt = logit(target)
    else:
        if a.target_value is None:
            raise ValueError("linear models need --target-value")
        side = a.side or "above"
        zt = a.target_value
    want_sign = -1 if side == "below" else 1
    need = (zt - z0) * want_sign
    res = {"current": {"score": z0, **({"prob": sigmoid(z0)} if logistic else {})}, "side": side,
           "target": a.target_prob if logistic else a.target_value}
    if logistic and a.target_prob is None:
        res["target"] = a.threshold
    if need <= 0:
        res["already"] = True
        return res
    need += a.margin
    opt = solve(spec, row, need, want_sign)
    res["optimal"] = describe(spec, row, opt)
    fcfg = spec.get("features", {})
    if not opt["feasible"]:
        immut = [f for f in spec["coefficients"] if f not in fcfg or not fcfg[f].get("mutable", True)]
        res["no_recourse"] = {"immutable": immut, "shortfall_score": opt["shortfall"]}
        return res
    alts, without_none = [], []
    for f in res["optimal"]["changes"]:
        s = solve(spec, row, need, want_sign, exclude=(f["feature"],))
        if s and s["feasible"]:
            alts.append({"without": f["feature"], **describe(spec, row, s)})
        else:
            without_none.append(f["feature"])
    res["essential"] = without_none                   # features every counterfactual must change
    singles = []
    for f in spec["coefficients"]:
        others = tuple(g for g in spec["coefficients"] if g != f)
        s = solve(spec, row, need, want_sign, exclude=others)
        if s and s["feasible"]:
            singles.append(describe(spec, row, s))
    singles.sort(key=lambda d: d["cost"])
    res["alternatives"], res["single_feature"] = alts, singles
    return res


def fmt(v):
    return f"{v:.4g}" if isinstance(v, float) else str(v)


def show(cf, logistic):
    lines = []
    for c in cf["changes"]:
        lines.append(f"    {c['feature']}: {fmt(c['from'])} -> {fmt(c['to'])} ({c['delta']:+.4g})")
    tail = f"cost {cf['cost']:.3f} (MAD units), {cf['sparsity']} feature(s) changed"
    tail += f", new probability {cf['prob']:.1%}" if logistic else f", new prediction {cf['score']:.4g}"
    return lines + ["    " + tail]


def report(res, logistic):
    cur = res["current"]
    lines = [("current probability: " + f"{cur['prob']:.1%}" if logistic else f"current prediction: {cur['score']:.4g}")
             + f"   target: {res['side']} {res['target']}"]
    if res.get("already"):
        lines.append("the row already meets the target: no change needed")
        return "\n".join(lines)
    opt = res["optimal"]
    if res.get("no_recourse"):
        lines.append("NO RECOURSE: no combination of allowed changes reaches the target")
        best = f"{opt['prob']:.1%}" if logistic else f"{opt['score']:.4g}"
        lines.append(f"  best reachable: {best}, using every allowed change:")
        lines += show(opt, logistic)[:-1]
        imm = res["no_recourse"]["immutable"]
        lines.append("  the rest of the score is fixed by the intercept and immutable features"
                     + (f" ({', '.join(imm)})" if imm else "")
                     + ": review whether a decision without recourse is acceptable here")
        return "\n".join(lines)
    lines.append("")
    lines.append("OPTIMAL (minimal cost):")
    lines += show(opt, logistic)
    for f in res.get("essential", []):
        lines.append(f"  no feasible counterfactual without changing {f}")
    if res["alternatives"]:
        lines.append("")
        lines.append("ALTERNATIVES (diverse options):")
        for alt in res["alternatives"]:
            lines.append(f"  without {alt['without']}:")
            lines += show(alt, logistic)
    if res["single_feature"]:
        lines.append("")
        lines.append("SINGLE-FEATURE options:")
        for s in res["single_feature"][:5]:
            lines += show(s, logistic)
    lines.append("")
    lines.append("These are changes to the model's inputs that change its output; they are recourse options only if "
                 "the features are causally actionable in the real world.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Minimal-cost counterfactuals for linear models.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model_json")
    ap.add_argument("row_json")
    ap.add_argument("--target-prob", type=float)
    ap.add_argument("--target-value", type=float)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--side", choices=["below", "above"])
    ap.add_argument("--margin", type=float, default=1e-6, help="extra score change beyond the target")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with open(a.model_json, encoding="utf-8") as f:
            spec = json.load(f)
        with open(a.row_json, encoding="utf-8") as f:
            row = json.load(f)
        if "coefficients" not in spec or "intercept" not in spec:
            raise ValueError("model spec needs intercept and coefficients")
        row = {k: float(v) for k, v in row.items()}
        res = run(spec, row, a)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    logistic = spec.get("model", "logistic") == "logistic"
    print(json.dumps(res, indent=2) if a.json else report(res, logistic))
    return 1 if res.get("no_recourse") else 0


if __name__ == "__main__":
    sys.exit(main())
