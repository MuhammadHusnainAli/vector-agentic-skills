---
name: imbalanced-class-handler
description: "Handle imbalanced classification (fraud, churn, defaults, failures, rare diseases) without fooling yourself: measure with PR-AUC, recall at capacity and expected cost instead of accuracy, keep test sets at natural prevalence, stratified and repeated CV for few positives, choose thresholds from capacity, costs or precision/recall targets, apply class weights (class_weight, scale_pos_weight, auto_class_weights), resample only inside an imblearn Pipeline (random undersampling, SMOTE, ADASYN, SMOTE-NC, Tomek, ENN), correct probabilities after resampling with the prior-shift formula, calibrate, and know when to switch to anomaly detection or collect more labels. Profiles a dataset's imbalance severity with a cheapest-first strategy ladder and imblearn code, and tunes thresholds under six policies with prior correction. Use when someone has rare positives, asks about SMOTE or class weights, gets high accuracy but useless recall, needs a threshold, or has miscalibrated probabilities after oversampling."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Imbalanced Class Handler

Imbalance is mostly an **evaluation and decision** problem, not a training problem. Gradient boosting and
logistic regression rank rare positives fine on the original data; what goes wrong is accuracy as the
metric, a 0.5 threshold, folds with a handful of positives, and resampling done before the split.
Fix those first, then use class weights if needed, and resample only inside the pipeline.
`scripts/imbalance_report.py` grades the imbalance and prints the cheapest-first strategy (with imblearn
code); `scripts/threshold_tuner.py` picks thresholds under six policies and undoes the probability bias
that resampling or weighting introduces.

## Trigger Conditions

Activate this skill when the user:
- Has a rare positive class (fraud, churn, default, failure, conversion, disease) and asks how to handle it
- Gets high accuracy with near-zero recall, or a model that never predicts the minority class
- Asks about SMOTE, oversampling, undersampling, class weights, `scale_pos_weight`, focal loss
- Needs a threshold for a review capacity, a cost ratio, or a precision/recall target
- Has probabilities that are far too high after oversampling or weighting
- Has a multiclass problem with tiny classes

## Workflow

```
1. PROFILE    -> python scripts/imbalance_report.py data.csv --target y --folds 5 --model gbm
2. METRICS    -> PR-AUC, recall/precision at K or at a cost-optimal threshold; natural-prevalence test set
3. CV         -> StratifiedKFold (repeated when positives per fold < ~30); StratifiedGroupKFold for entities
4. BASELINE   -> train on the original data, no weights; score ranking metrics
5. THRESHOLD  -> python scripts/threshold_tuner.py valid_preds.csv --k 400 --cost-fp 8 --cost-fn 600
6. WEIGHTS    -> only if recall at the threshold is still not enough; recalibrate afterwards
7. RESAMPLE   -> inside imblearn Pipeline; compare with weights on identical folds
8. CORRECT    -> threshold_tuner.py --train-rate r --true-rate pi for resampled models; check calibration
```

## Severity and Strategy

| Severity | Minority share / count | Do |
|----------|------------------------|----|
| Mild | >= 20% | good metrics, stratified CV |
| Moderate | 5-20% | + threshold from capacity/costs |
| Severe | 0.5-5% | + class weights; PR-AUC; capacity metrics; consider undersampling negatives for speed |
| Extreme | < 0.5% or < 100 positives | + anomaly detection, rules + label collection, two-stage models; CIs on every metric |

On the fixtures: churn (20.5%) is mild-to-moderate; card fraud (34 positives, 2.3%) is extreme by count:
~7 positives per fold, so every metric needs a confidence interval.

## Metrics That Work

| Metric | Why |
|--------|-----|
| PR-AUC (average precision) | focuses on ranking positives at the top; baseline = prevalence |
| Recall / precision at K | matches a review or call capacity |
| Expected cost at the chosen threshold | matches asymmetric error costs |
| ROC-AUC | fine for comparing rankers, but looks good even when precision is poor |
| Balanced accuracy, MCC | single-number summaries that respect both classes |
| Log loss / Brier + calibration | when probabilities are used downstream |
| **Not** accuracy | "always negative" scores 1 − prevalence |

Details and confidence intervals for few positives: [metrics-for-imbalance.md](references/metrics-for-imbalance.md).

## Thresholds

`threshold_tuner.py` on the preds fixture (10% positives, FP cost 8, FN cost 600):

```
policy             threshold precision  recall     F1  flagged     FP    FN
f2                    0.4095     0.526   0.968  0.682    19.0%     54     2
top-50                0.6468     0.880   0.710  0.786     8.3%      6    18
min-cost              0.3325     0.397   1.000  0.569    26.0%     94     0  cost/row 1.2533
```
- **Capacity:** take the top K per period.
- **Costs:** with calibrated probabilities the optimal rule is `p > C_fp / (C_fp + C_fn)`; with uncalibrated
  scores scan thresholds on validation data.
