# Statistical Tests for Model Comparison

Notation: k folds, per-fold difference d_i = score_A,i − score_B,i, mean d̄, sample variance s².

## Corrected resampled t-test (Nadeau & Bengio 2003)

```
t = d̄ / sqrt( (1/k + n_test/n_train) · s² ),   df = k − 1
```
For k-fold CV, n_test/n_train = 1/(k − 1). The ordinary paired t-test uses `s²/k` and ignores that training
sets overlap across folds, so it rejects far too often (inflated type I error). For repeated k-fold
(r repeats): use all r·k differences with `(1/(r·k) + n_test/n_train)`.

```python
import numpy as np
from scipy import stats
d = a - b; k = len(d)
t = d.mean() / np.sqrt((1 / k + 1 / (k - 1)) * d.var(ddof=1))
p = 2 * stats.t.sf(abs(t), k - 1)
```

## 5x2cv paired t-test (Dietterich 1998)

Five repetitions of 2-fold CV; statistic uses the first fold's difference over the averaged variance;
df = 5. Conservative and well-calibrated; available in `mlxtend.evaluate.paired_ttest_5x2cv`.

## Wilcoxon signed-rank

Ranks |d_i|, sums ranks of positive differences. Exact distribution for small k. With 5 folds the smallest
possible two-sided p-value is 2/32 = 0.0625: **it can never reach 0.05 with 5 folds**. Use 10 folds or repeated
CV if you want this test. `scipy.stats.wilcoxon(d)`.

## Friedman test and post-hoc

For K models over k folds (or datasets): rank models within each fold, average ranks R_j.
```
χ²_F = 12k / (K(K+1)) · Σ (R_j − (K+1)/2)²,   df = K − 1
```
Then post-hoc: Nemenyi (all pairs, critical difference `q_α sqrt(K(K+1)/(6k))`) or pairwise tests vs a control
with Holm correction (Demšar 2006). `scipy.stats.friedmanchisquare`, `scikit-posthocs` for Nemenyi.

## Bayesian correlated t-test (Corani & Benavoli 2015; Benavoli et al. 2017)

Posterior of the mean difference μ is Student-t:
```
μ ~ t_{k−1}( d̄, (1/k + ρ/(1−ρ)) · s² ),   ρ = n_test / (n_test + n_train)  (= 1/k for k-fold)
```
Note `ρ/(1−ρ) = n_test/n_train`, the same correction as Nadeau-Bengio. With a region of practical equivalence
[−r, r]: P(μ > r) = A better, P(|μ| <= r) = equivalent, P(μ < −r) = B better. Decide when one probability
exceeds e.g. 0.95. Implemented in `compare_models.py`; also in the `baycomp` package.

## DeLong test for correlated ROC-AUCs

AUC = mean of placement values. For each positive i: V10_i = share of negatives it outranks (ties ½); for each
negative j: V01_j = share of positives that outrank it. With S10, S01 the covariance matrices of these
components across the two models:
```
Var(AUC_A − AUC_B) = (S10_AA + S10_BB − 2 S10_AB)/m + (S01_AA + S01_BB − 2 S01_AB)/n
z = (AUC_A − AUC_B) / sqrt(Var)
```
`paired_predictions.py` uses the midrank (Sun & Xu 2014) form; it matches the brute-force definition to
machine precision on the fixture.

## McNemar's test

Only discordant pairs matter: b = A right & B wrong, c = A wrong & B right.
- Exact: two-sided binomial test of b vs Binomial(b + c, 0.5) (use when b + c < ~50).
- Chi-square with continuity correction: `(|b − c| − 1)² / (b + c)`, df 1.
`statsmodels.stats.contingency_tables.mcnemar([[n00, b], [c, n11]], exact=True)`.

## Paired bootstrap

Resample test rows with replacement (stratified by class for rare positives), compute both models' metric
on the **same** resample, record the difference; 95% CI from the 2.5/97.5 percentiles. Works for any metric
(PR-AUC, log loss, recall@K, MAE). 1,000-2,000 resamples are usually enough for a CI; more for small p-values.

## Choosing among them

| Situation | Primary | Secondary |
|-----------|---------|-----------|
| CV, 2 models | corrected t or Bayesian correlated t | Wilcoxon (with >= 10 folds) |
| CV, many models | Friedman + Holm vs best | average ranks plot |
| Holdout, ranking | DeLong | bootstrap of PR-AUC |
| Holdout, decisions | McNemar at the operating point | bootstrap of precision@K |
| Many datasets (benchmarks) | Wilcoxon / Friedman across datasets | Bayesian hierarchical test |
