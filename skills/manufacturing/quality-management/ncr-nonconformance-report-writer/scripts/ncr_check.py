#!/usr/bin/env python3
"""Check a nonconformance report (NCR) for completeness, containment and a valid disposition (ISO 9001 8.7).

NCR JSON keys: ncr_id, date, detected_by, detection_point (receiving/in-process/final/customer/supplier),
part_number, revision, lot, quantity_affected, quantity_checked, requirement, actual, description,
containment (list of {location, action, qty, by, date}), disposition (use-as-is/rework/repair/scrap/
return-to-supplier/regrade), disposition_by, concession_ref, reinspection, customer_notified, repeat,
capa_ref

Checks:
  NR001 high    no requirement vs actual (spec and what was found)
  NR002 high    part, lot or quantity missing: extent and traceability unknown
  NR003 high    no containment, or containment misses locations (stock, WIP, transit, customer) for late detection
  NR004 high    use-as-is / repair without a concession reference (customer or design authority approval)
  NR005 medium  rework / repair without re-inspection to the original requirement
  NR006 medium  customer-detected or repeat NCR without a corrective action reference
  NR007 medium  disposition missing or not a recognised option, or no disposition authority
  NR008 low     vague description ('bad', 'defective', 'wrong') with no measured value
  NR009 low     detection point or detector missing

Usage:
    python ncr_check.py ncr.json
    python ncr_check.py ncrs.json        # a JSON list of NCRs

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import json
import re
import sys

DISPOSITIONS = {"use-as-is", "rework", "repair", "scrap", "return-to-supplier", "regrade"}
LATE = {"final", "customer", "shipping", "field"}
VAGUE = re.compile(r"\b(bad|defective|wrong|not good|ng|faulty|poor|out of spec|failed)\b", re.I)


def check(n):
    g = lambda k: n.get(k)
    s = lambda k: str(n.get(k) or "").strip()
    f = []
    if not (s("requirement") and s("actual")):
        f.append(("NR001", "high", "state the requirement (drawing/spec, revision, tolerance) and the actual result"))
    missing = [k for k in ("part_number", "lot", "quantity_affected") if not s(k)]
    if missing:
        f.append(("NR002", "high", f"missing {', '.join(missing)}: extent and traceability unknown"))
    cont = g("containment") or []
    point = s("detection_point").lower()
    if not cont:
        f.append(("NR003", "high", "no containment recorded (what was quarantined, where, how many, by whom)"))
    elif point in LATE:
        locs = " ".join(str(c.get("location", "")).lower() for c in cont)
        gaps = [x for x in ("stock", "wip", "transit", "customer") if x not in locs]
        if gaps:
            f.append(("NR003", "high", f"detected at {point}: containment does not cover {', '.join(gaps)}"))
    disp = s("disposition").lower().replace(" ", "-").replace("_", "-")
    if disp in ("use-as-is", "repair") and not s("concession_ref"):
        f.append(("NR004", "high", f"{disp} needs a concession (customer or design-authority approval) reference"))
    if disp in ("rework", "repair") and not s("reinspection"):
        f.append(("NR005", "medium", f"{disp}: record re-inspection to the original requirement before release"))
    if (point == "customer" or str(g("repeat")).lower() in ("true", "yes", "1")) and not s("capa_ref"):
        f.append(("NR006", "medium", "customer-detected or repeat nonconformity: open a corrective action (CAPA/8D)"))
    if disp not in DISPOSITIONS:
        f.append(("NR007", "medium", f"disposition '{disp or 'blank'}' - use one of {', '.join(sorted(DISPOSITIONS))}"))
    elif not s("disposition_by"):
        f.append(("NR007", "medium", "no disposition authority (who decided, MRB member role)"))
    text = " ".join((s("description"), s("actual")))
    if VAGUE.search(text) and not re.search(r"\d", text):
        f.append(("NR008", "low", f"vague '{VAGUE.search(text).group(1)}' with no measured value"))
    if not (point and s("detected_by")):
        f.append(("NR009", "low", "record where it was detected and by which role"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ncr", help="NCR JSON (object or list), or - for stdin")
    a = ap.parse_args()
    try:
        data = json.load(sys.stdin if a.ncr == "-" else open(a.ncr, encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    items = data if isinstance(data, list) else [data]
    if not all(isinstance(x, dict) for x in items):
        print("error: expected an NCR object or a list of them", file=sys.stderr)
        return 2
    high = 0
    for n in items:
        f = check(n)
        high += sum(x[1] == "high" for x in f)
        print(f"{n.get('ncr_id', '(no id)')}: " + ("complete" if not f else f"{len(f)} issue(s)"))
        for code, sev, msg in f:
            print(f"    {code} [{sev}] {msg}")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
