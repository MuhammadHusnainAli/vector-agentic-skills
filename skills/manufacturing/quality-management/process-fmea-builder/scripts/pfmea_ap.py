#!/usr/bin/env python3
"""Rate a PFMEA with AIAG-VDA Action Priority (AP), legacy RPN, and check the ratings for common errors.

CSV columns: step, function, failure_mode, effect, S, cause, prevention, O, detection, D,
             special (CC/SC/blank), action, owner, due

Checks:
  FM001 high    AP = H without a recommended action (AIAG-VDA: action required or documented justification)
  FM002 high    severity 9-10 with no prevention or detection control
  FM003 high    rating missing or outside 1-10
  FM004 medium  D <= 3 claimed without an error-proofing / automatic detection control (rating inflation)
  FM005 medium  O <= 2 claimed without a prevention control
  FM006 medium  severity 9-10 not marked as a special characteristic (CC) - confirm with the customer's rules
  FM007 low     action without owner or due date

Usage:
    python pfmea_ap.py pfmea.csv
    python pfmea_ap.py pfmea.csv --sort rpn
    python pfmea_ap.py pfmea.csv --csv > pfmea_rated.csv      # adds AP and RPN columns

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import csv
import re
import sys

# AIAG-VDA FMEA Handbook (2019) action priority, rows by S band and O band; columns D 7-10, 5-6, 2-4, 1
AP_TABLE = {
    "9-10": {"8-10": "HHHH", "6-7": "HHHH", "4-5": "HHHM", "2-3": "HMLL", "1": "LLLL"},
    "7-8": {"8-10": "HHHH", "6-7": "HHHM", "4-5": "HMMM", "2-3": "MMLL", "1": "LLLL"},
    "4-6": {"8-10": "HHMM", "6-7": "MMML", "4-5": "MLLL", "2-3": "LLLL", "1": "LLLL"},
    "2-3": {"8-10": "MMLL", "6-7": "LLLL", "4-5": "LLLL", "2-3": "LLLL", "1": "LLLL"},
    "1": {"8-10": "LLLL", "6-7": "LLLL", "4-5": "LLLL", "2-3": "LLLL", "1": "LLLL"},
}
ERROR_PROOF = re.compile(r"poka|error[- ]?proof|mistake[- ]?proof|sensor|interlock|automatic|automated|vision|in-?line gauge|100%.*(auto|machine)|go/?no-?go fixture|presence detect", re.I)


def band(v, cuts):
    for label, lo, hi in cuts:
        if lo <= v <= hi:
            return label
    raise ValueError(v)


def action_priority(s, o, d):
    sb = band(s, [("9-10", 9, 10), ("7-8", 7, 8), ("4-6", 4, 6), ("2-3", 2, 3), ("1", 1, 1)])
    ob = band(o, [("8-10", 8, 10), ("6-7", 6, 7), ("4-5", 4, 5), ("2-3", 2, 3), ("1", 1, 1)])
    col = 0 if d >= 7 else 1 if d >= 5 else 2 if d >= 2 else 3
    return AP_TABLE[sb][ob][col]


def rating(v):
    try:
        n = int(str(v).strip())
        return n if 1 <= n <= 10 else None
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="PFMEA CSV, or - for stdin")
    ap.add_argument("--sort", choices=["ap", "rpn", "row"], default="ap")
    ap.add_argument("--csv", dest="as_csv", action="store_true", help="print the PFMEA with AP and RPN columns")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"failure_mode", "S", "O", "D"} <= set(rows[0]):
        print("error: PFMEA CSV needs failure_mode, S, O and D columns", file=sys.stderr)
        return 2
    findings, rated = [], []
    for i, r in enumerate(rows, 1):
        g = lambda k: (r.get(k) or "").strip()
        s, o, d = rating(r["S"]), rating(r["O"]), rating(r["D"])
        label = f"row {i} {g('step')} / {g('failure_mode')} / {g('cause')}".replace(" /  /", " /")
        if None in (s, o, d):
            findings.append(("FM003", "high", label, f"S/O/D must be 1-10 (got {r['S']}/{r['O']}/{r['D']})"))
            continue
        prio = action_priority(s, o, d)
        rpn = s * o * d
        rated.append((i, r, s, o, d, prio, rpn))
        if prio == "H" and not g("action"):
            findings.append(("FM001", "high", label, f"AP H (S{s} O{o} D{d}) needs an action or a documented justification"))
        if s >= 9 and not (g("prevention") or g("detection")):
            findings.append(("FM002", "high", label, f"severity {s} with no prevention or detection control"))
        if d <= 3 and not ERROR_PROOF.search(g("detection")):
            findings.append(("FM004", "medium", label, f"D{d} claimed for '{g('detection') or 'no control'}': D 1-3 needs error-proofing or automatic detection"))
        if o <= 2 and not g("prevention"):
            findings.append(("FM005", "medium", label, f"O{o} claimed with no prevention control"))
        if s >= 9 and g("special").upper() not in ("CC", "SC", "KC", "CRITICAL"):
            findings.append(("FM006", "medium", label, f"severity {s}: mark as special characteristic (CC) if the customer's rules require"))
        if g("action") and not (g("owner") and g("due")):
            findings.append(("FM007", "low", label, "action without owner or due date"))
    order = {"H": 0, "M": 1, "L": 2}
    if a.sort == "ap":
        rated.sort(key=lambda x: (order[x[5]], -x[2], -x[6]))
    elif a.sort == "rpn":
        rated.sort(key=lambda x: -x[6])
    if a.as_csv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        cols = list(rows[0].keys())
        w.writerow(cols + ["AP", "RPN"])
        for _, r, *_rest, prio, rpn in rated:
            w.writerow([r.get(c, "") for c in cols] + [prio, rpn])
    else:
        print(f"{'AP':<3}{'S':>3}{'O':>3}{'D':>3}{'RPN':>5}  {'Step':<14}{'Failure mode':<28}Cause")
        for i, r, s, o, d, prio, rpn in rated:
            print(f"{prio:<3}{s:>3}{o:>3}{d:>3}{rpn:>5}  {(r.get('step') or '')[:13]:<14}{(r.get('failure_mode') or '')[:27]:<28}{(r.get('cause') or '')[:40]}")
        counts = {k: sum(x[5] == k for x in rated) for k in "HML"}
        print(f"\nAction priority: H {counts['H']}, M {counts['M']}, L {counts['L']}  ({len(rated)} rated rows)\n")
    sev = {"high": 0, "medium": 1, "low": 2}
    for code, s_, label, msg in sorted(findings, key=lambda f: sev[f[1]]):
        print(f"{code} [{s_}] {label}: {msg}", file=sys.stderr if a.as_csv else sys.stdout)
    return 1 if any(f[1] == "high" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
