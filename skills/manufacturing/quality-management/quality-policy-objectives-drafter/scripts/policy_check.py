#!/usr/bin/env python3
"""Check a quality policy statement against ISO 9001:2015 clause 5.2.1 and common weaknesses.

Checks:
  PO001 high    no commitment to satisfy applicable requirements (customer, legal, statutory, regulatory)
  PO002 high    no commitment to continual improvement of the QMS
  PO003 medium  no framework for setting quality objectives
  PO004 medium  generic slogans with no link to the business ('world-class', 'highest quality', ...)
  PO005 medium  company name / products not mentioned (could be any company's policy)
  PO006 low     numeric targets in the policy (they belong in objectives; the policy should stay stable)
  PO007 low     length: under 25 words (thin) or over 150 words (nobody remembers it)

Usage:
    python policy_check.py policy.txt --company "Acme Precision"
    echo "We are committed to quality." | python policy_check.py -

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import re
import sys

REQUIREMENTS = r"(meet|satisfy|comply|conform|fulfil|fulfill)\w*\b.{0,60}\b(requirement|regulation|law|legal|statutory|specification)"
IMPROVE = r"(continual|continuous)\w*\s+improv|improve\w*\s.{0,40}(system|process|qms|performance|effectiveness)"
OBJECTIVES = r"\bobjective|\bmeasurable\b|\btargets?\b|\bgoals?\b"
SLOGANS = ["world-class", "world class", "highest quality", "best in class", "best-in-class", "zero defects",
           "total quality", "exceed customer expectations", "exceed expectations", "excellence in everything",
           "quality is everyone's responsibility", "quality first"]


def check(text, company):
    low = " ".join(text.lower().split())
    words = len(low.split())
    f = []
    if not re.search(REQUIREMENTS, low):
        f.append(("PO001", "high", "no commitment to satisfy applicable requirements (customer and statutory/regulatory)"))
    if not re.search(IMPROVE, low):
        f.append(("PO002", "high", "no commitment to continual improvement of the quality management system"))
    if not re.search(OBJECTIVES, low):
        f.append(("PO003", "medium", "no framework for setting quality objectives (say objectives are set and reviewed)"))
    hits = [s for s in SLOGANS if s in low]
    if hits:
        f.append(("PO004", "medium", f"generic slogan(s): {', '.join(hits)}; say what quality means for your customers"))
    if company and company.lower() not in low:
        f.append(("PO005", "medium", f"'{company}' is not named; the policy should be recognisably yours"))
    elif not company and not re.search(r"\b(we|our)\b", low):
        f.append(("PO005", "medium", "impersonal text; write it as the company speaking ('we', 'our customers')"))
    if re.search(r"\d+(\.\d+)?\s*(%|ppm|percent|days)", low):
        f.append(("PO006", "low", "numeric targets belong in quality objectives; keep the policy stable for years"))
    if words < 25:
        f.append(("PO007", "low", f"{words} words: too thin to show commitments and direction"))
    elif words > 150:
        f.append(("PO007", "low", f"{words} words: too long for staff to understand and apply (aim for 50-120)"))
    return f, words


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("policy", help="text file with the policy, or - for stdin")
    ap.add_argument("--company", help="company name that should appear in the policy")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.policy == "-" else open(a.policy, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings, words = check(text, a.company)
    for code, sev, msg in findings:
        print(f"{code} [{sev}] {msg}")
    print(f"\n{words} words, {len(findings)} finding(s)" if findings else f"{words} words: meets 5.2.1 and reads as your own.")
    return 1 if any(x[1] == "high" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
