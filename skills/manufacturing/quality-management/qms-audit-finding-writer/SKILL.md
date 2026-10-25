---
name: qms-audit-finding-writer
description: "Write audit nonconformities and observations that auditees accept and can act on: the three-part structure (requirement with clause, objective re-checkable evidence with record IDs, dates and sample size, one-sentence nonconformity statement), fact-only wording without opinions, names or prescribed solutions, and correct grading as major, minor or opportunity for improvement (ISO/IEC 17021-1, IATF 16949 and AS9100 practice). Lints findings for missing requirement or evidence, advice graded as a nonconformity, opinion words, named individuals, prescribed solutions, likely grade mismatches (single lapse graded major, total absence graded minor), vague quantities, missing sample sizes and overlong statements. Use when writing up internal, supplier or certification audit findings, reviewing an audit report, training auditors, or disputing how a finding was graded."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# QMS Audit Finding Writer

A finding is only useful if the auditee can verify it, find its cause and show it closed. That needs three parts:
**requirement**, **evidence**, **statement**, plus a grade that matches the evidence. `scripts/finding_lint.py`
checks a set of findings for the mistakes that cause disputes and weak corrective actions.

## Trigger Conditions

Activate this skill when the user:
- Is writing up nonconformities or OFIs after an internal, supplier or certification audit
- Wants findings reviewed before issuing the audit report
- Is unsure whether a finding is major, minor or an OFI
- Is training new auditors, or disputing a grade given by an external auditor

Full report around the findings: [audit-report-writer](../audit-report-writer/SKILL.md).

## Workflow

```
1. COLLECT  -> for each issue: requirement source, exact evidence (IDs, dates, locations, x of y sampled)
2. WRITE    -> requirement + evidence + statement (finding-anatomy.md)
3. GRADE    -> major / minor / OFI using the decision questions (grading-criteria.md)
4. LINT     -> python scripts/finding_lint.py findings.json
5. AGREE    -> confirm facts with the auditee at the closing meeting
6. ISSUE    -> in the report, with response deadlines per grade
```

## Finding Template

```
NC-01  Grade: minor   Clause: ISO 9001 7.1.5.2 a)
Requirement: Measuring equipment shall be calibrated at specified intervals against traceable standards.
Evidence:    At lathe 4, micrometer M-112 was in use with calibration due 2026-08-01 (CAL-REG).
             1 of 8 gauges sampled at the station was overdue.
Statement:   Measuring equipment used for product acceptance was not always within its calibration interval.
```

Before/after rewrites for common findings and the six writing rules:
[finding-anatomy.md](references/finding-anatomy.md).

## Grading

| Grade | When |
|-------|------|
| Major | Required process absent or broken down; nonconforming product shipped because of it; systemic or repeated |
| Minor | Single, isolated lapse; system still capable |
| OFI | No requirement broken; a risk or weakness |

Definitions (ISO/IEC 17021-1, IATF, AS9100), decision questions, graded examples and response times:
[grading-criteria.md](references/grading-criteria.md).

## Lint Codes (finding_lint.py)

| Code | Severity | Problem |
|------|----------|---------|
| AF001 | high | Nonconformity without clause/requirement |
| AF002 | high | No evidence, or nothing verifiable in it |
| AF003 | high | Advice ("consider", "could be improved") graded as a nonconformity |
| AF004 | medium | Opinion words |
| AF005 | medium | Names a person |
| AF006 | medium | Prescribes the solution |
| AF007 | medium | Grade does not match the evidence |
| AF008 | low | Vague quantities |
| AF009 | low | No sample size |
| AF010 | low | Statement over 50 words |

```
NC-02 (minor): 1 issue(s)
    AF007 [medium] graded minor but describes a total absence ('No internal audits'): likely major
```

## Output Format

For each finding give: ID, grade, clause, requirement, evidence, statement, and the response expected
(containment / root cause / action / due date). Then a summary: counts by grade and any lint issues resolved.

## Scripts

```bash
python scripts/finding_lint.py findings.json
python scripts/finding_lint.py findings.csv --json
```
Keys/columns: id, grade (major/minor/ofi), clause, requirement, evidence, statement. The checks are wording
heuristics: confirm each suggestion against the evidence. Exit codes: 0 no high issues, 1 high issues,
2 read or format error.

## Additional Resources

| File | Content |
|------|---------|
| [finding-anatomy.md](references/finding-anatomy.md) | Three-part structure, before/after rewrites, writing rules, OFIs |
| [grading-criteria.md](references/grading-criteria.md) | Major/minor/OFI definitions incl. IATF and AS9100, decision questions, examples, response times |
