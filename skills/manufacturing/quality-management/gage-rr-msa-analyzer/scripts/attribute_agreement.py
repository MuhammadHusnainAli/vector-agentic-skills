#!/usr/bin/env python3
"""Attribute agreement analysis (AIAG MSA 4th ed. 'cross-tab' method) for go/no-go and visual inspection.

CSV columns: part, appraiser, trial, result, and reference (known standard per part; optional but needed for
effectiveness, miss rate, false alarm and kappa vs standard). Results are any two labels, e.g. accept/reject;
--bad names the nonconforming label (default 'reject').

Per appraiser:
  within agreement  % of parts rated the same in every trial
  effectiveness     % of decisions matching the reference           (>= 90% acceptable, >= 80% marginal)
  miss rate         % of bad-part decisions rated good               (<= 2% acceptable, <= 5% marginal)
  false alarm rate  % of good-part decisions rated bad               (<= 5% acceptable, <= 10% marginal)
  kappa vs standard (Cohen)                                          (> 0.75 good, 0.40-0.75 marginal, < 0.40 poor)
System: % of parts where all appraisers agree with each other and with the reference.

Usage:
    python attribute_agreement.py attribute.csv
    python attribute_agreement.py attribute.csv --bad NOK

Exit codes: 0 every appraiser acceptable, 1 any marginal or unacceptable, 2 usage or data error.
"""

import argparse
import csv
import sys
from collections import defaultdict


def kappa(pairs, labels):
    n = len(pairs)
    if not n:
        return float("nan")
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def grade(eff, miss, fa, k):
    if eff >= 90 and miss <= 2 and fa <= 5 and k > 0.75:
        return "acceptable"
    if eff >= 80 and miss <= 5 and fa <= 10 and k >= 0.40:
        return "marginal"
    return "unacceptable"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--bad", default="reject", help="label for a nonconforming decision (default reject)")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"part", "appraiser", "result"} <= set(rows[0]):
        print("error: CSV needs part, appraiser, trial, result (and reference) columns", file=sys.stderr)
        return 2
    bad = a.bad.strip().lower()
    by = defaultdict(lambda: defaultdict(list))
    ref = {}
    for r in rows:
        p, ap_ = r["part"].strip(), r["appraiser"].strip()
        by[ap_][p].append(r["result"].strip().lower())
        if (r.get("reference") or "").strip():
            ref[p] = r["reference"].strip().lower()
    labels = sorted({v for d in by.values() for vs in d.values() for v in vs} | set(ref.values()))
    if len(labels) > 2:
        print(f"error: expected two result labels, found {', '.join(labels)}", file=sys.stderr)
        return 2
    if bad not in labels:
        print(f"error: --bad {a.bad!r} is not one of the labels {', '.join(labels)}", file=sys.stderr)
        return 2
    parts = sorted({p for d in by.values() for p in d}, key=lambda x: (len(x), x))
    print(f"Attribute agreement: {len(parts)} parts, {len(by)} appraisers, labels {'/'.join(labels)}\n")
    head = f"{'Appraiser':<12}{'Within':>8}" + (f"{'Effective':>11}{'Miss':>7}{'False al.':>11}{'Kappa':>8}  Grade" if ref else "")
    print(head)
    worst = "acceptable"
    for name, d in sorted(by.items()):
        within = 100 * sum(len(set(v)) == 1 for v in d.values()) / len(d)
        if not ref:
            print(f"{name:<12}{within:>7.0f}%")
            continue
        pairs = [(v, ref[p]) for p, vs in d.items() if p in ref for v in vs]
        eff = 100 * sum(x == y for x, y in pairs) / len(pairs)
        bad_dec = [x for x, y in pairs if y == bad]
        good_dec = [x for x, y in pairs if y != bad]
        miss = 100 * sum(x != bad for x in bad_dec) / len(bad_dec) if bad_dec else 0.0
        fa = 100 * sum(x == bad for x in good_dec) / len(good_dec) if good_dec else 0.0
        k = kappa(pairs, labels)
        g = grade(eff, miss, fa, k)
        worst = g if ["acceptable", "marginal", "unacceptable"].index(g) > ["acceptable", "marginal", "unacceptable"].index(worst) else worst
        print(f"{name:<12}{within:>7.0f}%{eff:>10.0f}%{miss:>6.1f}%{fa:>10.1f}%{k:>8.2f}  {g}")
    all_agree = sum(len({v for d in by.values() for v in d.get(p, [])}) == 1 for p in parts)
    print(f"\nAll appraisers agree with each other on {100 * all_agree / len(parts):.0f}% of parts", end="")
    if ref:
        sys_ok = sum({v for d in by.values() for v in d.get(p, [])} == {ref.get(p)} for p in parts)
        print(f"; with the reference on {100 * sys_ok / len(parts):.0f}%")
    else:
        print("; add a reference column to measure effectiveness, miss and false-alarm rates")
    if ref:
        print(f"Measurement system: {worst.upper()}")
    return 0 if ref and worst == "acceptable" else 1


if __name__ == "__main__":
    sys.exit(main())
