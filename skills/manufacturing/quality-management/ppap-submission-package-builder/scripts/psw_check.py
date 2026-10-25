#!/usr/bin/env python3
"""Check a Part Submission Warrant (PSW) and its initial process study results before signing.

PSW JSON keys: part_number, part_name, drawing_rev, eng_change_level, weight_kg, po_number, submission_level,
reason, results {dimensional, material, appearance, statistical: true/false}, imds, signed_by, signed_date,
studies: [{characteristic, special (true/false), ppk, cpk, n, stable (true/false)}]

Initial process study acceptance (AIAG PPAP 4th ed. 2.2.11): stable process with index > 1.67 meets acceptance;
1.33 to 1.67 may be acceptable - contact the customer; < 1.33 does not meet acceptance. At least 100 readings
from 25 or more subgroups; unstable processes need customer agreement before submission.

Checks:
  PS001 high    identification incomplete (part number, drawing revision, engineering change level, PO)
  PS002 high    part weight missing (kg, to four decimals)
  PS003 high    a results box is not 'meets requirements' - do not sign without customer-approved deviation
  PS004 high    special characteristic index < 1.33
  PS005 medium  special characteristic index 1.33-1.67, or process unstable - customer approval needed
  PS006 medium  study has fewer than 100 readings
  PS007 medium  reason for submission or submission level missing
  PS008 medium  material reporting (IMDS or customer system) not stated
  PS009 low     not signed or not dated

Usage:
    python psw_check.py psw.json

Exit codes: 0 ready to sign, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import sys


def check(p):
    f = []
    missing = [k for k in ("part_number", "drawing_rev", "eng_change_level", "po_number") if not p.get(k)]
    if missing:
        f.append(("PS001", "high", f"identification missing: {', '.join(missing)}"))
    w = p.get("weight_kg")
    if not isinstance(w, (int, float)) or w <= 0:
        f.append(("PS002", "high", "part weight in kg (four decimals) is required on the PSW"))
    for k, v in (p.get("results") or {}).items():
        if v is not True:
            f.append(("PS003", "high", f"{k} results do not meet requirements: resolve or obtain a deviation before signing"))
    if not p.get("results"):
        f.append(("PS003", "high", "no results declaration (dimensional, material, appearance, statistical)"))
    for s in p.get("studies") or []:
        name = s.get("characteristic", "?")
        idx = s.get("ppk") if s.get("ppk") is not None else s.get("cpk")
        if idx is None:
            f.append(("PS004", "high", f"{name}: no Ppk/Cpk reported"))
            continue
        special = s.get("special", False)
        if not s.get("stable", True):
            f.append(("PS005", "medium", f"{name}: process not stable - agree the approach with the customer before submitting"))
        if idx < 1.33:
            sev = "high" if special else "medium"
            f.append(("PS004", sev, f"{name}: index {idx:.2f} < 1.33 does not meet acceptance; 100% inspection and an action plan"))
        elif idx < 1.67:
            f.append(("PS005", "medium", f"{name}: index {idx:.2f} between 1.33 and 1.67 - contact the customer for approval"))
        if (s.get("n") or 0) < 100:
            f.append(("PS006", "medium", f"{name}: {s.get('n') or 0} readings; initial studies need >= 100 from >= 25 subgroups"))
    if not (p.get("reason") and p.get("submission_level")):
        f.append(("PS007", "medium", "state the reason for submission and the submission level"))
    if not p.get("imds"):
        f.append(("PS008", "medium", "state the IMDS (or customer system) submission ID and date"))
    if not (p.get("signed_by") and p.get("signed_date")):
        f.append(("PS009", "low", "authorized signature, title and date required"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("psw", help="PSW JSON, or - for stdin")
    a = ap.parse_args()
    try:
        p = json.load(sys.stdin if a.psw == "-" else open(a.psw, encoding="utf-8"))
        if not isinstance(p, dict):
            raise ValueError("PSW JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f = check(p)
    print(f"PSW {p.get('part_number', '?')} rev {p.get('drawing_rev', '?')} level {p.get('submission_level', '?')}")
    for s in p.get("studies") or []:
        idx = s.get("ppk") if s.get("ppk") is not None else s.get("cpk")
        print(f"  {'SC ' if s.get('special') else '   '}{s.get('characteristic', '?'):<28}index {idx if idx is not None else '-':<6} n={s.get('n', 0)}")
    print()
    for code, sev, msg in f:
        print(f"{code} [{sev}] {msg}")
    if any(x[1] == "high" for x in f):
        print("\nDo not sign yet.")
    elif any(x[1] == "medium" for x in f):
        print("\nReady to sign once the medium items are agreed with the customer.")
    else:
        print("\nReady to sign.")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
