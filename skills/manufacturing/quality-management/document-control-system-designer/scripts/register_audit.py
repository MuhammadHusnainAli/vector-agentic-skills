#!/usr/bin/env python3
"""Audit a document register (master list) for ISO 9001 clause 7.5 control failures.

CSV columns (header names; missing optional columns are skipped):
  doc_id, title, type, revision, status (draft/approved/obsolete), owner, approved_by, approval_date,
  last_review, review_months, retention, locations (';'-separated points of use)

Checks:
  DC001 high    duplicate rows for the same doc_id and revision
  DC002 high    two approved revisions of the same document at once
  DC003 high    approved document without approver or approval date
  DC004 high    obsolete document still listed at points of use
  DC005 medium  periodic review overdue (last_review + review_months < --today)
  DC006 medium  approved by its own owner/author (no independent review; external documents exempt)
  DC007 medium  no revision
  DC008 medium  record series (type REC) without a retention period
  DC009 low     external document (type EXT) not checked for currency within review_months
  DC010 low     doc_id does not match --pattern

Usage:
    python register_audit.py register.csv --today 2026-10-24
    python register_audit.py register.csv --today 2026-10-24 --pattern '^(QM|QP|WI|QF|REC|EXT)-\\d{3}$'

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import csv
import datetime as dt
import re
import sys
from collections import defaultdict


def months_after(d, n):
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, min(d.day, 28))


def parse_date(s):
    try:
        return dt.date.fromisoformat((s or "").strip()[:10])
    except ValueError:
        return None


def audit(rows, today, pattern):
    f = []
    g = lambda r, k: (r.get(k) or "").strip()
    seen = defaultdict(list)
    for r in rows:
        seen[g(r, "doc_id")].append(r)
    for doc_id, rs in seen.items():
        revs = [g(r, "revision") for r in rs]
        dup = {v for v in revs if revs.count(v) > 1}
        for v in dup:
            f.append(("DC001", "high", doc_id, f"revision {v or '(blank)'} listed {revs.count(v)} times"))
        approved = [g(r, "revision") for r in rs if g(r, "status").lower() == "approved"]
        if len(set(approved)) > 1:
            f.append(("DC002", "high", doc_id, f"revisions {', '.join(sorted(set(approved)))} all approved; obsolete the old one"))
    for r in rows:
        doc_id, status, kind = g(r, "doc_id"), g(r, "status").lower(), g(r, "type").upper()
        if status == "approved" and (not g(r, "approved_by") or not parse_date(g(r, "approval_date"))):
            f.append(("DC003", "high", doc_id, "approved without approver name or approval date"))
        if status == "obsolete" and g(r, "locations"):
            f.append(("DC004", "high", doc_id, f"obsolete but still at: {g(r, 'locations')}; withdraw or mark OBSOLETE"))
        if status == "approved" and today and g(r, "review_months").isdigit():
            last = parse_date(g(r, "last_review")) or parse_date(g(r, "approval_date"))
            if last:
                due = months_after(last, int(g(r, "review_months")))
                if due < today:
                    code, sev = ("DC009", "low") if kind == "EXT" else ("DC005", "medium")
                    what = "currency check of external document" if kind == "EXT" else "periodic review"
                    f.append((code, sev, doc_id, f"{what} due {due}, {(today - due).days} days overdue"))
        if status == "approved" and kind != "EXT" and g(r, "owner") and g(r, "owner").lower() == g(r, "approved_by").lower():
            f.append(("DC006", "medium", doc_id, f"approved by its own owner ({g(r, 'owner')})"))
        if not g(r, "revision"):
            f.append(("DC007", "medium", doc_id, "no revision"))
        if kind == "REC" and not g(r, "retention"):
            f.append(("DC008", "medium", doc_id, "record series without retention period"))
        if pattern and not re.match(pattern, doc_id):
            f.append(("DC010", "low", doc_id, f"ID does not match {pattern}"))
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(f, key=lambda x: (order[x[1]], x[0], x[2]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="register CSV, or - for stdin")
    ap.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(), help="YYYY-MM-DD (default: today)")
    ap.add_argument("--pattern", help="regex every doc_id must match")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or "doc_id" not in rows[0]:
        print("error: register needs a 'doc_id' column and at least one row", file=sys.stderr)
        return 2
    findings = audit(rows, a.today, a.pattern)
    statuses = defaultdict(int)
    for r in rows:
        statuses[(r.get("status") or "blank").strip().lower()] += 1
    print(f"{len(rows)} rows: " + ", ".join(f"{n} {s}" for s, n in sorted(statuses.items())))
    for code, sev, doc_id, msg in findings:
        print(f"{code} [{sev}] {doc_id}: {msg}")
    high = sum(x[1] == "high" for x in findings)
    print(f"\n{len(findings)} finding(s), {high} high")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
