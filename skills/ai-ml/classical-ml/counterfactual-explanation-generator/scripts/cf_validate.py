#!/usr/bin/env python3
"""Validate counterfactual explanations from any method (DiCE, Alibi, custom search) before showing them.

Inputs:
  --original   the explained row (JSON object, or a CSV whose first row is used)
  --cfs        counterfactual rows (CSV, same feature columns; an optional prediction column)
  --train      training data (CSV) for ranges, scales and plausibility
  --constraints JSON {"features": {name: {"mutable", "direction", "min", "max", "integer", "binary"}}}
               (the same "features" block as linear_counterfactual.py's model spec; optional)

Per counterfactual:
  changed      features that differ from the original (sparsity; fewer is easier to act on)
  violations   IMMUTABLE changed, DIRECTION wrong way, BOUNDS outside min/max, INTEGER not whole,
               UNSEEN category not in the training data
  range        numeric values outside the 1st-99th training percentile and further out than the original
               (moving an unusual row towards the data is fine)
  distance     L1 distance to the original in MAD units (numeric) + 1 per changed category
  plausibility distance to the nearest training row (MAD units) compared with the larger of the 95th
               percentile of nearest-neighbour distances among training rows and the original's own
               nearest-row distance: above it = off the data manifold
  RELATION     with --relation total=a*b (or / + -), a derived feature that no longer matches its inputs
               (e.g. total_charges changed while tenure and monthly charges did not), when the original
               satisfies the rule within --relation-tol
  valid        with --pred-col and --target-prob/--side, whether the prediction meets the target
Set level: mean pairwise distance between counterfactuals (diversity) and the distinct sets of changed
features.

Usage:
    python cf_validate.py --original row.json --cfs cfs.csv --train train.csv --constraints spec.json
    python cf_validate.py --original row.json --cfs cfs.csv --train train.csv --pred-col churn_prob --target-prob 0.3 --side below
    python cf_validate.py --original row.json --cfs cfs.csv --train train.csv --relation "total=tenure*monthly"

Exit codes: 0 all counterfactuals usable, 1 at least one violation, invalid or off-manifold counterfactual,
2 usage or read error.
"""

