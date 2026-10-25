#!/usr/bin/env python3
"""Filter-stage feature selection: drop empty, constant, redundant and signal-free columns, with reasons.

Steps (all model-free, standard library only):
  1. missing      drop columns missing in more than --max-missing of rows (default 0.95)
  2. constant     drop columns whose top value covers more than --max-top-share (default 0.995)
  3. id-like      drop text columns that are almost all unique
  4. signal       univariate signal vs the target: out-of-fold AUC (binary) or |Spearman| (numeric),
                  categoricals via smoothed out-of-fold level means; flags > 0.9 AUC as possible leak
  5. redundancy   |Spearman| between numeric features; groups with |rho| >= --corr (default 0.9)
                  keep the member with the strongest signal, drop the rest
  6. weak         with --min-signal, mark columns below it as "weak" (kept unless --drop-weak)

Output: a keep/drop table with reasons and the final list of kept columns (--keep-list prints
just the names, one per line, for scripting).

Usage:
    python filter_select.py data.csv --target churned --drop customer_id
    python filter_select.py data.csv --target price --corr 0.85 --min-signal 0.05 --drop-weak
    python filter_select.py data.csv --target churned --keep-list > features.txt

Exit codes: 0 done, 2 usage or read error.
"""

import argparse
import csv
import json
import math
import sys
import zlib
from collections import Counter, defaultdict

MISSING = {"", "na", "n/a", "nan", "null", "none", "?"}


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


def pearson(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    va = math.sqrt(sum((x - ma) ** 2 for x in a))
    vb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return 0.0 if not va or not vb else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb)


def auc_from_ranks(r, y):
    pos = sum(y)
    neg = len(y) - pos
    return None if not pos or not neg else (sum(ri for ri, t in zip(r, y) if t) - pos * (pos + 1) / 2) / (pos * neg)


def oof_means(vals, ys, prior):
    folds = [zlib.crc32(str(i).encode()) % 2 for i in range(len(vals))]
    out = [prior] * len(vals)
    for f in (0, 1):
        st = defaultdict(lambda: [0.0, 0])
        for v, y, k in zip(vals, ys, folds):
            if k != f:
                st[v][0] += y
                st[v][1] += 1
        for i, (v, k) in enumerate(zip(vals, folds)):
            if k == f:
                s, n = st.get(v, (0.0, 0))
                out[i] = (s + 10 * prior) / (n + 10)
    return out


