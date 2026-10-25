# Statistics for Effectiveness Checks

## Before/after rate comparison (`effectiveness.py rate`)

Defect counts are modelled as Poisson with exposure (units). Conditional on the total k = k1 + k2, if the rate
did not change, the after-count follows Binomial(k, n2 / (n1 + n2)). The one-sided p-value is P(X <= k2).
This test is exact and valid for small counts, where normal-approximation tests fail.

Example: 12 defects in 4,000 units before, 1 in 3,500 after. k = 13, share = 3,500/7,500 = 0.467,
P(X <= 1) = 0.0035 -> significant at 5%; reduction 90% -> effective.

## Zero-defect demonstration (`effectiveness.py zero`)

To show the rate is below p with confidence C after observing zero defects:

    n = ln(1 - C) / ln(1 - p)          (rule of three: n ~ 3 / p at 95%)

| Target rate | 90% | 95% | 99% |
|-------------|-----|-----|-----|
| 1% | 230 | 299 | 459 |
| 0.5% | 460 | 598 | 919 |
| 0.1% (1,000 ppm) | 2,302 | 2,995 | 4,603 |
| 0.01% (100 ppm) | 23,025 | 29,956 | 46,050 |

## Upper confidence bound (`effectiveness.py upper`)

Clopper-Pearson exact bound: the largest rate still consistent with the observed defects. Use it to state
"the defect rate is now below X ppm with 95% confidence". With 0 defects in n units at 95%, the bound is
1 - 0.05^(1/n), close to 3/n.

## Continuous characteristics

If the problem was a dimension out of tolerance, compare capability instead of counts: Cpk before vs after
(see manufacturing-cpk-capability-calculator), and a two-sample test on mean or variance
(see hypothesis-test-selector).

## Significance vs practical effect

Require both: a statistically significant drop (p < 0.05) **and** a practically meaningful reduction
(`--min-reduction`, default 50%). A tiny but significant improvement on a huge volume is not a fix.
