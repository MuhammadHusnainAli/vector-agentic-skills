---
name: iso-audit-checklist-generator
description: "Generate ISO 9001 internal or supplier audit checklists for a process (leadership, sales, design, purchasing, production, inspection, warehouse, maintenance, HR, quality) or for chosen clauses: open 'show me' questions with the evidence to sample, the clauses asked in every process audit (risks, objectives, competence, documented information, monitoring, corrective action), and optional turtle-diagram questions (inputs, outputs, with what, with whom, how, measures). Outputs a Markdown table or a CSV to fill in with results. Covers how to use a checklist: process approach, audit trails, sample sizes, questioning techniques, recording conforming evidence, nonconformities and OFIs. Use when preparing an internal audit, a process audit, a clause-based system audit or a pre-certification audit, or when someone asks 'what should I ask when auditing purchasing?'."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# ISO Audit Checklist Generator

A good audit checklist asks open questions, says what evidence to sample, and follows the process rather
than reading the standard aloud. `scripts/checklist.py` builds one from a question bank of about 70 questions
covering every clause family; the bank lives in `references/question-bank.md` and can be extended.

## Trigger Conditions

Activate this skill when the user:
- Needs a checklist for an upcoming internal audit or process audit
- Asks what to ask or what evidence to look at when auditing a process or clause
- Is preparing auditors for a pre-certification or surveillance audit
- Wants a fill-in audit record (CSV) for the audit team

Scheduling the audits: [internal-audit-schedule-planner](../internal-audit-schedule-planner/SKILL.md); writing up
the nonconformities: [qms-audit-finding-writer](../qms-audit-finding-writer/SKILL.md).

## Workflow

```
1. SCOPE    -> process or clauses, site, date, auditor (from the audit programme)
2. PREPARE  -> previous report, open CAPAs, KPIs, complaints, recent changes for this process
3. GENERATE -> python scripts/checklist.py --process production --turtle
4. TAILOR   -> add questions on recent problems; remove what does not apply; pick audit trails
5. AUDIT    -> follow the work; sample records yourself; record evidence for every C, NC and OFI
6. CLOSE    -> agree facts at the closing meeting; write findings and report
```

## Process -> Clause Sets

| Process | Clauses | Plus in every process audit |
|---------|---------|-----------------------------|
| leadership | 4.1-4.4, 5.1-5.3, 6.3, 9.3, 10.3 | 6.1, 6.2, 7.2, 7.5, 9.1, 10.2 |
| sales | 8.2, 7.4 | same |
| design | 8.3, 7.1.6 | same |
| purchasing | 8.4 | same |
| production | 8.1, 8.5.1, 8.5.2, 8.5.6, 7.1.3, 7.1.5, 7.3 | same |
| inspection | 8.6, 8.7, 7.1.5, 8.5.2 | same |
| warehouse | 8.5.4, 8.5.2, 8.6 | same |
| maintenance | 7.1.3 | same |
| hr | 7.2, 7.3, 7.1.6 | same |
| quality | 9.1, 9.2, 10.2, 8.7, 7.5 | same |

Use `--no-common` to drop the common set, or `--clauses` for a clause-based system audit. All questions and
their evidence: [question-bank.md](references/question-bank.md).

## Example Output

```
| 7 | 6.1 Risks and opportunities | Show me the risks and opportunities for this process and the actions taken. | Risk register, action status |  |  |
| 15 | 8.4 External providers | Show me a purchase order: does it state the drawing revision, quality requirements and verification? | PO |  |  |
```

Turtle diagram, audit trails, sample sizes, questioning do's and don'ts, and how to record each result:
[auditing-techniques.md](references/auditing-techniques.md).

## Output Format

Deliver:
1. **Audit header** - process/clauses, criteria (ISO 9001:2015 + internal procedures), date, auditor, auditee.
2. **Checklist** - numbered questions with clause, evidence to sample and empty result/notes columns.
3. **Tailored additions** - questions from previous findings, complaints and changes.
4. **Planned audit trails** - which orders, NCRs or suppliers will be followed.

## Scripts

```bash
python scripts/checklist.py --process purchasing --turtle
python scripts/checklist.py --clauses 8.4 8.5.1 7.1.5
python scripts/checklist.py --process production --csv > checklist.csv
python scripts/checklist.py --list-processes
```
Clause families expand (`8.5` -> all 8.5.x) and sub-clauses resolve to their parent. Exit codes: 0 printed,
1 no questions matched, 2 no selection or unknown process.

## Additional Resources

| File | Content |
|------|---------|
| [question-bank.md](references/question-bank.md) | Open audit questions with evidence to sample, by clause (read by the script) |
| [auditing-techniques.md](references/auditing-techniques.md) | Turtle diagram, audit trails, sample sizes, questioning, recording results, preparation |
