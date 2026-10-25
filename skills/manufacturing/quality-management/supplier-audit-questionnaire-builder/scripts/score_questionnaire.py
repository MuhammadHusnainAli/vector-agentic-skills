#!/usr/bin/env python3
"""Score a completed supplier questionnaire (CSV from questionnaire.py with the score column filled).

Section score = points / (3 x answered questions); 'na' is excluded. The overall score weights sections by
section_weight (re-normalised over the sections that have answers).

Decision:
  NOT APPROVED (knockout)   any knockout question scored 0 or 1
  APPROVED                  overall >= 85% and every section >= 60%
  CONDITIONAL               overall >= 70%: approve with an improvement plan for sections below 70%
  NOT APPROVED              otherwise
  INCOMPLETE                more than 10% of questions unanswered

Usage:
    python score_questionnaire.py completed.csv
    python score_questionnaire.py completed.csv --approve 90 --conditional 75

Exit codes: 0 approved, 1 conditional / not approved / incomplete, 2 read or format error.
"""

import argparse
import csv
import sys
from collections import OrderedDict

POINTS = {"0": 0, "1": 1, "2": 2, "3": 3, "no": 0, "partly": 1, "partial": 1, "mostly": 2, "yes": 3, "fully": 3}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="completed questionnaire CSV, or - for stdin")
    ap.add_argument("--approve", type=float, default=85, help="overall %% for approval (default 85)")
    ap.add_argument("--conditional", type=float, default=70, help="overall %% for conditional approval (default 70)")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    need = {"id", "section", "section_weight", "knockout", "score"}
    if not rows or not need <= set(rows[0]):
        print(f"error: CSV needs columns {', '.join(sorted(need))} (generate it with questionnaire.py --csv)", file=sys.stderr)
        return 2
    secs = OrderedDict()
    blank, bad, ko_fail = [], [], []
    for r in rows:
        s = secs.setdefault(r["section"], {"w": float(r["section_weight"] or 0), "pts": 0, "n": 0})
        v = (r["score"] or "").strip().lower()
        if v == "na":
            continue
        if v == "":
            blank.append(r["id"])
            continue
        if v not in POINTS:
            bad.append(f"{r['id']}={v}")
            continue
        s["pts"] += POINTS[v]
        s["n"] += 1
        if (r["knockout"] or "").strip().lower() in ("yes", "y", "ko", "true") and POINTS[v] <= 1:
            ko_fail.append(f"{r['id']} {r.get('question', '')[:70]} (scored {POINTS[v]})")
    if bad:
        print(f"error: invalid scores (use 0-3, na): {', '.join(bad)}", file=sys.stderr)
        return 2
    scored = {k: v for k, v in secs.items() if v["n"]}
    wsum = sum(v["w"] for v in scored.values()) or 1
    print(f"{'Section':<46}{'Answered':>9}{'Score':>8}")
    weak = []
    for name, v in secs.items():
        if not v["n"]:
            print(f"{name:<46}{0:>9}{'-':>8}")
            continue
        pct = 100 * v["pts"] / (3 * v["n"])
        v["pct"] = pct
        if pct < 70:
            weak.append((name, pct))
        print(f"{name:<46}{v['n']:>9}{pct:>7.0f}%")
    overall = sum(v["pct"] * v["w"] for v in scored.values()) / wsum if scored else 0
    print(f"\nOverall weighted score: {overall:.1f}%")
    if len(blank) > 0.1 * len(rows):
        decision = "INCOMPLETE"
    elif ko_fail:
        decision = "NOT APPROVED (knockout)"
    elif overall >= a.approve and all(v["pct"] >= 60 for v in scored.values()):
        decision = "APPROVED"
    elif overall >= a.conditional:
        decision = "CONDITIONAL"
    else:
        decision = "NOT APPROVED"
    print(f"Decision: {decision}")
    for k in ko_fail:
        print(f"  knockout failed: {k}")
    if blank:
        print(f"  unanswered: {', '.join(blank)}")
    if decision != "APPROVED" and weak:
        print("Improvement plan needed for: " + ", ".join(f"{n} ({p:.0f}%)" for n, p in weak))
    return 0 if decision == "APPROVED" else 1


if __name__ == "__main__":
    sys.exit(main())
