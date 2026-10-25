---
name: acceptance-sampling-plan-selector
description: "Select and evaluate acceptance sampling plans for incoming, in-process and final inspection: ANSI/ASQ Z1.4 / ISO 2859-1 single sampling under normal inspection (code letter from lot size and inspection level I, II, III, S-1 to S-4; sample size, Ac and Re from AQL, following the table's arrows to the correct plan; 100% when n reaches the lot size; AQLs above 10 per 100 units), operating characteristic curves (Pa at any quality, producer's quality level, indifference point, LTPD, AOQ and AOQL, binomial or hypergeometric), plans designed from producer and consumer risk, and c = 0 zero-acceptance plans. Covers AQL choice by defect class, switching rules between normal, tightened and reduced inspection, when sampling is not appropriate, and random sampling. Use when setting up incoming inspection, picking an AQL plan, checking whether a plan protects against bad lots, or answering a customer's c = 0 requirement."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Acceptance Sampling Plan Selector

A sampling plan is a risk trade: the AQL says what quality passes most of the time, the OC curve says what bad
quality still slips through. `scripts/z14_plan.py` reads ANSI/ASQ Z1.4 (normal inspection) correctly, including the
arrows that change the sample size; `scripts/oc_curve.py` shows the protection a plan gives, designs plans from
producer and consumer risks, and sizes c = 0 plans.

## Trigger Conditions

Activate this skill when the user:
- Needs a sampling plan for incoming or final inspection, or asks "how many do I check from a lot of N?"
- Uses Z1.4 / ISO 2859-1 and wants the code letter, n, Ac, Re
- Wants to know whether a plan protects against bad lots (OC curve, LTPD, AOQL)
- Has a customer demanding c = 0 sampling

Inspection levels per part and supplier: [incoming-inspection-plan-writer](../incoming-inspection-plan-writer/SKILL.md).

## Workflow

```
1. CLASSIFY -> characteristics as critical / major / minor; critical -> 100% or error-proofing, not sampling
2. AQL      -> per class (customer AQLs when given): major 0.65-1.0, minor 2.5-4.0
3. PLAN     -> python scripts/z14_plan.py --lot 1000 --aql 1.0 [--level II]
4. CHECK    -> python scripts/oc_curve.py oc --n 80 --c 2 --lot 1000   (is the LTPD acceptable?)
5. DESIGN   -> if not: python scripts/oc_curve.py design --aql 0.01 --ltpd 0.05, or c0 --ltpd 0.05
6. RUN      -> random sample from the whole lot; record; apply switching rules
```

## Examples

```
Lot 200, inspection level II -> code letter G (n = 32)
Table II-A arrow (down) -> use the plan for code letter H
Normal inspection, single sampling: n = 50, Ac = 1, Re = 2
```
```
Plan n = 80, c = 2 (binomial)
  Pa = 0.95 at p = 1.0298%   (producer's quality level)
  Pa = 0.10 at p = 6.5160%   (LTPD / consumer's quality level)
```

Code-letter table, common plans, inspection levels, switching rules and related standards:
[z14-and-switching.md](references/z14-and-switching.md). When to sample, AQL by defect class, OC interpretation,
designing from risks, c = 0 plans and executing the plan: [choosing-a-plan.md](references/choosing-a-plan.md).

## Output Format

Deliver:
1. **Characteristic classes** and the AQL for each.
2. **Plan** - code letter, n, Ac, Re (and any arrow followed).
3. **Protection** - producer's quality level, LTPD and AOQL from the OC curve.
4. **Decision rule and switching** - accept/reject, what happens to rejected lots, when to tighten.

## Scripts

```bash
python scripts/z14_plan.py --lot 1000 --aql 1.0
python scripts/z14_plan.py --lot 5000 --aql 0.65 --level S-3
python scripts/z14_plan.py --lot 1000 --aql 25 --per-100-units
```
Normal inspection only; tightened and reduced plans are in Tables II-B and II-C of the standard. Exit codes:
0 plan printed, 2 invalid lot, AQL or level.

```bash
python scripts/oc_curve.py oc --n 80 --c 2 [--lot 1000] [--svg > oc.svg]
python scripts/oc_curve.py design --aql 0.01 --ltpd 0.05 --alpha 0.05 --beta 0.10
python scripts/oc_curve.py c0 --ltpd 0.05 --beta 0.10
```
Exit codes: 0 computed, 1 no plan within limits, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [z14-and-switching.md](references/z14-and-switching.md) | Code letters, sample sizes, common plans, inspection levels, switching rules, related standards |
| [choosing-a-plan.md](references/choosing-a-plan.md) | When to sample, AQL selection, OC curves, risk-based design, c = 0 plans, execution |
