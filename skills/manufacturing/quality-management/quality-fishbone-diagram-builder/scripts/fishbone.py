#!/usr/bin/env python3
"""Build an Ishikawa (fishbone) diagram from a cause list, check it, and list what to verify next.

CSV columns: category, cause, subcause (optional), status (untested/likely/verified/ruled-out), evidence
Categories are normalised to the 6M: Man, Machine, Method, Material, Measurement, Environment
(aliases: people/personnel -> Man, equipment/tooling -> Machine, process/procedure -> Method,
 materials/supplier -> Material, inspection/gauge -> Measurement, mother nature/surroundings -> Environment).
Other category names are kept as extra bones (e.g. Management, Software for services).

Checks:
  FB001 medium  a 6M bone is empty - brainstorm it before concluding
  FB002 medium  a 'cause' is a solution ('need', 'should', 'install', 'buy') - restate it as the condition
  FB003 medium  a cause blames a person - restate it as the process condition
  FB004 low     duplicate cause on several bones
  FB005 low     nothing is marked likely or verified yet - vote or test the top candidates

Usage:
    python fishbone.py causes.csv --problem "Scratches on HS-110 face A"
    python fishbone.py causes.csv --problem "..." --format mermaid > fishbone.mmd

Exit codes: 0 diagram printed (no medium findings), 1 medium findings, 2 read error.
"""

import argparse
import csv
import re
import sys
from collections import OrderedDict

SIX_M = ["Man", "Machine", "Method", "Material", "Measurement", "Environment"]
ALIASES = {"people": "Man", "personnel": "Man", "manpower": "Man", "operator": "Man", "equipment": "Machine",
           "machines": "Machine", "tooling": "Machine", "process": "Method", "methods": "Method", "procedure": "Method",
           "materials": "Material", "supplier": "Material", "measurements": "Measurement", "inspection": "Measurement",
           "gauge": "Measurement", "environment": "Environment", "mother nature": "Environment", "surroundings": "Environment"}
SOLUTION = re.compile(r"^\s*(need|needs|should|must|install|buy|add|implement|use a|get a)\b|\bshould\b", re.I)
BLAME = re.compile(r"\b(careless|lazy|forgot|operator error|human error|not paying attention|bad attitude)\b", re.I)
MARK = {"verified": "[V]", "likely": "[L]", "ruled-out": "[x]", "untested": "[ ]", "": "[ ]"}


def norm(cat):
    c = cat.strip()
    if c.title() in SIX_M:
        return c.title()
    return ALIASES.get(c.lower(), c.strip().title() or "Other")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", help="cause list CSV, or - for stdin")
    ap.add_argument("--problem", default="Problem", help="effect at the fish head")
    ap.add_argument("--format", choices=["text", "mermaid"], default="text")
    a = ap.parse_args()
    try:
        fh = sys.stdin if a.csv == "-" else open(a.csv, newline="", encoding="utf-8-sig")
        with fh:
            rows = list(csv.DictReader(fh))
    except (OSError, csv.Error) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not rows or not {"category", "cause"} <= set(rows[0]):
        print("error: CSV needs category and cause columns", file=sys.stderr)
        return 2
    bones = OrderedDict((m, OrderedDict()) for m in SIX_M)
    findings, seen = [], {}
    for r in rows:
        cat, cause = norm(r["category"]), (r["cause"] or "").strip()
        if not cause:
            continue
        status = (r.get("status") or "").strip().lower()
        node = bones.setdefault(cat, OrderedDict()).setdefault(cause, {"status": status, "subs": [], "evidence": r.get("evidence", "")})
        if r.get("subcause", "").strip():
            node["subs"].append(r["subcause"].strip())
        if status in ("verified", "likely"):
            node["status"] = status
        key = cause.lower()
        if key in seen and seen[key] != cat:
            findings.append(("FB004", "low", f"'{cause}' appears on {seen[key]} and {cat}: keep it on one bone"))
        seen.setdefault(key, cat)
        if SOLUTION.search(cause):
            findings.append(("FB002", "medium", f"{cat}: '{cause}' is a solution; write the condition it would fix"))
        if BLAME.search(cause):
            findings.append(("FB003", "medium", f"{cat}: '{cause}' blames a person; describe the process condition"))
    for m in SIX_M:
        if not bones[m]:
            findings.append(("FB001", "medium", f"{m} bone is empty: brainstorm it (see 6m-prompts.md)"))
    candidates = [(c, cat, n) for cat, causes in bones.items() for c, n in causes.items() if n["status"] in ("likely", "verified")]
    if not candidates:
        findings.append(("FB005", "low", "no cause marked likely or verified: multi-vote, then test the top 3"))

    if a.format == "mermaid":
        print("flowchart LR")
        print(f'  head["{a.problem}"]')
        for i, (cat, causes) in enumerate(bones.items()):
            if not causes:
                continue
            print(f'  b{i}["{cat}"] --> head')
            for j, (c, n) in enumerate(causes.items()):
                print(f'  c{i}_{j}["{MARK.get(n["status"], "[ ]")} {c}"] --> b{i}')
                for k, s in enumerate(n["subs"]):
                    print(f'  s{i}_{j}_{k}["{s}"] --> c{i}_{j}')
    else:
        print(f"EFFECT: {a.problem}\n")
        for cat, causes in bones.items():
            print(f"{cat}")
            if not causes:
                print("  (empty)")
            for c, n in causes.items():
                print(f"  {MARK.get(n['status'], '[ ]')} {c}")
                for s in n["subs"]:
                    print(f"        - {s}")
        print("\nKey: [V] verified  [L] likely  [x] ruled out  [ ] untested")
        if candidates:
            print("\nVerify next (likely causes) / root causes (verified):")
            for c, cat, n in sorted(candidates, key=lambda x: x[2]["status"] != "verified"):
                print(f"  {MARK[n['status']]} {cat}: {c}" + (f"  - {n['evidence']}" if n["evidence"] else ""))
    out = sys.stderr if a.format == "mermaid" else sys.stdout
    if findings:
        print(file=out)
    for code, sev, msg in findings:
        print(f"{code} [{sev}] {msg}", file=out)
    return 1 if any(x[1] == "medium" for x in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
