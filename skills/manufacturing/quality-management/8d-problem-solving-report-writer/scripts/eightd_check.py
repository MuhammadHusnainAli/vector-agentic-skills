#!/usr/bin/env python3
"""Check an 8D report discipline by discipline, as an automotive customer quality engineer would.

8D JSON keys (dates YYYY-MM-DD):
  id, opened, champion, team (list of roles),
  d2: {what, where, when, how_many, how_detected, is_not}
  d3: {actions, date, verified}
  d4: {occurrence_cause, occurrence_verified, escape_cause, escape_verified, method}
  d5: {actions: [{action, addresses: occurrence|escape}], verified}
  d6: {date, validation, containment_removed}
  d7: {fmea_updated, control_plan_updated, similar_products, lessons_learned}
  d8: {date, recognition}

Checks:
  8D01 medium  D1 team under 3 roles or no champion
  8D02 high    D2 problem description misses what / where / when / how many / how detected, or states a cause
  8D03 high    D3 containment missing, not verified, or later than --d3-hours after opening
  8D04 high    D4 missing or unverified occurrence or escape (non-detection) root cause, or 'human error'
  8D05 high    D5 no action for occurrence or for escape, or actions not verified before implementation
  8D06 medium  D6 no validation evidence, or interim containment not removed after validation
  8D07 medium  D7 FMEA / control plan not updated, or no horizontal deployment to similar products
  8D08 medium  discipline dates out of order, or D4 later than --d4-days after opening
  8D09 low     D8 closure / team recognition missing

Usage:
    python eightd_check.py 8d.json
    python eightd_check.py 8d.json --d3-hours 24 --d4-days 10

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import datetime as dt
import json
import re
import sys

BLAME = re.compile(r"\b(operator|human|worker)\s+(error|mistake)|\bnot trained|\bcareless|\bforgot\b", re.I)
CAUSE_WORDS = re.compile(r"\b(because|due to|caused by|root cause)\b", re.I)


def date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def check(r, d3_hours, d4_days):
    f, status = [], {}
    sec = lambda k: r.get(k) or {}
    team = r.get("team") or []
    ok = len(team) >= 3 and r.get("champion")
    status["D1"] = ok
    if not ok:
        f.append(("8D01", "medium", "D1: name a champion and a cross-functional team of at least 3 roles"))
    d2 = sec("d2")
    miss = [k for k in ("what", "where", "when", "how_many", "how_detected") if not d2.get(k)]
    status["D2"] = not miss
    if miss:
        f.append(("8D02", "high", f"D2: problem description lacks {', '.join(miss)} (use 5W2H and is / is-not)"))
    if CAUSE_WORDS.search(str(d2.get("what", ""))):
        f.append(("8D02", "high", "D2: the problem statement contains a cause; describe the effect only"))
        status["D2"] = False
    if not d2.get("is_not"):
        f.append(("8D02", "high", "D2: add is / is-not (which parts, lots, lines, shifts are NOT affected)"))
        status["D2"] = False
    d3 = sec("d3")
    opened = date(r.get("opened"))
    d3d = date(d3.get("date"))
    status["D3"] = bool(d3.get("actions") and d3.get("verified"))
    if not d3.get("actions"):
        f.append(("8D03", "high", "D3: no containment actions"))
    elif not d3.get("verified"):
        f.append(("8D03", "high", "D3: containment not verified effective (e.g. sorted stock, clean-point date, certified parts)"))
    if opened and d3d and (d3d - opened).days * 24 > d3_hours:
        f.append(("8D03", "high", f"D3: containment {(d3d - opened).days} days after opening (expected within {d3_hours} h)"))
        status["D3"] = False
    d4 = sec("d4")
    status["D4"] = True
    for kind in ("occurrence", "escape"):
        cause = str(d4.get(f"{kind}_cause") or "")
        if not cause:
            f.append(("8D04", "high", f"D4: no {kind} root cause" + (" (why was it not detected?)" if kind == "escape" else "")))
            status["D4"] = False
        elif BLAME.search(cause):
            f.append(("8D04", "high", f"D4: {kind} cause '{cause[:50]}' is human error; why did the process allow it?"))
            status["D4"] = False
        elif not d4.get(f"{kind}_verified"):
            f.append(("8D04", "high", f"D4: {kind} cause not verified (reproduce it or switch it on/off)"))
            status["D4"] = False
    d5 = sec("d5")
    acts = d5.get("actions") or []
    status["D5"] = True
    for kind in ("occurrence", "escape"):
        if not any(str(x.get("addresses", "")).lower() == kind for x in acts):
            f.append(("8D05", "high", f"D5: no permanent corrective action for the {kind} cause"))
            status["D5"] = False
    if acts and not d5.get("verified"):
        f.append(("8D05", "high", "D5: verify the chosen actions work before implementing them (trial, capability run)"))
        status["D5"] = False
    d6 = sec("d6")
    status["D6"] = bool(d6.get("validation") and d6.get("containment_removed"))
    if not d6.get("validation"):
        f.append(("8D06", "medium", "D6: no validation evidence after implementation (data from production, Cpk, zero defects)"))
    elif not d6.get("containment_removed"):
        f.append(("8D06", "medium", "D6: record when D3 containment was removed after validation"))
    d7 = sec("d7")
    miss7 = [k for k in ("fmea_updated", "control_plan_updated", "similar_products") if not d7.get(k)]
    status["D7"] = not miss7
    if miss7:
        f.append(("8D07", "medium", f"D7: missing {', '.join(miss7)} (prevent recurrence across the system)"))
    dates = [("D3", d3d), ("D6", date(d6.get("date"))), ("D8", date(sec("d8").get("date")))]
    known = [(k, v) for k, v in dates if v]
    for (k1, v1), (k2, v2) in zip(known, known[1:]):
        if v2 < v1:
            f.append(("8D08", "medium", f"{k2} date {v2} is before {k1} date {v1}"))
    d4d = date(d4.get("date"))
    if opened and d4d and (d4d - opened).days > d4_days:
        f.append(("8D08", "medium", f"D4 completed {(d4d - opened).days} days after opening (target {d4_days})"))
    status["D8"] = bool(sec("d8").get("date"))
    if not status["D8"]:
        f.append(("8D09", "low", "D8: closure date and team recognition missing"))
    return f, status


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", help="8D JSON, or - for stdin")
    ap.add_argument("--d3-hours", type=int, default=24)
    ap.add_argument("--d4-days", type=int, default=10)
    a = ap.parse_args()
    try:
        r = json.load(sys.stdin if a.report == "-" else open(a.report, encoding="utf-8"))
        if not isinstance(r, dict):
            raise ValueError("8D JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f, status = check(r, a.d3_hours, a.d4_days)
    print(f"8D {r.get('id', '(no id)')}: " + "  ".join(f"{k} {'ok' if v else '--'}" for k, v in status.items()))
    for code, sev, msg in f:
        print(f"{code} [{sev}] {msg}")
    print(f"\n{len(f)} issue(s)" if f else "All disciplines complete.")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
