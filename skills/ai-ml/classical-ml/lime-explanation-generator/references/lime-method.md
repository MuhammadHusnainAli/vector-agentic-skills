# The LIME Method (tabular)

Ribeiro, Singh and Guestrin (2016), "Why should I trust you?". The `lime` package, `lime_tabular` module.

## Algorithm

```
given row x, model f, training data T:
1. draw N perturbed samples z around x:
     continuous features (discretize_continuous=True): pick a quartile bin from the training distribution,
       then a value inside the bin; the surrogate sees a 0/1 "same bin as x" indicator
     continuous features (discretize_continuous=False): z = x + noise scaled by the training std
     categorical features: draw a level with the training frequencies; the surrogate sees 1 if equal to x's level
2. query the model: f(z)  (the probability of the explained class, or the regression output)
3. weight each sample by proximity: w = exp(-d(x, z)^2 / kernel_width^2), d = Euclidean on scaled features
4. select K features (forward selection / highest weights / lasso path)
5. fit weighted ridge regression f(z) ~ features of z; the coefficients are the explanation
6. score = weighted R^2 of that fit (fidelity); local_pred = the surrogate's prediction at x
```

## Calls

```python
from lime.lime_tabular import LimeTabularExplainer
explainer = LimeTabularExplainer(
    X_train_encoded, feature_names=cols, categorical_features=cat_idx,
    categorical_names={i: levels for i, levels in ...}, class_names=["stay", "churn"],
    mode="classification", discretize_continuous=True, discretizer="quartile",
    kernel_width=None, random_state=0)
exp = explainer.explain_instance(x_encoded, predict_fn, num_features=8, num_samples=5000, labels=(1,))
exp.as_list(label=1), exp.score, exp.local_pred, exp.intercept
exp.save_to_file("row.html")
```
- `predict_fn` receives a NumPy array in the encoded space and must return class probabilities
  (classification) or predictions (regression). Decode categorical codes back to the original values
  before calling a Pipeline. The generated script does this.
- `random_state` is read at construction. To repeat with new seeds, set
  `explainer.random_state = np.random.RandomState(seed)` before each `explain_instance`.
- `discretizer` can be `"quartile"`, `"decile"` or `"entropy"` (the last needs labels).
- `feature_selection`: `"auto"` (default), `"forward_selection"`, `"lasso_path"`, `"highest_weights"`, `"none"`.

## Kernel width

The default is `0.75 x sqrt(n_features)` on standardised distances. Smaller widths make the explanation more
local but noisier, because fewer samples carry weight. Larger widths approach a global linear model. Try 2-3
values and keep the one with acceptable fidelity and stability, then use it consistently across rows.

## Cost

N model evaluations per explanation (5000 by default) and per repeat. Batch predictions are vectorised, so
a fast model takes seconds per row. For an external API, cache predictions and reduce N.

## Variants

| Variant | Idea |
|---------|------|
| Anchors (Ribeiro 2018, `alibi.explainers.AnchorTabular`) | if-then rules with a precision guarantee: "if support_calls > 3 and plan = basic, the prediction is churn with 95% precision" |
| SP-LIME (submodular pick) | choose a few representative rows to explain the model globally |
| BayLIME / stable LIME variants | reduce sampling variance |
| KernelSHAP | LIME with the Shapley kernel: additive, consistent, slower |
