# Data Volume and Sample Size

## Events per variable (EPV)

For logistic regression and other parametric models, the number of minority-class events per estimated
parameter controls coefficient stability and overfitting. Classic guidance is EPV >= 10; simulation studies
(Riley et al. 2019, BMJ) suggest calculating the size properly, often needing 15-20+ for good calibration.

Count **parameters**, not columns: a categorical with 12 levels one-hot encoded is 11 parameters; a spline
with 4 knots is 4-5 parameters; interactions count separately.

| Minority events | Max parameters at EPV 10 | Implication |
|-----------------|--------------------------|-------------|
| 50 | 5 | a handful of hand-picked features, strong regularisation |
| 200 | 20 | a modest model |
| 1,000 | 100 | most tabular projects |
| 10,000+ | 1,000+ | volume is not the bottleneck |

Tree ensembles do not have a clean EPV rule; they need more data than linear models for the same stability,
but regularisation (min_child_samples, max_depth, learning rate) and early stopping help.

## Confidence interval of a proportion metric

Precision, recall, accuracy and positive rate are proportions with denominator n:

```
half_width = z * sqrt(p (1 - p) / n)          z = 1.96 for 95%
n          = z^2 p (1 - p) / half_width^2
```

| p | +/-0.05 | +/-0.03 | +/-0.02 | +/-0.01 |
|---|---------|---------|---------|---------|
| 0.5 | 385 | 1,068 | 2,401 | 9,604 |
| 0.7 | 323 | 897 | 2,017 | 8,068 |
| 0.9 | 139 | 385 | 865 | 3,458 |

The denominator matters: recall's denominator is the positives, so at a 2% positive rate measuring recall to
+/-3 points at p = 0.7 needs ~900 positives = ~45,000 test rows.

For small n or p near 0 or 1 use the Wilson interval instead of the normal approximation.

## AUC standard error (Hanley and McNeil 1982)

```
Q1 = A / (2 - A)
Q2 = 2A^2 / (1 + A)
SE^2 = [A(1-A) + (n_pos - 1)(Q1 - A^2) + (n_neg - 1)(Q2 - A^2)] / (n_pos n_neg)
```

| Positives | Negatives | AUC 0.75: 95% half-width | AUC 0.85 |
|-----------|-----------|--------------------------|----------|
| 50 | 500 | 0.080 | 0.068 |
| 100 | 1,000 | 0.057 | 0.048 |
| 300 | 3,000 | 0.033 | 0.028 |
| 1,000 | 10,000 | 0.018 | 0.015 |

The positive count dominates. For comparing two AUCs on the same rows use DeLong's test or a paired bootstrap
(see ml-model-comparison-reporter); the paired difference is much tighter than the two separate CIs suggest.

## Comparing two classifiers (McNemar)

On a shared test set, only rows where the models disagree matter. With disagreement rate `p_d` and accuracy
difference `d`:

```
n = (z_a sqrt(p_d) + z_b sqrt(p_d - d^2))^2 / d^2
```

Example: models disagree on 10% of rows; to detect a 3-point accuracy difference with 80% power at alpha 0.05
you need ~870 rows. At 5% disagreement and a 1-point difference you need ~4,000.

## Learning-curve extrapolation

Fit the validation metric against training size with a power law, `err(n) = a + b n^(-c)`, on 5-6 sizes
(e.g. 10%, 20%, 40%, 60%, 80%, 100%). The asymptote `a` is the best achievable error with this feature set;
if the current error is close to it, more data will not help, better features will. See
learning-curve-diagnoser for the fitting script.

## Rare events

When positives are below ~1% of rows:
- Collect over longer windows or pool similar populations (regions, products) with a group feature.
- Downsample negatives for training (keep all positives) and correct probabilities afterwards.
- Evaluate on the full, natural-prevalence test set.
- Consider anomaly detection or rules until a few hundred positives exist.

## Multiclass

Plan for the rarest class you care about: 50-100 examples is a practical floor for a usable per-class F1
estimate. Merge classes below that into "other" or a hierarchy level.

## Time series

- Local models per series: at least two full seasonal cycles (two years for yearly seasonality, two weeks for
  weekly).
- Global models across series: many short series can work; pool with series-level features.
- Backtesting needs several forecast origins: history >= training window + k x horizon.

## How long until we have enough?

```
periods = positives_needed / (rows_per_period x positive_rate) + label_delay
```

If the answer is longer than the business can wait, change the framing (longer window, broader event
definition), start with rules and collect labels from them, or buy/borrow data.
