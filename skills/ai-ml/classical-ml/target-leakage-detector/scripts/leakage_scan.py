#!/usr/bin/env python3
"""Scan a training table for target leakage: features that know the answer.

Checks (codes, severity):
  LD001 high    single-feature out-of-fold AUC > --auc (default 0.9) / |Spearman| > 0.95 for numeric targets
  LD002 high    missingness of a column predicts the target (is-missing AUC > 0.85): filled after the event
  LD003 high    a datetime column is later than the prediction time (--time-col) in > 1% of rows
  LD004 medium  column name suggests an outcome or post-event field (status, reason, refund, chargeback,
                cancel, closed, resolution, outcome, result, final, settled, approved...)
  LD005 medium  row order or a numeric ID predicts the target (AUC of the row index / ID > 0.65):
                data sorted by outcome, or IDs assigned after labelling
  LD006 medium  a feature is (almost) a deterministic function of the target: one value per class
                (categorical) or |Spearman| > 0.98 (numeric target)
  LD007 low     identical feature rows with different labels or duplicated rows (label noise / joins)
  LD008 info    a feature has much stronger signal in the oldest than the newest third of rows
                (--time-col): backfilled or overwritten history

Usage:
    python leakage_scan.py data.csv --target churned
    python leakage_scan.py data.csv --target churned --time-col score_date --drop customer_id
    python leakage_scan.py data.csv --target price --json

Exit codes: 0 no high findings, 1 high findings, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import re
import sys
import zlib
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}
OUTCOME_NAMES = re.compile(r"(status|reason|refund|chargeback|cancel|closed|close_date|resolution|resolved|outcome|"
                           r"result|final|settled|approved|denied|decision|disposition|churn|default|paid_off|"
                           r"written_off|collection|_after|post_|label|target|response)", re.I)
DATE_RE = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def ranks(xs):
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


def auc(s, y):
    pos = sum(y)
    neg = len(y) - pos
    if not pos or not neg:
        return None
    r = ranks(s)
    return (sum(ri for ri, t in zip(r, y) if t) - pos * (pos + 1) / 2) / (pos * neg)


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((x - mb) ** 2 for x in rb))
    return 0.0 if not va or not vb else sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (va * vb)


def oof_level_scores(vals, y, prior):
    folds = [zlib.crc32(str(i).encode()) % 2 for i in range(len(vals))]
    out = [prior] * len(vals)
    for f in (0, 1):
        st = defaultdict(lambda: [0.0, 0])
        for v, t, k in zip(vals, y, folds):
            if k != f:
                st[v][0] += t
                st[v][1] += 1
        for i, (v, k) in enumerate(zip(vals, folds)):
            if k == f:
                s, n = st.get(v, (0.0, 0))
                out[i] = (s + 5 * prior) / (n + 5)
    return out


def signal(vals, y, binary, prior):
    """(strength 0..1, description) for one column, out-of-fold for categoricals."""
    idx = [i for i, v in enumerate(vals) if v.lower() not in MISSING]
    if len(idx) < 20:
        return None, ""
    xs = [num(vals[i]) for i in idx]
    ys = [y[i] for i in idx]
    numeric = sum(x is not None for x in xs) / len(xs) > 0.95
    if numeric:
        s = [x if x is not None else 0.0 for x in xs]
    else:
        s = oof_level_scores([vals[i] for i in idx], ys, prior)
    if binary:
        a = auc(s, ys)
        return (None, "") if a is None else (max(a, 1 - a), f"AUC {max(a, 1 - a):.3f}")
    rho = spearman(s, ys)
    return abs(rho), f"spearman {rho:+.3f}"


def main():
    ap = argparse.ArgumentParser(description="Scan a training table for target leakage.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--time-col", help="prediction-time column (scoring date / event time)")
    ap.add_argument("--drop", nargs="*", default=[], help="columns to skip (keys you already know about)")
    ap.add_argument("--auc", type=float, default=0.9, help="single-feature AUC threshold for LD001 (default 0.9)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        with (sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")) as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = [r for r in reader if (r.get(a.target) or "").strip().lower() not in MISSING]
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if a.target not in header or len(rows) < 30:
        print(f"error: target {a.target!r} missing or fewer than 30 labelled rows", file=sys.stderr)
        return 2
    if a.time_col and a.time_col not in header:
        print(f"error: time column {a.time_col!r} not found", file=sys.stderr)
        return 2
    tv = [r[a.target].strip() for r in rows]
    classes = Counter(tv)
    binary = len(classes) == 2
    if binary:
        pos = min(classes, key=classes.get)
        y = [1.0 if v == pos else 0.0 for v in tv]
    elif all(num(v) is not None for v in tv):
        y = [float(v) for v in tv]
    else:
        print("error: target must be binary or numeric", file=sys.stderr)
        return 2
    prior = sum(y) / len(y)
    findings = []

    def add(code, sev, col, msg):
        findings.append({"code": code, "severity": sev, "column": col, "message": msg})

    feats = [c for c in header if c not in (a.target, a.time_col) and c not in a.drop]
    # LD005: row order
    if binary:
        ra = auc(list(range(len(rows))), y)
        if ra is not None and max(ra, 1 - ra) > 0.65:
            add("LD005", "medium", "(row order)", f"row position predicts the target (AUC {max(ra, 1 - ra):.2f}): the file "
                "is sorted by outcome or time; shuffle or split by time deliberately")
    for c in feats:
        vals = [(r.get(c) or "").strip() for r in rows]
        present = [v for v in vals if v.lower() not in MISSING]
        if not present:
            continue
        miss = 1 - len(present) / len(vals)
        if OUTCOME_NAMES.search(c):
            add("LD004", "medium", c, "name suggests an outcome or post-event field; confirm it is known at prediction time")
        if binary and 0.01 < miss < 0.99:
            m = auc([1.0 if v.lower() in MISSING else 0.0 for v in vals], y)
            if m is not None and max(m, 1 - m) > 0.85:
                add("LD002", "high", c, f"missingness predicts the target (is-missing AUC {max(m, 1 - m):.3f}): the field "
                    "is filled because the outcome happened")
        is_date = sum(bool(DATE_RE.match(v)) for v in present) / len(present) > 0.9
        if is_date and a.time_col:
            later = sum(1 for r, v in zip(rows, vals) if v and DATE_RE.match(v) and v[:19] > (r.get(a.time_col) or "")[:19])
            share = later / len(present)
            if share > 0.01:
                add("LD003", "high", c, f"{share:.0%} of values are later than {a.time_col}: information from the future")
            continue
        if is_date:
            continue
        sig, desc = signal(vals, y, binary, prior)
        if sig is None:
            continue
        nums = [num(v) for v in present]
        numeric = sum(x is not None for x in nums) / len(nums) > 0.95
        if binary and sig > a.auc:
            add("LD001", "high", c, f"single feature {desc} > {a.auc}: almost certainly leakage or a proxy of the label")
        elif not binary and sig > 0.95:
            add("LD001", "high", c, f"single feature {desc}: nearly the target itself")
        if not numeric and binary:
            by_level = defaultdict(set)
            for v, t in zip(vals, y):
                if v.lower() not in MISSING:
                    by_level[v].add(t)
            pure = sum(1 for s in by_level.values() if len(s) == 1)
            if len(by_level) > 1 and pure == len(by_level) and len(by_level) <= 0.5 * len(present):
                add("LD006", "medium", c, f"every level of {c} maps to a single class: deterministic of the target")
        if numeric and not binary and sig > 0.98:
            add("LD006", "medium", c, "near-perfect rank correlation with the target: derived from it?")
        if numeric and binary and re.search(r"(^id$|_id$|^id_|number|_no$)", c, re.I):
            if sig > 0.65:
                add("LD005", "medium", c, f"identifier predicts the target ({desc}): IDs assigned in outcome order")
        if a.time_col and sig > 0.65:
            order = sorted(range(len(rows)), key=lambda i: rows[i].get(a.time_col, ""))
            third = len(order) // 3
            old, new = order[:third], order[-third:]
            s_old, _ = signal([vals[i] for i in old], [y[i] for i in old], binary, prior)
            s_new, _ = signal([vals[i] for i in new], [y[i] for i in new], binary, prior)
            if s_old and s_new and s_old - s_new > 0.15:
                add("LD008", "info", c, f"signal {s_old:.2f} in the oldest third vs {s_new:.2f} in the newest: "
                    "history may be backfilled or overwritten")
    seen = defaultdict(set)
    dup = 0
    for r, t in zip(rows, tv):
        key = tuple((r.get(c) or "").strip() for c in feats)
        if key in seen:
            dup += 1
        seen[key].add(t)
    conflict = sum(1 for s in seen.values() if len(s) > 1)
    if conflict:
        add("LD007", "low", "(rows)", f"{conflict} identical feature vectors carry different labels (label noise, or "
            "the distinguishing information is missing)")
    if dup:
        add("LD007", "low", "(rows)", f"{dup} duplicated feature rows: duplicates across train/test inflate scores")
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["code"], f["column"]))
    high = sum(f["severity"] == "high" for f in findings)
    if a.json:
        print(json.dumps({"rows": len(rows), "target": a.target, "findings": findings}, indent=2))
        return 1 if high else 0
    print(f"Leakage scan of {len(feats)} feature(s) on {len(rows)} labelled rows (target {a.target!r})")
    if not findings:
        print("No leakage signals found. Still confirm every source's write time with its owner.")
    for f in findings:
        print(f"{f['code']} [{f['severity']}] {f['column']}: {f['message']}")
    print(f"\n{len(findings)} finding(s), {high} high")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
