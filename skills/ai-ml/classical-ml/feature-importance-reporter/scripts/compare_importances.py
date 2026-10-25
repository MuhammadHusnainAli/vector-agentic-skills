#!/usr/bin/env python3
"""Compare feature importances from several methods and explain where they disagree.

Input: a wide CSV with a `feature` column and one column per method, e.g.
    feature,gain,split,permutation,permutation_std,mean_abs_shap,drop_column
Method kinds are recognised from the column name: gain/split/weight/cover = impurity-based (training data),
permutation/drop = held-out loss-based, shap = mean |SHAP|, coef = |standardised coefficient|. A column
`<method>_std` gives the standard deviation over permutation repeats.

Reports:
  table       each method as a share of its total (negative permutation values kept as-is), the rank per
              method, and the consensus rank (mean rank across methods)
  agreement   Spearman correlation between every pair of methods
  flags       IMPURITY-ONLY  high gain/split share but little held-out (permutation/drop) importance: split bias
                             towards continuous or high-cardinality features, or redundancy with a
                             correlated feature (permuting one is compensated by the other)
              NO-EFFECT      held-out importance within 2 std of zero (or <= 0 without std): no measurable
                             contribution on new data; candidate to drop (check correlated groups first)
              ID-LIKE        name looks like an identifier/hash/timestamp: should not be a feature
              DOMINANT       one feature holds > 50% of a held-out method: check for leakage
              SHAP-VS-PERM   mean |SHAP| share at least 3x the held-out share: the model uses it, but a
                             correlated feature carries the same information
With --groups groups.csv (written by gen_importance_script.py: group, group_permutation,
group_permutation_std, sum_single_permutation), groups whose joint permutation exceeds the sum of their
single-feature permutations by > 30% are reported as SHARED-INFO: the members carry overlapping information,
so report the group's importance rather than each member's.
The recommended headline method is held-out permutation (or drop-column) importance, with SHAP for
direction and impurity importance only as a cheap first look.

Usage:
    python compare_importances.py importances.csv
    python compare_importances.py importances.csv --groups groups.csv
    python compare_importances.py importances.csv --top 10 --json

Exit codes: 0 compared, 1 a DOMINANT or ID-LIKE flag was raised, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys

ID_LIKE = re.compile(r"(^id$|_id$|^id_|uuid|guid|hash|_key$|index|row_?num|timestamp|^ts$|created_at|updated_at)", re.I)


def kind_of(col):
    c = col.lower()
    if "shap" in c:
        return "shap"
    if "perm" in c or "drop" in c:
        return "heldout"
    if "coef" in c:
        return "coef"
    if any(k in c for k in ("gain", "split", "weight", "cover", "impurity", "gini", "mdi")):
        return "impurity"
    return "other"


def ranks_desc(xs):
    order = sorted(range(len(xs)), key=lambda i: -xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks_desc(a), ranks_desc(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return num / den if den else 0.0


def load(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("no rows")
    cols = list(rows[0])
    fcol = next((c for c in cols if c.lower() in ("feature", "features", "name", "variable")), None)
    if fcol is None:
        raise ValueError("need a 'feature' column")
    methods = [c for c in cols if c != fcol and not c.lower().endswith("_std")]
    if not methods:
        raise ValueError("no method columns")
    feats = [r[fcol] for r in rows]
    if len(set(feats)) < len(feats):
        raise ValueError("features repeat: this looks like a long (run, feature, importance) file; pivot it to one "
                         "row per feature, or check run-to-run stability with importance_stability.py")
    vals, stds = {}, {}
    for m in methods:
        try:
            vals[m] = [float(r[m]) if r[m] not in ("", None) else 0.0 for r in rows]
        except ValueError:
            raise ValueError(f"column {m!r} is not numeric")
        sc = next((c for c in cols if c.lower() == f"{m.lower()}_std"), None)
        if sc:
            stds[m] = [float(r[sc] or 0) for r in rows]
    return feats, methods, vals, stds


def analyse(feats, methods, vals, stds):
    n = len(feats)
    kinds = {m: kind_of(m) for m in methods}
    shares, rank = {}, {}
    for m in methods:
        tot = sum(abs(v) for v in vals[m]) or 1.0
        shares[m] = [v / tot for v in vals[m]]
        rank[m] = ranks_desc(vals[m])
    consensus = [sum(rank[m][i] for m in methods) / len(methods) for i in range(n)]
    agree = {f"{a} vs {b}": spearman(vals[a], vals[b]) for i, a in enumerate(methods) for b in methods[i + 1:]}
    held = [m for m in methods if kinds[m] == "heldout"]
    imp = [m for m in methods if kinds[m] == "impurity"]
    shap = [m for m in methods if kinds[m] == "shap"]
    flags = {f: [] for f in feats}
    for i, f in enumerate(feats):
        heldout_null = None
        for m in held:
            v = vals[m][i]
            sd = stds.get(m, [0.0] * n)[i]
            null = v <= 2 * sd if sd > 0 else v <= 1e-12 or shares[m][i] < 0.005
            heldout_null = null if heldout_null is None else (heldout_null and null)
            if shares[m][i] > 0.5:
                flags[f].append(("DOMINANT", f"{shares[m][i]:.0%} of {m}: check for target leakage"))
        if heldout_null:
            flags[f].append(("NO-EFFECT", "held-out importance indistinguishable from zero"))
        for m in imp:
            if shares[m][i] >= 0.1 and held and all(shares[h][i] < shares[m][i] / 3 for h in held):
                flags[f].append(("IMPURITY-ONLY", f"{shares[m][i]:.0%} of {m} but "
                                 + ", ".join(f"{shares[h][i]:.0%} of {h}" for h in held)
                                 + ": split bias (continuous/high-cardinality) or redundancy with a correlated feature"))
                break
        for m in shap:
            if shares[m][i] >= 0.08 and held and all(shares[h][i] < shares[m][i] / 3 for h in held):
                flags[f].append(("SHAP-VS-PERM", f"{shares[m][i]:.0%} of mean |SHAP| but "
                                 + ", ".join(f"{shares[h][i]:.0%} of {h}" for h in held)
                                 + ": the model uses it, but a correlated feature carries the same information"))
                break
        if ID_LIKE.search(f):
            flags[f].append(("ID-LIKE", "identifier/hash/timestamp-like name: remove it from the features"))
    order = sorted(range(n), key=lambda i: consensus[i])
    return {"methods": methods, "kinds": kinds, "features": [
        {"feature": feats[i], "consensus_rank": consensus[i],
         "shares": {m: shares[m][i] for m in methods}, "ranks": {m: rank[m][i] for m in methods},
         "flags": [{"flag": k, "detail": d} for k, d in flags[feats[i]]]} for i in order],
        "agreement": agree}


def load_groups(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = []
    for g in rows:
        try:
            joint, single = float(g["group_permutation"]), float(g["sum_single_permutation"])
        except (KeyError, ValueError):
            raise ValueError("groups file needs group, group_permutation, sum_single_permutation columns")
        sd = float(g.get("group_permutation_std") or 0)
        shared = joint > 1.3 * max(single, 0) and joint - max(single, 0) > 2 * sd
        out.append({"group": g["group"], "joint": joint, "single_sum": single, "std": sd, "shared": shared})
    return out


def report(r, top):
    ms = r["methods"]
    w = max(12, max(len(m) for m in ms) + 2)
    lines = [f"{'consensus':>9}  {'feature':<22}" + "".join(f"{m:>{w}}" for m in ms) + "   (share of each method)"]
    for d in r["features"][:top]:
        lines.append(f"{d['consensus_rank']:>9.1f}  {d['feature'][:22]:<22}"
                     + "".join(f"{d['shares'][m]:>{w}.1%}" for m in ms))
    if len(r["features"]) > top:
        lines.append(f"  ... {len(r['features']) - top} more")
    lines.append("")
    lines.append("method agreement (Spearman):")
    for k, v in r["agreement"].items():
        lines.append(f"  {k:<40} {v:>6.2f}")
    lines.append("")
    flagged = [d for d in r["features"] if d["flags"]]
    for d in flagged:
        for fl in d["flags"]:
            lines.append(f"{fl['flag']:<14} {d['feature']}: {fl['detail']}")
    if not flagged:
        lines.append("no flags: the methods tell a consistent story")
    for g in r.get("groups", []):
        if g["shared"]:
            lines.append(f"{'SHARED-INFO':<14} {g['group']}: joint permutation {g['joint']:.4g} vs {g['single_sum']:.4g} "
                         "summed singly: overlapping information, report the group's importance")
        else:
            lines.append(f"{'group':<14} {g['group']}: joint {g['joint']:.4g} vs {g['single_sum']:.4g} summed singly")
    kinds = set(r["kinds"].values())
    lines.append("")
    if "heldout" not in kinds:
        lines.append("NOTE: no held-out method (permutation or drop-column): impurity and SHAP importances describe "
                     "how the model uses features on training data, not what generalises")
    else:
        lines.append("Headline: use the held-out method's ranking; SHAP for direction; impurity only as a first look.")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Compare feature importance methods.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--groups", help="groups.csv with grouped permutation results")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        feats, methods, vals, stds = load(a.csv)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    r = analyse(feats, methods, vals, stds)
    if a.groups:
        try:
            r["groups"] = load_groups(a.groups)
        except (OSError, ValueError) as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
    print(json.dumps(r, indent=2) if a.json else report(r, a.top))
    bad = any(fl["flag"] in ("DOMINANT", "ID-LIKE") for d in r["features"] for fl in d["flags"])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
