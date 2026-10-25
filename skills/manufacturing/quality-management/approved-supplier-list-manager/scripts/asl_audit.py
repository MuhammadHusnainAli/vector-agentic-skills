#!/usr/bin/env python3
"""Audit an approved supplier list (ASL) and, optionally, purchase orders against it (ISO 9001 8.4.1,
IATF 16949 8.4, AS9100 8.4.1 external provider register).

ASL CSV columns: supplier, status (approved/conditional/probation/disqualified/pending), scope (';'-separated
commodities or processes), risk (high/medium/low), certification, cert_expiry, last_evaluation, approved_by,
condition_until (for conditional/probation), single_source (yes/no), backup (alternative source or plan)
PO CSV columns (optional): po, supplier, scope (commodity / process bought), date

Checks:
  AL001 high    PO with a supplier that is disqualified, pending or not on the ASL
  AL002 high    PO for a commodity / process outside the supplier's approved scope
  AL003 medium  certificate expired, or expiring within --warn-days
  AL004 medium  re-evaluation overdue (high risk 12, medium 24, low 36 months)
  AL005 medium  conditional / probation status past its condition_until date: decide approve or disqualify
  AL006 medium  high-risk supplier without the required certification (--require-cert, default 'ISO 9001')
  AL007 low     single-source high-risk supplier without a backup plan
  AL008 low     no approver recorded

Usage:
    python asl_audit.py asl.csv --today 2026-10-24
    python asl_audit.py asl.csv --pos pos.csv --today 2026-10-24 --require-cert "IATF 16949"

Exit codes: 0 no high findings, 1 high findings, 2 read or usage error.
"""

import argparse
import csv
import datetime as dt
import sys
from collections import Counter

EVAL_MONTHS = {"high": 12, "medium": 24, "low": 36}


def d(s):
    try:
        return dt.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def read(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def scopes(s):
    return {x.strip().lower() for x in (s or "").split(";") if x.strip()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("asl")
    ap.add_argument("--pos", help="purchase order CSV to check against the ASL")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--warn-days", type=int, default=60)
    ap.add_argument("--require-cert", default="ISO 9001", help="certification required for high-risk suppliers")
    a = ap.parse_args()
    try:
        asl = read(a.asl)
        pos = read(a.pos) if a.pos else []
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not asl or not {"supplier", "status"} <= set(asl[0]):
        print("error: ASL needs supplier and status columns", file=sys.stderr)
        return 2
    f = []
    by = {}
    for r in asl:
        g = lambda k: (r.get(k) or "").strip()
        name, status, risk = g("supplier"), g("status").lower(), g("risk").lower() or "medium"
        by[name.lower()] = r
        if status == "disqualified":
            continue
        exp = d(g("cert_expiry"))
        if exp and exp < a.today:
            f.append(("AL003", "medium", name, f"certificate ({g('certification') or '?'}) expired {exp}"))
        elif exp and (exp - a.today).days <= a.warn_days:
            f.append(("AL003", "medium", name, f"certificate expires {exp} ({(exp - a.today).days} days): request the renewal"))
        last = d(g("last_evaluation"))
        months = EVAL_MONTHS.get(risk, 24)
        if not last:
            f.append(("AL004", "medium", name, "no evaluation date recorded"))
        elif (a.today - last).days > months * 30.44:
            f.append(("AL004", "medium", name, f"re-evaluation overdue: last {last}, {risk} risk needs every {months} months"))
        until = d(g("condition_until"))
        if status in ("conditional", "probation"):
            if not until:
                f.append(("AL005", "medium", name, f"{status} without an end date: set a decision date"))
            elif until < a.today:
                f.append(("AL005", "medium", name, f"{status} ended {until}: decide approve or disqualify"))
        if risk == "high" and a.require_cert.lower() not in g("certification").lower():
            f.append(("AL006", "medium", name, f"high risk without {a.require_cert} certification ({g('certification') or 'none'})"))
        if risk == "high" and g("single_source").lower() in ("yes", "y", "true") and not g("backup"):
            f.append(("AL007", "low", name, "single-source high-risk supplier without a backup source or contingency plan"))
        if not g("approved_by"):
            f.append(("AL008", "low", name, "no approver recorded"))
    for p in pos:
        sup = (p.get("supplier") or "").strip()
        r = by.get(sup.lower())
        po = p.get("po", "?")
        if not r:
            f.append(("AL001", "high", sup, f"PO {po}: supplier is not on the ASL"))
            continue
        st = (r.get("status") or "").strip().lower()
        if st in ("disqualified", "pending"):
            f.append(("AL001", "high", sup, f"PO {po}: supplier status is {st}"))
        want = (p.get("scope") or "").strip().lower()
        if want and want not in scopes(r.get("scope")):
            f.append(("AL002", "high", sup, f"PO {po}: '{want}' is outside the approved scope ({r.get('scope') or 'none'})"))
    counts = Counter((r.get("status") or "blank").strip().lower() for r in asl)
    print(f"ASL: {len(asl)} suppliers - " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    if pos:
        print(f"Purchase orders checked: {len(pos)}")
    order = {"high": 0, "medium": 1, "low": 2}
    for code, sev, name, msg in sorted(f, key=lambda x: (order[x[1]], x[0], x[2])):
        print(f"{code} [{sev}] {name}: {msg}")
    high = sum(x[1] == "high" for x in f)
    print(f"\n{len(f)} finding(s), {high} high")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
