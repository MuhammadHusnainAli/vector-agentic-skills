#!/usr/bin/env python3
"""Write a risk-based incoming inspection plan per part characteristic, with dynamic (switching) levels.

CSV columns: part, characteristic, class (critical/major/minor), supplier, supplier_grade (A-D),
accepted_lots (consecutive accepted lots of this part), lot_size, new_part (yes/no), coc (certificate supplied yes/no)

Decision per row:
  new part or new supplier (< 3 accepted lots)  -> first-article / 100% of the first lots, then tightened
  supplier grade D                               -> tightened (or 100% for critical), SCAR open
  critical characteristic                        -> 100% or c = 0 at LTPD 0.5%; never certificate-only
  grade A, >= 10 accepted lots, not critical     -> skip-lot (inspect 1 lot in 4) with CoC
  grade A, >= 20 accepted lots, minor, CoC       -> dock-to-stock with periodic audit (1 lot in 10)
  otherwise                                      -> normal c = 0 sampling
c = 0 sample sizes come from the LTPD per class at 90% confidence: n = ln(0.10) / ln(1 - LTPD);
LTPD normal: critical 0.5%, major 2%, minor 5%; tightened halves the LTPD. n >= lot size means 100%.

Critical characteristics never drop to skip-lot or certificate-only. Flags:
  II001 medium  grade D supplier without an open SCAR recorded (column 'scar')
  II002 low     skip-lot or dock-to-stock without a certificate of conformance

Usage:
    python inspection_plan.py parts.csv
    python inspection_plan.py parts.csv --csv > plan.csv

Exit codes: 0 plan printed without flags, 1 medium flags, 2 usage or data error.
"""

import argparse
import csv
import math
import sys

LTPD = {"critical": 0.005, "major": 0.02, "minor": 0.05}


def c0(ltpd, lot):
    n = math.ceil(math.log(0.10) / math.log(1 - ltpd))
    return ("100%", "inspect every unit") if lot and n >= lot else (f"n={n}, c=0", f"LTPD {ltpd:.1%} at 90% confidence")


def plan(r):
    g = lambda k: (r.get(k) or "").strip()
    cls, grade = g("class").lower() or "major", g("supplier_grade").upper() or "B"
    lots = int(g("accepted_lots") or 0)
    lot = int(g("lot_size") or 0)
    new = g("new_part").lower() in ("yes", "y", "true")
    coc = g("coc").lower() in ("yes", "y", "true")
    if cls not in LTPD:
        raise ValueError(f"class '{cls}' for {g('part')} must be critical, major or minor")
    if new or lots < 3:
        level, (method, why) = "first lots", ("100% (first article on lot 1)", "new part or supplier: build history first")
    elif grade == "D":
        level = "tightened"
        method, why = ("100%", "grade D supplier, critical characteristic") if cls == "critical" else c0(LTPD[cls] / 2, lot)
    elif cls == "critical":
        level, (method, why) = "normal", c0(LTPD["critical"], lot)
        why += "; consider supplier SPC data or source inspection"
    elif grade == "A" and lots >= 20 and cls == "minor" and coc:
        level, method, why = "dock-to-stock", "CoC review; audit 1 lot in 10", f"{lots} consecutive accepted lots, grade A"
    elif grade == "A" and lots >= 10:
        m, _ = c0(LTPD[cls], lot)
        level, method, why = "skip-lot", f"1 lot in 4 at {m}; CoC every lot", f"{lots} consecutive accepted lots, grade A"
    elif grade == "C":
        level, (method, why) = "tightened", c0(LTPD[cls] / 2, lot)
    else:
        level, (method, why) = "normal", c0(LTPD[cls], lot)
    return level, method, why, cls, grade, coc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--csv", dest="as_csv", action="store_true", help="output the plan as CSV")
    a = ap.parse_args()
    try:
        with open(a.csv, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        if not rows or not {"part", "characteristic", "class"} <= set(rows[0]):
            raise ValueError("CSV needs part, characteristic and class columns (see --help)")
        plans = [(r, *plan(r)) for r in rows]
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    flags = []
    for r, level, method, why, cls, grade, coc in plans:
        if grade == "D" and not (r.get("scar") or "").strip():
            f = ("II001", "medium", f"{r.get('supplier')}: grade D supplier - record the open SCAR")
            if f not in flags:
                flags.append(f)
        if level in ("skip-lot", "dock-to-stock") and not coc:
            flags.append(("II002", "low", f"{r['part']} {r['characteristic']}: {level} without a certificate of conformance"))
    if a.as_csv:
        w = csv.writer(sys.stdout, lineterminator="\n")
        w.writerow(["part", "characteristic", "class", "supplier", "grade", "level", "method", "rationale"])
        for r, level, method, why, cls, grade, _ in plans:
            w.writerow([r["part"], r["characteristic"], cls, r.get("supplier", ""), grade, level, method, why])
    else:
        print(f"{'Part':<10}{'Characteristic':<22}{'Class':<9}{'Grd':<4}{'Level':<14}Method")
        for r, level, method, why, cls, grade, _ in plans:
            print(f"{r['part'][:9]:<10}{r['characteristic'][:21]:<22}{cls:<9}{grade:<4}{level:<14}{method}  ({why})")
        print("\nSwitching: 2 rejected lots in 5 -> tightened; 5 accepted on tightened -> normal; 10 accepted + grade A -> skip-lot;"
              " any reject on skip-lot or dock-to-stock -> back to normal.")
    for code, sev, msg in flags:
        print(f"{code} [{sev}] {msg}", file=sys.stderr if a.as_csv else sys.stdout)
    return 1 if any(f[1] == "medium" for f in flags) else 0


if __name__ == "__main__":
    sys.exit(main())
