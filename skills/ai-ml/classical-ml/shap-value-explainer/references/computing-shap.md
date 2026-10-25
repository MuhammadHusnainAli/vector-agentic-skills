# Computing SHAP

Verified with shap 0.54, scikit-learn 1.9, LightGBM 4.7, XGBoost 3.4, CatBoost 1.2.

## Tree models

```python
import shap
background = X_train.sample(500, random_state=0)
explainer = shap.TreeExplainer(model, data=background, feature_perturbation="interventional", model_output="raw")
sv = explainer.shap_values(X_explain)          # (rows, features); binary LightGBM/XGBoost: log-odds
base = explainer.expected_value                 # scalar (or one per class)
assert abs(base + sv.sum(1) - model.predict(X_explain, raw_score=True)).max() < 1e-6     # LightGBM
```
- XGBoost raw output: `model.predict(X, output_margin=True)`; sklearn GBM / HGB: `decision_function`.
- Random forests: SHAP in probability units (the forest averages probabilities).
- `feature_perturbation="tree_path_dependent"` (no background) is the default without `data=`. It is
  fast and exact for the tree, but credit flows along the training cover. Use it for HistGradientBoosting,
  where interventional output in shap 0.54 misses the baseline (about 2 log-odds off in our check).
- Interaction values: `explainer.shap_interaction_values(X)` gives (rows, features, features). The row
  sums equal the SHAP values. Use them for path-dependent trees on up to a few thousand rows.

## CatBoost

```python
from catboost import Pool
raw = model.get_feature_importance(Pool(X, cat_features=cat_cols), type="ShapValues")
sv, base = raw[:, :-1], raw[0, -1]             # last column is the expected value; multiclass: (rows, classes, f+1)
```
Native categorical handling; output in raw (log-odds) space; matches `predict(prediction_type="RawFormulaVal")`.

## Linear models

```python
explainer = shap.LinearExplainer(model, background)   # independent-feature assumption by default
sv = explainer.shap_values(X)                          # = coef * (x - background mean) for each feature
```
Scale-free reading: SHAP is in output units, so unlike coefficients it is comparable across features.

## Model-agnostic

```python
f = lambda a: model.predict_proba(pd.DataFrame(a, columns=cols))[:, 1]
explainer = shap.PermutationExplainer(f, shap.maskers.Independent(background, max_samples=100), seed=0)
e = explainer(X_explain)                                # e.values, e.base_values
```
Cost is about 2 x features x background evaluations per row. Keep the background at 50-200 rows and
explain a sample. `KernelExplainer` is older and slower; prefer Permutation, or Exact for fewer than
about 15 features.

## Background data

| Choice | Effect |
|--------|--------|
| Random sample of training data (100-1000 rows) | "relative to a typical case": the default |
| Only negatives (e.g. non-fraud) | "why is this flagged relative to normal": useful for alerts; say so |
| k-means summary (`shap.kmeans(X, 50)`) | cheaper for permutation/kernel methods |
| A single reference row | contrastive explanation against that row |
| The test row itself | wrong: everything cancels |

The base value is the mean model output over the background. Change the background and every SHAP value
changes, so report which one was used.

## Pipelines and encoded features

```python
prep, est = pipe[:-1], pipe[-1]
Xt = pd.DataFrame(prep.transform(X), columns=prep.get_feature_names_out())
sv = shap.TreeExplainer(est).shap_values(Xt)
# group one-hot columns back: SHAP is additive, so sums are exact
groups = {"plan": ["cat__plan_basic", "cat__plan_premium"], ...}
```
`gen_shap_script.py --group` maps each output column to the longest matching input column name after the
`transformer__` prefix.

## Multiclass

SHAP values come per class: shape (rows, features, classes) in shap >= 0.45, with one base value per class.
Explain the class of interest (`--class k`). For softmax models each class's SHAP is in its own log-odds,
so explain the predicted class, or the class that matters for the decision.

## Cost guide

| Explainer | 10k rows x 50 features |
|-----------|------------------------|
| TreeExplainer path-dependent | seconds |
| TreeExplainer interventional, 500 background rows | tens of seconds to minutes |
| Linear | instant |
| Permutation, 100 background rows | hours; explain a sample of 500-2000 rows |
