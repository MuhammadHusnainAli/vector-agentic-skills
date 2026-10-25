#!/usr/bin/env python3
"""Build an audit report in Markdown from a JSON audit record, with the content ISO 19011 6.5.1 expects.

Audit JSON keys:
  audit_id, type (internal/supplier/certification-readiness), organization, site, objectives, scope,
  criteria (list), start, end, lead_auditor, team (list), auditees (list of roles), sampled (list),
  strengths (list), findings (list of {id, grade major/minor/ofi, clause, statement, evidence, requirement}),
  conclusion (optional; generated from the findings when absent), diverging_opinions, distribution (list),
  response_due_days (default 30)

Missing required content (objectives, scope, criteria, dates, lead auditor) is listed as RP001 warnings and
exits 1 so incomplete reports are not issued.

Usage:
    python report_build.py audit.json > report.md

Exit codes: 0 report complete, 1 report written but required content missing, 2 read or JSON error.
"""

import argparse
import json
import sys
from collections import Counter

REQUIRED = ["objectives", "scope", "criteria", "start", "lead_auditor"]
GRADE_ORDER = {"major": 0, "minor": 1, "ofi": 2}


def conclusion(a, counts):
    if counts["major"]:
        return (f"The management system is not effectively implemented within the audit scope: {counts['major']} major "
                f"nonconformit{'y' if counts['major'] == 1 else 'ies'} show(s) a required process absent or broken down. "
                "Corrective action and verification are required before the next milestone.")
    if counts["minor"]:
        return (f"The management system is implemented and generally effective within the audit scope, with "
                f"{counts['minor']} minor nonconformit{'y' if counts['minor'] == 1 else 'ies'} requiring corrective action.")
    return "The management system conforms to the audit criteria and is effectively implemented within the audit scope."


def bullet(items):
    return "\n".join(f"- {x}" for x in items) if items else "- None recorded."


def render(a):
    f = sorted(a.get("findings", []), key=lambda x: (GRADE_ORDER.get(str(x.get("grade", "")).lower(), 3), str(x.get("id"))))
    counts = Counter(str(x.get("grade", "")).lower() for x in f)
    due = a.get("response_due_days", 30)
    rows = ["| ID | Grade | Clause | Finding |", "|----|-------|--------|---------|"]
    rows += [f"| {x.get('id')} | {x.get('grade', '').upper()} | {x.get('clause', '')} | {x.get('statement', '')} |" for x in f]
    detail = []
    for x in f:
        detail.append(f"### {x.get('id')} - {x.get('grade', '').upper()} - {x.get('clause', '')}\n")
        if x.get("requirement"):
            detail.append(f"**Requirement:** {x['requirement']}\n")
        detail.append(f"**Evidence:** {x.get('evidence', 'TODO')}\n")
        detail.append(f"**Statement:** {x.get('statement', 'TODO')}\n")
    end = a.get("end") or a.get("start", "TODO")
    return f"""# Audit Report {a.get('audit_id', 'TODO')} - {a.get('organization', 'TODO')}

| | |
|---|---|
| Audit type | {a.get('type', 'internal')} |
| Site | {a.get('site', 'TODO')} |
| Dates | {a.get('start', 'TODO')} to {end} |
| Lead auditor | {a.get('lead_auditor', 'TODO')} |
| Audit team | {', '.join(a.get('team', [])) or '-'} |
| Auditees | {', '.join(a.get('auditees', [])) or 'TODO'} |

## 1. Summary
{a.get('conclusion') or conclusion(a, counts)}

| Major | Minor | OFI |
|-------|-------|-----|
| {counts['major']} | {counts['minor']} | {counts['ofi']} |

## 2. Objectives
{a.get('objectives', 'TODO')}

## 3. Scope
{a.get('scope', 'TODO')}

## 4. Criteria
{bullet(a.get('criteria', []))}

## 5. Method and sampling
The audit was performed by interviews, observation and review of records on a sample basis; findings relate
only to the items sampled and other nonconformities may exist. Items sampled:
{bullet(a.get('sampled', []))}

## 6. Strengths
{bullet(a.get('strengths', []))}

## 7. Findings
{chr(10).join(rows)}

{chr(10).join(detail) if detail else 'No findings.'}
## 8. Diverging opinions
{a.get('diverging_opinions') or 'None. Findings were presented and agreed at the closing meeting.'}

## 9. Follow-up
Nonconformities require a response with containment/correction, root cause, corrective action, owner and due
date within {due} days of this report. Major nonconformities are verified before closure; OFIs are for the
auditee's consideration.

## 10. Distribution
{bullet(a.get('distribution', []))}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audit", help="audit JSON, or - for stdin")
    args = ap.parse_args()
    try:
        a = json.load(sys.stdin if args.audit == "-" else open(args.audit, encoding="utf-8"))
        if not isinstance(a, dict):
            raise ValueError("audit JSON must be an object")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(render(a))
    missing = [k for k in REQUIRED if not a.get(k)]
    for k in missing:
        print(f"RP001 [high] report lacks '{k}' (ISO 19011 6.5.1)", file=sys.stderr)
    for x in a.get("findings", []):
        if str(x.get("grade", "")).lower() in ("major", "minor") and not (x.get("evidence") and x.get("clause")):
            print(f"RP002 [high] finding {x.get('id')} has no clause or evidence", file=sys.stderr)
            missing.append(x.get("id"))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
