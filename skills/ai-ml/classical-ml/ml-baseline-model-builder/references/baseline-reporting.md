# Reporting Baselines

## Table template

| Model | Split | Primary: recall@400 | PR-AUC | ROC-AUC | Log loss | Notes |
|-------|-------|---------------------|--------|---------|----------|-------|
| Prior (dummy) | time holdout 2024-04..06 | 0.17 (random) | 0.170 | 0.500 | 0.463 | floor |
| Current rule | same | 0.38 | 0.378 | 0.723 | - | rule is 0/1, log loss n/a |
| One feature (last_login_days) | same | 0.29 | 0.286 | 0.631 | 0.438 | |
| Logistic regression | same | 0.52 ± 0.05 | 0.556 | 0.869 | 0.346 | ± = bootstrap 95% CI |
| HistGBM (default) | same | 0.47 ± 0.05 | 0.425 | 0.795 | 0.429 | worse than linear: small data |

Always include: the split and its dates, the test size and positive count, the primary metric first, the CI.

## Estimating noise

### Bootstrap CI on a fixed holdout
```python
import numpy as np
from sklearn.metrics import roc_auc_score

def bootstrap_ci(y, p, metric=roc_auc_score, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    stats = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        stats.append(metric(y[idx], p[idx]))
    return np.percentile(stats, [2.5, 97.5])
```

### Paired difference vs the baseline
The CI of the *difference* is what matters; resample the same indices for both models:
```python
def paired_diff_ci(y, p_model, p_base, metric=roc_auc_score, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    y, a, b = map(np.asarray, (y, p_model, p_base))
    d = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].min() == y[idx].max():
            continue
        d.append(metric(y[idx], a[idx]) - metric(y[idx], b[idx]))
    return np.mean(d), np.percentile(d, [2.5, 97.5])
```
"Beats the baseline" means the lower bound of this interval is above 0 (and above the minimum useful lift).

### Repeated CV for small data
`RepeatedStratifiedKFold(n_splits=5, n_repeats=10)`: report mean and standard deviation across the 50 folds,
and compare models on the same folds (ml-model-comparison-reporter has the corrected t-test).

## How to phrase the result

Good:
> On the April-June 2024 holdout (100 customers, 17 churners) logistic regression reaches PR-AUC 0.56
> (95% CI 0.41-0.70) vs 0.38 for the current rule; the paired difference is +0.18 (CI +0.05 to +0.31).

Bad:
> The model achieves 85% accuracy.

## Reading mistakes

| Mistake | Correction |
|---------|-----------|
| Comparing a tuned model to an untuned baseline on different splits | same split, report both tuned and untuned |
| Calling PR-AUC 0.3 bad | compare with prevalence: 0.3 at 2% prevalence is 15x random |
| Ignoring that the rule cannot produce probabilities | compare on ranking/threshold metrics |
| Baseline scored on the full data, model on the holdout | same holdout for all |
| One random split for 500 rows | repeated CV or bootstrap CI |
| Reporting accuracy for imbalanced classes | balanced accuracy, PR-AUC, recall@K |
| R² on a log target compared with R² on the raw target | compare in original units |
