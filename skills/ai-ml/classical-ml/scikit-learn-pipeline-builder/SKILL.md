---
name: scikit-learn-pipeline-builder
description: "Build correct, production-shaped scikit-learn pipelines: Pipeline and ColumnTransformer per column role (impute + scale, one-hot with infrequent grouping, cross-fitted TargetEncoder, native categoricals for HistGradientBoosting, TF-IDF + SVD for text, date transformers), the right CV splitter (StratifiedKFold, StratifiedGroupKFold, TimeSeriesSplit with gap), cross_validate with several metrics, RandomizedSearchCV / HalvingRandomSearchCV with step__param names, nested CV, custom transformers with get_feature_names_out, set_output, caching, joblib/skops persistence and a predict helper. Generates a runnable training script from a CSV and lints code for API misuse (hard labels into roc_auc_score, removed parameters, LabelEncoder on features, get_dummies, unpicklable lambdas, scoring on training data, missing random_state, nested n_jobs). Use when someone asks to build, fix or review a scikit-learn pipeline, ColumnTransformer, preprocessing + model workflow, or sees errors from sklearn upgrades."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# scikit-learn Pipeline Builder

A scikit-learn model is only as trustworthy as its pipeline. Everything learned from data (imputation values,
scaling statistics, encodings, vocabularies, selected features) goes inside one `Pipeline`, so that
cross-validation refits it per fold and the saved artefact reproduces training exactly at inference time.
`scripts/gen_pipeline.py` writes a complete training script for a CSV: inferred column roles, a
`ColumnTransformer`, the right CV splitter, optional search, `cross_validate` metrics, a saved model and a
`predict()` helper. It is verified to run for binary, multiclass and regression targets with linear,
HistGradientBoosting and random-forest models, text and date columns, groups, time order and both search
types. `scripts/pipeline_lint.py` catches scikit-learn API misuse that produces wrong numbers or fails after
upgrades.

## Trigger Conditions

Activate this skill when the user:
- Asks to build a preprocessing + model pipeline, a ColumnTransformer, or "the sklearn way" of doing it
- Has preprocessing done with pandas outside the model and needs it inside a deployable pipeline
- Gets errors such as "Found unknown categories", "feature names unseen at fit time", `TypeError:
  __init__() got an unexpected keyword argument 'sparse'`, ConvergenceWarning, or pickling errors
- Wants grid/random/halving search over preprocessing and model parameters together
- Needs custom transformers that work with `get_feature_names_out`, `set_output` and cloning
- Wants a code review of a scikit-learn training script

Leakage-specific review: [target-leakage-detector](../target-leakage-detector/SKILL.md); choosing the CV scheme:
[cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md); search spaces:
[hyperparameter-search-planner](../hyperparameter-search-planner/SKILL.md).

## Workflow

```
1. ROLES     -> numeric / categorical / high-cardinality / date / text / ID per column
2. GENERATE  -> python scripts/gen_pipeline.py data.csv --target y --model hgb --time-col ts -o train.py
3. SPLITTER  -> stratified (iid), group (repeated entities), time (forward prediction, gap = label window)
4. EVALUATE  -> cross_validate with 2-3 metrics, train and test scores (gap = overfitting)
5. SEARCH    -> --search random|halving; nested CV for an unbiased estimate of a tuned model
6. LINT      -> python scripts/pipeline_lint.py train.py ; then target-leakage-detector's code_leak_lint.py
7. PERSIST   -> joblib dump of the fitted Pipeline + column list + versions; predict() reindexes columns
```

## Anatomy of a Correct Pipeline

```python
from sklearn.compose import ColumnTransformer, make_column_selector as sel
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder
from sklearn.linear_model import LogisticRegression

prep = ColumnTransformer([
    ("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()),
     sel(dtype_include="number")),
    ("cat", make_pipeline(SimpleImputer(strategy="most_frequent"),
                          OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20)),
     ["plan", "region"]),
    ("hc", TargetEncoder(smooth="auto"), ["merchant_id"]),          # cross-fitted during fit_transform
], remainder="drop", verbose_feature_names_out=True)

model = Pipeline([("prep", prep), ("clf", LogisticRegression(C=1.0, max_iter=5000))])
model.fit(X_train, y_train)
print(model[:-1].get_feature_names_out()[:10])                     # names after preprocessing
```

