# Drift Metrics and Adversarial Validation

## Per-feature metrics

| Metric | Data | Notes |
|--------|------|-------|
| PSI | binned numeric or categorical | Σ (p_test − p_train) ln(p_test / p_train); < 0.1 stable, 0.1-0.25 moderate, > 0.25 large; bins from training deciles |
| KS statistic | numeric | max CDF gap; sensitive to large samples (tiny shifts become "significant") |
| Chi-square | categorical | test of independence between set membership and level |
| Wasserstein distance | numeric | in units of the feature; interpretable magnitude |
| Jensen-Shannon divergence | distributions | bounded [0, ln 2]; symmetric |

With big samples, p-values flag everything; judge magnitude (PSI, Wasserstein in units) instead.

## Adversarial validation

```python
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import roc_auc_score

for c in cat_cols:                                    # shared category dtype: HGB "from_dtype" needs it
    cats = pd.api.types.union_categoricals([pd.Categorical(train[c]), pd.Categorical(test[c])]).categories
    train[c] = pd.Categorical(train[c], categories=cats)
    test[c] = pd.Categorical(test[c], categories=cats)
both = pd.concat([train[feats].assign(is_test=0), test[feats].assign(is_test=1)], ignore_index=True)
X, y = both[feats], both.pop("is_test")
clf = HistGradientBoostingClassifier(categorical_features="from_dtype", random_state=0)
p = cross_val_predict(clf, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
print("adversarial AUC", roc_auc_score(y, p))     # churn train vs the drifted production fixture: 0.90
clf.fit(X, y)
# feature importance (permutation or SHAP) shows which features differ
```
Uses:
- Diagnose: AUC and the top features explain how test (or production) differs.
- Validate like production: pick the training rows that look most like production (highest p) as the
  validation set.
- Reweight: importance weights w = p / (1 − p) on training rows approximate the production distribution
  (covariate shift correction); clip extreme weights.

## Types of shift and responses

| Shift | What changes | Response |
|-------|--------------|----------|
| Covariate shift | P(X) | reweighting, more representative training data, robust features |
| Prior (label) shift | P(y) | recalibrate (prior correction), re-threshold |
| Concept drift | P(y | X) | retrain on recent data, monitor performance with labels |
| Split artefact | a feature encodes the split (time, source) | rebuild the feature or the split |

## Monitoring after deployment

Compute PSI per feature and for the score weekly against the training snapshot; alert on PSI > 0.25 for key
features or the score, and investigate before retraining blindly.
