# Assumptions, Errors and Sample Size

## Assumptions

| Assumption | Check | If violated |
|------------|-------|-------------|
| Normality (small samples) | Anderson-Darling, probability plot of each group / residuals | n >= 30 per group: t-tests are robust; else non-parametric or transform |
| Equal variances (pooled t, ANOVA) | Levene test, ratio of SDs < 2 | Welch t (default in run_test.py t2), Welch ANOVA |
| Independence | Data collection design; time-order plot | Paired designs, blocking, time-series methods |
| Expected counts >= 5 (chi-square) | Expected table | Combine categories, Fisher's exact |
| Same measurement system | MSA | Fix the gauge first |

## Errors

| | H0 true | H0 false |
|---|---------|----------|
| Reject H0 | Type I error (alpha, producer's risk) | Correct (power = 1 - beta) |
| Do not reject | Correct | Type II error (beta, consumer's risk) |

## Sample size (two-sample means, equal n per group)

n per group ~ 2 (z_(1-alpha/2) + z_(1-beta))^2 (sigma / delta)^2

| delta / sigma | n per group (alpha 0.05, power 80%) | n per group (power 90%) |
|---------------|-------------------------------------|-------------------------|
| 0.5 | 63 | 85 |
| 0.75 | 28 | 38 |
| 1.0 | 16 | 22 |
| 1.5 | 7 | 10 |
| 2.0 | 4 | 6 |

Paired designs need far fewer units when the unit-to-unit variation is large: use sigma of the differences.

Two proportions: n per group ~ (z_(1-alpha/2) + z_(1-beta))^2 (p1(1 - p1) + p2(1 - p2)) / (p1 - p2)^2. Detecting
2% vs 4% defective at 80% power needs about 1,140 per group.

## Common mistakes

- Running many tests and reporting the one with p < 0.05 (multiple comparisons): use ANOVA + Tukey, or adjust alpha.
- Choosing one-sided after seeing the data.
- Treating "not significant" as "no difference" with n = 5.
- Comparing groups measured with different gauges or at different times without randomisation.
