---
name: incoming-inspection-plan-writer
description: "Write risk-based incoming (receiving) inspection plans for purchased parts and materials: classify characteristics as critical, major or minor, set the inspection level from supplier grade and lot history (first article and 100% for new parts or suppliers, tightened for grade C/D or repeated rejects, normal c = 0 sampling from LTPD per class, skip-lot for proven grade A suppliers, dock-to-stock with periodic audit), compute c = 0 sample sizes capped at the lot size, and apply switching rules; flags grade D suppliers without an open SCAR and reduced inspection without certificates. Covers certificate (CoC/CoA) review, lot-homogeneous characteristics, what to check at receiving, the plan document format and shifting effort upstream to supplier SPC and source inspection. Use when setting up receiving inspection, deciding how much to inspect from a supplier, reducing inspection cost, or reacting to supplier quality problems."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Incoming Inspection Plan Writer

Incoming inspection is a risk decision per characteristic and per supplier: how bad is a defect, and how much
evidence is there that this supplier does not ship them? `scripts/inspection_plan.py` turns a part/characteristic
list with supplier grades and lot history into a plan with levels, sample sizes and rationale.

## Trigger Conditions

Activate this skill when the user:
- Is setting up or revising receiving inspection for purchased parts
- Asks how many parts to check from a supplier's lot, or when inspection can be reduced
- Has a supplier with quality problems and needs tighter controls
- Wants to cut inspection cost without increasing risk

Supplier grades come from [supplier-quality-scorecard-builder](../supplier-quality-scorecard-builder/SKILL.md);
Z1.4 plans and OC curves from [acceptance-sampling-plan-selector](../acceptance-sampling-plan-selector/SKILL.md).

## Workflow

```
1. CLASSIFY -> each characteristic critical / major / minor (drawing symbols, PFMEA severity, customer CSRs)
2. HISTORY  -> supplier grade, consecutive accepted lots, new part?, certificate supplied?
3. PLAN     -> python scripts/inspection_plan.py parts.csv
4. DOCUMENT -> plan per part: gauge, sample, accept/reject, record (plan-document.md)
5. SWITCH   -> apply switching rules on every lot result; review level changes monthly
6. UPSTREAM -> for critical characteristics move control to the supplier (SPC data, source inspection)
```

## Levels

| Level | When | Method |
|-------|------|--------|
| First lots | New part / supplier, < 3 accepted lots | First article, 100% |
| Tightened | Grade C/D or repeated rejects | c = 0 at half the LTPD, or 100% (critical) |
| Normal | Default | c = 0: critical n 460, major n 114, minor n 45 (capped at lot size) |
| Skip-lot | Grade A, >= 10 accepted lots, not critical | 1 lot in 4 |
| Dock-to-stock | Grade A, >= 20 lots, minor, CoC | CoC review, audit 1 lot in 10 |

```
CB-400    Outside diameter      major    A   skip-lot      1 lot in 4 at n=114, c=0; CoC every lot  (25 consecutive accepted lots, grade A)
CA-77     Porosity              critical D   tightened     100%  (grade D supplier, critical characteristic)
II001 [medium] CastCorp: grade D supplier - record the open SCAR
```

Levels, classes, receiving checks, lot-homogeneous characteristics and reducing inspection safely:
[dynamic-inspection.md](references/dynamic-inspection.md). The plan document and its rules:
[plan-document.md](references/plan-document.md).

## Output Format

Deliver the plan table (part, characteristic, class, supplier grade, level, method, rationale), the switching rules,
flags with actions, and the per-part plan documents for the highest-risk parts.

## Scripts

```bash
python scripts/inspection_plan.py parts.csv
python scripts/inspection_plan.py parts.csv --csv > plan.csv
```
Columns: part, characteristic, class, supplier, supplier_grade, accepted_lots, lot_size, new_part, coc, scar.
Exit codes: 0 plan without flags, 1 medium flags, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [dynamic-inspection.md](references/dynamic-inspection.md) | Inspection levels and switching, classes and sample sizes, receiving checks, upstream control |
| [plan-document.md](references/plan-document.md) | Plan header, table format, rules to state |
