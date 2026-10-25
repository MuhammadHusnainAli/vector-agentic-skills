# Acting on the Diagnosis

## High variance (large gap)

| Model | Levers, strongest first |
|-------|-------------------------|
| Gradient boosting (LightGBM/XGBoost/HGB) | larger min_child_samples / min_samples_leaf, fewer leaves / lower depth, subsample + colsample < 1, L2 (reg_lambda), lower learning rate with early stopping |
| CatBoost | larger l2_leaf_reg, lower depth, early stopping (od_wait), more random_strength |
| Random forest | larger min_samples_leaf, lower max_features, max_depth limit |
| Linear / logistic | stronger penalty (lower C), L1 to drop features, fewer high-cardinality one-hot columns |
| k-NN | larger k |
| SVM (RBF) | lower C, lower gamma |
| Any | remove noisy / ID-like / high-cardinality features, target-encode with cross-fitting, bag several models |

Confirm: the gap at the largest size shrinks and the validation score does not fall.

## Data-limited (large gap and rising validation)

Do the variance fixes now; plan data collection from the 2x prediction (see data-size-extrapolation.md).
Confirm after collecting: the new point lies near the prediction. If it lies below, the new data differs
(drift, labelling change).

## High bias (gap closed, score low)

| Model | Levers |
|-------|--------|
| Linear / logistic | interactions, splines, log/ratio transforms, weaker penalty, or switch to boosting |
| Gradient boosting | more leaves / depth, smaller min_child_samples, more rounds (higher early-stopping patience), less regularisation |
| Random forest | min_samples_leaf=1, max_features up |
| Any | new features with signal: aggregates over history, entity-level statistics, domain ratios, external data |
| Any | check the target: label noise caps every model; measure label agreement on a sample |

Confirm: the training score rises; the validation score follows; the gap may reopen slightly (expected).

## Converged

The model is as good as this data and these features allow. Gains now come from new information (features,
sources) or a different problem framing, not from tuning or rows. Compare with the irreducible-error estimate
from [ml-feasibility-assessor](../../ml-feasibility-assessor/SKILL.md) if one exists.

## Data problems the curve reveals

| Symptom | Check |
|---------|-------|
| Validation falls at larger sizes | `shuffle=True`? sorted file? drift between early and late rows (adversarial validation) |
| Wild fold-to-fold swings | groups split across folds, very small classes, outliers in the target |
| Validation above training | tiny validation folds, regularisation stronger at train time, duplicated rows across folds |
| Curve far better than production | leakage: run [target-leakage-detector](../../target-leakage-detector/SKILL.md) |

## One change at a time

Re-run the same curve (same splitter, sizes and seeds) after each change and compare the two CSVs. Changing
regularisation and features together hides which one helped.
