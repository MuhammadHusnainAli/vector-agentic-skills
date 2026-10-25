#!/usr/bin/env python3
"""Review a quality manual (Markdown or plain text) against ISO 9001:2015 expectations.

Checks:
  QM001 high    no scope statement (4.3) naming products/services
  QM002 high    a clause is declared not applicable without a justification, or one that cannot be excluded
  QM003 high    no quality policy, or no reference to where it is
  QM004 medium  no description of processes and their interaction (4.4)
  QM005 medium  no revision / approval block
  QM006 medium  ISO 9001:2008 leftovers: management representative, preventive action procedure, 'quality
                manual' as a mandatory document, six mandatory procedures, ISO 9001:2008
  QM007 low     parrots the standard ('the organization shall'): a manual should say what *we* do
  QM008 low     unresolved placeholders (TODO, [Company], XXX, lorem ipsum)
  QM009 low     no mention of climate change in context (ISO 9001:2015/Amd 1:2024)

Usage:
    python manual_check.py quality-manual.md
    python manual_check.py manual.txt --json

Exit codes: 0 no high findings, 1 high findings, 2 read error.
"""

import argparse
import json
import re
import sys

MAY_NOT_APPLY = {"7.1.5", "8.3", "8.5.3", "8.5.5"}
LEGACY = [
    (r"management representative", "'management representative' was removed in 2015; assign the responsibilities in 5.3"),
    (r"preventive action", "preventive action is replaced by risk-based thinking (6.1); drop the separate procedure"),
    (r"six (mandatory|documented) procedures", "the six mandatory procedures no longer exist"),
    (r"ISO\s*9001\s*:\s*2008", "references ISO 9001:2008"),
    (r"quality manual (is|shall be) (required|mandatory)", "a quality manual is not mandatory since 2015"),
]
PLACEHOLDER = re.compile(r"\bTODO\b|\[company\]|\bXXX\b|lorem ipsum|<insert", re.I)
EXCL = re.compile(r"(not applicable|excluded?|exclusion|does not apply)", re.I)
CLAUSE = re.compile(r"\b(\d{1,2}(?:\.\d+){1,2})\b")


def check(text):
    low = text.lower()
    f = []
    if not re.search(r"\bscope\b", low) or not re.search(r"(product|service)", low):
        f.append(("QM001", "high", "no scope statement naming products/services and sites (4.3)"))
    for line in text.splitlines():
        if not EXCL.search(line):
            continue
        for c in CLAUSE.findall(line):
            if c.split(".")[0] not in {"4", "5", "6", "7", "8", "9", "10"}:
                continue
            if c not in MAY_NOT_APPLY and not c.startswith(("8.3.", "7.1.5.")):
                hint = " (7.3 was design in ISO 9001:2008; design is 8.3 now)" if c == "7.3" else ""
                f.append(("QM002", "high", f"clause {c} declared not applicable; it cannot be excluded{hint}: {line.strip()[:90]}"))
            elif len(EXCL.split(line, 1)[-1].split()) + len(line.split(c, 1)[-1].split()) < 8:
                f.append(("QM002", "high", f"clause {c} excluded without a convincing justification: {line.strip()[:90]}"))
    if "quality policy" not in low:
        f.append(("QM003", "high", "no quality policy and no reference to where it is (5.2)"))
    if not re.search(r"interaction|process map|turtle|sequence", low):
        f.append(("QM004", "medium", "processes and their sequence/interaction are not described (4.4)"))
    if not re.search(r"revision|rev\.|issue \d|approved by", low):
        f.append(("QM005", "medium", "no revision or approval block (7.5.2)"))
    for pat, msg in LEGACY:
        if re.search(pat, text, re.I):
            f.append(("QM006", "medium", msg))
    shall = len(re.findall(r"the organization shall", low))
    if shall >= 3:
        f.append(("QM007", "low", f"'the organization shall' appears {shall} times; describe what the company does, "
                                  "in its own words"))
    holes = len(PLACEHOLDER.findall(text))
    if holes:
        f.append(("QM008", "low", f"{holes} unresolved placeholder(s) (TODO, [Company], XXX)"))
    if "climate" not in low:
        f.append(("QM009", "low", "context section does not say whether climate change is a relevant issue (Amd 1:2024)"))
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("manual", help="Markdown or text file, or - for stdin")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        text = sys.stdin.read() if a.manual == "-" else open(a.manual, encoding="utf-8").read()
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    findings = check(text)
    if a.json:
        print(json.dumps([dict(zip(("code", "severity", "message"), x)) for x in findings], indent=2))
    else:
        for code, sev, msg in findings:
            print(f"{code} [{sev}] {msg}")
        high = sum(x[1] == "high" for x in findings)
        print(f"\n{len(findings)} finding(s), {high} high" if findings else "No findings: manual covers the expected content.")
    return 1 if any(x[1] == "high" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
