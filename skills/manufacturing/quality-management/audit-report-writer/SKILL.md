---
name: audit-report-writer
description: "Write internal, supplier and pre-certification audit reports with the content ISO 19011:2018 6.5 expects: audit objectives, scope, criteria with revisions, dates, team and auditees, method and sampling statement, specific strengths, findings table and three-part finding details (requirement, evidence, statement), conclusion on the degree of fulfilment of criteria, diverging opinions, follow-up deadlines and distribution. Builds a Markdown report from a JSON audit record, generates the conclusion from the findings (major / minor / none) and flags reports missing required content or findings without clause or evidence. Covers conclusion wording, closing meetings, response expectations and verifying corrective actions. Use when writing up an audit, standardising the audit report template, reviewing an auditor's report, or preparing management review inputs from audits."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Audit Report Writer

An audit report must let a reader who was not there understand what was audited, against what, what was found
with what evidence, and what the auditee must do next. `scripts/report_build.py` builds the report from a JSON
audit record and refuses to call a report complete when ISO 19011 content is missing.

## Trigger Conditions

Activate this skill when the user:
- Has finished an internal, supplier or readiness audit and needs the report
- Wants a standard audit report template for the audit programme
- Needs an auditor's report reviewed for completeness
- Must summarise audit results for management review

Individual findings: [qms-audit-finding-writer](../qms-audit-finding-writer/SKILL.md).

## Workflow

```
1. RECORD   -> audit.json: objectives, scope, criteria, dates, team, auditees, sampled items, strengths, findings
2. CHECK    -> lint findings first (qms-audit-finding-writer)
3. BUILD    -> python scripts/report_build.py audit.json > report.md
4. CONCLUDE -> review the generated conclusion; tailor it to the audit objectives
5. CLOSE    -> closing meeting: present strengths and findings, agree facts, set deadlines
6. ISSUE    -> within 5 working days; track responses and verification
```

## Report Structure

| Section | Content |
|---------|---------|
| Header | Type, site, dates, lead auditor, team, auditees |
| 1 Summary | Conclusion + count of major / minor / OFI |
| 2-4 | Objectives, scope, criteria (with revisions) |
| 5 Method and sampling | What was sampled; audit is a sample |
| 6 Strengths | Specific, evidence-based |
| 7 Findings | Table, then requirement / evidence / statement per finding |
| 8 Diverging opinions | Or "none, agreed at closing meeting" |
| 9 Follow-up | Response content and deadline |
| 10 Distribution | Who receives the report |

Required vs recommended elements, conclusion patterns and specific strengths:
[report-contents.md](references/report-contents.md). Closing meeting agenda, response expectations and how
to verify and close findings: [closing-meeting-and-follow-up.md](references/closing-meeting-and-follow-up.md).

## Generated Conclusion

| Findings | Conclusion |
|----------|------------|
| Any major | Not effectively implemented; corrective action and verification required |
| Minors only | Implemented and generally effective, with N minor nonconformities |
| None | Conforms and is effectively implemented within the scope |

## Output Format

Deliver the report Markdown (from `report_build.py`), followed by:
1. **Completeness check** - RP001/RP002 warnings resolved.
2. **Response tracker** - finding, owner, due date for root cause/action, verification method.

## Scripts

```bash
python scripts/report_build.py audit.json > report.md
```
Keys: audit_id, type, organization, site, objectives, scope, criteria, start, end, lead_auditor, team, auditees,
sampled, strengths, findings (id, grade, clause, requirement, evidence, statement), conclusion, diverging_opinions,
distribution, response_due_days. Warnings go to stderr: RP001 missing objectives/scope/criteria/start/lead
auditor, RP002 nonconformity without clause or evidence. Exit codes: 0 complete, 1 written but incomplete,
2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [report-contents.md](references/report-contents.md) | ISO 19011 6.5 content, conclusion patterns, strengths, timing and style |
| [closing-meeting-and-follow-up.md](references/closing-meeting-and-follow-up.md) | Closing meeting agenda, response expectations, verification and closure, feeding the programme |
