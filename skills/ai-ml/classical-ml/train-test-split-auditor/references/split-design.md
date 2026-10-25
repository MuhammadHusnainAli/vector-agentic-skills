# Split Design

## Roles

| Set | Used for | Touched |
|-----|----------|---------|
| Training | fitting | always |
| Validation (or CV folds) | model selection, tuning, thresholds, early stopping | many times |
| Test (holdout) | final, unbiased estimate | once |
| Production sample | shift check before/after deployment | for monitoring |

## Split types

```python
from sklearn.model_selection import train_test_split, GroupShuffleSplit

# stratified random (i.i.d.)
tr, te = train_test_split(df, test_size=0.2, stratify=df.y, random_state=0)

# grouped (new entities)
gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=0)
tr_idx, te_idx = next(gss.split(df, groups=df.customer_id))

# time-based (next period), with a purge gap for 30-day labels
cut = pd.Timestamp("2024-05-01")
tr = df[df.score_date < cut - pd.Timedelta(days=30)]
te = df[df.score_date >= cut]

# out-of-distribution: hold out whole regions
te = df[df.region.isin(["north"])]; tr = df[~df.region.isin(["north"])]
```

## Sizes

- Test size is set by the precision needed for the metric (ml-feasibility-assessor `sample_size.py`): e.g.
  ~900 positives to measure recall to ±3 points.
- Large data: a fixed-size test set (e.g. 100k rows) is enough; more data goes to training.
- Small data: prefer repeated CV plus a modest holdout, or CV only with nested tuning.

## Ordering of operations

1. Deduplicate (exact and near) or assign duplicate-cluster group ids.
2. Split (by time / group / stratified).
3. Fit every preprocessing step on training data only.
4. Tune with CV inside training.
5. Evaluate once on the test set.

## Protecting the holdout

- Store it separately with restricted access; log every evaluation against it.
- Freeze model, features and threshold before evaluating.
- If it was used to make decisions, build a fresh one (new period or new entities).
