#!/usr/bin/env python3
"""Check a control plan (AIAG CP columns) for completeness and, optionally, against its PFMEA.

Control plan CSV columns: part, phase, op, process, char_no, product_char, process_char, special, spec, method,
sample_size, frequency, control_method, reaction_plan

Checks:
  CPL001 high    characteristic without specification / tolerance (or process setting)
  CPL002 high    no evaluation / measurement technique
  CPL003 high    no sample size or frequency
  CPL004 high    no reaction plan
  CPL005 high    special characteristic (CC/SC) controlled without SPC, 100% check or error-proofing
  CPL006 medium  reaction plan does not contain suspect product (quarantine / since last good check)
  CPL007 medium  PFMEA cross-check (--pfmea): PFMEA control or special characteristic missing from the plan
  CPL008 low     TODO placeholders left; phase missing

Usage:
    python cp_check.py control_plan.csv
    python cp_check.py control_plan.csv --pfmea pfmea.csv

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import csv
import re
import sys

STRONG = re.compile(r"spc|x-?bar|i-?mr|chart|100\s*%|error[- ]?proof|poka|sensor|interlock|automatic", re.I)
CONTAIN = re.compile(r"quarantin|segregat|contain|since (the )?last (good|ok|confirmed)|hold|red tag|sort", re.I)


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="control plan CSV")
    ap.add_argument("--pfmea", help="PFMEA CSV to cross-check")
    a = ap.parse_args()
    try:
        rows = read(a.csv)
        pf = read(a.pfmea) if a.pfmea else []
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or "method" not in rows[0]:
        print("error: control plan CSV needs the AIAG columns (see --help)", file=sys.stderr)
        return 2
    f = []
    todo = 0
    for r in rows:
        g = lambda k: (r.get(k) or "").strip()
        char = g("product_char") or g("process_char") or "?"
        label = f"{g('op')} #{g('char_no')} {char[:40]}"
        todo += sum("TODO" in (v or "") for v in r.values())
        if not g("spec") or g("spec").upper().startswith("TODO"):
            f.append(("CPL001", "high", label, "no specification / tolerance or process setting"))
        if not g("method"):
            f.append(("CPL002", "high", label, "no evaluation / measurement technique"))
        if not g("sample_size") or not g("frequency") or "TODO" in g("sample_size") + g("frequency"):
            f.append(("CPL003", "high", label, "sample size and frequency required"))
        if not g("reaction_plan"):
            f.append(("CPL004", "high", label, "no reaction plan"))
        elif g("product_char") and not CONTAIN.search(g("reaction_plan")):
            f.append(("CPL006", "medium", label, "reaction plan must contain suspect product (quarantine since last good check)"))
        if g("special").upper() in ("CC", "SC") and not STRONG.search(g("control_method") + " " + g("method")) or \
                (g("special").upper() in ("CC", "SC") and "TODO" in g("control_method")):
            f.append(("CPL005", "high", label, f"{g('special').upper()} needs SPC, 100% inspection or error-proofing (has '{g('control_method') or 'none'}')"))
        if not g("phase"):
            f.append(("CPL008", "low", label, "phase (prototype / pre-launch / production) missing"))
    if pf:
        methods = " | ".join((r.get("method") or "").lower() for r in rows)
        cp_special = {(r.get("op") or "").strip() for r in rows if (r.get("special") or "").strip().upper() in ("CC", "SC")}
        for p in pf:
            op = (p.get("step") or "").split(" ")[0]
            for ctrl in ((p.get("prevention") or "").strip(), (p.get("detection") or "").strip()):
                if ctrl and ctrl.lower() not in methods:
                    f.append(("CPL007", "medium", f"PFMEA {p.get('step')}", f"control '{ctrl}' from the PFMEA is not in the control plan: update the plan or the PFMEA"))
            if (p.get("special") or "").strip().upper() in ("CC", "SC") and op not in cp_special:
                f.append(("CPL007", "medium", f"PFMEA {p.get('step')}", f"special characteristic ({p['special']}) not marked in the control plan"))
    if todo:
        f.append(("CPL008", "low", "plan", f"{todo} TODO placeholder(s) left"))
    order = {"high": 0, "medium": 1, "low": 2}
    seen = set()
    for code, sev, label, msg in sorted(f, key=lambda x: order[x[1]]):
        if (code, label, msg) in seen:
            continue
        seen.add((code, label, msg))
        print(f"{code} [{sev}] {label}: {msg}")
    high = sum(x[1] == "high" for x in f)
    print(f"\n{len(rows)} rows, {len(seen)} finding(s), {high} high" if f else f"{len(rows)} rows: no findings.")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
