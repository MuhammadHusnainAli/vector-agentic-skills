#!/usr/bin/env python3
"""Score whether a tabular dataset can support the ML problem you framed: GO, GO WITH RISKS or NO-GO.

Reads a CSV with a target column and checks four dimensions:
  volume    rows, labelled rows, minority-class count, events per candidate feature (EPV)
  labels    missing labels, constant labels, label share over time (drift) if --time-col
  signal    out-of-fold single-feature AUC (binary) or |Spearman| (numeric target) per column;
            the best one says whether there is anything to learn - and > 0.95 says "leak?"
  coverage  feature missingness, near-constant columns, duplicate rows, history span

Single-feature signal is computed out-of-fold (2 folds by row hash) so high-cardinality
columns do not look predictive just by memorising the target.

Usage:
    python feasibility_scan.py data.csv --target churned
    python feasibility_scan.py data.csv --target churned --time-col signup_date --drop customer_id
    python feasibility_scan.py data.csv --target price --json

Exit codes: 0 GO or GO WITH RISKS, 1 NO-GO, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
import zlib
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def is_missing(v):
    return v is None or v.strip().lower() in MISSING


def to_num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def ranks(xs):
    """Average ranks (1-based) handling ties."""
    order = sorted(range(len(xs)), key=xs.__getitem__)
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


def auc(scores, labels):
    """ROC-AUC via Mann-Whitney U; labels are 0/1."""
    pos = sum(labels)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    r = ranks(scores)
    u = sum(ri for ri, y in zip(r, labels) if y) - pos * (pos + 1) / 2
    return u / (pos * neg)


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return None if va == 0 or vb == 0 else cov / (va * vb)


def oof_category_scores(cats, y, folds):
    """Out-of-fold mean target per category (smoothed), so rare levels cannot memorise the label."""
    prior = sum(y) / len(y)
    out = [prior] * len(y)
    for f in (0, 1):
        stats = defaultdict(lambda: [0.0, 0])
        for c, t, k in zip(cats, y, folds):
            if k != f:
                stats[c][0] += t
                stats[c][1] += 1
        for i, (c, k) in enumerate(zip(cats, folds)):
            if k == f:
                s, n = stats.get(c, (0.0, 0))
                out[i] = (s + 10 * prior) / (n + 10)
    return out


def feature_signal(col, ys, binary, folds):
    """Return (signal, kind, note) for one feature column against the labelled target."""
    pairs = [(v, t, k) for v, t, k in zip(col, ys, folds) if not is_missing(v)]
    if len(pairs) < 20:
        return None, "sparse", "fewer than 20 non-missing values"
    vals = [p[0] for p in pairs]
    nums = [to_num(v) for v in vals]
    numeric = sum(x is not None for x in nums) / len(nums) > 0.95
    if binary:
        y = [int(p[1]) for p in pairs]
        if numeric:
            xs = [x if x is not None else 0.0 for x in nums]
            a = auc(xs, y)
            kind = "numeric"
        else:
            a = auc(oof_category_scores(vals, y, [p[2] for p in pairs]), y)
            kind = "categorical"
        if a is None:
            return None, kind, "one class only among non-missing rows"
        return abs(a - 0.5) * 2, kind, f"AUC {max(a, 1 - a):.3f}"
    y = [p[1] for p in pairs]
    if numeric:
        rho = spearman([x if x is not None else 0.0 for x in nums], y)
        kind = "numeric"
    else:
        means = oof_category_scores(vals, y, [p[2] for p in pairs])
        rho = spearman(means, y)
        kind = "categorical"
    return (None if rho is None else abs(rho)), kind, ("" if rho is None else f"spearman {rho:+.3f}")


def month_of(v):
    v = v.strip()
    return v[:7] if len(v) >= 7 and v[4] in "-/" else None


def scan(rows, header, target, drop, time_col):
    res = {"findings": [], "features": []}

    def add(dim, sev, msg):
        res["findings"].append({"dimension": dim, "severity": sev, "message": msg})

    labelled = [r for r in rows if not is_missing(r.get(target))]
    n, n_lab = len(rows), len(labelled)
    tvals = [r[target].strip() for r in labelled]
    distinct = Counter(tvals)
    tnums = [to_num(v) for v in tvals]
    binary = len(distinct) == 2
    numeric_target = not binary and all(x is not None for x in tnums) and len(distinct) > 2
    res.update(rows=n, labelled=n_lab, target_kind="binary" if binary else ("numeric" if numeric_target else "other"))
    feats = [c for c in header if c != target and c not in drop and c != time_col]
    res["candidate_features"] = len(feats)

    # ---- volume
    if n_lab < 100:
        add("volume", "blocking", f"only {n_lab} labelled rows")
    elif n_lab < 1000:
        add("volume", "risk", f"{n_lab} labelled rows: expect noisy estimates; use repeated CV and simple models")
    if binary:
        pos_label = min(distinct, key=distinct.get)
        minority = distinct[pos_label]
        y = [1 if v == pos_label else 0 for v in tvals]
        epv = minority / max(1, len(feats))
        res.update(minority_label=pos_label, minority=minority, minority_share=round(minority / n_lab, 4),
                   events_per_feature=round(epv, 2))
        if minority < 50:
            add("volume", "blocking", f"{minority} minority examples: too few to learn and to evaluate")
        elif minority < 200:
            add("volume", "risk", f"{minority} minority examples: confidence intervals will be wide")
        if epv < 10:
            add("volume", "risk", f"{epv:.1f} minority events per candidate feature (< 10): regularise strongly or "
                "cut features")
    elif numeric_target:
        y = tnums
    else:
        if len(distinct) <= 1:
            add("labels", "blocking", "target has one distinct value")
        else:
            add("labels", "risk", f"target has {len(distinct)} non-numeric classes; signal is scored one-vs-rest "
                "for the most frequent class")
        top = distinct.most_common(1)[0][0] if distinct else None
        y = [1 if v == top else 0 for v in tvals]
        binary = len(distinct) > 1

    # ---- labels
    if n and (n - n_lab) / n > 0.1:
        add("labels", "risk", f"{(n - n_lab) / n:.0%} of rows have no label: censored, filtered or not yet known?")
    if time_col and time_col in header and (binary or numeric_target):
        by_month = defaultdict(list)
        for r, t in zip(labelled, y):
            m = month_of(r.get(time_col, ""))
            if m:
                by_month[m].append(t)
        months = sorted(by_month)
        res["months"] = len(months)
        if months:
            res["span"] = f"{months[0]} .. {months[-1]}"
        if len(months) < 6:
            add("coverage", "risk", f"{len(months)} month(s) of history: cannot test stability over time")
        overall = sum(y) / len(y) if y else 0.0
        var = overall * (1 - overall) if binary else (
            sum((t - overall) ** 2 for t in y) / len(y) if y else 0.0)
        odd = []   # months whose mean label is > 3 standard errors from the overall mean
        for m in months:
            ts = by_month[m]
            if len(ts) >= 30 and var > 0 and abs(sum(ts) / len(ts) - overall) / math.sqrt(var / len(ts)) > 3:
                odd.append(f"{m} ({sum(ts) / len(ts):.3g})")
        if odd:
            add("labels", "risk", f"label mean shifts in {', '.join(odd[:4])} vs overall {overall:.3g}: definition "
                "change or drift; validate on the latest period")

    # ---- signal and coverage
    folds = [zlib.crc32(str(i).encode()) % 2 for i in range(n_lab)]
    best = 0.0
    for c in feats:
        col = [r.get(c, "") for r in labelled]
        miss = sum(is_missing(v) for v in col) / max(1, n_lab)
        present = [v for v in col if not is_missing(v)]
        top_share = Counter(present).most_common(1)[0][1] / len(present) if present else 1.0
        sig, kind, note = feature_signal(col, y, binary, folds)
        if binary and 0.02 < miss < 0.98:   # missingness itself can encode the label (filled only after the event)
            m_auc = auc([1.0 if is_missing(v) else 0.0 for v in col], y)
            if m_auc is not None and abs(m_auc - 0.5) * 2 > (sig or 0):
                sig, kind, note = abs(m_auc - 0.5) * 2, "missingness", f"is-missing AUC {max(m_auc, 1 - m_auc):.3f}"
        entry = {"feature": c, "kind": kind, "missing": round(miss, 3), "signal": None if sig is None else round(sig, 3),
                 "note": note}
        res["features"].append(entry)
        if miss > 0.5:
            add("coverage", "info", f"{c}: {miss:.0%} missing")
        if top_share > 0.99 and present:
            add("coverage", "info", f"{c}: one value in > 99% of rows (near-constant)")
        if sig is not None:
            if sig > 0.8:   # single-feature AUC > 0.9
                add("signal", "risk", f"{c}: single-feature signal {note} is suspiciously high - check for target "
                    "leakage before celebrating (target-leakage-detector)")
            else:
                best = max(best, sig)
    res["features"].sort(key=lambda e: -(e["signal"] or 0))
    res["best_signal"] = round(best, 3)
    if feats and best < 0.05:
        add("signal", "blocking", "no feature carries measurable signal on its own (best < 0.05); interactions may "
            "exist, but get better data or reframe before modelling")
    elif feats and best < 0.15:
        add("signal", "risk", f"weak single-feature signal (best {best:.2f}); expect modest lift over baseline")
    seen = Counter(tuple(r.get(c, "") for c in header) for r in rows)
    dups = sum(c - 1 for c in seen.values() if c > 1)
    if dups:
        add("coverage", "risk" if dups / n > 0.01 else "info", f"{dups} exact duplicate row(s)")

    sev = [f["severity"] for f in res["findings"]]
    res["verdict"] = "NO-GO" if "blocking" in sev else ("GO WITH RISKS" if "risk" in sev else "GO")
    return res


def main():
    ap = argparse.ArgumentParser(description="Assess ML feasibility of a CSV dataset for a target.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="CSV with header, or - for stdin")
    ap.add_argument("--target", required=True)
    ap.add_argument("--time-col", help="date/datetime column used to check history span and label drift")
    ap.add_argument("--drop", nargs="*", default=[], help="columns to ignore (IDs, known leaks)")
    ap.add_argument("--top", type=int, default=10, help="features to list (default 10)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = list(reader)
    except OSError as e:
        print(f"error: cannot read {a.csv}: {e}", file=sys.stderr)
        return 2
    if a.target not in header:
        print(f"error: target {a.target!r} not in columns: {', '.join(header)}", file=sys.stderr)
        return 2
    res = scan(rows, header, a.target, set(a.drop), a.time_col)
    if a.json:
        print(json.dumps(res, indent=2))
        return 1 if res["verdict"] == "NO-GO" else 0

    print(f"Feasibility: {res['verdict']}")
    line = f"rows {res['rows']}, labelled {res['labelled']}, target {res['target_kind']}, features {res['candidate_features']}"
    if "minority" in res:
        line += (f", minority {res['minority_label']!r} = {res['minority']} ({res['minority_share']:.1%}), "
                 f"EPV {res['events_per_feature']}")
    print(line)
    if "span" in res:
        print(f"history {res['span']} ({res['months']} months)")
    print(f"\nTop single-feature signal (out-of-fold; 0 = none, 1 = perfect):")
    for e in res["features"][:a.top]:
        sig = "-" if e["signal"] is None else f"{e['signal']:.3f}"
        print(f"  {e['feature']:<24} {e['kind']:<12} signal {sig:>6}  missing {e['missing']:5.1%}  {e['note']}")
    for dim in ("volume", "labels", "signal", "coverage"):
        for f in res["findings"]:
            if f["dimension"] == dim:
                print(f"[{f['severity']}] {dim}: {f['message']}")
    return 1 if res["verdict"] == "NO-GO" else 0


if __name__ == "__main__":
    sys.exit(main())
