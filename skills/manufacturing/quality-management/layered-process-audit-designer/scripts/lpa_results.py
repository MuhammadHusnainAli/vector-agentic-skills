#!/usr/bin/env python3
"""Analyse layered process audit results: compliance, repeat failures, stale questions and layer gaps.

Results CSV columns: date, layer, area, auditor, question_id, result (pass/fail/na), corrected (yes/no)
Optional column: question (text).

Reports:
  compliance % by area, by layer and by question
  LR001 high    repeat failure: same question fails in the same area >= --repeat times -> open a CAPA
  LR002 medium  failure not corrected on the spot and no follow-up recorded
  LR003 medium  layer gap: layer 1 pass rate is >= 15 points above layers 2-3 in an area (check rigour)
  LR004 low     question passed every time over >= --stale audits -> rotate or retire it

Usage:
    python lpa_results.py results.csv
    python lpa_results.py results.csv --repeat 3 --stale 20

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import csv
import sys
from collections import defaultdict


def pct(p, n):
    return 100 * p / n if n else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="results CSV, or - for stdin")
    ap.add_argument("--repeat", type=int, default=3, help="failures of one question in one area that trigger LR001")
    ap.add_argument("--stale", type=int, default=20, help="all-pass answers after which a question is stale")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    need = {"layer", "area", "question_id", "result"}
    if not rows or not need <= set(rows[0]):
        print(f"error: CSV needs columns {', '.join(sorted(need))}", file=sys.stderr)
        return 2
    by = {k: defaultdict(lambda: [0, 0]) for k in ("area", "layer", "question_id")}
    area_layer = defaultdict(lambda: [0, 0])
    fails = defaultdict(int)
    text = {}
    findings = []
    for r in rows:
        res = (r["result"] or "").strip().lower()
        if res not in ("pass", "fail"):
            continue
        ok = res == "pass"
        q, area, layer = r["question_id"].strip(), r["area"].strip(), r["layer"].strip()
        text[q] = (r.get("question") or "").strip()
        for k, v in (("area", area), ("layer", layer), ("question_id", q)):
            by[k][v][0] += ok
            by[k][v][1] += 1
        area_layer[(area, "1" if layer == "1" else "2+")][0] += ok
        area_layer[(area, "1" if layer == "1" else "2+")][1] += 1
        if not ok:
            fails[(q, area)] += 1
            if (r.get("corrected") or "").strip().lower() not in ("yes", "y", "true"):
                findings.append(("LR002", "medium", f"{r.get('date', '')} {area} {q}: failed, not corrected on the spot - record the follow-up action"))
    total_p = sum(v[0] for v in by["area"].values())
    total_n = sum(v[1] for v in by["area"].values())
    print(f"Overall compliance: {pct(total_p, total_n):.1f}% ({total_n} answers)\n")
    for k, label in (("area", "Area"), ("layer", "Layer")):
        print(f"{label:<14}{'Answers':>8}{'Compliance':>12}")
        for v, (p, n) in sorted(by[k].items()):
            print(f"{v:<14}{n:>8}{pct(p, n):>11.1f}%")
        print()
    print(f"{'Question':<10}{'Answers':>8}{'Compliance':>12}  Text")
    for q, (p, n) in sorted(by["question_id"].items(), key=lambda kv: pct(*kv[1])):
        print(f"{q:<10}{n:>8}{pct(p, n):>11.1f}%  {text.get(q, '')[:60]}")
        if p == n and n >= a.stale:
            findings.append(("LR004", "low", f"{q}: passed all {n} times - rotate in a new question on a current risk"))
    for (q, area), n in sorted(fails.items()):
        if n >= a.repeat:
            findings.append(("LR001", "high", f"{q} failed {n} times in {area} - systemic: open a corrective action"))
    for area in sorted({k[0] for k in area_layer}):
        l1, l2 = area_layer.get((area, "1")), area_layer.get((area, "2+"))
        if l1 and l2 and l1[1] and l2[1] and pct(*l1) - pct(*l2) >= 15:
            findings.append(("LR003", "medium", f"{area}: layer 1 finds {pct(*l1):.0f}% compliance, higher layers {pct(*l2):.0f}% - coach layer 1 on what to check"))
    order = {"high": 0, "medium": 1, "low": 2}
    print()
    for code, sev, msg in sorted(findings, key=lambda f: (order[f[1]], f[0])):
        print(f"{code} [{sev}] {msg}")
    return 1 if any(f[1] == "high" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
