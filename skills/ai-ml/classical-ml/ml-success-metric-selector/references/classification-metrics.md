# Classification Metrics

Notation: TP, FP, FN, TN from the confusion matrix at a threshold; P = TP + FN positives; N = FP + TN negatives.

## Threshold metrics

| Metric | Formula | Use | Misleads when |
|--------|---------|-----|---------------|
| Accuracy | (TP + TN) / (P + N) | balanced classes, equal costs | classes are imbalanced |
| Balanced accuracy | (TPR + TNR) / 2 | imbalanced, both classes matter | costs are very asymmetric |
| Precision (PPV) | TP / (TP + FP) | cost of acting on false alarms | few predicted positives (noisy) |
| Recall (TPR, sensitivity) | TP / P | cost of missing positives | used alone (flag everything = 1.0) |
| Specificity (TNR) | TN / N | screening negatives | - |
| FPR | FP / N | false-decline / false-alarm rate | - |
| F1 | 2PR / (P + R) | quick single number when costs unknown | costs differ; TN matter |
| F-beta | (1+β²)PR / (β²P + R) | recall β times as important as precision | β chosen arbitrarily |
| MCC | (TP·TN − FP·FN) / sqrt((TP+FP)(TP+FN)(TN+FP)(TN+FN)) | one balanced number, uses all four cells | you need an interpretable business number |
| Cohen's kappa | (p_o − p_e) / (1 − p_e) | agreement beyond chance | prevalence extreme (kappa paradox) |

## Ranking metrics (threshold-free)

### ROC-AUC
Probability that a random positive scores above a random negative. 0.5 = random, 1.0 = perfect. Insensitive
to prevalence, which is both its strength (comparable across datasets) and its weakness (at 0.1% prevalence an
AUC of 0.95 can still mean precision of 2% at useful recall).

### PR-AUC / average precision
Area under precision-recall; `average_precision_score` computes the step-wise sum
`Σ (R_k − R_{k−1}) P_k`. Random = prevalence (not 0.5). Focuses on the top of the ranking, where rare-event
decisions are made. Do not use trapezoidal interpolation of the PR curve (`auc(recall, precision)`): it is
optimistic.

### Partial AUC
ROC-AUC restricted to FPR ≤ x (`roc_auc_score(..., max_fpr=0.05)`, McClish-standardised). Use when only a low
false-positive region is operationally relevant (fraud, screening).

### Precision@K, recall@K, lift@K
Sort by score, take K. Lift = precision@K / prevalence. The right metric for capacity-bound actions.

## Probability metrics

| Metric | Formula | Notes |
|--------|---------|-------|
| Log loss | −mean(y log p + (1−y) log(1−p)) | proper scoring rule; punishes confident mistakes; baseline = entropy of the prior |
| Brier | mean((p − y)²) | proper scoring rule; bounded; decomposes into calibration + refinement |
| ECE | Σ_bins (n_b/n) · |mean p_b − frac positive_b| | depends on binning; report with the reliability curve |

A model can have excellent AUC and terrible calibration (any monotone transform keeps AUC). Calibrate with
`CalibratedClassifierCV(method="isotonic" | "sigmoid")` on held-out data when probabilities are consumed.
Resampling (SMOTE, undersampling) and `class_weight` distort probabilities; recalibrate afterwards.

## Multiclass averaging

| Average | Computes | Use |
|---------|----------|-----|
| micro | pool all TP/FP/FN over classes | equals accuracy for single-label multiclass |
| macro | unweighted mean of per-class metric | every class equally important |
| weighted | mean weighted by class support | frequency = importance |

Report the per-class table (`classification_report`) whenever classes differ in importance.
Multiclass ROC-AUC: `roc_auc_score(y, P, multi_class="ovr", average="macro")` or `"ovo"` (insensitive to
imbalance).

## Confusion-matrix costs

```
               predicted 0     predicted 1
actual 0       0 (TN)          C_fp
actual 1       C_fn            C_tp (often negative = benefit)
```
Expected cost per row = (FP·C_fp + FN·C_fn + TP·C_tp) / n. For calibrated p, predict 1 when
`p·(C_fn − C_tp) > (1−p)·C_fp`, i.e. `p > C_fp / (C_fp + C_fn − C_tp)`.

## scikit-learn calls

```python
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score, brier_score_loss,
                             classification_report, confusion_matrix, f1_score, fbeta_score, log_loss,
                             matthews_corrcoef, precision_recall_curve, roc_auc_score, top_k_accuracy_score)
from sklearn.calibration import calibration_curve

roc_auc_score(y, p)
average_precision_score(y, p)
roc_auc_score(y, p, max_fpr=0.05)
log_loss(y, p); brier_score_loss(y, p)
frac_pos, mean_pred = calibration_curve(y, p, n_bins=10, strategy="quantile")
fbeta_score(y, p >= t, beta=2)
top_k_accuracy_score(y_multi, P, k=3)
```

`TunedThresholdClassifierCV` (scikit-learn >= 1.5) selects a threshold by cross-validation for a chosen
scorer, including a custom cost scorer built with `make_scorer`.

## Common mistakes

- Reporting accuracy or F1 at 0.5 for an imbalanced problem.
- Comparing PR-AUC across datasets with different prevalence (normalise by prevalence: lift).
- Choosing the threshold on the test set and reporting the test metric at it.
- Averaging per-fold precision when folds have very different predicted-positive counts (pool instead).
- Treating AUC differences of 0.005 as meaningful without a paired test.
