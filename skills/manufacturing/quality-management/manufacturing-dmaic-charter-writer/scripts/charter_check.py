#!/usr/bin/env python3
"""Review a DMAIC project charter for the mistakes that sink Six Sigma projects.

Charter JSON keys: title, business_case, problem_statement, goal_statement, customer_ctq,
primary_metric {name, unit, baseline, target, direction: lower|higher}, secondary_metric,
scope {in, out}, champion, process_owner, belt, team (list), phases {define, measure, analyze, improve,
control: due dates YYYY-MM-DD}, financial_benefit

Checks:
  CH001 high    problem statement contains a cause or a solution (because, due to, lack of, implement ...)
  CH002 high    problem statement has no magnitude or time frame (numbers and when)
  CH003 high    goal statement has no target number or no date
  CH004 high    primary metric missing baseline / target, or target not better than baseline
  CH005 medium  scope in / out not both defined
  CH006 medium  no champion or no process owner
  CH007 medium  phase dates missing or out of order; longer than --max-months
  CH008 medium  business case without money or strategic link
  CH009 low     no secondary (counter-balance) metric
  CH010 low     no customer CTQ

Usage:
    python charter_check.py charter.json [--max-months 6]

Exit codes: 0 no high findings, 1 high findings, 2 read or JSON error.
"""

import argparse
import datetime as dt
import json
import re
import sys

CAUSE = re.compile(r"\b(because|due to|caused by|as a result of|lack of|insufficient|poor|not enough)\b", re.I)
SOLUTION = re.compile(r"\b(implement|install|introduce|buy|purchase|automate|we need|need to|should|by adding|new system)\b", re.I)
NUM = re.compile(r"\d")
TIME = re.compile(r"\b(19|20)\d\d\b|\b(q[1-4]|month|week|year|since|between|ytd|last \d+|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.I)
PHASES = ["define", "measure", "analyze", "improve", "control"]


def check(c, max_months):
    f = []
    ps = str(c.get("problem_statement") or "")
    gs = str(c.get("goal_statement") or "")
    if not ps:
        f.append(("CH001", "high", "no problem statement"))
    else:
        m = CAUSE.search(ps) or SOLUTION.search(ps)
        if m:
            f.append(("CH001", "high", f"problem statement contains '{m.group(1)}': describe the gap, not its cause or a solution"))
        if not (NUM.search(ps) and TIME.search(ps)):
            f.append(("CH002", "high", "problem statement needs magnitude and time frame (what, how much, since when, where)"))
    if not (NUM.search(gs) and TIME.search(gs)):
        f.append(("CH003", "high", "goal statement needs a target number and a date (reduce X from A to B by DATE)"))
    pm = c.get("primary_metric") or {}
    b, t = pm.get("baseline"), pm.get("target")
    if not pm.get("name") or b is None or t is None:
        f.append(("CH004", "high", "primary metric needs name, unit, baseline and target"))
    else:
        lower = str(pm.get("direction", "lower")).lower() == "lower"
        if (lower and t >= b) or (not lower and t <= b):
            f.append(("CH004", "high", f"target {t} is not better than baseline {b} ({'lower' if lower else 'higher'} is better)"))
    sc = c.get("scope") or {}
    if not (sc.get("in") and sc.get("out")):
        f.append(("CH005", "medium", "define scope in AND out (process start/stop, products, sites)"))
    if not (c.get("champion") and c.get("process_owner")):
        f.append(("CH006", "medium", "name a champion (removes barriers) and a process owner (keeps the gains)"))
    ph = c.get("phases") or {}
    dates = []
    for p in PHASES:
        try:
            dates.append(dt.date.fromisoformat(str(ph.get(p))[:10]))
        except ValueError:
            f.append(("CH007", "medium", f"phase '{p}' has no valid due date"))
            dates = None
            break
    if dates:
        if any(b2 < a2 for a2, b2 in zip(dates, dates[1:])):
            f.append(("CH007", "medium", "phase dates are out of order"))
        start = c.get("start")
        try:
            s = dt.date.fromisoformat(str(start)[:10]) if start else dates[0] - dt.timedelta(weeks=3)
            months = (dates[-1] - s).days / 30.4
            if months > max_months:
                f.append(("CH007", "medium", f"project runs {months:.0f} months (> {max_months}): narrow the scope or split it"))
        except ValueError:
            pass
    bc = str(c.get("business_case") or "")
    if not (re.search(r"[$€£]|\b(usd|eur|gbp|k|m)\b|\d", bc, re.I) and bc) and not c.get("financial_benefit"):
        f.append(("CH008", "medium", "business case needs money (COPQ, savings) or a named strategic objective"))
    if not c.get("secondary_metric"):
        f.append(("CH009", "low", "add a counter-balance metric (e.g. cycle time or OTD must not get worse)"))
    if not c.get("customer_ctq"):
        f.append(("CH010", "low", "state the customer CTQ the project protects"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("charter", help="charter JSON, or - for stdin")
    ap.add_argument("--max-months", type=float, default=6)
    a = ap.parse_args()
    try:
        c = json.load(sys.stdin if a.charter == "-" else open(a.charter, encoding="utf-8"))
        if not isinstance(c, dict):
            raise ValueError("charter JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    f = check(c, a.max_months)
    print(f"Charter: {c.get('title', '(untitled)')}")
    for code, sev, msg in f:
        print(f"{code} [{sev}] {msg}")
    print(f"\n{len(f)} issue(s)" if f else "Charter is ready for the champion's sign-off.")
    return 1 if any(x[1] == "high" for x in f) else 0


if __name__ == "__main__":
    sys.exit(main())
