#!/usr/bin/env python3
"""Generate a QMS procedure in Markdown from a JSON process description.

Produces the standard sections (purpose, scope, responsibilities, definitions, procedure steps with an actor
for every step, records with retention, references, revision history) plus a RACI table built from the steps.

Spec (JSON):
  {
    "id": "QP-07", "title": "Control of Nonconforming Product", "owner": "Quality manager",
    "purpose": "...", "scope": "...", "clauses": ["8.7", "10.2"],
    "definitions": {"MRB": "Material Review Board"},
    "steps": [
      {"actor": "Inspector", "action": "Tag the part red and move it to quarantine", "record": "NCR form QF-07"},
      {"actor": "Quality engineer", "action": "Decide disposition within 2 working days",
       "consulted": ["Production manager"], "informed": ["Customer"]}
    ],
    "records": [{"name": "NCR form QF-07", "retention": "10 years", "location": "QMS database"}],
    "references": ["QP-08 Corrective action"]
  }

Usage:
    python procedure_scaffold.py spec.json > QP-07.md

Exit codes: 0 written, 1 spec has steps without an actor or action, 2 read or JSON error.
"""

import argparse
import json
import sys


def load(path):
    fh = sys.stdin if path == "-" else open(path, encoding="utf-8")
    with fh:
        spec = json.load(fh)
    if not isinstance(spec, dict) or not spec.get("title") or not isinstance(spec.get("steps"), list):
        raise ValueError("spec must be an object with 'title' and a 'steps' list")
    return spec


def raci(steps, owner):
    roles = []
    for s in steps:
        for r in [s.get("actor")] + s.get("consulted", []) + s.get("informed", []):
            if r and r not in roles:
                roles.append(r)
    head = "| Step | " + " | ".join(roles) + " |"
    sep = "|------|" + "|".join("-" * (len(r) + 2) for r in roles) + "|"
    rows = [head, sep]
    for i, s in enumerate(steps, 1):
        cells = []
        for r in roles:
            cell = "R" if r == s.get("actor") else "C" if r in s.get("consulted", []) else "I" if r in s.get("informed", []) else ""
            if r == owner and cell == "R":
                cell = "A/R"
            cells.append(cell)
        rows.append(f"| {i} | " + " | ".join(cells) + " |")
    return "\n".join(rows) + f"\n\nAccountable for the procedure: {owner}."


def render(sp):
    steps = sp["steps"]
    defs = "\n".join(f"- **{k}** - {v}" for k, v in sp.get("definitions", {}).items()) or "- None."
    step_lines = []
    for i, s in enumerate(steps, 1):
        line = f"{i}. **{s['actor']}** - {s['action']}."
        if s.get("record"):
            line += f" Record: {s['record']}."
        step_lines.append(line)
    recs = ["| Record | Retention | Location |", "|--------|-----------|----------|"]
    recs += [f"| {r['name']} | {r.get('retention', 'TODO')} | {r.get('location', 'TODO')} |" for r in sp.get("records", [])]
    refs = "\n".join(f"- {r}" for r in sp.get("references", [])) or "- None."
    clauses = ", ".join(sp.get("clauses", [])) or "TODO"
    return f"""# {sp.get('id', 'QP-XX')} {sp['title']}

| Revision | Owner | Approved by | Effective date |
|----------|-------|-------------|----------------|
| A | {sp.get('owner', 'TODO')} | TODO | TODO |

## 1. Purpose
{sp.get('purpose', 'TODO one or two sentences on why this procedure exists')}

## 2. Scope
{sp.get('scope', 'TODO where it applies and where it does not')}
ISO 9001:2015 clauses: {clauses}.

## 3. Responsibilities
{raci(steps, sp.get('owner', ''))}

## 4. Definitions
{defs}

## 5. Procedure
{chr(10).join(step_lines)}

## 6. Records
{chr(10).join(recs)}

## 7. References
{refs}

## 8. Revision history
| Rev | Date | Change | By |
|-----|------|--------|----|
| A | TODO | First issue | {sp.get('owner', 'TODO')} |
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", help="JSON spec, or - for stdin")
    a = ap.parse_args()
    try:
        sp = load(a.spec)
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    bad = [i for i, s in enumerate(sp["steps"], 1) if not s.get("actor") or not s.get("action")]
    if bad:
        print(f"error: step(s) {', '.join(map(str, bad))} need both 'actor' and 'action'; every step needs a role",
              file=sys.stderr)
        return 1
    print(render(sp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
