#!/usr/bin/env python3
"""Check audit findings for the three-part structure (requirement, evidence, statement) and fair grading.

Input: JSON list (or CSV) of findings with keys id, grade (major/minor/ofi), clause, requirement, evidence, statement.

Checks:
  AF001 high    no requirement: clause or requirement text missing for a nonconformity
  AF002 high    no objective evidence, or evidence with nothing verifiable (no ID, date, number or location)
  AF003 high    graded nonconformity but worded as advice ('could be improved', 'consider') - make it an OFI
  AF004 medium  opinion or loaded words (poor, inadequate, sloppy, lack of commitment, I feel)
  AF005 medium  names a person (Mr/Ms/Dr ...): findings are about the system, not people
  AF006 medium  nonconformity prescribes the solution ('should implement', 'must purchase')
  AF007 medium  grade looks wrong: 'major' for a single lapse, or 'minor' worded as a total absence/breakdown
  AF008 low     vague quantities (some, several, many) without numbers
  AF009 low     no sample size ('3 of 12 records') in the evidence of a nonconformity
  AF010 low     statement over 50 words

Usage:
    python finding_lint.py findings.json
    python finding_lint.py findings.csv --json

Exit codes: 0 no high findings, 1 high findings, 2 read or format error.
"""

import argparse
import csv
import json
import re
import sys

ADVICE = re.compile(r"\b(could be improved|could be better|consider\w*|recommend\w*|suggest\w*|it would be good|may wish|opportunity)\b", re.I)
OPINION = re.compile(r"\b(poor(ly)?|inadequate|sloppy|careless|lazy|terrible|bad|lack of commitment|unprofessional|i feel|i think|seems|apparently|obviously|clearly)\b", re.I)
PERSON = re.compile(r"\b(Mr|Mrs|Ms|Miss|Dr)\.?\s+[A-Z][a-z]+")
PRESCRIBE = re.compile(r"\b(should|must|needs? to|shall)\s+(implement|purchase|buy|install|hire|create|introduce|use|adopt)\b", re.I)
SYSTEMIC = re.compile(r"\b(no (evidence of any|internal audits?|management review|procedure|system|records? at all)|not (been )?(established|implemented|carried out|conducted) (at all|since)|never|none of|absence of|all \d+|0 of \d+)\b", re.I)
SINGLE = re.compile(r"\b(one|1|a single|isolated)\s+(of|instance|record|gauge|case|occasion)\b", re.I)
VAGUE = re.compile(r"\b(some|several|many|various|a few|numerous|most)\b", re.I)
VERIFIABLE = re.compile(r"\d|[A-Z]{2,}-?\d|\b(station|line|cell|area|shift|machine|lathe|press)\b", re.I)
SAMPLE = re.compile(r"\b\d+\s+(of|out of)\s+\d+\b|\bsampled\b|\breviewed \d+", re.I)


def load(path):
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8-sig").read()
    if text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
    else:
        data = list(csv.DictReader(text.splitlines()))
    if not isinstance(data, list) or not data or not all(isinstance(d, dict) for d in data):
        raise ValueError("expected a JSON list of finding objects or a CSV with a header")
    return data


def lint(fd):
    g = lambda k: str(fd.get(k) or "").strip()
    grade = g("grade").lower()
    nc = grade in ("major", "minor", "nc", "nonconformity")
    ev, st, req = g("evidence"), g("statement"), g("requirement")
    allt = " ".join((req, ev, st))
    out = []
    if nc and not (g("clause") and req):
        out.append(("AF001", "high", "state the requirement: clause number and what it requires (or the procedure clause)"))
    if not ev:
        out.append(("AF002", "high", "no objective evidence"))
    elif not VERIFIABLE.search(ev):
        out.append(("AF002", "high", "evidence has nothing verifiable: add record IDs, dates, quantities or locations"))
    if nc and ADVICE.search(st):
        out.append(("AF003", "high", f"worded as advice ('{ADVICE.search(st).group(1)}'): if no requirement is broken, grade it OFI"))
    m = OPINION.search(allt)
    if m:
        out.append(("AF004", "medium", f"opinion word '{m.group(1)}': state facts only"))
    m = PERSON.search(allt)
    if m:
        out.append(("AF005", "medium", f"names a person ('{m.group(0)}'): use the role"))
    if nc and PRESCRIBE.search(st):
        out.append(("AF006", "medium", "prescribes a solution; the auditee owns root cause and action"))
    if grade == "major" and SINGLE.search(ev) and not SYSTEMIC.search(allt):
        out.append(("AF007", "medium", "graded major but evidence shows a single lapse: likely minor unless it shipped nonconforming product"))
    elif grade == "minor" and SYSTEMIC.search(allt):
        out.append(("AF007", "medium", f"graded minor but describes a total absence ('{SYSTEMIC.search(allt).group(0)}'): likely major"))
    m = VAGUE.search(ev)
    if m and not re.search(r"\d", ev):
        out.append(("AF008", "low", f"vague quantity '{m.group(1)}': give the count"))
    if nc and ev and not SAMPLE.search(ev):
        out.append(("AF009", "low", "say how many were sampled and how many failed ('3 of 12 records')"))
    if len(st.split()) > 50:
        out.append(("AF010", "low", f"statement is {len(st.split())} words; keep it to one or two sentences"))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="findings JSON or CSV, or - for stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        findings = load(a.file)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    report, high = [], 0
    for i, fd in enumerate(findings, 1):
        issues = lint(fd)
        high += sum(s == "high" for _, s, _ in issues)
        report.append({"id": fd.get("id") or i, "grade": fd.get("grade", ""), "issues": issues})
    if a.json:
        print(json.dumps([{**r, "issues": [dict(zip(("code", "severity", "message"), x)) for x in r["issues"]]}
                          for r in report], indent=2))
    else:
        for r in report:
            print(f"{r['id']} ({r['grade'] or 'no grade'}): " + ("ok" if not r["issues"] else f"{len(r['issues'])} issue(s)"))
            for code, sev, msg in r["issues"]:
                print(f"    {code} [{sev}] {msg}")
        print(f"\n{len(report)} finding(s) checked, {high} high issue(s)")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
