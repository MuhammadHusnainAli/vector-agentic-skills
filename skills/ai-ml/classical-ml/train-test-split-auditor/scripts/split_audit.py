#!/usr/bin/env python3
"""Audit a train/test (or train/validation, or train/production) split for leakage and shift.

Checks (codes):
  SA001 high    exact duplicate feature rows present in both sets (label ignored)
  SA002 high    --id-col / --group-col values present in both sets (entity leakage)
  SA003 high    with --time-col and --expect forward: test rows earlier than the latest training row
  SA004 medium  feature drift: PSI > 0.25 (numeric: train deciles; categorical: level shares), with KS for numerics
  SA005 medium  a single feature separates train from test (univariate "adversarial" AUC > 0.7)
  SA006 medium  target distribution differs (rate / mean outside the train CI, or PSI > 0.25)
  SA007 low     categories in test never seen in train (share of test rows affected)
  SA008 low     missing-value share differs by > 10 points
  SA009 info    size and ratio of the sets

PSI = sum((p_test - p_train) * ln(p_test / p_train)) over bins; < 0.1 stable, 0.1-0.25 moderate, > 0.25 large.

Usage:
    python split_audit.py train.csv test.csv --target churned --id-col customer_id
    python split_audit.py train.csv test.csv --target churned --time-col signup_date --expect forward
    python split_audit.py train.csv prod_sample.csv --drop customer_id --json

Exit codes: 0 no high findings, 1 high findings, 2 usage or read error.
"""

import argparse
import csv
import datetime as dt
import json
import math
import sys
from collections import Counter

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        rd = csv.DictReader(fh)
        return rd.fieldnames or [], list(rd)


def num(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        pass
    if isinstance(v, str) and len(v) >= 10 and v[4] in "-/" and v[7] in "-/":
        try:                                  # ISO-like dates compare as day numbers, not as categories
            return float(dt.date(int(v[:4]), int(v[5:7]), int(v[8:10])).toordinal())
        except ValueError:
            return None
    return None


def psi(p, q):
    eps = 1e-4
    return sum((b - a) * math.log((b + eps) / (a + eps)) for a, b in zip(p, q))


def ks(a, b):
    a, b = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    while i < len(a) and j < len(b):
        if a[i] <= b[j]:
            i += 1
        else:
            j += 1
        d = max(d, abs(i / len(a) - j / len(b)))
    return d


def auc(s, y):
    pairs = sorted(zip(s, y))
    pos = sum(y)
    neg = len(y) - pos
    rank, i = [0.0] * len(pairs), 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][0] == pairs[i][0]:
            j += 1
        for k in range(i, j + 1):
            rank[k] = (i + j) / 2 + 1
        i = j + 1
    a = (sum(r for r, (_, t) in zip(rank, pairs) if t) - pos * (pos + 1) / 2) / (pos * neg)
    return max(a, 1 - a)


