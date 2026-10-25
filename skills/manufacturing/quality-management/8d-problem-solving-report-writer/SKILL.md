---
name: 8d-problem-solving-report-writer
description: "Write and review 8D problem-solving reports for customer complaints and serious nonconformities (automotive and aerospace practice: Ford Global 8D, VDA, GM, Stellantis formats): D0 emergency response, D1 cross-functional team and champion, D2 problem description with 5W2H and is / is-not and no cause in the statement, D3 interim containment within 24 hours with verification and clean point, D4 verified occurrence and escape (non-detection) root causes plus systemic cause, D5 permanent corrective actions for each cause verified before implementation, D6 implementation, validation with production data and removal of containment, D7 PFMEA, control plan and read-across to similar products, D8 closure and recognition. Checks an 8D discipline by discipline for missing content, human-error root causes, missing escape cause or action, late containment and dates out of order. Use when a customer demands an 8D, reviewing a supplier's 8D, or coaching a team through one."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# 8D Problem-Solving Report Writer

Customers read an 8D to answer three questions: are we protected now (D3), do you know why it happened and why you
did not catch it (D4), and will it stay fixed everywhere (D5-D7)? `scripts/eightd_check.py` reviews an 8D the way a
customer quality engineer does and shows which disciplines are complete.

## Trigger Conditions

Activate this skill when the user:
- Received a customer complaint that requires an 8D
- Needs to review a supplier's 8D before accepting it
- Is leading or coaching an 8D team
- Had an 8D rejected by a customer

For simpler internal problems use [capa-plan-writer](../capa-plan-writer/SKILL.md); for the cause analysis itself,
[five-whys-analysis-facilitator](../five-whys-analysis-facilitator/SKILL.md) and
[quality-fishbone-diagram-builder](../quality-fishbone-diagram-builder/SKILL.md).

## Workflow

```
D0  Emergency response: safety, line-stop, notify
D1  Champion + cross-functional team (>= 3 roles)
D2  5W2H + is / is-not; effect only, no cause            (problem-description-tools.md)
D3  Contain within 24 h: stock, WIP, transit, customer; verify; clean point
D4  Occurrence AND escape root cause, each verified; systemic cause
D5  Action per cause, verified by trial before implementation
D6  Implement, validate with production data, then remove D3
D7  PFMEA, control plan, WIs, read-across to similar products and sites
D8  Close with the customer; recognise the team
CHECK -> python scripts/eightd_check.py 8d.json
```

Content, deadlines and rejection reasons per discipline, occurrence/escape/systemic legs, verification vs
validation and the clean point: [8d-disciplines.md](references/8d-disciplines.md).

## Checks (eightd_check.py)

| Code | Severity | Problem |
|------|----------|---------|
| 8D01 | medium | Team under 3 roles or no champion |
| 8D02 | high | D2 misses 5W2H elements or is/is-not, or states a cause |
| 8D03 | high | D3 missing, unverified or later than 24 h |
| 8D04 | high | Occurrence or escape cause missing, unverified or human error |
| 8D05 | high | No action for occurrence or escape, or actions not verified |
| 8D06 | medium | No validation, or containment not removed |
| 8D07 | medium | No FMEA / control plan update or read-across |
| 8D08 | medium | Dates out of order; D4 later than target |
| 8D09 | low | D8 missing |

```
8D 8D-C40: D1 --  D2 --  D3 --  D4 --  D5 --  D6 --  D7 --  D8 --
8D04 [high] D4: occurrence cause 'Operator error' is human error; why did the process allow it?
8D04 [high] D4: no escape root cause (why was it not detected?)
```

## Output Format

Deliver the 8D as one section per discipline (D0-D8) with dates and owners, D2 as a 5W2H table plus is/is-not
table, D4 with occurrence, escape and systemic causes and their verification evidence, D5/D6 as an action table
(action, cause leg, owner, verification, implementation date, validation result), and D7 listing every document
and similar product updated. Finish with the `eightd_check.py` status line.

## Scripts

```bash
python scripts/eightd_check.py 8d.json
python scripts/eightd_check.py 8d.json --d3-hours 48 --d4-days 15     # customer-specific deadlines
```
Keys: id, opened, champion, team, d2 (what, where, when, how_many, how_detected, is_not), d3 (actions, date,
verified), d4 (date, occurrence_cause, occurrence_verified, escape_cause, escape_verified, method), d5 (actions
with addresses occurrence/escape, verified), d6 (date, validation, containment_removed), d7 (fmea_updated,
control_plan_updated, similar_products, lessons_learned), d8 (date, recognition). Exit codes: 0 no high issues,
1 high issues, 2 read or JSON error.

## Additional Resources

| File | Content |
|------|---------|
| [8d-disciplines.md](references/8d-disciplines.md) | Each discipline's content, deadlines and rejection reasons; occurrence/escape/systemic; verification vs validation; clean point |
| [problem-description-tools.md](references/problem-description-tools.md) | 5W2H, is / is-not with distinctions, problem statement template |
