---
name: supplier-audit-questionnaire-builder
description: "Build and score supplier audit and self-assessment questionnaires for approving new suppliers or re-evaluating existing ones (ISO 9001 8.4, IATF 16949 8.4.2, AS9100): questions chosen by supplier type (machining, electronics, chemical, distributor, service) and risk level, weighted sections (management system, contract review, sub-tier control, process control, inspection and measurement, nonconforming product and CAPA, traceability and delivery, commodity specifics such as ESD, MSL, IPC-A-610, batch records, CoA, authorized-channel sourcing), knockout questions, evidence to request, and a 0-3 scoring scale. Scores completed questionnaires by section and overall, applies knockouts and returns approved, conditional (with improvement plan) or not approved. Covers supplier risk classes and on-site vs self-assessment. Use when onboarding a supplier, preparing a supplier audit, sending a supplier self-assessment, or deciding supplier approval."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Supplier Audit Questionnaire Builder

Supplier approval should depend on evidence that the supplier controls what matters for your product.
`scripts/questionnaire.py` assembles a weighted questionnaire for the supplier's type and risk;
`scripts/score_questionnaire.py` scores the answers, applies knockout questions and gives the approval decision.

## Trigger Conditions

Activate this skill when the user:
- Is onboarding a new supplier and needs a self-assessment or audit questionnaire
- Is preparing an on-site supplier audit
- Has a completed questionnaire and needs a score and approval decision
- Asks what to check at a machining, electronics, chemical, distributor or service supplier

After approval, the supplier goes on the [approved-supplier-list-manager](../approved-supplier-list-manager/SKILL.md)
and is monitored with [supplier-quality-scorecard-builder](../supplier-quality-scorecard-builder/SKILL.md).

## Workflow

```
1. CLASSIFY -> supplier type and risk (product impact, process complexity, spend, supply risk)
2. BUILD    -> python scripts/questionnaire.py --type machining --risk high --csv > sa.csv
3. SEND     -> supplier answers 0-3 with evidence for every 3; high risk: verify on site
4. SCORE    -> python scripts/score_questionnaire.py sa.csv
5. DECIDE   -> approved / conditional with improvement plan / not approved
6. RECORD   -> ASL entry with risk class, scope, decision, re-assessment date
```

## Question Selection

| Risk | Sections included |
|------|-------------------|
| low | Management system, process control and inspection (manufacturers), nonconforming product, distributor/service specifics |
| medium | + contract review and planning, sub-tier control, traceability and delivery |
| high | + commodity specifics (machining, electronics, chemical) and on-site verification |

Knockout questions (`[KO]`) cover accredited certification, controlled instructions, calibrated gauges,
segregation of nonconforming product, authorized sourcing for distributors and competence for services. Full
question sets with evidence: [question-sets.md](references/question-sets.md) (add questions there; the script reads it).

## Decision Rules

| Decision | Rule |
|----------|------|
| NOT APPROVED (knockout) | Any KO scored 0 or 1, whatever the total |
| APPROVED | Overall >= 85% and no section < 60% |
| CONDITIONAL | Overall >= 70%; improvement plan for sections below 70% |
| NOT APPROVED | Overall < 70% |
| INCOMPLETE | More than 10% unanswered |

```
Inspection, test and measurement                      4     58%
Overall weighted score: 89.5%
Decision: NOT APPROVED (knockout)
  knockout failed: 5.1 Are all gauges and test equipment calibrated and traceable to national (scored 1)
```

Risk classes, the scoring scale, self-assessment bias, improvement plans and weighting:
[scoring-and-approval.md](references/scoring-and-approval.md).

## Output Format

Deliver:
1. **Supplier classification** - type, risk class and why.
2. **Questionnaire** - sections, weights, questions, evidence requested, KO marks.
3. **Score** - section and overall percentages, knockouts, decision.
4. **Improvement plan** (if conditional) - gap, action, evidence, due date, verifier.
5. **Re-assessment date** and monitoring method.

## Scripts

```bash
python scripts/questionnaire.py --type electronics --risk high
python scripts/questionnaire.py --type distributor --risk low --csv > sa.csv
```
Exit codes: 0 printed, 2 invalid type or risk.

```bash
python scripts/score_questionnaire.py completed.csv
python scripts/score_questionnaire.py completed.csv --approve 90 --conditional 75
```
Scores: 0-3 (or no/partly/mostly/yes) and na. Exit codes: 0 approved, 1 conditional / not approved /
incomplete, 2 read or format error.

## Additional Resources

| File | Content |
|------|---------|
| [question-sets.md](references/question-sets.md) | Weighted sections and questions by supplier type and risk, knockouts, evidence (read by the script) |
| [scoring-and-approval.md](references/scoring-and-approval.md) | Risk classes and assessment depth, scoring scale, decision rules, improvement plans, weighting |
