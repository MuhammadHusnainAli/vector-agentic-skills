# Hypothesis Test Roadmap

| Y (output) | X (input) | Compare | Test | Non-parametric / alternative |
|------------|-----------|---------|------|------------------------------|
| Continuous | none (vs target) | mean | 1-sample t | 1-sample Wilcoxon, sign test |
| Continuous | none | variance | Chi-square 1 variance | Bonett |
| Continuous | 2 groups, independent | mean | 2-sample t (Welch) | Mann-Whitney |
| Continuous | 2 groups, paired | mean | Paired t | Wilcoxon signed-rank |
| Continuous | 2 groups | variance | F-test (normal) | Levene / Brown-Forsythe |
| Continuous | k groups | mean | One-way ANOVA (+ Tukey) | Kruskal-Wallis, Mood's median |
| Continuous | k groups | variance | Bartlett (normal) | Levene |
| Continuous | continuous | relation | Correlation / regression | Spearman |
| Proportion | none | p | 1-proportion (exact binomial) | - |
| Proportion | 2 groups | p | 2-proportion z | Fisher's exact |
| Proportion | paired | p | McNemar | - |
| Proportion | k groups | p | Chi-square of association | Fisher (2x2) |
| Proportion | continuous | odds | Binary logistic regression | - |
| Count | none / 2 groups | rate | 1- / 2-sample Poisson rate | - |

## Steps

1. **State the practical question** ("does line 2 make larger bores than line 1?").
2. **Translate** into H0 (no difference) and H1 (difference; one-sided only if decided in advance).
3. **Choose alpha** (usually 0.05) and the difference that matters (delta).
4. **Check the sample size** gives enough power to detect delta (see assumptions-and-power.md).
5. **Collect data** representative of the comparison (randomised, same measurement system).
6. **Check assumptions** (normality, equal variances, independence) and pick the test.
7. **Run the test**; report p-value, effect size and confidence interval.
8. **Translate back** into a practical conclusion and decision.

## Reading the p-value

p is the probability of seeing a difference at least this large if H0 were true. p < alpha: reject H0. p >= alpha:
the data do not show a difference, which is not the same as showing there is none (low power). A tiny p with a
tiny effect on huge data can be practically irrelevant: always look at the confidence interval.
