# Search Spaces by Model Family

| Family | Parameter | Range | Scale | Notes |
|--------|-----------|-------|-------|-------|
| Logistic regression | C | 1e-4 - 1e2 | log | solver="saga" for l1/elasticnet; scale features |
| | penalty | l1, l2, elasticnet (+ l1_ratio 0.05-0.95) | cat | conditional l1_ratio |
| Ridge / Lasso / ElasticNet | alpha | 1e-5 - 1e1 | log | RidgeCV/LassoCV do this cheaply |
| SVM (RBF) | C | 1e-2 - 1e3 | log | tune with gamma jointly |
| | gamma | 1e-4 - 1e1 | log | "scale" is a good centre |
| k-NN | n_neighbors | 3 - 100 | log int | weights uniform/distance; scale features |
| Random forest | max_features | 0.1 - 0.8 (or sqrt/log2) | lin | most important RF knob |
| | min_samples_leaf | 1 - 50 | log int | regularisation |
| | max_depth | None, 8, 16, 32 | cat | usually None + leaf size |
| | n_estimators | fixed 300-500 | - | more trees never hurt accuracy |
| HistGradientBoosting | learning_rate | 0.02 - 0.3 | log | with early_stopping=True |
| | max_leaf_nodes | 8 - 128 | log int | capacity |
| | min_samples_leaf | 5 - 300 | log int | scale with data size |
| | l2_regularization | 1e-4 - 10 | log | |
| LightGBM | num_leaves | 7 - 255 | log int | capacity |
| | min_child_samples | 5 - 500 | log int | ~0.1-1% of rows |
| | subsample (+ subsample_freq=1) | 0.5 - 1.0 | lin | |
| | colsample_bytree | 0.3 - 1.0 | lin | |
| | reg_lambda / reg_alpha | 1e-3 - 30 / 1e-3 - 10 | log | |
| XGBoost | max_depth | 3 - 10 | int | |
| | min_child_weight | 1 - 50 | log | |
| | gamma | 1e-3 - 5 | log | |
| CatBoost | depth | 4 - 9 | int | |
| | l2_leaf_reg | 1 - 20 | log | |
| | random_strength | 0.1 - 10 | log | |
| MLP | hidden units | 16 - 512 | log int | 1-3 layers |
| | alpha (L2) | 1e-6 - 1e-1 | log | |
| | learning_rate_init | 1e-4 - 1e-2 | log | early_stopping=True |

## Fix, do not search

- Number of boosting rounds: early stopping.
- Learning rate for GBMs during search: fixed (0.05-0.1), lowered for the final fit.
- `random_state`, `n_jobs`, verbosity.
- Forest size: as many trees as time allows.

## Conditional spaces (Optuna)

```python
def objective(trial):
    model_type = trial.suggest_categorical("model", ["logreg", "hgb"])
    if model_type == "logreg":
        penalty = trial.suggest_categorical("penalty", ["l1", "l2", "elasticnet"])
        l1_ratio = trial.suggest_float("l1_ratio", 0.05, 0.95) if penalty == "elasticnet" else None
        C = trial.suggest_float("C", 1e-4, 1e2, log=True)
        ...
    else:
        lr = trial.suggest_float("learning_rate", 0.02, 0.3, log=True)
        ...
```

## Two-stage search

1. Coarse: wide log ranges, 30-60 random/TPE trials, possibly on a data sample.
2. Analyse: drop insensitive parameters; widen ranges at boundaries.
3. Fine: narrower ranges around the best region, full data, 30-100 trials.

## Preprocessing in the space

Pipelines let you tune preprocessing too (`prep__num__imputer__strategy`, `select__k`,
`prep__cat__onehot__min_frequency`). Include it only if it matters; each added dimension costs trials.
