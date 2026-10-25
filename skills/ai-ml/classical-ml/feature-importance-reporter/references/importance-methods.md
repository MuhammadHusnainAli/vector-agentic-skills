# Importance Methods

## Impurity / gain (model-based)

| Library | Call | Default type |
|---------|------|--------------|
| LightGBM | `model.booster_.feature_importance(importance_type="gain")` | `feature_importances_` is **split** count by default (`importance_type="split"`) |
| XGBoost | `model.get_booster().get_score(importance_type="total_gain")` | `feature_importances_` uses `gain` (average gain per split) for tree boosters |
| CatBoost | `model.get_feature_importance()` | PredictionValuesChange; `type="LossFunctionChange"` needs data and is held-out-capable |
| scikit-learn trees/forests | `model.feature_importances_` | mean decrease in impurity (MDI), normalised to sum 1 |

Prefer total gain over split counts: split counts reward features that are split on often for small gains.
All of these are computed from training data and inherit training-set overfitting.

## Coefficients

`|coef_j| x std(x_j)` (or the coefficients of a model fitted on standardised features) gives the change in the
linear predictor for a one-standard-deviation change. Without scaling, coefficients are not comparable. Under
collinearity they are unstable, so use permutation importance instead.

## Permutation importance (held-out)

```python
from sklearn.inspection import permutation_importance
r = permutation_importance(pipe, X_test, y_test, scoring="roc_auc", n_repeats=10, random_state=0, n_jobs=-1)
r.importances_mean, r.importances_std, r.importances      # (features, repeats)
```
- Run it on the **whole pipeline** with raw input columns: importance is then per input feature, and one-hot
  levels are permuted together automatically.
- Use 10-30 repeats. Report mean ± std; a feature is distinguishable from zero if mean > 2 x std.
- Several scorers at once: `scoring=["roc_auc", "average_precision"]` returns a dict of results.
- Cost: features x repeats x one prediction pass, with no refitting.

## Grouped permutation

Permuting one of two correlated features barely hurts, because the model reads the other one. Permuting the
group jointly measures the information they share.

```python
def group_importance(model, X, y, scorer, members, repeats=10, seed=0):
    rng = np.random.default_rng(seed)
    base = scorer(model, X, y)
    drops = []
    for _ in range(repeats):
        Xp = X.copy()
        Xp[members] = Xp[members].to_numpy()[rng.permutation(len(Xp))]     # same shuffle for all members
        drops.append(base - scorer(model, Xp, y))
    return np.mean(drops), np.std(drops)
```
Groups come from domain knowledge (all "billing" features) or from correlation clustering (|Spearman| >= 0.7;
`gen_importance_script.py` uses union-find over that threshold).

## Drop-column importance

Retrain without the feature (same CV, same seeds) and compare held-out scores. This is the most faithful
answer to "do we need this feature?", but it costs one refit per feature (or group). Use it for a shortlist
or a final decision, not for screening hundreds of features.

## Mean |SHAP|

See [shap-value-explainer](../../shap-value-explainer/SKILL.md). Summing |SHAP| over one-hot columns is valid for
a "use" measure (sum the signed values first per row, then take the absolute value, as
`gen_shap_script.py --group` does).

## Conditional / model-agnostic alternatives

| Method | When |
|--------|------|
| Conditional permutation (permute within bins of correlated features) | correlated features, want the unique contribution |
| LOCO (leave one covariate out) with refits | statistical inference on importance |
| SAGE (Shapley additive global importance) | Shapley-fair global importance of loss; expensive |
| Boruta (shadow features) | all-relevant feature selection, not ranking |
