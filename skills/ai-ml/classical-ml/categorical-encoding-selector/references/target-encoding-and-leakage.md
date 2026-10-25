# Target Encoding and Leakage

## Why in-sample encoding leaks

A level seen once with y = 1 gets encoding 1.0; the model learns "encoding 1.0 -> positive". Every
singleton level now predicts its own label perfectly in training and in any CV where the encoding was
computed before splitting. In production a new row with that level has its own (unknown) label, so the
signal disappears.

Even with many rows per level, including the row's own label biases the encoding toward it, and models
(especially GBMs) amplify the bias.

## Smoothing

```
enc(level) = (n · mean(level) + m · prior) / (n + m)
```
- m = 0: raw mean (maximum leakage for small n).
- Large m: everything collapses to the prior.
- Choose m by CV, or use empirical Bayes: `TargetEncoder(smooth="auto")` sets the shrinkage per level from
  the ratio of within-level variance to between-level variance.

Smoothing reduces but does not remove leakage; cross-fitting removes it.

## Cross-fitting (out-of-fold encoding)

```
for each fold k:
    fit the level -> mean mapping on rows not in fold k
    encode rows in fold k with it
final mapping for test/production = fit on all training rows
```
scikit-learn's `TargetEncoder.fit_transform(X, y)` does exactly this (`cv=5` by default); calling
`fit(X, y).transform(X)` instead does **not** cross-fit, so always use `fit_transform` on training data (a
Pipeline does this automatically).

```python
from sklearn.pipeline import make_pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import TargetEncoder
from sklearn.linear_model import LogisticRegression

prep = ColumnTransformer([("te", TargetEncoder(smooth="auto"), ["merchant", "zip3"])], remainder="passthrough")
model = make_pipeline(prep, LogisticRegression(max_iter=2000))
# cross_val_score(model, X, y, cv=...) refits the encoder inside every outer fold: honest evaluation.
```

## Nested structure

Two levels of folds exist:
- **Outer CV** (model evaluation): the encoder is refitted on each outer training fold.
- **Inner cross-fitting** (inside `fit_transform`): produces leakage-free training features within that fold.

Fitting the encoder once on all data and then running CV leaks the evaluation folds' labels into training
features: the CV score is optimistic.

## Time-aware encoding

When rows are events in time, encode each row from **earlier** rows only (expanding mean per level), which is
also how production works:

```python
df = df.sort_values("ts")
g = df.groupby("merchant")["is_fraud"]
prior = df["is_fraud"].mean()
cum_sum = g.cumsum() - df["is_fraud"]          # exclude the current row
cum_n = g.cumcount()
m = 20
df["merchant_te_time"] = (cum_sum + m * prior) / (cum_n + m)
```
Strictly, use only labels that were *known* at the row's time (respect label delay).

## Multiclass and regression targets

- Multiclass: one column per class with P(class | level) (sklearn `target_type="multiclass"`).
- Regression: mean target per level; consider the median or a log-target mean for skewed targets.

## Diagnosing leakage

1. `te_leakage_check.py`: in-sample vs out-of-fold vs holdout single-feature AUC.
2. Compare CV score with a time-ordered holdout score; a large gap with target-encoded features is a red
   flag.
3. Importance check: a target-encoded high-cardinality column at the top of importance with a much weaker
   holdout effect.

## Low-cardinality note

For a column with few levels and many rows per level, in-sample optimism is small. Out-of-fold encodings of
pure-noise columns can even give AUC below 0.5 (leaving out a fold shifts each level's mean away from that
fold's labels), so small gaps there are not alarming. The danger grows as rows per level fall below ~50.
