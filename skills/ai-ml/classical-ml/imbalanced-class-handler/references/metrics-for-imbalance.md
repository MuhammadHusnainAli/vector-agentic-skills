# Metrics for Imbalanced Problems

## Why accuracy fails

At 2% prevalence "always negative" is 98% accurate and catches nothing. Any metric dominated by true
negatives hides the minority class.

## ROC vs PR

| | ROC-AUC | PR-AUC (average precision) |
|-|---------|----------------------------|
| Random baseline | 0.5 | prevalence (e.g. 0.02) |
| Sensitive to prevalence | no | yes |
| Focus | whole ranking | top of the ranking (where decisions happen) |
| Good for | comparing rankers across datasets | rare-event decisions |

A model can have ROC-AUC 0.95 and PR-AUC 0.2 at 0.5% prevalence: thousands of false positives per true one.
Report both, decide on PR-AUC or the operating-point metric.

## Operating-point metrics

```python
import numpy as np
def at_k(y, s, k):
    idx = np.argsort(-s)[:k]
    tp = y[idx].sum()
    return {"precision@k": tp / k, "recall@k": tp / y.sum(), "lift@k": (tp / k) / y.mean()}
```
Expected cost at a threshold: `(FP * C_fp + FN * C_fn) / n`.

## Few positives: confidence intervals

With 34 positives the standard error of recall is ~sqrt(r(1−r)/34): at r = 0.7 that is ±0.08 (one SE).
Always attach intervals:
```python
def bootstrap(y, s, metric, n=2000, seed=0):
    rng = np.random.default_rng(seed); out = []
    pos, neg = np.where(y == 1)[0], np.where(y == 0)[0]
    for _ in range(n):
        idx = np.concatenate([rng.choice(pos, len(pos)), rng.choice(neg, len(neg))])   # stratified resample
        out.append(metric(y[idx], s[idx]))
    return np.percentile(out, [2.5, 97.5])
```
Stratified bootstrap keeps the positive count fixed so intervals are not distorted by resamples with
too few positives.

## CV with few positives

- `StratifiedKFold` so each fold has its share of positives.
- `RepeatedStratifiedKFold(n_splits=5, n_repeats=5)` to average out fold noise.
- Pool out-of-fold predictions (`cross_val_predict`) and compute PR-AUC once on all of them, in addition to
  per-fold means: per-fold PR-AUC with 7 positives is extremely noisy.

## Multiclass with rare classes

- Per-class precision/recall/F1 (`classification_report`).
- Macro averages so rare classes count equally; weighted averages for frequency-weighted views.
- One-vs-rest PR-AUC per class.
- Confusion matrix normalised by true class (`normalize="true"`).

## Summary metrics that respect both classes

| Metric | Notes |
|--------|-------|
| Balanced accuracy | mean of TPR and TNR |
| MCC | correlation between predictions and labels; robust single number |
| G-mean | sqrt(TPR x TNR) |
| F-beta | weighs recall vs precision; ignores TN |
