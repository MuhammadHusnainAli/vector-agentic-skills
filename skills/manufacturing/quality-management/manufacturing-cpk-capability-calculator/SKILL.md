---
name: manufacturing-cpk-capability-calculator
description: "Calculate and interpret process capability for manufacturing characteristics: Cp, Cpk, Pp, Ppk and Cpm with within-subgroup sigma (R-bar/d2, pooled S, MR-bar/1.128) and overall sigma, one-sided specifications, expected ppm within and overall vs observed ppm, a Bissell confidence interval for Cpk, Anderson-Darling normality test, and the percentile method for non-normal data. Explains off-centre processes, Ppk below Cpk from shifts and drift, wide intervals from small samples, and requirements such as PPAP Ppk 1.67, ongoing Cpk 1.33 and customer-specific thresholds; covers data prerequisites (MSA, stability, 100+ values) and non-normal causes and methods. Use when computing Cpk or Ppk for PPAP, a control plan, customer request or capability study, when Cpk and Ppk disagree, or when data look non-normal."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Manufacturing Cpk Capability Calculator

Capability answers whether a stable process fits its tolerance. The number is only meaningful if the gauge is
capable, the process is in control, the data are representative and the distribution model fits.
`scripts/capability.py` computes all the indices and also checks those conditions: normality, the gap between
Cpk and Ppk, off-centring, observed vs expected defects and the confidence interval.

## Trigger Conditions

Activate this skill when the user:
- Needs Cpk / Ppk for a PPAP, control plan, customer or capability study
- Has Cpk and Ppk that disagree, or a Cpk near the requirement
- Has skewed or bounded data (flatness, runout, roughness) and asks how to compute capability
- Asks what Cpk 1.33 means in ppm or how much data is needed

Control chart first: [manufacturing-spc-chart-builder](../manufacturing-spc-chart-builder/SKILL.md); gauge first:
[gage-rr-msa-analyzer](../gage-rr-msa-analyzer/SKILL.md).

## Workflow

```
1. PREREQS -> gauge OK (Gage R&R), process stable (control chart), >= 100 representative values
2. RUN     -> python scripts/capability.py data.csv --value diameter --lsl 12.000 --usl 12.018 --subgroup hour
3. NORMAL? -> if Anderson-Darling p < 0.05: find why (mixture, drift, bound); --method percentile if natural
4. READ    -> Cp vs Cpk (centring), Cpk vs Ppk (stability), CI (enough data?), observed vs expected ppm
5. DECIDE  -> compare with the requirement (--target-index 1.33 / 1.67); plan centring or variation reduction
```

## Output

```
Cp    1.38   Cpk   1.35   (95% CI 1.17 to 1.53)
Pp    1.17   Ppk   1.14
Expected ppm: within 36   overall 470   observed 8,000
  Ppk well below Cpk: between-subgroup variation (shifts, drift) - check the control chart.
  Observed 1 out-of-spec value(s) - far more than the normal model predicts: special causes or heavy tails.
```

Here Cpk passes 1.33 but the interval reaches 1.17, Ppk is 1.14 and a subgroup shifted: the process is not yet
proven capable. Index definitions, ppm table, requirements and how to read patterns:
[capability-indices.md](references/capability-indices.md). Prerequisites, normality causes and non-normal
methods: [data-requirements-and-non-normal.md](references/data-requirements-and-non-normal.md).

## Output Format

Deliver:
1. **Data and conditions** - n, subgrouping, gauge status, control-chart status, normality result.
2. **Indices** - Cp, Cpk (with CI), Pp, Ppk, Cpm if a target is given; method used.
3. **Defect rates** - expected within / overall and observed ppm.
4. **Interpretation** - centring, stability, data sufficiency.
5. **Verdict** vs the requirement and the improvement action (centre, stabilise, reduce variation).

## Scripts

```bash
python scripts/capability.py bore.csv --value diameter --lsl 12.000 --usl 12.018 --subgroup hour
python scripts/capability.py flatness.csv --value flatness --usl 0.05 --method percentile
python scripts/capability.py data.csv --value x --lsl 10 --usl 20 --target 15 --target-index 1.67 --json
```
Exit codes: 0 index meets --target-index (and data normal for the normal method), 1 below target or normality
rejected, 2 usage or data error (fewer than 25 values, bad specs).

## Additional Resources

| File | Content |
|------|---------|
| [capability-indices.md](references/capability-indices.md) | Index formulas, ppm table, typical requirements, reading patterns, Cpk confidence interval |
| [data-requirements-and-non-normal.md](references/data-requirements-and-non-normal.md) | Prerequisites, normality check causes, percentile / distribution / Box-Cox methods |
