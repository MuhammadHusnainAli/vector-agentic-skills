---
name: gage-rr-msa-analyzer
description: "Run and interpret measurement system analysis (AIAG MSA 4th edition, IATF 16949 7.1.5.1.1): crossed variable Gage R&R by ANOVA (variance components, operator x part interaction test with pooling at p > 0.25, %contribution, %study variation, %tolerance, ndc) and by the Average and Range worksheet method (EV, AV, PV, GRR, range-chart check), and attribute agreement analysis for go/no-go and visual inspection (within-appraiser agreement, effectiveness, miss rate, false alarm rate, Cohen's kappa vs the reference, system agreement). Applies the 10% / 30% and ndc >= 5 criteria, says whether repeatability or reproducibility dominates, and covers study design, %tolerance vs %study variation, bias, linearity, stability, destructive tests and how to improve gauges and inspectors. Use when qualifying a gauge for a control plan or PPAP, analysing Gage R&R data, or checking inspectors on visual or go/no-go inspection."
metadata:
  category: manufacturing
  subcategory: quality-management
  version: "1.0.0"
---

# Gage R&R and MSA Analyzer

If the measurement system cannot tell good parts from bad, or one part from another, every downstream number
(SPC, Cpk, inspection results) is noise. `scripts/gage_rr_anova.py` is the preferred variable study;
`scripts/gage_rr_xbar_r.py` reproduces the AIAG hand worksheet and checks ranges; `scripts/attribute_agreement.py`
qualifies inspectors on pass/fail decisions. Shared input checks live in `scripts/_msa.py`.

## Trigger Conditions

Activate this skill when the user:
- Must qualify a gauge for a control plan, PPAP or customer requirement
- Has Gage R&R data to analyse, or results to interpret (%GRR, ndc, %tolerance)
- Wants to check visual inspectors or go/no-go gauges
- Sees SPC or capability results that do not make sense (often the gauge)

## Workflow

```
1. DESIGN   -> 10 parts over the process range, 3 appraisers, 2-3 trials, blind random order
2. MEASURE  -> CSV: part, operator, trial, value
3. ANALYSE  -> python scripts/gage_rr_anova.py grr.csv --tolerance 0.018
4. CHECK    -> python scripts/gage_rr_xbar_r.py grr.csv --tolerance 0.018   (range-chart check, worksheet values)
5. ATTRIBUTE-> python scripts/attribute_agreement.py attribute.csv --bad reject
6. DECIDE   -> < 10% acceptable; 10-30% conditional; > 30% not; ndc >= 5
7. IMPROVE  -> fix the dominant component and re-run
```

## Results

```
Source               Variance  %Contrib  %StudyVar  %Tolerance
Total Gage R&R      3.063e-07      1.0%      10.1%       18.4%
  Repeatability     2.504e-07      0.8%       9.1%       16.7%
Number of distinct categories (ndc): 13
Verdict on %Tolerance 18.4% and ndc 13: CONDITIONALLY ACCEPTABLE (depends on application, cost, customer approval)
Repeatability dominates: the gauge itself (fixture, resolution, wear, method) needs attention.
```

```
Appraiser     Within  Effective   Miss  False al.   Kappa  Grade
Ana              95%        98%   0.0%       3.6%    0.94  acceptable
Cleo             75%        78%  25.0%      21.4%    0.50  unacceptable
```

Study design, acceptance criteria, %tolerance vs %study variation, ANOVA vs Average and Range, bias, linearity,
stability and attribute study design: [study-design-and-criteria.md](references/study-design-and-criteria.md).
Causes and fixes by dominant component, resolution rule, attribute inspection fixes:
[improving-measurement-systems.md](references/improving-measurement-systems.md).

## Output Format

Deliver:
1. **Study design** - parts, appraisers, trials, randomisation, gauge resolution.
2. **Results table** - components with %contribution, %study variation, %tolerance; ndc; interaction test.
3. **Verdict** against the criteria and the basis used (%tolerance for inspection, %study variation for SPC).
4. **Diagnosis** - dominant component and its likely causes.
5. **Actions** and the re-study plan.

## Scripts

```bash
python scripts/gage_rr_anova.py grr.csv --tolerance 0.018 [--k 5.15] [--alpha-interaction 0.25] [--json]
python scripts/gage_rr_xbar_r.py grr.csv --tolerance 0.018
python scripts/attribute_agreement.py attribute.csv --bad reject
```
Variable studies: columns part, operator, value (balanced). Attribute studies: part, appraiser, trial, result,
reference. Exit codes: 0 acceptable, 1 conditional / not acceptable (or ranges out of control), 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [study-design-and-criteria.md](references/study-design-and-criteria.md) | Study design, criteria, %tolerance vs %study variation, methods compared, bias/linearity/stability, attribute design |
| [improving-measurement-systems.md](references/improving-measurement-systems.md) | Diagnosing repeatability vs reproducibility, resolution rule, attribute fixes, re-study |