- **Targets:** "recall >= 90%" -> the highest-precision threshold meeting it.
- Choose on validation, report on test; re-choose after every retrain.

## Class Weights vs Resampling

| Technique | Effect on ranking | Effect on probabilities | Cost | Typical verdict |
|-----------|-------------------|-------------------------|------|-----------------|
| Nothing (original data) | baseline | calibrated | - | start here; often best for GBMs |
| Class weights | small change, sometimes better recall at default threshold | inflated: recalibrate | free | first thing to try if needed |
| Random undersampling of negatives | small loss or none; big speed-up | inflated: prior-correct | cheaper training | good for very large data |
| Random oversampling | like weights, more memory | inflated | more data | rarely better than weights |
| SMOTE / ADASYN / SMOTE-NC | can help linear / kNN on dense numerics; rarely GBMs | inflated | synthetic data | test on identical folds; never before the split |
| Cleaning (Tomek links, ENN) | removes borderline negatives | shifts | moderate | situational |
| Focal loss / custom objectives | focuses on hard examples | not calibrated | custom code | deep learning mostly |

Code for each with imbalanced-learn, and the leakage rule (resampling only on training folds):
[resampling-and-weights.md](references/resampling-and-weights.md).

## Correcting Probabilities After Resampling

Training at positive rate r (after undersampling, oversampling or weighting) when the real rate is π shifts
probabilities. Correct with:

```
p_true = p * (π / r) / ( p * (π / r) + (1 - p) * ((1 - π) / (1 - r)) )
```
On the resampled-scores fixture (trained at 50%, real 3.2%) the correction takes ECE from 0.318 to 0.012
(`threshold_tuner.py --train-rate 0.5 --true-rate 0.03`). Ranking metrics are unchanged; thresholds,
expected-value calculations and calibration plots are fixed. Alternatives: `CalibratedClassifierCV` on a
holdout at natural prevalence. Derivation and calibration checks: [calibration-and-prior-shift.md](references/calibration-and-prior-shift.md).

## When the Minority Is Too Small

- < ~50-100 positives: estimates are unstable; report intervals, use simple models, add domain features.
- Use anomaly detection (isolation forest, robust z-scores) to rank candidates and collect labels from reviews.
- Two-stage models: a high-recall cheap filter, then a precise model on the filtered set.
- Pool related populations or extend the time window to gather more positives.

## Output Format

When handling imbalance, deliver:
1. **Profile** - counts, share, positives per fold, severity (`imbalance_report.py`).
2. **Evaluation setup** - metric at the operating point, natural-prevalence test set, CV scheme.
3. **Baseline vs treatments** - original data vs weights vs resampling on identical folds (PR-AUC, recall@K).
4. **Threshold** - policy, value, precision/recall/flagged share on validation and test (`threshold_tuner.py`).
5. **Probabilities** - prior correction or calibration if a treatment changed them; ECE before/after.
6. **Risks** - few positives (CIs), drift in prevalence, re-thresholding after retraining.

## Scripts

```bash
python scripts/imbalance_report.py data.csv --target is_fraud
python scripts/imbalance_report.py data.csv --target churned --folds 5 --model linear --code
python scripts/imbalance_report.py data.csv --target queue --json
```
Class counts and shares, imbalance ratio, minority rows per fold, severity (mild / moderate / severe / extreme),
the strategy ladder for that severity, notes for few-positives folds, tiny multiclass classes and model family;
`--code` prints imblearn pipelines for weights, undersampling (ratio derived from the data) and SMOTE, with the
prior-correction command. Exit codes: 0 printed, 2 usage error.

```bash
python scripts/threshold_tuner.py preds.csv --beta 2 --min-precision 0.5 --min-recall 0.9 --k 50 --cost-fp 8 --cost-fn 600
python scripts/threshold_tuner.py preds.csv --train-rate 0.5 --true-rate 0.03 --write corrected.csv
```
Sweeps every distinct score and reports the best threshold for F-beta, Youden J, minimum precision, minimum
recall, top-K and minimum expected cost (plus the Bayes threshold for calibrated probabilities), with precision,
recall, F1, flagged share, FP and FN. Prior correction with ECE before/after and optional output of corrected
scores. Exit codes: 0 done, 2 usage or data error.

## Additional Resources

| File | Content |
|------|---------|
| [metrics-for-imbalance.md](references/metrics-for-imbalance.md) | PR vs ROC, baselines, metrics at K and at cost, MCC, CIs with few positives, multiclass macro metrics |
| [resampling-and-weights.md](references/resampling-and-weights.md) | Class weights per library, imblearn samplers, SMOTE variants and when they help, pipeline placement, experiments |
| [calibration-and-prior-shift.md](references/calibration-and-prior-shift.md) | Prior-shift derivation, CalibratedClassifierCV, reliability curves, prevalence drift in production |
| [extreme-imbalance-playbook.md](references/extreme-imbalance-playbook.md) | < 100 positives: anomaly detection, label collection, two-stage models, pooling, evaluation with CIs |
