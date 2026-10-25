# scikit-learn API Changes and Gotchas

## Removed / renamed parameters (all raise in 1.9)

| Old | New | Removed in |
|-----|-----|-----------|
| `OneHotEncoder(sparse=False)` | `sparse_output=False` | 1.4 |
| `LogisticRegression(penalty="none")` | `penalty=None` | 1.4 |
| `normalize=True` (LinearRegression, Ridge, Lasso...) | `StandardScaler` step | 1.2 |
| `base_estimator=` (Bagging, AdaBoost, CalibratedClassifierCV...) | `estimator=` | 1.4 |
| `max_features="auto"` (forests, trees) | `"sqrt"` (classifiers), `1.0` (regressors) | 1.3 |
| `criterion="mse"` / `"mae"` | `"squared_error"` / `"absolute_error"` | 1.2 |
| `loss="deviance"` (GradientBoosting), `"ls"`, `"lad"` | `"log_loss"`, `"squared_error"`, `"absolute_error"` | 1.3 |
| `SGDClassifier(loss="log")` | `loss="log_loss"` | 1.3 |
| `AgglomerativeClustering(affinity=)` | `metric=` | 1.4 |
| `mean_squared_error(squared=False)` | `root_mean_squared_error()` | 1.6 |
| `cross_val_score(fit_params=)` | `params=` | 1.6 |
| `AdaBoostClassifier(algorithm="SAMME.R")` | (only SAMME; parameter later removed) | 1.6+ |
| `LogisticRegression(multi_class=)` | multinomial is the default; `OneVsRestClassifier` for OvR | deprecated 1.5 |
| `TargetEncoder(shuffle=, random_state=)` | pass a CV splitter as `cv=` | deprecated 1.9 |

Run `pipeline_lint.py` (SK002) after upgrades.

## Behaviour changes worth knowing

| Change | Impact |
|--------|--------|
| `HistGradientBoosting*` `categorical_features="from_dtype"` default (1.6) | pandas `category` columns are treated as categorical automatically |
| `OneHotEncoder` `handle_unknown="infrequent_if_exist"`, `min_frequency`, `max_categories` (1.1) | rare-level grouping without custom code |
| `set_output(transform="pandas")` (1.2), `"polars"` (1.4) | DataFrame outputs with names |
| Metadata routing (1.3+, opt-in) | sample weights and groups routed explicitly |
| `TunedThresholdClassifierCV`, `FixedThresholdClassifier` (1.5) | threshold selection as an estimator |
| `root_mean_squared_error`, `d2_*` scores (1.4+) | new metric functions |
| `validate_data` function replaces `self._validate_data` (1.6) | custom estimators |

## Error messages and fixes

| Message | Cause | Fix |
|---------|-------|-----|
| `Found unknown categories [...] in column ... during transform` | encoder without `handle_unknown` | `handle_unknown="ignore"` / `"infrequent_if_exist"` / `"use_encoded_value"` |
| `The feature names should match those that were passed during fit` | columns renamed/reordered | `X.reindex(columns=train_columns)` |
| `X has N features, but ... is expecting M features` | different preprocessing at inference | use the saved Pipeline, not separate steps |
| `ConvergenceWarning: lbfgs failed to converge` | unscaled features, low `max_iter` | scale; `max_iter=2000+`; check regularisation |
| `Input X contains NaN` | estimator without native NaN support | `SimpleImputer` step, or HistGradientBoosting |
| `could not convert string to float` | categorical column not encoded | add it to the ColumnTransformer |
| `Can't pickle <function <lambda>>` | lambda in FunctionTransformer / custom params | module-level function |
| `n_components must be <= n_features` | SVD/PCA on a small vocabulary or fold | cap components (see TextSVD in gen_pipeline output) |
| `All the N fits failed` | an error inside CV folds | `error_score="raise"` to see the first traceback |

## Gotchas

- `predict` returns labels; ranking metrics need `predict_proba(X)[:, 1]` or `decision_function`.
- `classes_` order defines `predict_proba` columns; for string labels check `model.classes_`.
- `train_test_split` shuffles by default; time-ordered data needs `shuffle=False` or explicit cutoffs.
- `StratifiedKFold` without `shuffle=True` keeps data order within classes (often sorted data -> biased folds).
- `cross_val_score` uses `StratifiedKFold` for classifiers when `cv=int`, unshuffled.
- `LogisticRegression` regularises by default (`C=1.0`); unscaled features are penalised by units.
- `RandomForest*` impurity importances are biased; use permutation importance on held-out data.
