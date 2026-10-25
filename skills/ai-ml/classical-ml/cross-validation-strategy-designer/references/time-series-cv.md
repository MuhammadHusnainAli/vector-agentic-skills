# Time-Series Cross-Validation

## TimeSeriesSplit

```python
from sklearn.model_selection import TimeSeriesSplit
df = df.sort_values("score_date").reset_index(drop=True)
cv = TimeSeriesSplit(n_splits=5, test_size=None, gap=0, max_train_size=None)
for tr, te in cv.split(df):
    ...
```
- Expanding window by default; `max_train_size=N` makes it sliding.
- `test_size` fixes the test block length (rows); `gap` removes rows between train and test.
- Splits by **row position**: with irregular timestamps or many rows per date, build folds by date instead.

## Date-based folds

```python
cutoffs = pd.date_range("2024-01-01", "2024-06-01", freq="MS")
for c in cutoffs:
    train = df[df.score_date < c - pd.Timedelta(days=LABEL_WINDOW)]      # purge: labels must be complete before c
    test = df[(df.score_date >= c) & (df.score_date < c + pd.offsets.MonthBegin(1))]
```

## Purging and embargo

A row scored at t with a label window w uses information up to t + w. If training rows' label windows reach into
the test period, their labels contain test-period outcomes:
- **Purge**: drop training rows with t + w > test start (gap >= w).
- **Embargo**: when training data also comes after the test block (combinatorial / K-fold on time), drop rows
  within an embargo period after the test block, because features computed from rolling windows can overlap.

`fold_preview.py --strategy time --label-window W` flags folds whose gap is shorter than W days.

## Rolling-origin evaluation for forecasting

For horizon h, repeat: fit on data up to origin o, forecast o+1..o+h, move o forward by a step.
```python
origins = range(len(y) - 13 * 7, len(y) - 7, 7)          # weekly origins over the last quarter
for o in origins:
    model.fit(y[:o]); forecasts = model.predict(h=7); errors.append(metric(y[o:o + 7], forecasts))
```
Report error by horizon step (h = 1 is easier than h = 7).

## Panel data (many series)

- Split by time for all series together (same cutoff dates).
- Optionally also hold out entire series to measure cold-start performance.
- Make sure features (lags, rolling stats) are recomputed per fold from data before the cutoff.

## Choosing window settings

| Question | Setting |
|----------|---------|
| Does old data still represent the future? | no -> sliding window (`max_train_size`) |
| How often will the model be retrained? | test block = retraining interval |
| How far ahead are labels? | gap >= label window |
| How many folds? | enough to cover seasonality (e.g. 12 monthly folds for yearly patterns) when data allows |
