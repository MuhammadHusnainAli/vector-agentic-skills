# MSA Study Design and Acceptance Criteria (AIAG MSA 4th edition)

## Variable gauge R&R (crossed)

| Item | Recommendation |
|------|----------------|
| Parts | 10, covering the expected process range (not 10 near-identical parts) |
| Appraisers | 3 who normally use the gauge |
| Trials | 2-3 per appraiser per part |
| Order | Randomised and blind (appraiser does not know which part or previous reading) |
| Resolution | At least 1/10 of the tolerance (or of the process spread) |
| Conditions | Normal environment, normal method, calibrated gauge |

## Acceptance

| %GRR (of tolerance or study variation) | Decision |
|----------------------------------------|----------|
| < 10% | Acceptable |
| 10-30% | May be acceptable depending on application, cost of the gauge, cost of repair; customer approval |
| > 30% | Not acceptable: improve the measurement system |

Also require **ndc >= 5** (number of distinct categories the gauge can resolve within the process variation).

| Basis | Use when |
|-------|----------|
| %Tolerance (6 sigma_GRR / tolerance) | The gauge is used to accept or reject parts against the specification |
| %Study variation (sigma_GRR / sigma_total) | The gauge is used for process control (SPC) or improvement |
| %Contribution (variance ratio) | Comparing components; sums to 100% (study variation percentages do not) |

## ANOVA vs Average and Range

| | ANOVA (`gage_rr_anova.py`) | Average and Range (`gage_rr_xbar_r.py`) |
|---|---|---|
| Operator x part interaction | Estimated and tested (pooled if p > 0.25) | Cannot be separated |
| Accuracy | Preferred | Approximation with tabulated constants |
| Hand calculation | Hard | Easy (AIAG worksheet) |
| Range control check | No | Yes: ranges above D4 R-double-bar show measurement errors |

## Other MSA studies

| Study | Question | Method |
|-------|----------|--------|
| Bias | Does the gauge read the true value on average? | 10+ measurements of a reference part; t-test of the mean vs reference |
| Linearity | Is bias constant across the range? | Reference parts across the range; regression of bias on reference value |
| Stability | Does the gauge drift over time? | Control chart of a master part measured periodically |
| Destructive / non-replicable | Same part cannot be re-measured | Nested Gage R&R with homogeneous batches |

## Attribute agreement

50 or more parts (AIAG example uses 50), about a third marginal near the limits, a known reference for each part,
3 appraisers x 2-3 trials, blind random order. Criteria in `attribute_agreement.py`: effectiveness >= 90%,
miss rate <= 2%, false alarm <= 5%, kappa > 0.75 for acceptable.
