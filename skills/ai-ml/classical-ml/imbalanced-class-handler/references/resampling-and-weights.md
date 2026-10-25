# Resampling and Class Weights

## Class weights per library

| Library | Parameter |
|---------|-----------|
| scikit-learn linear models, SVM, trees, forests | `class_weight="balanced"` (or `"balanced_subsample"` for forests), or a dict |
| HistGradientBoosting | `class_weight="balanced"` (>= 1.2) or `sample_weight` in `fit` |
| LightGBM | `scale_pos_weight=neg/pos` or `is_unbalance=True` (not both); `class_weight` in the sklearn API |
| XGBoost | `scale_pos_weight=neg/pos`; `max_delta_step=1` can stabilise extreme cases |
| CatBoost | `auto_class_weights="Balanced"` / `"SqrtBalanced"`, `class_weights`, or `scale_pos_weight` (one only) |
| Any estimator | `sample_weight` array in `fit` |

`balanced` weights each class by `n / (n_classes * n_class)`. Square-root weighting is a milder compromise.

## imbalanced-learn samplers

```python
from imblearn.pipeline import Pipeline
from imblearn.under_sampling import RandomUnderSampler, TomekLinks, EditedNearestNeighbours, NearMiss
from imblearn.over_sampling import RandomOverSampler, SMOTE, BorderlineSMOTE, ADASYN, SMOTENC, SMOTEN
from imblearn.combine import SMOTETomek, SMOTEENN

pipe = Pipeline([("prep", prep), ("sampler", SMOTE(k_neighbors=5, random_state=0)), ("model", clf)])
```
- `sampling_strategy` as a float = desired minority/majority ratio **after** resampling; it must be larger than
  the current ratio for undersampling, or it raises.
- `SMOTENC` handles mixed numeric + categorical features (`categorical_features=[...]`); `SMOTEN` all-categorical.
- SMOTE needs numeric, scaled features (it interpolates); put it after the preprocessing step.
- Samplers in an imblearn `Pipeline` run only during `fit`: validation folds are never resampled.

## When resampling helps (and when it does not)

| Model | Usually |
|-------|---------|
| Gradient boosting | unweighted or weighted training + threshold beats SMOTE; undersampling for speed only |
| Random forest | `class_weight="balanced_subsample"` or balanced bagging (`BalancedRandomForestClassifier`) |
| Logistic regression / linear SVM | weights ≈ random oversampling; SMOTE occasionally better on dense numerics |
| k-NN | SMOTE / cleaning methods can help decision boundaries |
| Neural nets | weights or focal loss; oversampling per batch |

Always compare on identical folds with the decision metric.

## Experiment template

```python
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=0)
variants = {
    "none": Pipeline([("prep", prep), ("model", base())]),
    "weights": Pipeline([("prep", prep), ("model", base(class_weight="balanced"))]),
    "under_0.2": Pipeline([("prep", prep), ("s", RandomUnderSampler(sampling_strategy=0.2, random_state=0)), ("model", base())]),
    "smote": Pipeline([("prep", prep), ("s", SMOTE(random_state=0)), ("model", base())]),
}
for name, p in variants.items():
    s = cross_val_score(p, X, y, cv=cv, scoring="average_precision")
    print(f"{name:<10} {s.mean():.4f} ± {s.std():.4f}")
```

## Leakage reminder

Resampling before the train/test split (or before CV) puts synthetic neighbours of test rows into training
and inflates scores. target-leakage-detector's `code_leak_lint.py` flags it (LK002).

## Undersampling for speed

With millions of negatives, keep all positives and a random 5-20% of negatives: training is much faster and
ranking quality barely changes. Record the sampling rate and prior-correct probabilities afterwards.
