---
name: supplier-development-plan-writer
description: "Prioritise and plan supplier development (IATF 16949 8.4.2.5, ISO 9001 8.4): rank suppliers by spend share, risk, performance gap and single-source exposure; decide develop, replace or monitor; and draft a dated 90-day development plan per selected supplier with kick-off, joint assessment, signed action plan, levers matched to each gap (process control, MSA, capability, problem solving, delivery and planning, APQP/PPAP, quality system, special processes, sub-tier control), on-site verification and close-out, plus PPM, OTD and score targets. Covers the develop-or-replace matrix, signs a development effort will or will not work, governance and records. Use when a key supplier keeps failing the scorecard, after repeated SCARs, when planning supplier quality engineering effort for the year, or before resourcing a part."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Supplier Development Plan Writer

Supplier development is an investment: it pays off for strategic, hard-to-replace suppliers who are willing to
change, and wastes effort on small, replaceable ones. `scripts/dev_plan.py` ranks suppliers, decides develop /
replace / monitor, and drafts a dated 90-day plan with the right levers for each gap.

## Trigger Conditions

Activate this skill when the user:
- Has a key supplier with poor scorecard results or repeated SCARs
- Is planning where supplier quality engineers should spend their time
- Must decide whether to develop or resource a supplier
- Needs a supplier development plan for a customer or IATF audit

Inputs: [supplier-quality-scorecard-builder](../supplier-quality-scorecard-builder/SKILL.md) for scores,
[supplier-corrective-action-request-writer](../supplier-corrective-action-request-writer/SKILL.md) for open SCARs.

## Workflow

```
1. DATA     -> supplier, spend, score, ppm, otd, risk, strategic, single_source, gaps
2. RANK     -> python scripts/dev_plan.py suppliers.csv --top 3 --start 2026-11-02
3. DECIDE   -> DEVELOP / REPLACE / MONITOR; confirm with purchasing (develop-or-replace.md)
4. KICK-OFF -> supplier management commits owner, data and targets
5. EXECUTE  -> levers per gap; weekly calls, monthly steering (plan-structure.md)
6. CLOSE    -> day 90 review: monitor, escalate or resource
```

## Example

```
Supplier           Spend %  Score    Risk   Index  Decision
CastCorp             31.1%     52    high   67.15  DEVELOP
SmallParts            1.6%     61     low    0.61  REPLACE
## Development plan: CastCorp  (score 52, PPM 7,600, OTD 81%)
Targets at day 90: PPM <= 3,800 (then <= 500), OTD >= 95%, score >= 80
  2026-12-02  day 30  process control: Control plan review on key characteristics; SPC with reaction plans; LPA at the supplier
```

Decision matrix and signs of success or failure: [develop-or-replace.md](references/develop-or-replace.md).
The 90-day structure, levers by gap, targets and governance: [plan-structure.md](references/plan-structure.md).

## Output Format

Deliver the priority table with decisions, then for each supplier to develop: current performance, targets,
the dated plan with owners, governance rhythm and the close-out criteria. List the suppliers to resource with the
reason.

## Scripts

```bash
python scripts/dev_plan.py suppliers.csv --top 3 --start 2026-11-02
python scripts/dev_plan.py suppliers.csv --ppm-target 500 --otd-target 95
```
Columns: supplier, spend, score, ppm, otd, risk, strategic, single_source, gaps (`;`-separated). Exit codes:
0 plan printed, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [develop-or-replace.md](references/develop-or-replace.md) | Decision matrix, priority index, signs development will or will not work |
| [plan-structure.md](references/plan-structure.md) | 90-day plan, levers by gap, targets, governance |
