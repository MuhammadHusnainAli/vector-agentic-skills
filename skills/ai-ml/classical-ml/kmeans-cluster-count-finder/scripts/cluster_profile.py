#!/usr/bin/env python3
"""Profile clusters so they can be named, checked and acted on.

Input: a CSV with a cluster-label column (from any algorithm; -1 is treated as noise) plus the
features. For each cluster:
  size and share
  numeric features: mean, the standardised difference from the rest of the data
                    (mean_in - mean_out) / pooled_sd, and the most distinctive features ranked by |d|
  categorical features: the level most over-represented relative to the population (lift)
  outcome (--outcome): mean of a business outcome per cluster (churn rate, spend), to check that
                    segments actually behave differently
Warnings: tiny clusters (< --min-share), clusters with no feature |d| >= 0.5 (hard to tell apart), and an
outcome that barely differs across clusters.

Usage:
    python cluster_profile.py segments.csv --label cluster
    python cluster_profile.py segments.csv --label cluster --outcome churned --drop customer_id --top 4
    python cluster_profile.py segments.csv --label cluster --json

Exit codes: 0 profiled, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def mean_sd(xs):
    if not xs:
        return None, None
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1))


def main():
    ap = argparse.ArgumentParser(description="Profile clusters for naming and validation.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--label", required=True, help="cluster label column")
    ap.add_argument("--outcome", help="business outcome column to compare across clusters")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--min-share", type=float, default=0.02)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            rd = csv.DictReader(fh)
            header = rd.fieldnames or []
            rows = list(rd)
        for c in (a.label, a.outcome):
            if c and c not in header:
                raise ValueError(f"column {c!r} not found")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    feats = [c for c in header if c not in (a.label, a.outcome) and c not in a.drop]
    numeric = [c for c in feats if all(num(r[c]) is not None for r in rows if (r[c] or "").strip().lower() not in MISSING)]
    categorical = [c for c in feats if c not in numeric and len({r[c] for r in rows}) <= 50]
    groups = defaultdict(list)
    for r in rows:
        groups[r[a.label].strip()].append(r)
    n = len(rows)
    out = {"rows": n, "clusters": []}
    pop_cat = {c: Counter(r[c] for r in rows) for c in categorical}
    outcome_means = []
    for lab in sorted(groups, key=lambda l: (l == "-1", -len(groups[l]))):
        g = groups[lab]
        rest = [r for r in rows if r[a.label].strip() != lab]
        prof = {"label": lab, "size": len(g), "share": len(g) / n, "noise": lab == "-1", "numeric": [], "categorical": []}
        for c in numeric:
            xin = [num(r[c]) for r in g if num(r[c]) is not None]
            xout = [num(r[c]) for r in rest if num(r[c]) is not None]
            mi, si = mean_sd(xin)
            mo, so = mean_sd(xout)
            if mi is None or mo is None:
                continue
            pooled = math.sqrt(((len(xin) - 1) * si ** 2 + (len(xout) - 1) * so ** 2) / max(1, len(xin) + len(xout) - 2)) or 1e-12
            prof["numeric"].append({"feature": c, "mean": mi, "rest_mean": mo, "d": (mi - mo) / pooled})
        prof["numeric"].sort(key=lambda e: -abs(e["d"]))
        for c in categorical:
            cnt = Counter(r[c] for r in g)
            best = max(cnt, key=lambda v: (cnt[v] / len(g)) / (pop_cat[c][v] / n))
            prof["categorical"].append({"feature": c, "level": best, "share_in": cnt[best] / len(g),
                                        "share_pop": pop_cat[c][best] / n,
                                        "lift": (cnt[best] / len(g)) / (pop_cat[c][best] / n)})
        prof["categorical"].sort(key=lambda e: -e["lift"])
        if a.outcome:
            ys = [num(r[a.outcome]) for r in g if num(r[a.outcome]) is not None]
            prof["outcome_mean"] = sum(ys) / len(ys) if ys else None
            if ys and lab != "-1":
                outcome_means.append(prof["outcome_mean"])
        warn = []
        if prof["share"] < a.min_share and lab != "-1":
            warn.append(f"tiny cluster ({prof['share']:.1%})")
        if prof["numeric"] and abs(prof["numeric"][0]["d"]) < 0.5 and not any(e["lift"] > 1.5 for e in prof["categorical"]):
            warn.append("no feature separates it clearly (max |d| < 0.5): hard to name or act on")
        prof["warnings"] = warn
        out["clusters"].append(prof)
    if a.outcome and len(outcome_means) >= 2:
        lo, hi = min(outcome_means), max(outcome_means)
        out["outcome_spread"] = {"min": lo, "max": hi, "ratio": hi / lo if lo else None}
    if a.json:
        print(json.dumps(out, indent=2))
        return 0
    print(f"{n} rows, {len(groups)} clusters; {len(numeric)} numeric, {len(categorical)} categorical features")
    for p in out["clusters"]:
        tag = " (noise)" if p["noise"] else ""
        oc = f", {a.outcome} mean {p['outcome_mean']:.3g}" if a.outcome and p.get("outcome_mean") is not None else ""
        print(f"\ncluster {p['label']}{tag}: {p['size']} rows ({p['share']:.1%}){oc}")
        for e in p["numeric"][:a.top]:
            arrow = "higher" if e["d"] > 0 else "lower"
            print(f"  {e['feature']:<22} mean {e['mean']:.4g} vs {e['rest_mean']:.4g} elsewhere  (d {e['d']:+.2f}, {arrow})")
        for e in p["categorical"][:2]:
            if e["lift"] > 1.2:
                print(f"  {e['feature']}={e['level']:<16} {e['share_in']:.0%} vs {e['share_pop']:.0%} overall (lift {e['lift']:.1f}x)")
        for w in p["warnings"]:
            print(f"  warning: {w}")
    if "outcome_spread" in out:
        sp = out["outcome_spread"]
        print(f"\n{a.outcome} ranges {sp['min']:.3g} .. {sp['max']:.3g} across clusters" + (
            "; segments barely differ on the outcome - check whether they need different actions"
            if sp["ratio"] and sp["ratio"] < 1.2 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
