# Choosing and Reporting a Feature Set

## Score vs number of features

```python
import matplotlib.pyplot as plt
res = rfecv.cv_results_
n = range(rfecv.min_features_to_select, rfecv.min_features_to_select + len(res["mean_test_score"]))
plt.errorbar(list(n), res["mean_test_score"], yerr=res["std_test_score"], fmt="-o", capsize=2)
plt.xlabel("features kept"); plt.ylabel("CV score")
```
With `step` > 1 the x-axis is not every integer; compute it from the elimination schedule
(`rfecv.cv_results_["n_features"]`, available in scikit-learn >= 1.5).

## One-standard-error rule

```python
import numpy as np
mean, std = np.array(res["mean_test_score"]), np.array(res["std_test_score"])
se = std / np.sqrt(n_folds)
best = mean.argmax()
threshold = mean[best] - se[best]
chosen = next(i for i in range(len(mean)) if mean[i] >= threshold)   # smallest set within 1 SE of the best
```

## Cost-aware selection

When features differ in cost (API calls, real-time aggregates, licensed data), compare
`score_gain / cost` per feature group. A simple policy: drop any group whose removal costs less than the noise
level of the metric and saves serving cost or latency.

| Group | Δ PR-AUC when removed | Cost | Decision |
|-------|-----------------------|------|----------|
| real-time velocity (12 features) | −0.031 ± 0.006 | stream processor | keep |
| bureau data (8 features) | −0.004 ± 0.005 | $0.05/call | drop (within noise) |
| text TF-IDF (5k features) | −0.010 ± 0.004 | CPU 20 ms | keep for now, revisit |

## Documentation template

```
Feature set v3 (2026-10-24)
Procedure: filter_select (junk + |rho| > 0.9 groups) -> L1-logistic inside 5x5 nested CV -> one-SE rule.
Kept: 24 features (list attached). Selection frequency >= 80% across outer folds for 20 of them.
Dropped: 61 features (reasons: 9 junk, 3 probable leaks, 14 redundant, 35 below noise).
Score: outer PR-AUC 0.412 ± 0.021 (all features 0.415 ± 0.022).
Serving savings: 2 external API calls, 18 ms p50 latency.
```

## Red flags in a selection report

- Selection done once on all data, CV afterwards.
- No mention of correlated groups while importances are presented feature by feature.
- Final set chosen at the single best CV point with no noise estimate.
- A dropped feature reappears as a "driver" in the model explanation.
