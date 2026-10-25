---
name: six-sigma-dpmo-calculator
description: "Calculate Six Sigma defect metrics for manufacturing and transactional processes: DPU, DPO, DPMO, yield per opportunity, Poisson and observed first-time yield, sigma level with or without the 1.5 sigma shift, conversions between DPMO, yield and sigma level, rolled throughput yield across process steps with normalised yield and the hidden factory, and a sigma table. Covers how to count defect opportunities consistently, ppm defective vs DPMO, DPU vs DPO, FTY vs RTY, and the relation between sigma level and Cpk. Use when reporting a baseline or result in sigma terms, comparing processes of different complexity, finding the hidden factory in a multi-step process, or answering a Green Belt exam question on DPMO and sigma."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Six Sigma DPMO Calculator

DPMO and sigma level let processes of different complexity be compared, but only if opportunities are counted
honestly and the shift convention is stated. `scripts/dpmo.py` computes every defect metric, converts between
DPMO, yield and sigma, and exposes the hidden factory with rolled throughput yield.

## Trigger Conditions

Activate this skill when the user:
- Needs DPU, DPMO or a sigma level for a DMAIC baseline or result
- Wants to convert between yield, DPMO, ppm and sigma
- Has a multi-step process and wants RTY or the hidden factory
- Asks how to count defect opportunities, or why ppm and DPMO differ

## Workflow

```
1. DEFINE    -> unit, defect, defective, and the fixed list of opportunities per unit (counting-opportunities.md)
2. COUNT     -> defects, units, defective units over a representative period
3. COMPUTE   -> python scripts/dpmo.py dpmo --defects 38 --units 1200 --opportunities 14
4. PROCESS   -> python scripts/dpmo.py rty --steps steps.csv   (first-pass yield per step)
5. REPORT    -> DPMO and sigma with the opportunity count and the shift convention stated
```

## Examples

```
  DPMO = 2,262
  Sigma level = 4.34 (short-term, 1.5 shift)
```
```
Rolled throughput yield = 89.86%  (probability a unit passes every step first time)
Hidden factory: 10.1% of units are scrapped or reworked somewhere; worst step: step 2 (95.00%)
```

Sigma table, the 1.5 shift, sigma vs Cpk, and DPU / DPO / DPMO / ppm / FTY / RTY definitions:
[sigma-conversions.md](references/sigma-conversions.md). Opportunity counting rules, examples, hidden factory and
a worked example: [counting-opportunities.md](references/counting-opportunities.md).

## Output Format

Deliver: the definitions used (unit, defect, opportunities), the computed metrics (DPU, DPMO, yields, sigma with
shift convention), RTY by step if relevant, and the interpretation (worst step, gap to target).

## Scripts

```bash
python scripts/dpmo.py dpmo --defects 38 --units 1200 --opportunities 14 [--defective-units 35]
python scripts/dpmo.py sigma --dpmo 6210          # or --yield 0.9938, or --level 4.5
python scripts/dpmo.py --no-shift sigma --level 3
python scripts/dpmo.py rty --yields 0.98 0.95 0.995 0.97
python scripts/dpmo.py rty --steps steps.csv     # step, units_in, defective_units
python scripts/dpmo.py table
```
Exit codes: 0 computed, 2 usage error.

## Additional Resources

| File | Content |
|------|---------|
| [sigma-conversions.md](references/sigma-conversions.md) | Sigma/DPMO/yield table, 1.5 shift, metric definitions |
| [counting-opportunities.md](references/counting-opportunities.md) | Opportunity rules and examples, RTY and hidden factory, worked example |
