# Reading Learning Curves

## The decomposition

For a fixed model and data distribution, as the training set size n grows:
- the **training score** falls (it is harder to fit more rows), approaching the best achievable score
  for this model class from above;
- the **validation score** rises towards the same limit from below;
- the **gap** (train - validation) is the variance part of the error; the distance from the common limit to
  the perfect score is bias plus irreducible noise.

So the curve answers three questions:

| Question | Read |
|----------|------|
| Does more data help? | validation slope at the largest sizes, per doubling |
| How much can more data give at most? | headroom = training score - validation score at the largest size |
| Is the model capable enough? | the training score itself: if it is already low, the model cannot fit even what it sees |

## Canonical shapes

```
HIGH VARIANCE, DATA-LIMITED        HIGH VARIANCE, FLAT              HIGH BIAS
score                               score                             score
1.0 |T T T T T                      1.0 |T T T T T T                   |
    |          T  T                     |                              |T T T
    |              v  v                 |    v v v v v v               |      T T T T
    |         v  v                      |  v                           |  v v v v v v  (both low, met)
    |   v  v                            |v                             |v
    +---------------- n (log)           +---------------- n            +---------------- n
```

## Metric conventions

- scikit-learn scorers are **higher is better**; losses appear as `neg_*` (e.g. `neg_root_mean_squared_error`
  around -35 000). `diagnose_curve.py` uses that convention by default; use `--lower-better` for curves
  stored as positive losses.
- The default gap threshold is 0.02 x max(1, |score|): two points of AUC or accuracy, 2% of an RMSE. Set
  `--gap-threshold` from what matters for the product (e.g. 0.01 AUC for a mature fraud model).
- For accuracy on imbalanced data the curve can look converged at the majority-class rate: use AUC, average
  precision or log loss.

## Common misreadings

| Misreading | Reality |
|------------|---------|
| "Training is 1.0, so the model is great" | memorisation; only the validation curve matters, and the gap is variance |
| "The gap is closing, so we are fine" | if both curves meet at a low score, that is bias |
| "Validation went down at the largest size, we are overfitting" | more rows cannot cause overfitting; look for drift, label noise or non-random subsets |
| "One point higher at 2x, let's collect 10x" | power laws flatten; measure again after the next doubling |
| Reading a single fold | fold noise often exceeds the gain from doubling; use the mean and its standard error |
| Comparing curves from different splitters | grouped and random splits give different curves; keep the evaluation design fixed |
| Tuning hyperparameters on each subset without saying so | the curve then mixes data effect and tuning effect |

## Learning curves for special data

- **Time series**: `TimeSeriesSplit` with `shuffle=False`: the smallest size is the earliest window, so the
  curve also contains time drift. A falling validation curve then can mean the older rows are less relevant;
  test a recency-weighted or a rolling-window model.
- **Grouped data** (customers, patients): use the number of groups, not rows, as the size you plan to collect.
- **Imbalanced targets**: what helps is more positives; report the number of positives at each size.
