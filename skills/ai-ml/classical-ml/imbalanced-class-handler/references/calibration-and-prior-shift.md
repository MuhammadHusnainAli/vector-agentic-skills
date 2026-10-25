# Calibration and Prior Shift

## Why resampling distorts probabilities

By Bayes' rule the model's odds are prior odds x likelihood ratio. Training at positive rate r instead of the
real rate π multiplies the prior odds by `(r / (1 − r)) / (π / (1 − π))`. Undo it:

```
odds_true = odds_model x (π / (1 − π)) / (r / (1 − r))
p_true    = p·a / (p·a + (1 − p)·b),   a = π / r,  b = (1 − π) / (1 − r)
```
Exact for pure prior shift (the features' class-conditional distributions are unchanged, which holds for
random under/oversampling). For SMOTE (synthetic points) and class weights it is a good first-order
correction; check with a calibration curve.

```python
import numpy as np
def prior_correct(p, train_rate, true_rate):
    a, b = true_rate / train_rate, (1 - true_rate) / (1 - train_rate)
    return p * a / (p * a + (1 - p) * b)
```
For class weights w1 (positives) and w0 (negatives) the effective training rate is
`r = w1·π / (w1·π + w0·(1 − π))`.

## Calibration methods

```python
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
cal = CalibratedClassifierCV(estimator=model, method="isotonic", cv=5)    # or method="sigmoid" for small data
cal.fit(X_train, y_train)
frac_pos, mean_pred = calibration_curve(y_test, cal.predict_proba(X_test)[:, 1], n_bins=10, strategy="quantile")
```
- `sigmoid` (Platt) for few positives; `isotonic` with plenty of data.
- Calibrate on data at the **natural prevalence**.
- `FrozenEstimator` (scikit-learn >= 1.6) wraps an already-fitted model to calibrate on a holdout
  (`CalibratedClassifierCV(FrozenEstimator(model))`); the older `cv="prefit"` option was deprecated.

## Checking calibration

| Check | Tool |
|-------|------|
| Reliability curve | `calibration_curve` with quantile bins (equal counts) |
| ECE | weighted mean |mean predicted − observed rate| over bins (`threshold_tuner.py` prints it) |
| Brier score | proper scoring rule; decreases with better calibration and discrimination |
| Mean prediction vs prevalence | quick sanity check |

## Prevalence drift in production

If the real positive rate changes (fraud spike, seasonal churn), calibrated probabilities drift even when
ranking is stable. Monitor mean predicted probability vs observed rate (with label delay); apply the same
prior-shift formula with the new π, or recalibrate on recent labelled data. Capacity-based thresholds (top K)
are robust to prevalence changes; fixed probability thresholds are not.