| Rule | Why |
|------|-----|
| Every fitted step inside the Pipeline | CV refits it per fold; the saved model reproduces it |
| `handle_unknown` on every encoder | production sees new levels |
| Explicit column lists (or selectors) and `remainder=` | silent column drops are bugs |
| `add_indicator=True` on numeric imputers | missingness often carries signal |
| Search parameters as `step__param` (`clf__C`, `prep__num__simpleimputer__strategy`) | nested names address any step |
| One saved object (`joblib.dump(model)`) | no separate scaler/encoder files to drift apart |

Every building block with variants (selectors, `set_output(transform="pandas")`, caching with `memory=`,
`FunctionTransformer`, `TransformedTargetRegressor`, `FeatureUnion`): [pipeline-anatomy.md](references/pipeline-anatomy.md).

## Model-Family Presets (what gen_pipeline.py emits)

| `--model` | Numeric | Categorical | High-cardinality | Dates | Text |
|-----------|---------|-------------|------------------|-------|------|
| `linear` | median impute + indicator, StandardScaler | one-hot, `min_frequency=20` | TargetEncoder | DateFeatures -> scaled | TF-IDF (1-2 grams) |
| `hgb` | passthrough (NaN native) | OrdinalEncoder first, `categorical_features=` indices | TargetEncoder | DateFeatures | TF-IDF -> capped SVD |
| `rf` | median impute | OrdinalEncoder | TargetEncoder | DateFeatures | TF-IDF -> capped SVD |

HistGradientBoosting gets categorical column *indices*: the ordinal block is placed first in the
ColumnTransformer, so indices 0..k-1 stay correct whatever the width of later blocks (multiclass target
encoding, SVD).

## Cross-Validation and Search Inside the Pipeline

```python
from sklearn.model_selection import StratifiedKFold, cross_validate, RandomizedSearchCV
from scipy.stats import loguniform

cv = StratifiedKFold(5, shuffle=True, random_state=0)
res = cross_validate(model, X, y, cv=cv, scoring=["roc_auc", "average_precision", "neg_log_loss"],
                     return_train_score=True)

search = RandomizedSearchCV(model, {"clf__C": loguniform(1e-3, 1e2),
                                    "prep__cat__onehotencoder__min_frequency": [5, 20, 50]},
                            n_iter=40, scoring="average_precision", cv=cv, random_state=0, n_jobs=-1)
nested = cross_validate(search, X, y, cv=StratifiedKFold(5, shuffle=True, random_state=1),
                        scoring="average_precision")        # unbiased estimate of "tune then fit"
```
- `best_score_` of a search is optimistic (it is the max over configurations); report nested CV or a fresh
  holdout.
- `groups=` must be passed to `fit` / `cross_validate` for group splitters (and is routed to the inner CV).
- Use `scoring=` names, not hard-label metrics, for ranking problems.

Search, nested CV, metadata routing and `TunedThresholdClassifierCV`:
[cv-and-search-in-pipelines.md](references/cv-and-search-in-pipelines.md).

## Custom Transformers

```python
from sklearn.base import BaseEstimator, TransformerMixin, OneToOneFeatureMixin
import numpy as np

class Log1pClip(OneToOneFeatureMixin, TransformerMixin, BaseEstimator):
    """log1p after clipping at a training quantile. Learned state ends with '_'."""

    def __init__(self, upper_quantile=0.99):
        self.upper_quantile = upper_quantile          # store params unchanged: clone() and set_params rely on it

    def fit(self, X, y=None):
        self.upper_ = np.nanquantile(np.asarray(X, dtype=float), self.upper_quantile, axis=0)
        self.n_features_in_ = np.asarray(X).shape[1]
        return self

    def transform(self, X):
        return np.log1p(np.clip(np.asarray(X, dtype=float), 0, self.upper_))
```
Rules (`__init__` only stores parameters, fitted attributes end in `_`, `get_feature_names_out`, no lambdas,
`check_estimator` for libraries): [custom-transformers.md](references/custom-transformers.md).

## API Misuse the Linter Catches

