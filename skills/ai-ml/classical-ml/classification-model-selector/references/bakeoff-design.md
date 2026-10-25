# Bake-Off Design

## Protocol

1. **Fix the evaluation first**: split strategy (time / group / stratified), primary metric at the operating
   point, secondary metrics, and the final untouched holdout.
2. **Shortlist** 3-5 models: logistic baseline, 1-2 GBMs, one model per hard constraint (EBM if
   explanations are mandatory), and the incumbent production model.
3. **Round 1: defaults** on identical folds. Purpose: find the family that fits the data, not the winner.
4. **Round 2: equal tuning budget** for the top two (same number of trials, same search method, same
   inner CV), nested inside the outer folds or followed by a fresh holdout.
5. **Compare with paired statistics** on per-fold scores (corrected resampled t-test, Wilcoxon) and
   bootstrap CIs on the holdout.
6. **Decide** with the decision rule (simplest within noise that meets constraints).
7. **Confirm** on the untouched holdout once.

## Folds

| Data | Splitter | Notes |
|------|----------|-------|
| i.i.d. rows | `StratifiedKFold(5, shuffle=True, random_state=0)`, repeated 3x for small data | report mean ± std |
| Repeated entities | `StratifiedGroupKFold` | the same entity never in train and test |
| Forward prediction | `TimeSeriesSplit` or rolling origin with a gap | the most recent fold matters most |

Precompute fold indices once and pass the same list to every model (the generated script does this).

## Metrics and costs

Record per fold: primary metric, secondary metrics, fit seconds, prediction latency per 1k rows, model size
(pickle bytes). Latency and size often decide between two models within noise.

## Budgets

| Model | Round-2 search |
|-------|----------------|
| Logistic | C on a log grid (10-20 values), penalty type |
| GBMs | 50-100 random/Bayesian trials over learning rate, leaves/depth, min child size, subsampling, regularisation; early stopping inside each fold |
| RF | max_features, min_samples_leaf (10-20 trials) |
| EBM | interactions, max_bins (5-10 trials) |

Give every finalist the same number of trials; report the budget.

## Time-based bake-off

For forecasting-like classification (churn, fraud), add a "by period" view: train on months 1..k, test on
month k+1, for several k. A model that wins on average but loses on the latest periods is a worse choice.

## Common pitfalls

| Pitfall | Effect |
|---------|--------|
| Different folds per model | differences reflect folds, not models |
| Tuning only the favourite | biased comparison |
| Selecting the winner on the test set and reporting its test score | optimistic |
| Comparing means without fold-level pairing | over- or under-states significance |
| Ignoring cost columns | a 0.002 AUC gain that doubles latency |
| Using impurity importances to compare models | not comparable across model types |

## Report template

```
Bake-off: churn_30d, 400 customers, StratifiedKFold(5, shuffle, seed 0), primary PR-AUC
| model    | PR-AUC mean ± sd | ROC-AUC | log loss | fit s | ms/1k rows |
| logreg   | 0.621 ± 0.095    | 0.799   | 0.400    | 0.01  | 33         |
| ebm      | 0.605 ± 0.114    | 0.787   | 0.413    | 2.7   | 8          |
| catboost | 0.557 ± 0.070    | 0.763   | 0.515    | 0.56  | 7          |
Paired test logreg vs ebm: difference +0.016, corrected t-test p = 0.6 (no evidence of a difference).
Decision: logistic regression (simplest, fastest, best calibrated); revisit GBMs when data > 5k rows.
```
