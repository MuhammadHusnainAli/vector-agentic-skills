# Pipeline Anatomy

## Pipeline and make_pipeline

```python
from sklearn.pipeline import Pipeline, make_pipeline
pipe = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=2000))])
pipe = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))   # names: standardscaler, logisticregression
```
- All steps but the last must be transformers (`fit` + `transform`); the last can be anything.
- `pipe[:-1]` is the preprocessing sub-pipeline; `pipe[-1]` / `pipe.named_steps["clf"]` the model.
- `"passthrough"` or `None` disables a step (useful in searches: `{"select": ["passthrough", SelectKBest(k=20)]}`).

## ColumnTransformer

```python
from sklearn.compose import ColumnTransformer, make_column_selector as sel
ct = ColumnTransformer(
    transformers=[
        ("num", num_pipe, sel(dtype_include="number")),
        ("cat", cat_pipe, sel(dtype_include=["object", "category", "string"])),
        ("txt", TfidfVectorizer(), "description"),           # a single string column -> 1-D input for text
    ],
    remainder="drop",                # or "passthrough", or a transformer
    sparse_threshold=0.3,            # output sparse if overall density < 0.3
    verbose_feature_names_out=True,  # prefixes names with the transformer name: "num__age"
    n_jobs=None,
)
```
- Column spec: list of names, a single name (1-D for text vectorisers), boolean mask, slice, or a selector.
- Text vectorisers need a **string**, not a list: `"description"` not `["description"]`.
- `ct.get_feature_names_out()` after fitting; `ct.named_transformers_["cat"]` to inspect a fitted block.

## set_output

```python
ct.set_output(transform="pandas")     # DataFrame out, with column names (sklearn >= 1.2)
```
Requires every inner transformer to support `set_output` (text vectorisers and some third-party
transformers do not) and dense output. Useful for debugging and for models that read column names.

## Caching

```python
from tempfile import mkdtemp
pipe = Pipeline(steps, memory=mkdtemp())     # caches fitted transformers across a grid search
```
Helps when preprocessing is expensive and only the model's parameters vary.

## FeatureUnion

Concatenates outputs of transformers applied to the **same** input:
```python
from sklearn.pipeline import FeatureUnion
from sklearn.decomposition import PCA, TruncatedSVD
feats = FeatureUnion([("pca", PCA(n_components=10)), ("raw", "passthrough")])
```

## FunctionTransformer

```python
import numpy as np
from sklearn.preprocessing import FunctionTransformer
log1p = FunctionTransformer(np.log1p, inverse_func=np.expm1, feature_names_out="one-to-one")
```
Stateless only (learns nothing). Pass a module-level function, not a lambda, so the pipeline pickles.

## TransformedTargetRegressor

```python
from sklearn.compose import TransformedTargetRegressor
reg = TransformedTargetRegressor(regressor=pipe, func=np.log1p, inverse_func=np.expm1)
```
Transforms y for fitting and inverts predictions automatically.

## Imputation inside pipelines

| Imputer | Use |
|---------|-----|
| `SimpleImputer(strategy="median", add_indicator=True)` | default for numerics |
| `SimpleImputer(strategy="most_frequent")` or `fill_value="missing"` with `strategy="constant"` | categoricals |
| `KNNImputer(n_neighbors=5)` | small data, related features; needs scaling first |
| `IterativeImputer` (experimental import) | MICE-style; slow; rarely worth it for GBMs |
| none | HistGradientBoosting, LightGBM, XGBoost handle NaN natively |

## Inspecting a fitted pipeline

```python
pipe.fit(X, y)
names = pipe[:-1].get_feature_names_out()
coefs = pd.Series(pipe[-1].coef_.ravel(), index=names).sort_values()
pipe.set_params(clf__C=0.1)                 # same naming as search spaces
print(pipe.get_params().keys())             # every addressable parameter
from sklearn import set_config; set_config(display="diagram")   # HTML diagram in notebooks
```