| Code | Mistake | Fix |
|------|---------|-----|
| SK001 | `roc_auc_score(y, model.predict(X))` | `model.predict_proba(X)[:, 1]` |
| SK002 | removed params: `OneHotEncoder(sparse=)`, `penalty="none"`, `normalize=`, `base_estimator=`, `max_features="auto"`, `criterion="mse"`, `loss="deviance"`, `affinity=`, `mean_squared_error(squared=False)`, `fit_params=`, `algorithm="SAMME.R"` | `sparse_output=`, `penalty=None`, scaler step, `estimator=`, `"sqrt"`, `"squared_error"`, `"log_loss"`, `metric=`, `root_mean_squared_error`, `params=`, drop it |
| SK003 | `LabelEncoder` on features | `OrdinalEncoder` / `OneHotEncoder` |
| SK004 | `pd.get_dummies` before training | `OneHotEncoder` in the Pipeline |
| SK005 | `FunctionTransformer(lambda ...)` | named function |
| SK006 | `.score(X, y)` on the fit data | held-out split / CV |
| SK007 | no `random_state` | set it on estimators, splitters, searches |
| SK008 | `n_jobs=-1` in both search and estimator | parallelise one level |
| SK009 | `LogisticRegression` without `max_iter` | scale + `max_iter=2000+` |
| SK010 | `ColumnTransformer` without `remainder=` | explicit choice |

All SK002 parameters were checked to raise in scikit-learn 1.9. Version notes:
[api-changes-and-gotchas.md](references/api-changes-and-gotchas.md).

## Persistence and Serving

```python
import joblib, sklearn
joblib.dump({"model": model, "columns": list(X.columns), "sklearn": sklearn.__version__}, "model.joblib")
bundle = joblib.load("model.joblib")
X_new = X_new.reindex(columns=bundle["columns"])           # same columns, same order; missing -> NaN
p = bundle["model"].predict_proba(X_new)[:, 1]
```
Load only trusted pickles (joblib/pickle execute code). `skops.io` gives a safer format; ONNX
(`skl2onnx`) for non-Python serving. Pin the scikit-learn version: pickles are not guaranteed across
versions. Details: [persistence-and-serving.md](references/persistence-and-serving.md).

## Output Format

When building or reviewing a pipeline, deliver:
1. **Column roles** and the preprocessing per role (table).
2. **Code** - the full Pipeline (generated by `gen_pipeline.py` or written by hand), splitter, metrics, search.
3. **Evaluation** - `cross_validate` results with train vs test means and standard deviations.
4. **Lint results** - `pipeline_lint.py` and `code_leak_lint.py` findings with fixes.
5. **Serving notes** - saved artefact contents, column contract, version pins, unknown-category behaviour.

## Scripts

```bash
python scripts/gen_pipeline.py data.csv --target churned --model hgb --time-col signup_date -o train.py
python scripts/gen_pipeline.py data.csv --target churned --model linear --group-col customer_id --search random
python scripts/gen_pipeline.py data.csv --target price --model rf --drop house_id --search halving
python scripts/gen_pipeline.py tickets.csv --target queue --model hgb --text-cols body --cat-cols account
```
Infers numeric, categorical, high-cardinality (> 50 levels or zip-like codes), date, text and dropped
columns (`--cat-cols` / `--text-cols` / `--drop` override). Writes a script with a DateFeatures transformer,
the model-family preprocessor, the CV splitter (`StratifiedKFold`/`KFold`, `StratifiedGroupKFold`/`GroupKFold`
with `--group-col`, `TimeSeriesSplit(gap=)` with `--time-col`), `cross_validate` on 3 metrics with train scores,
optional `RandomizedSearchCV` or `HalvingRandomSearchCV` with ranges scaled to the data size, a joblib bundle and
`predict()`. Exit codes: 0 written, 2 usage or read error.

```bash
python scripts/pipeline_lint.py train.py
python scripts/pipeline_lint.py src/*.py --json
```
Rules SK001-SK010 in the table above (AST-based). Exit codes: 0 no high findings, 1 high findings, 2 read or
syntax error.

## Additional Resources

| File | Content |
|------|---------|
| [pipeline-anatomy.md](references/pipeline-anatomy.md) | Pipeline, make_pipeline, ColumnTransformer, selectors, FeatureUnion, set_output, memory caching, TransformedTargetRegressor, slicing and inspecting fitted pipelines |
| [custom-transformers.md](references/custom-transformers.md) | Estimator contract, fitted attributes, feature names, stateless vs stateful transformers, testing with check_estimator, common bugs |
| [cv-and-search-in-pipelines.md](references/cv-and-search-in-pipelines.md) | cross_validate, parameter naming, searches, nested CV, groups and metadata routing, threshold tuning, refit strategies |
| [persistence-and-serving.md](references/persistence-and-serving.md) | joblib, skops, ONNX, version pinning, column contracts, input validation, batch and online inference |
| [api-changes-and-gotchas.md](references/api-changes-and-gotchas.md) | Removed/renamed parameters by version, behaviour changes, common error messages and their fixes |
