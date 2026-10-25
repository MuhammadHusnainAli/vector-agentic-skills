# Reading Minitab Output

## Process Capability Report

| Output | Meaning | Look for |
|--------|---------|----------|
| StDev(Within) | Short-term sigma from subgroups (R-bar/d2, pooled S) | Basis of Cp/Cpk |
| StDev(Overall) | Sample standard deviation of all data | Basis of Pp/Ppk |
| Cp / Cpk | Potential (within) capability | >= 1.33 typical requirement |
| Pp / Ppk | Overall performance | Close to Cpk if the process is stable |
| PPM Observed vs Expected | Actual out-of-spec vs normal-model prediction | Observed >> expected: tails or special causes |
| Cpm | Capability around the target | Only when a target is entered |

Check the I-MR/X-bar chart and the normality test before believing the indices (Capability Sixpack shows both).

## Gage R&R (ANOVA)

| Output | Meaning | Criteria |
|--------|---------|----------|
| Two-way ANOVA table | Part, Operator, Part*Operator, Repeatability | Part*Operator P > 0.25 -> removed (pooled) |
| %Contribution | Variance share | GRR < 1% good, < 9% acceptable |
| %Study Var | SD share of total variation | < 10% good, 10-30% conditional, > 30% bad |
| %Tolerance | 6 SD / tolerance | Same thresholds; use when the gauge accepts/rejects parts |
| Number of Distinct Categories | 1.41 x PV / GRR | >= 5 |

## Regression

| Output | Meaning | Look for |
|--------|---------|----------|
| Coef, P-Value | Term effect and significance | P < 0.05 to keep (remove weak terms one at a time, highest P first) |
| VIF | Variance inflation (collinearity) | > 5 (some use 10): predictors correlated, coefficients unreliable |
| S | Residual standard deviation | In response units: typical prediction error |
| R-sq / R-sq(adj) | Variation explained (adjusted for terms) | Adj penalises useless terms |
| R-sq(pred) | Predictive ability (leave-one-out) | Much lower than R-sq = over-fitting |
| Residual plots | Normal, constant variance, no pattern vs order | Funnel = transform; pattern vs order = time effect |
| Unusual observations | Large residual (R) or leverage (X) | Check data entry and special causes |

## t-tests and ANOVA

P-Value < alpha: reject H0. Read the **CI for the difference**: it tells the size and direction. ANOVA tells
that at least one mean differs; Tukey comparisons tell which. Check "Test for Equal Variances" when groups have
different spread (use Welch).

## DOE (Analyze Factorial Design)

Coded Coefficients table: Effect = 2 x Coef. Pareto and normal plots of standardised effects show what matters.
Use the reduced model (significant terms + hierarchy), check residuals, then Response Optimizer for settings and
confirmation runs.
