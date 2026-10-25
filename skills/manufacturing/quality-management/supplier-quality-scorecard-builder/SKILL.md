---
name: supplier-quality-scorecard-builder
description: "Build supplier quality scorecards for ISO 9001 8.4 and IATF 16949 8.4.2.4 supplier monitoring: PPM from received and rejected quantities, on-time delivery, responsiveness to corrective action requests, scored 0-100 with configurable weights, a weighted total, A/B/C/D grades, trend against previous periods, and flags for grade D suppliers, two-period declines and PPM above target without a SCAR. Covers KPI definitions (PPM, incidents, OTD window, OTIF, premium freight, disruptions), normalising for low volumes and commodities, grade-to-action rules, the automotive escalation ladder (SCAR, executive escalation, controlled shipping levels 1 and 2, new-business hold, resourcing) and avoiding distorted scores. Use when setting up supplier monitoring, producing monthly or quarterly supplier scorecards, preparing a supplier review meeting, or deciding which suppliers need development or escalation."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Supplier Quality Scorecard Builder

A scorecard turns supplier performance into a number the supplier can reproduce and act on, and into decisions:
who gets new business, who gets reduced inspection, who gets a SCAR and a development plan.
`scripts/scorecard.py` scores quality, delivery and responsiveness per period, grades each supplier and flags
the ones that need action.

## Trigger Conditions

Activate this skill when the user:
- Needs a supplier scorecard or supplier performance monitoring (ISO 9001 8.4, IATF 8.4.2.4)
- Is preparing a quarterly supplier review or supplier day
- Wants to decide which suppliers to escalate, develop or reward
- Asks how to calculate supplier PPM or OTD

Actions for poor performers: [supplier-corrective-action-request-writer](../supplier-corrective-action-request-writer/SKILL.md),
[supplier-development-plan-writer](../supplier-development-plan-writer/SKILL.md).

## Workflow

```
1. DEFINE  -> KPI definitions (kpi-definitions.md), PPM target per commodity, weights
2. COLLECT -> per supplier per period: received, rejected, deliveries, on_time, scars, scars_on_time
3. SCORE   -> python scripts/scorecard.py supplier_perf.csv --ppm-target 500
4. REVIEW  -> grade D, decliners (SC002), silent quality problems (SC003)
5. ACT     -> grade-to-action rules and escalation ladder (grading-and-actions.md)
6. SHARE   -> each supplier gets its card, definitions and raw data
```

## Scoring

| Component | Basis | Points |
|-----------|-------|--------|
| Quality | PPM vs target | <= target 100, <= 2x 85, <= 5x 70, <= 10x 50, else 0 |
| Delivery | OTD % | >= 98 100, >= 95 85, >= 90 70, >= 85 50, else 0 |
| Responsiveness | SCARs answered on time | % on time (100 if none) |

```
Supplier                 PPM   OTD %    Q    D    R  Score  Grade  Trend
PlastiForm               886    96.6   85   85  100   88.0    B    flat
CastCorp               7,600    81.2    0    0   33    6.7    D    down
SC002 CastCorp: score fell two periods running (88 -> 56 -> 7)
SC003 PlastiForm: PPM 886 above target with no SCAR issued
```

KPI definitions, IATF monitoring requirements and normalising: [kpi-definitions.md](references/kpi-definitions.md).
Grade actions, escalation ladder, running the scorecard and avoiding distortion:
[grading-and-actions.md](references/grading-and-actions.md).

## Output Format

Deliver the scorecard table for the period, grade distribution, flags with the action for each supplier
(SCAR, development plan, inspection level change, escalation), and the definitions used.

## Scripts

```bash
python scripts/scorecard.py supplier_perf.csv --ppm-target 500
python scripts/scorecard.py supplier_perf.csv --period 2026-Q3 --weights 40 40 20
```
Columns: supplier, period, received, rejected, deliveries, on_time, scars, scars_on_time. Periods sort as text
(use 2026-Q3 or 2026-09). Exit codes: 0 no flags, 1 flags raised, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [kpi-definitions.md](references/kpi-definitions.md) | PPM, incidents, OTD, OTIF, responsiveness, premium freight, disruptions; normalising |
| [grading-and-actions.md](references/grading-and-actions.md) | Grade actions, escalation ladder, running the scorecard, distortion |
