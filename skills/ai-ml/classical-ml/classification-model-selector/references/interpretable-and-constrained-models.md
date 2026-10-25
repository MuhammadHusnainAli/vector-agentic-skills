# Interpretable and Constrained Models

## Glass-box options

| Model | What you can show | Accuracy (tabular) |
|-------|-------------------|--------------------|
| Logistic regression | coefficient per feature (odds ratio per unit / per SD) | good with engineered features |
| Points scorecard | integer points per bin; total -> probability | close to logistic |
| GAM / EBM | a shape curve per feature, a heatmap per interaction pair | often close to GBMs |
| Shallow decision tree / rule list | IF-THEN rules | lower |
| Monotone GBM + SHAP reason codes | per-decision top reasons, guaranteed directions | high |

## EBM (InterpretML)

```python
from interpret.glassbox import ExplainableBoostingClassifier
ebm = ExplainableBoostingClassifier(interactions=10, random_state=0)
ebm.fit(X_train, y_train)                          # handles strings and NaN
glob = ebm.explain_global()                        # shape functions; interpret.show(glob) in notebooks
local = ebm.explain_local(X_test[:5], y_test[:5])  # exact additive contributions per row
```
Shape functions can be edited (e.g. to remove an implausible bump) and monotonicity enforced after fitting
(`ebm.monotonize(term, increasing=True)` in recent versions).

## Points scorecard (credit-style)

1. Bin each feature (quantiles or optimal binning, e.g. `optbinning`), enforcing monotone event rates where
   required.
2. Replace bins by weight of evidence, fit logistic regression.
3. Scale: `points = offset + factor * (coef * WoE)` with `factor = PDO / ln(2)` (points to double the odds).

## Monotone constraints

| Library | Parameter |
|---------|-----------|
| HistGradientBoosting | `monotonic_cst=[1, 0, -1, ...]` (or a dict by feature name, >= 1.2) |
| LightGBM | `monotone_constraints=[1, 0, -1, ...]`, `monotone_constraints_method="advanced"` |
| XGBoost | `monotone_constraints="(1,0,-1)"` or a dict |
| CatBoost | `monotone_constraints=["feature:1", ...]` |
| EBM | `monotonize()` after fit |

Constraints usually cost little accuracy when they match domain knowledge and make models safer under drift.

## Reason codes

For adverse-action notices (e.g. credit decisions), report the top features that pushed the score toward
the decision. For GBMs: TreeSHAP values per row, mapped to human-readable reasons; for scorecards: the bins
with the largest point loss relative to the maximum. Document the method and test stability of the top
reasons.

## Regulation checklist (high level)

- Model inventory and documentation (model card).
- Prohibited features and proxies reviewed (protected attributes, close proxies such as zip in some contexts).
- Per-group performance and error rates.
- Explanation method validated (stable, faithful).
- Change management and monitoring.

Specific obligations depend on jurisdiction and sector; involve compliance early.
