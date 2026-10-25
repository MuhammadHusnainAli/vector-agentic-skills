---
name: pareto-defect-analyzer
description: "Analyse defect, scrap, rework and complaint data with Pareto charts: counts, quantities or cost-weighted Paretos with cumulative percentages and the vital few up to 80%, grouping of small categories into Other, stratified Paretos by line, shift, supplier or part, before/after comparison by period, and an SVG chart with the cumulative line. Warns when Other outgrows the top category, when the Pareto is flat (stratify differently), and when the count and cost Paretos disagree. Covers choosing count vs cost vs severity, rates vs counts, one-off events vs chronic losses, defect code design and the cost-of-defect model. Use when prioritising quality problems, building monthly scrap or complaint reports, selecting an improvement project, or checking that an action shrank the top defect."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Pareto Defect Analyzer

A Pareto says where to start: a few categories usually carry most of the defects or cost. It only helps if the
categories are specific, the measure matches the question (count vs cost), and the top bar is stratified until the
problem has an address (line, shift, supplier, part). `scripts/pareto.py` does all of that from a defect log.

## Trigger Conditions

Activate this skill when the user:
- Has scrap, rework, NCR or complaint data and wants to know what to fix first
- Needs a monthly Pareto for a quality report or management review
- Is choosing a Six Sigma or Kaizen project
- Wants to show that an improvement reduced the top defect

## Workflow

```
1. QUESTION -> what are we prioritising: frequency, cost or customer risk?
2. DATA     -> defect log with specific codes, quantity, cost, line, shift, period
3. PARETO   -> python scripts/pareto.py defects.csv --count qty --cost unit_cost
4. COST     -> python scripts/pareto.py defects.csv --count qty --cost unit_cost --weight cost --other 0.03
5. STRATIFY -> python scripts/pareto.py defects.csv --count qty --by line
6. ACT      -> project on the top bar with owner and target
7. CONFIRM  -> python scripts/pareto.py defects.csv --period month --compare 2026-08 2026-10
```

## Output

```
Category                             Count      %   Cum %
burr                                   289  35.6%   35.6%  *
scratch                                178  21.9%   57.5%  *
  line L2: total 437; top scratch 41%, burr 22%, oversize bore 16%
PA003 top by count is 'burr' but top by cost is 'oversize bore'
```

| Warning | Meaning |
|---------|---------|
| PA001 | "Other" bigger than the top category: categories too vague |
| PA002 | Flat Pareto: stratify by another factor |
| PA003 | Count and cost disagree on the top category |

Method, count vs cost, pitfalls and before/after comparison: [pareto-method.md](references/pareto-method.md).
Designing defect codes and the cost-of-defect model: [defect-coding.md](references/defect-coding.md).

## Output Format

Deliver:
1. **Question and measure** (count, quantity, cost, severity) and the period.
2. **Pareto table** with %, cumulative % and the vital few; SVG chart if useful.
3. **Stratification** of the top categories.
4. **Recommendation** - top one or two problems with owner and target; warnings resolved.
5. **Follow-up** - when to repeat the comparison.

## Scripts

```bash
python scripts/pareto.py defects.csv [--category defect] [--count qty] [--cost unit_cost --weight cost]
python scripts/pareto.py defects.csv --by line
python scripts/pareto.py defects.csv --period month --compare 2026-08 2026-10
python scripts/pareto.py defects.csv --other 0.03 --cut 0.8 --svg > pareto.svg
```
Exit codes: 0 printed, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [pareto-method.md](references/pareto-method.md) | Steps, count vs cost vs severity, pitfalls, before/after |
| [defect-coding.md](references/defect-coding.md) | Defect code rules, example code list, cost-of-defect model |
