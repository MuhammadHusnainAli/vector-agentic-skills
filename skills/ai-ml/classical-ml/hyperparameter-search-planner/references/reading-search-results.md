# Reading Search Results

## Export

```python
import pandas as pd
pd.DataFrame(search.cv_results_).to_csv("cv_results.csv", index=False)       # scikit-learn
study.trials_dataframe().to_csv("trials.csv", index=False)                   # Optuna
```

## Boundaries

If the best value lies in the outer 15% of the searched range (on the scale searched), the optimum may be
outside: extend that side and rerun. Example from the fixture: best `learning_rate` 0.0175 in [0.011, 0.28] ->
search lower values.

## Sensitivity

- **Effect range**: mean score across quartile bins of a parameter; small range = the parameter barely matters.
- **Direction**: Spearman of parameter (log scale when it spans decades) vs score.
- **Peaked**: the middle bins clearly beat both ends -> the optimum is inside the range.
- Optuna: `optuna.importance.get_param_importances(study)` (fANOVA) and
  `optuna.visualization.plot_slice / plot_contour` for interactions.

Interactions matter (learning rate and number of trees, C and gamma): look at 2-D slices for the top two
parameters.

## The one-standard-error rule

Configurations whose mean score is within one standard error of the best are statistically indistinguishable
from it. Choose the simplest (smaller trees, stronger regularisation, fewer features, faster): it generalises at
least as well and costs less. scikit-learn supports this through a callable `refit`:
```python
def one_se(cv_results):
    import numpy as np
    m, s = np.array(cv_results["mean_test_score"]), np.array(cv_results["std_test_score"])
    best = m.argmax(); thr = m[best] - s[best] / np.sqrt(5)
    ok = np.where(m >= thr)[0]
    leaves = np.array(cv_results["param_model__max_leaf_nodes"], dtype=float)
    return int(ok[np.argmin(leaves[ok])])
search = RandomizedSearchCV(pipe, dist, refit=one_se, ...)
```

## Overfitting the validation set

The best of N noisy trials is biased upward, and the bias grows with N. Symptoms: tuned CV score well above the
holdout score; improvements of the order of the fold standard deviation. Remedies: nested CV, a fresh holdout,
fewer and coarser trials, repeated CV for the final comparison.

## Progress

Plot best-so-far vs trial number. A curve that has been flat for the second half of the budget says more trials
will not help; change features, the model family or the validation design instead.

## Reporting a search

```
Search: Optuna TPE, 120 trials (MedianPruner, 38 pruned), 5-fold StratifiedGroupKFold, PR-AUC.
Best: 0.412 ± 0.021 (inner CV); nested outer estimate 0.401 ± 0.025; holdout 0.398.
Default configuration: 0.389. Gain: +0.012 (paired corrected t-test p = 0.04).
Most important: min_child_samples, num_leaves; learning rate fixed at 0.05 (final 0.025, 1,900 trees).
```