def main():
    ap = argparse.ArgumentParser(description="Audit a train/test split for leakage and drift.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("train")
    ap.add_argument("test")
    ap.add_argument("--target")
    ap.add_argument("--id-col", help="row/entity identifier that must not appear in both sets")
    ap.add_argument("--group-col", help="entity whose rows must stay on one side")
    ap.add_argument("--time-col")
    ap.add_argument("--expect", choices=["forward", "random"], default="random",
                    help="forward: test must come after train in time")
    ap.add_argument("--drop", nargs="*", default=[])
    ap.add_argument("--psi-max", type=float, default=0.25)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        h1, tr = read(a.train)
        h2, te = read(a.test)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    common = [c for c in h1 if c in h2]
    for c in (a.target, a.id_col, a.group_col, a.time_col):
        if c and c not in common:
            print(f"error: column {c!r} must exist in both files", file=sys.stderr)
            return 2
    findings = []

    def add(code, sev, col, msg):
        findings.append({"code": code, "severity": sev, "column": col, "message": msg})

    add("SA009", "info", "(sets)", f"train {len(tr)} rows, test {len(te)} rows (test share "
        f"{len(te) / max(1, len(tr) + len(te)):.1%}); {len(set(h1) ^ set(h2))} column(s) not shared")
    feats = [c for c in common if c not in (a.target, a.id_col, a.group_col, a.time_col) and c not in a.drop]
    key = lambda r: tuple((r.get(c) or "").strip() for c in feats)
    tr_keys = Counter(key(r) for r in tr)
    dup = sum(1 for r in te if key(r) in tr_keys)
    if dup:
        add("SA001", "high", "(rows)", f"{dup} test row(s) ({dup / len(te):.1%}) have an identical feature row in train: "
            "the model has seen them (dedupe or group duplicates on one side)")
    for col in (a.id_col, a.group_col):
        if col:
            s1 = {r[col] for r in tr}
            shared = {r[col] for r in te if r[col] in s1}
            if shared:
                rows_aff = sum(1 for r in te if r[col] in shared)
                add("SA002", "high", col, f"{len(shared)} {col} value(s) in both sets, covering {rows_aff} test rows "
                    f"({rows_aff / len(te):.1%}): split by {col} (grouped split)")
    if a.time_col:
        t1 = sorted(r[a.time_col] for r in tr if r[a.time_col])
        t2 = sorted(r[a.time_col] for r in te if r[a.time_col])
        if t1 and t2:
            early = sum(1 for v in t2 if v <= t1[-1])
            if a.expect == "forward" and early:
                add("SA003", "high", a.time_col, f"{early} test row(s) ({early / len(t2):.1%}) are not after the last "
                    f"training time {t1[-1]}: train and test overlap in time")
            elif a.expect == "random" and t2[0] > t1[-1]:
                add("SA009", "info", a.time_col, "test is entirely after train (a forward split)")
    for c in feats + ([a.target] if a.target else []):
        v1 = [(r.get(c) or "").strip() for r in tr]
        v2 = [(r.get(c) or "").strip() for r in te]
        m1 = sum(v.lower() in MISSING for v in v1) / len(v1)
        m2 = sum(v.lower() in MISSING for v in v2) / len(v2)
        if abs(m1 - m2) > 0.1 and c != a.target:
            add("SA008", "low", c, f"missing share {m1:.0%} in train vs {m2:.0%} in test")
        p1 = [v for v in v1 if v.lower() not in MISSING]
        p2 = [v for v in v2 if v.lower() not in MISSING]
        if not p1 or not p2:
            continue
        n1 = [num(v) for v in p1]
        n2 = [num(v) for v in p2]
        numeric = all(x is not None for x in n1 + n2) and len(set(p1)) > 10
        if numeric:
            srt = sorted(n1)
            edges = sorted({srt[int(len(srt) * q / 10)] for q in range(1, 10)})
            def bins(xs):
                cnt = Counter(sum(1 for e in edges if x >= e) for x in xs)
                return [cnt.get(b, 0) / len(xs) for b in range(len(edges) + 1)]
            pv = psi(bins(n1), bins(n2))
            kv = ks(n1, n2)
            adv = auc(n1 + n2, [0] * len(n1) + [1] * len(n2))
            detail = f"PSI {pv:.3f}, KS {kv:.3f}"
        else:
            c1, c2 = Counter(p1), Counter(p2)
            levels = sorted(set(c1) | set(c2))
            pv = psi([c1[l] / len(p1) for l in levels], [c2[l] / len(p2) for l in levels])
            unseen = sum(n for l, n in c2.items() if l not in c1)
            if unseen and c != a.target:
                add("SA007", "low", c, f"{unseen} test row(s) ({unseen / len(p2):.1%}) have levels unseen in train")
            rate = {l: c1[l] / len(p1) for l in c1}
            adv = auc([rate.get(v, 0.0) for v in p1] + [rate.get(v, 0.0) for v in p2], [0] * len(p1) + [1] * len(p2)) \
                if len(levels) > 1 else 0.5
            detail = f"PSI {pv:.3f}"
        if c == a.target:
            if pv > a.psi_max or (numeric is False and len(set(p1)) == 2 and _rate_shift(p1, p2)):
                add("SA006", "medium", c, f"target distribution shifted ({detail}): rates/means differ between sets")
            continue
        if pv > a.psi_max:
            add("SA004", "medium", c, f"drift: {detail}")
        if adv > 0.7 and c not in (a.id_col,):
            add("SA005", "medium", c, f"{c} alone separates train from test (AUC {adv:.2f}): a time-ordered or "
                "selected split, or a feature that encodes the split")
    order = {"high": 0, "medium": 1, "low": 2, "info": 3}
    findings.sort(key=lambda f: (order[f["severity"]], f["code"]))
    high = sum(f["severity"] == "high" for f in findings)
    if a.json:
        print(json.dumps({"findings": findings, "high": high}, indent=2))
        return 1 if high else 0
    for f in findings:
        print(f"{f['code']} [{f['severity']}] {f['column']}: {f['message']}")
    print(f"\n{len(findings)} finding(s), {high} high")
    return 1 if high else 0


def _rate_shift(p1, p2):
    """Binary target: is the test positive rate outside train rate +/- 3 standard errors?"""
    lv = sorted(set(p1) | set(p2))
    pos = min(lv, key=lambda l: p1.count(l))
    r1, r2 = p1.count(pos) / len(p1), p2.count(pos) / len(p2)
    se = math.sqrt(max(r1 * (1 - r1), 1e-9) / len(p2))
    return abs(r2 - r1) > 3 * se


if __name__ == "__main__":
    sys.exit(main())
