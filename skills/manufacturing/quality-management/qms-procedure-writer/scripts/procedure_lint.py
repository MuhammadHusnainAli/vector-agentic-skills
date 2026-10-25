#!/usr/bin/env python3
"""Lint a QMS procedure or work instruction (Markdown or plain text) for clarity and auditability.

Checks:
  PR001 high    a core section is missing: purpose, scope, responsibilities, procedure/steps, records
  PR002 medium  vague wording an auditor cannot verify ('as needed', 'periodically', 'promptly', 'etc.', 'and/or')
  PR003 medium  passive step with no actor ('the part is inspected') - who does it?
  PR004 medium  'should' / 'may' in a step: is it required or optional?
  PR005 medium  records named without a retention period
  PR006 low     step over 40 words - split it
  PR007 low     no revision / approval block
  PR008 low     no time limits anywhere ('within 2 days', 'before shipment')
  PR009 low     more than 25 steps - split into a procedure plus work instructions

Usage:
    python procedure_lint.py QP-07.md
    python procedure_lint.py WI-10.txt --json

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import json
import re
import sys

SECTIONS = {"purpose": r"purpose|objective", "scope": r"scope|applicab", "responsibilities": r"responsib|raci|roles",
            "procedure": r"procedure|steps|process|method|instructions?", "records": r"records?|documented information"}
VAGUE = ["as needed", "as necessary", "as appropriate", "where appropriate", "where necessary", "if required",
         "when required", "periodically", "regularly", "from time to time", "promptly", "as soon as possible", "asap",
         "in a timely manner", "adequate", "sufficient", "suitable", "etc", "and/or", "relevant personnel",
         "appropriate personnel", "concerned department"]
VAGUE_RE = re.compile(r"\b(" + "|".join(re.escape(v) for v in VAGUE) + r")\b\.?", re.I)
PASSIVE = re.compile(r"\b(is|are|shall be|will be|must be|should be|gets?|get)\s+(\w+ed|done|made|kept|sent|given|taken|held|seen|built)\b", re.I)
STEP = re.compile(r"^\s*(\d+[.)]|[-*]\s|\d+\.\d+\s)")
MODAL = re.compile(r"\b(should|may|might|could)\b", re.I)
TIME = re.compile(r"\bwithin\b|\b\d+\s*(working\s+)?(hours?|days?|weeks?|minutes?|shifts?)\b|\bbefore\s+(shipment|release|use|start)\b|\bdaily\b|\bweekly\b|\bmonthly\b|\beach (shift|batch|lot)\b", re.I)


def headings(lines):
    return [l.lower() for l in lines if l.lstrip().startswith("#") or re.match(r"^\s*\d+(\.\d+)?\s+[A-Z][a-z]", l)]


def lint(text):
    lines = text.splitlines()
    heads = " ".join(headings(lines))
    f = []
    for name, pat in SECTIONS.items():
        if not re.search(pat, heads):
            f.append(("PR001", "high", 0, f"no '{name}' section"))
    steps = 0
    in_records = False
    records_text = []
    for n, line in enumerate(lines, 1):
        if line.lstrip().startswith("#"):
            in_records = bool(re.search(r"record", line, re.I))
            continue
        if in_records:
            records_text.append(line)
        for m in VAGUE_RE.finditer(line):
            f.append(("PR002", "medium", n, f"vague '{m.group(1)}': say who, how often, how much or by when"))
        if STEP.match(line):
            steps += 1
            body = STEP.sub("", line, count=1)
            if PASSIVE.search(body) and not re.search(r"\bby\b", body) and not re.match(r"\s*\*\*[^*]+\*\*", body):
                f.append(("PR003", "medium", n, f"passive step with no actor: '{body.strip()[:70]}'"))
            mm = MODAL.search(body)
            if mm:
                f.append(("PR004", "medium", n, f"'{mm.group(1)}' in a step: use 'must' or state the condition"))
            if len(body.split()) > 40:
                f.append(("PR006", "low", n, f"step has {len(body.split())} words; split it"))
    rec = "\n".join(records_text)
    if rec.strip() and not re.search(r"\d+\s*(years?|months?)|permanent|life of (the )?(part|product)|retention", rec, re.I):
        f.append(("PR005", "medium", 0, "records listed without retention periods"))
    if not re.search(r"revision|rev\b|rev\.|approved by|issue \d", text, re.I):
        f.append(("PR007", "low", 0, "no revision / approval block"))
    if not TIME.search(text):
        f.append(("PR008", "low", 0, "no step has a time limit or trigger; add 'within ...' or 'before ...'"))
    if steps > 25:
        f.append(("PR009", "low", 0, f"{steps} steps; split detail into work instructions"))
    return f, steps


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", help="procedure file, or - for stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings, steps = lint(text)
    if a.json:
        print(json.dumps([dict(zip(("code", "severity", "line", "message"), x)) for x in findings], indent=2))
    else:
        for code, sev, n, msg in findings:
            print(f"{code} [{sev}] {'line ' + str(n) + ': ' if n else ''}{msg}")
        print(f"\n{steps} step(s), {len(findings)} finding(s)" if findings else f"{steps} step(s): no findings.")
    return 1 if any(x[1] == "high" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