def main():
    ap = argparse.ArgumentParser(description="Model-free feature filtering with reasons.", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--target", required=True)
    ap.add_argument("--drop", nargs="*", default=[], help="columns to exclude up front (IDs, time, leaks)")
    ap.add_argument("--max-missing", type=float, default=0.95)
    ap.add_argument("--max-top-share", type=float, default=0.995)
    ap.add_argument("--corr", type=float, default=0.9, help="|Spearman| threshold for redundancy (default 0.9)")
    ap.add_argument("--min-signal", type=float, default=0.0)
    ap.add_argument("--drop-weak", action="store_true")
    ap.add_argument("--keep-list", action="store_true")
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
    if a.target not in header or not rows:
        print(f"error: target {a.target!r} missing or no labelled rows", file=sys.stderr)
        return 2
    tvals = [r[a.target].strip() for r in rows]
    classes = Counter(tvals)
    binary = len(classes) == 2
    if binary:
        pos = min(classes, key=classes.get)
        y = [1.0 if v == pos else 0.0 for v in tvals]
    elif all(num(v) is not None for v in tvals):
        y = [float(v) for v in tvals]
    else:
        print("error: target must be binary or numeric", file=sys.stderr)
        return 2
    prior = sum(y) / len(y)
    ry = ranks(y)
    report, numeric_cols = {}, {}
    for c in header:
        if c == a.target or c in a.drop:
            continue
        vals = [(r.get(c) or "").strip() for r in rows]
        present = [v for v in vals if v.lower() not in MISSING]
        miss = 1 - len(present) / len(vals)
        e = {"feature": c, "missing": round(miss, 4), "status": "keep", "reason": ""}
        report[c] = e
        if miss > a.max_missing:
            e.update(status="drop", reason=f"{miss:.0%} missing")
            continue
        top = Counter(present).most_common(1)[0][1] / len(present)
        if top > a.max_top_share:
            e.update(status="drop", reason=f"near-constant (top value {top:.1%})")
            continue
        nums = [num(v) for v in vals]
        is_num = sum(x is not None for x in nums) >= 0.95 * len(present)
        if not is_num and len(set(present)) > 0.9 * len(present) and len(present) > 50:
            e.update(status="drop", reason="near-unique text (ID)")
            continue
        if is_num:
            med = sorted(x for x in nums if x is not None)[len([x for x in nums if x is not None]) // 2]
            filled = [x if x is not None else med for x in nums]
            rx = ranks(filled)
            numeric_cols[c] = rx
            if binary:
                au = auc_from_ranks(rx, y)
                sig = abs(au - 0.5) * 2
                e.update(kind="numeric", signal=round(sig, 4), detail=f"AUC {max(au, 1 - au):.3f}")
            else:
                rho = pearson(rx, ry)
                e.update(kind="numeric", signal=round(abs(rho), 4), detail=f"spearman {rho:+.3f}")
        else:
            enc = oof_means(vals, y, prior)
            re_ = ranks(enc)
            if binary:
                au = auc_from_ranks(re_, y)
                e.update(kind="categorical", signal=round(abs(au - 0.5) * 2, 4), detail=f"OOF AUC {max(au, 1 - au):.3f}")
            else:
                rho = pearson(re_, ry)
                e.update(kind="categorical", signal=round(abs(rho), 4), detail=f"OOF spearman {rho:+.3f}")
        if binary and e["signal"] > 0.8:
            e["reason"] = "possible leak: single-feature AUC > 0.9 - check when this field is written"
    # redundancy among kept numeric columns
    kept_num = [c for c in numeric_cols if report[c]["status"] == "keep"]
    pairs = []
    for i, c1 in enumerate(kept_num):
        for c2 in kept_num[i + 1:]:
            rho = pearson(numeric_cols[c1], numeric_cols[c2])
            if abs(rho) >= a.corr:
                pairs.append((c1, c2, rho))
    parent = {c: c for c in kept_num}

    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    for c1, c2, _ in pairs:
        parent[find(c1)] = find(c2)
    groups = defaultdict(list)
    for c in kept_num:
        groups[find(c)].append(c)
    redundant = []
    for members in groups.values():
        if len(members) > 1:
            best = max(members, key=lambda m: report[m].get("signal", 0))
            for m in members:
                if m != best:
                    rho = pearson(numeric_cols[m], numeric_cols[best])
                    report[m].update(status="drop", reason=f"redundant with {best} (|spearman| {abs(rho):.2f}); "
                                                           f"kept the stronger one")
            redundant.append({"kept": best, "dropped": [m for m in members if m != best]})
    for e in report.values():
        if e["status"] == "keep" and e.get("signal", 1) < a.min_signal:
            e.update(status="drop" if a.drop_weak else "weak", reason=f"signal {e['signal']:.3f} < {a.min_signal}")
    kept = [c for c, e in report.items() if e["status"] in ("keep", "weak")]
    if a.keep_list:
        print("\n".join(kept))
        return 0
    if a.json:
        print(json.dumps({"kept": kept, "redundant_groups": redundant, "features": list(report.values())}, indent=2))
        return 0
    print(f"Filter selection for {a.target!r} ({'binary' if binary else 'numeric'} target, {len(rows)} rows): "
          f"{len(kept)} kept of {len(report)}")
    print(f"{'feature':<24} {'status':<6} {'signal':>7} {'missing':>8}  detail / reason")
    for e in sorted(report.values(), key=lambda e: (e["status"] != "keep", -(e.get("signal") or 0))):
        sig = f"{e['signal']:.3f}" if "signal" in e else "-"
        print(f"{e['feature']:<24} {e['status']:<6} {sig:>7} {e['missing']:>8.1%}  {e.get('detail', '')}"
              f"{'  ' + e['reason'] if e['reason'] else ''}")
    print("\nFilter results are a first pass: confirm with model-based selection inside CV (permutation importance, "
          "L1, RFECV) before dropping signal for good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
