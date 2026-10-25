# Baseline Catalog

Code assumes `X_train, X_test, y_train, y_test` from the deployment-faithful split.

## Classification

### Dummy predictors
```python
from sklearn.dummy import DummyClassifier
from sklearn.metrics import average_precision_score, log_loss, roc_auc_score

for strategy in ("most_frequent", "prior", "stratified"):
    d = DummyClassifier(strategy=strategy, random_state=0).fit(X_train, y_train)
    p = d.predict_proba(X_test)[:, 1]
    print(strategy, roc_auc_score(y_test, p), average_precision_score(y_test, p), log_loss(y_test, p, labels=[0, 1]))
```
- `prior` gives the log-loss and Brier floor.
- PR-AUC of any constant score equals the test prevalence.

### Current business rule
```python
rule = (X_test["support_calls"] >= 3) | (X_test["last_login_days"] > 30)
from sklearn.metrics import precision_score, recall_score
print("rule precision", precision_score(y_test, rule), "recall", recall_score(y_test, rule))
```
For capacity-bound decisions, compare at the same K: rank by the rule's own priority order (or randomly within
the rule's positives) and take the top K.

### One feature (OneR)
```python
import pandas as pd
from sklearn.metrics import roc_auc_score

def one_feature_auc(col, bins=10):
    if pd.api.types.is_numeric_dtype(X_train[col]):
        edges = pd.qcut(X_train[col], bins, retbins=True, duplicates="drop")[1]
        tr = pd.cut(X_train[col], edges, include_lowest=True)
        te = pd.cut(X_test[col].clip(edges[0], edges[-1]), edges, include_lowest=True)
    else:
        tr, te = X_train[col], X_test[col]
    rate = y_train.groupby(tr, observed=True).mean()
    return roc_auc_score(y_test, te.map(rate).astype(float).fillna(y_train.mean()))
```
Pick the column on a validation split, not on the test set.

### Linear and GBM baselines
See first-model-recipes.md; untuned `LogisticRegression(max_iter=2000)` and
`HistGradientBoostingClassifier()` in pipelines.

## Regression

```python
from sklearn.dummy import DummyRegressor
for strategy in ("mean", "median"):
    d = DummyRegressor(strategy=strategy).fit(X_train, y_train)
```
- Median minimises MAE; mean minimises squared error; report the one that matches the metric.
- R² of the mean predictor on the test set is ≈ 0 (slightly negative because the train mean differs).
- For WAPE/MAPE-reported problems, also try `DummyRegressor(strategy="quantile", quantile=0.5)`.

## Forecasting

```python
import numpy as np

def naive(y, h):                      # last observed value
    return np.repeat(y[-1], h)

def seasonal_naive(y, h, m):          # same point one season ago
    return np.array([y[-m + (i % m)] for i in range(h)])

def drift(y, h):                      # straight line from first to last value
    slope = (y[-1] - y[0]) / (len(y) - 1)
    return y[-1] + slope * np.arange(1, h + 1)

def moving_average(y, h, w=28):
    return np.repeat(np.mean(y[-w:]), h)

def mase(y_true, y_pred, y_train, m):
    scale = np.mean(np.abs(y_train[m:] - y_train[:-m]))
    return np.mean(np.abs(y_true - y_pred)) / scale
```
Backtest on several rolling origins (see time-series-forecasting-model-builder).

### Intermittent demand (Croston / SBA)
```python
def croston(y, h, alpha=0.1, sba=True):
    z = p = None
    q = 1
    for v in y:
        if v > 0:
            z = v if z is None else z + alpha * (v - z)
            p = q if p is None else p + alpha * (q - p)
            q = 1
        else:
            q += 1
    if z is None:
        return np.zeros(h)
    f = z / p * ((1 - alpha / 2) if sba else 1)
    return np.repeat(f, h)
```

## Recommendation

```python
popular = train.groupby("item_id").size().sort_values(ascending=False).index[:10]
# per-user top-k excluding items already seen
def recommend(user, k=10):
    seen = set(train.loc[train.user_id == user, "item_id"])
    return [i for i in popular_full if i not in seen][:k]
```
Segment popularity (most popular among users in the same country/plan) is a stronger, still-cheap rung.

## Ranking

- Current production ranking or BM25 score.
- Sort by one strong feature (clicks, recency).
- Random order within a query gives the NDCG floor (compute it, it is not 0).

## Anomaly detection

```python
med = X_train.median()
mad = (X_train - med).abs().median() * 1.4826
score = ((X_test - med).abs() / mad.replace(0, np.nan)).max(axis=1)   # worst robust z across features
```

## Survival

Kaplan-Meier without covariates predicts the same survival curve for everyone: concordance 0.5, and its
integrated Brier score is the floor for covariate models.

## Uplift

| Policy | Expected value |
|--------|----------------|
| Treat nobody | control conversion rate x N |
| Treat everyone | treatment conversion rate x N - cost x N |
| Random targeting of K | linear between the two; Qini = 0 |
| Response model (top K by P(convert)) | often worse than random for uplift: targets sure things |

## Multiclass

- Majority class: accuracy = majority share; macro-F1 ≈ 1/K x F1 of the majority.
- Class priors (stratified dummy).
- Keyword or rule router (rung 2).

## Clustering

Compare silhouette / stability against:
- K random clusters of the same sizes (silhouette ≈ 0).
- The same algorithm on data with each column independently shuffled (destroys structure).