import argparse
import csv
import json
import math
import random
import sys


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def quantile(xs, q):
    s = sorted(xs)
    k = (len(s) - 1) * q
    lo = math.floor(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def profile(train, feats):
    prof = {}
    for f in feats:
        vals = [num(r.get(f)) for r in train]
        nums = [v for v in vals if v is not None]
        if len(nums) >= 0.9 * len(train) and nums:
            med = quantile(nums, 0.5)
            mad = quantile([abs(v - med) for v in nums], 0.5)
            if mad == 0:
                m = sum(nums) / len(nums)
                mad = math.sqrt(sum((v - m) ** 2 for v in nums) / max(1, len(nums) - 1)) or 1.0
            prof[f] = {"kind": "num", "mad": mad, "p01": quantile(nums, 0.01), "p99": quantile(nums, 0.99)}
        else:
            prof[f] = {"kind": "cat", "levels": {r.get(f, "") for r in train}}
    return prof


def distance(a, b, feats, prof):
    d = 0.0
    for f in feats:
        p = prof[f]
        if p["kind"] == "num":
            x, y = num(a.get(f)), num(b.get(f))
            if x is not None and y is not None:
                d += abs(x - y) / p["mad"]
        elif str(a.get(f, "")) != str(b.get(f, "")):
            d += 1.0
    return d


def parse_relation(text):
    """'total=a*b' -> (total, a, op, b); supports * / + - between two columns or a column and a number."""
    import re
    m = re.match(r"^\s*(\w+)\s*=\s*([\w.]+)\s*([*/+-])\s*([\w.]+)\s*$", text)
    if not m:
        raise ValueError(f"cannot parse relation {text!r}; use target=a*b (operators * / + -)")
    return m.groups()


def check_relation(row, rel, tol):
    target, a, op, b = rel
    va = num(row.get(a)) if num(a) is None else num(a)
    vb = num(row.get(b)) if num(b) is None else num(b)
    vt = num(row.get(target))
    if None in (va, vb, vt):
        return None
    expect = {"*": va * vb, "/": va / vb if vb else math.inf, "+": va + vb, "-": va - vb}[op]
    return abs(vt - expect) <= tol * max(1.0, abs(expect)), expect


def validate(orig, cfs, train, feats, cons, a):
    prof = profile(train, feats)
    rng = random.Random(0)
    sample = train if len(train) <= 1500 else rng.sample(train, 1500)
    ref = sample[: min(300, len(sample))]
    nn = []
    for r in ref:
        nn.append(min(distance(r, s, feats, prof) for s in sample if s is not r))
    nn_p95 = quantile(nn, 0.95) if nn else None
    orig_nearest = min(distance(orig, s, feats, prof) for s in sample)
    limit = max(nn_p95, orig_nearest) if nn_p95 is not None else None     # judge relative to the original
    fc = cons.get("features", {})
    out = []
    for i, cf in enumerate(cfs):
        changed, viol, rng_flags = [], [], []
        for f in feats:
            p = prof[f]
            ov, nv = orig.get(f), cf.get(f)
            if p["kind"] == "num":
                x, y = num(ov), num(nv)
                if x is None or y is None or abs(x - y) <= 1e-9 * max(1.0, abs(x)):
                    continue
                changed.append(f)
                c = fc.get(f, {})
                if c and not c.get("mutable", True):
                    viol.append(f"IMMUTABLE {f}")
                if c.get("direction") == "increase" and y < x or c.get("direction") == "decrease" and y > x:
                    viol.append(f"DIRECTION {f} ({x:g} -> {y:g}, allowed: {c['direction']})")
                if ("min" in c and y < c["min"]) or ("max" in c and y > c["max"]):
                    viol.append(f"BOUNDS {f} = {y:g}")
                if (c.get("integer") or c.get("binary")) and abs(y - round(y)) > 1e-9:
                    viol.append(f"INTEGER {f} = {y:g}")
                lo, hi = p["p01"], p["p99"]
                gap = lambda v: max(lo - v, v - hi, 0.0)       # distance outside the typical range
                crossed = (y < lo) != (x < lo) or (y > hi) != (x > hi)
                if gap(y) > 0 and (crossed or gap(y) > gap(x) - 1e-12):   # moving towards the data is fine
                    rng_flags.append(f"{f} = {y:g} outside the training 1-99% range [{p['p01']:g}, {p['p99']:g}]")
            else:
                if str(ov) == str(nv):
                    continue
                changed.append(f)
                if fc.get(f) and not fc[f].get("mutable", True):
                    viol.append(f"IMMUTABLE {f}")
                if nv not in p["levels"]:
                    viol.append(f"UNSEEN {f} = {nv!r}")
        for rel in a.relations:
            chk = check_relation(cf, rel, a.relation_tol)
            if chk and not chk[0]:
                base = check_relation(orig, rel, a.relation_tol)
                if base is None or base[0]:               # the original satisfies it, the counterfactual does not
                    viol.append(f"RELATION {rel[0]} = {num(cf.get(rel[0])):g} but {rel[1]}{rel[2]}{rel[3]} = "
                                f"{chk[1]:g}")
        d = distance(orig, cf, feats, prof)
        nearest = min(distance(cf, s, feats, prof) for s in sample)
        res = {"index": i, "changed": changed, "violations": viol, "range": rng_flags, "distance": d,
               "nearest_train": nearest, "off_manifold": limit is not None and nearest > limit}
        if a.pred_col:
            pv = num(cf.get(a.pred_col))
            if pv is not None and a.target_prob is not None:
                res["prediction"] = pv
                res["valid"] = pv <= a.target_prob if a.side == "below" else pv >= a.target_prob
        out.append(res)
    div = None
    if len(cfs) >= 2:
        ds = [distance(cfs[i], cfs[j], feats, prof) for i in range(len(cfs)) for j in range(i + 1, len(cfs))]
        div = sum(ds) / len(ds)
    sets = sorted({tuple(sorted(r["changed"])) for r in out})
    return {"counterfactuals": out, "nn_p95": nn_p95, "original_nearest": orig_nearest, "limit": limit, "diversity": div, "changed_sets": [list(s) for s in sets]}


def usable(r):
    return not r["violations"] and not r["off_manifold"] and r.get("valid", True)


def report(res):
    lines = [f"original: nearest training row at {res['original_nearest']:.2f}; training nearest-neighbour p95 "
             f"{res['nn_p95']:.2f}; off-manifold limit {res['limit']:.2f}", "",
             f"{'#':>3} {'changed':<40} {'dist':>6} {'nearest':>8}  status"]
    for r in res["counterfactuals"]:
        status = "OK" if usable(r) else "REJECT"
        lines.append(f"{r['index']:>3} {', '.join(r['changed'])[:40]:<40} {r['distance']:>6.2f} {r['nearest_train']:>8.2f}  "
                     f"{status}")
        for v in r["violations"]:
            lines.append(f"      violation: {v}")
        for v in r["range"]:
            lines.append(f"      implausible: {v}")
        if r["off_manifold"]:
            lines.append(f"      off-manifold: nearest training row {r['nearest_train']:.2f} > limit {res['limit']:.2f}")
        if r.get("valid") is False:
            lines.append(f"      invalid: prediction {r['prediction']:.4g} does not meet the target")
    lines.append("")
    if res["diversity"] is not None:
        lines.append(f"diversity (mean pairwise distance): {res['diversity']:.2f}; distinct changed-feature sets: "
                     f"{len(res['changed_sets'])}")
    ok = sum(usable(r) for r in res["counterfactuals"])
    lines.append(f"{ok} of {len(res['counterfactuals'])} counterfactual(s) usable")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Validate counterfactual explanations.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", required=True)
    ap.add_argument("--cfs", required=True)
    ap.add_argument("--train", required=True)
    ap.add_argument("--constraints")
    ap.add_argument("--features", nargs="*", help="feature columns (default: the original's keys present in --cfs)")
    ap.add_argument("--pred-col")
    ap.add_argument("--target-prob", type=float)
    ap.add_argument("--side", choices=["below", "above"], default="below")
    ap.add_argument("--relation", action="append", default=[],
                    help="derived-feature rule that must keep holding, e.g. total_charges=tenure_months*monthly_charges")
    ap.add_argument("--relation-tol", type=float, default=0.05, help="relative tolerance for --relation (5%%)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        if a.original.endswith(".json"):
            with open(a.original, encoding="utf-8") as f:
                orig = {k: str(v) for k, v in json.load(f).items()}
        else:
            orig = read_csv(a.original)[0]
        cfs = read_csv(a.cfs)
        train = read_csv(a.train)
        cons = {}
        if a.constraints:
            with open(a.constraints, encoding="utf-8") as f:
                cons = json.load(f)
        a.relations = [parse_relation(r) for r in a.relation]
        feats = a.features or [k for k in orig if k in cfs[0] and k in train[0] and k != a.pred_col]
        if not feats:
            raise ValueError("no shared feature columns between --original, --cfs and --train")
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    res = validate(orig, cfs, train, feats, cons, a)
    print(json.dumps(res, indent=2) if a.json else report(res))
    return 0 if all(usable(r) for r in res["counterfactuals"]) else 1


if __name__ == "__main__":
    sys.exit(main())
