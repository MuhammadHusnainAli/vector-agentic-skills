#!/usr/bin/env python3
"""Check a supplier corrective action request (SCAR) and evaluate the supplier's response: accept or reject.

SCAR JSON keys:
  scar_id, supplier, part, issued (YYYY-MM-DD), ncr_ref,
  problem {requirement, actual, quantity, evidence}
  due {containment, root_cause, closure}              (dates)
  response {containment, containment_date, clean_point, occurrence_cause, escape_cause, cause_verification,
            actions: [{action, addresses: occurrence|escape, due}], effectiveness, fmea_control_plan, read_across,
            root_cause_date, closure_date}

Request checks:
  SR001 high    problem lacks requirement, actual result, quantity or evidence
  SR002 medium  response due dates missing or loose (containment > 2 days, root cause > 15 days, closure > 60 days)
Response checks (when 'response' is present):
  SR101 high    no containment of stock at the supplier, in transit and at the customer, or no clean point
  SR102 high    occurrence or escape cause missing, or 'human error' / 'operator' blame
  SR103 high    actions are only corrections or training
  SR104 medium  cause not verified, or no effectiveness plan
  SR105 medium  PFMEA / control plan not updated, or no read-across to similar parts and lines
  SR106 medium  response steps later than the due dates
Verdict: ACCEPT (no high, no medium), ACCEPT WITH COMMENTS (medium only), REJECT (any high).

Usage:
    python scar_check.py scar.json

Exit codes: 0 request complete and response accepted (or no response yet), 1 rejected / incomplete, 2 read error.
"""

import argparse
import datetime as dt
import json
import re
import sys

BLAME = re.compile(r"\b(human|operator|worker)\s+(error|mistake)|\bnot trained|\bcareless|\bforgot\b|\binattention\b", re.I)
WEAK = re.compile(r"\b(retrain|train|remind|re-?brief|warn|be careful|sort(ed)?|rework(ed)?|scrap(ped)?|replace(d)?|100% inspection)\b", re.I)
STRONG = re.compile(r"poka|error[- ]?proof|fixture|sensor|interlock|automat|redesign|design change|spc|control chart|vision|go/?no-?go", re.I)


def date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def check(s):
    f = []
    pr = s.get("problem") or {}
    miss = [k for k in ("requirement", "actual", "quantity", "evidence") if not pr.get(k)]
    if miss:
        f.append(("SR001", "high", f"problem lacks {', '.join(miss)}: the supplier cannot investigate without them"))
    issued, due = date(s.get("issued")), s.get("due") or {}
    limits = {"containment": 2, "root_cause": 15, "closure": 60}
    for k, lim in limits.items():
        d = date(due.get(k))
        if not d:
            f.append(("SR002", "medium", f"no {k.replace('_', ' ')} due date"))
        elif issued and (d - issued).days > lim:
            f.append(("SR002", "medium", f"{k.replace('_', ' ')} due {(d - issued).days} days after issue (typical <= {lim})"))
    r = s.get("response")
    if not r:
        return f, False
    cont = str(r.get("containment") or "").lower()
    gaps = [x for x in ("supplier", "transit", "customer") if x not in cont]
    if not cont or gaps or not r.get("clean_point"):
        what = ", ".join(gaps) if cont else "everything"
        f.append(("SR101", "high", f"containment must cover stock at supplier, in transit and at customer (missing: {what})"
                  + ("" if r.get("clean_point") else "; define the clean point (first certified shipment)")))
    for leg in ("occurrence", "escape"):
        c = str(r.get(f"{leg}_cause") or "")
        if not c:
            f.append(("SR102", "high", f"no {leg} root cause" + (" (why was it not detected before shipping?)" if leg == "escape" else "")))
        elif BLAME.search(c):
            f.append(("SR102", "high", f"{leg} cause '{c[:50]}' blames a person: why did the process allow it?"))
    acts = r.get("actions") or []
    strong = [x for x in acts if STRONG.search(str(x.get("action", "")))]
    if not acts or (all(WEAK.search(str(x.get("action", ""))) for x in acts) and not strong):
        f.append(("SR103", "high", "actions are corrections or training only: require error-proofing, process or design changes"))
    for leg in ("occurrence", "escape"):
        if acts and not any(str(x.get("addresses", "")).lower() == leg for x in acts):
            f.append(("SR103", "high", f"no action addresses the {leg} cause"))
    if not r.get("cause_verification"):
        f.append(("SR104", "medium", "root cause not verified (reproduce it, switch it on/off, data)"))
    if not r.get("effectiveness"):
        f.append(("SR104", "medium", "no effectiveness plan (measure, period, target)"))
    if not r.get("fmea_control_plan"):
        f.append(("SR105", "medium", "PFMEA and control plan updates not shown"))
    if not r.get("read_across"):
        f.append(("SR105", "medium", "no read-across to similar parts, lines or sites"))
    for k, rk in (("containment", "containment_date"), ("root_cause", "root_cause_date"), ("closure", "closure_date")):
        d, got = date(due.get(k)), date(r.get(rk))
        if d and got and got > d:
            f.append(("SR106", "medium", f"{k.replace('_', ' ')} response {(got - d).days} days late"))
    return f, True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scar", help="SCAR JSON, or - for stdin")
    a = ap.parse_args()
    try:
        s = json.load(sys.stdin if a.scar == "-" else open(a.scar, encoding="utf-8"))
        if not isinstance(s, dict):
            raise ValueError("SCAR JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f, has_resp = check(s)
    print(f"SCAR {s.get('scar_id', '?')} to {s.get('supplier', '?')} for {s.get('part', '?')}")
    for code, sev, msg in f:
        print(f"{code} [{sev}] {msg}")
    req_bad = any(c.startswith("SR00") and sv == "high" for c, sv, _ in f)
    if not has_resp:
        print("\nRequest " + ("incomplete: fix before sending." if req_bad else "ready to send."))
        return 1 if req_bad else 0
    high = any(sv == "high" for c, sv, _ in f if c.startswith("SR1"))
    med = any(sv == "medium" for c, sv, _ in f if c.startswith("SR1"))
    verdict = "REJECT" if high else "ACCEPT WITH COMMENTS" if med else "ACCEPT"
    print(f"\nSupplier response: {verdict}")
    return 1 if high or req_bad else 0


if __name__ == "__main__":
    sys.exit(main())
