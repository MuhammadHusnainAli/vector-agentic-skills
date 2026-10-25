# Reading SHAP

## Plot types

| Plot | Shows | Read it as |
|------|-------|-----------|
| Bar (mean \|SHAP\|) | global importance | how much the output moves because of each feature, on average |
| Beeswarm | every row's SHAP, coloured by feature value | direction (red right = high values raise), spread, outliers |
| Dependence / scatter | SHAP vs feature value, coloured by a second feature | shape of the effect, thresholds, interaction (vertical spread by colour) |
| Waterfall | one row, base to prediction | why this prediction |
| Force | the same as waterfall, horizontally | compact local view |
| Decision plot | cumulative paths for many rows | how groups of rows diverge |
| Heatmap | rows x features | clusters of explanations |

```python
e = shap.Explanation(values=sv, base_values=base, data=X.values, feature_names=list(X.columns))
shap.plots.beeswarm(e, max_display=15)
shap.plots.scatter(e[:, "tenure_months"], color=e)        # colour by the strongest interacting feature
shap.plots.waterfall(e[17])
```

## What shap_summary.py's columns mean

| Column | Meaning | Watch for |
|--------|---------|-----------|
| mean\|SHAP\| | average absolute contribution | compare within one model and one output space only |
| share | fraction of the total | a single feature > 50%: check for leakage |
| mean | average signed contribution | far from 0: the background differs from the explained rows |
| rho | Spearman(value, SHAP) | sign against domain knowledge: proxy, leakage or a data bug |
| spread | SHAP variance not explained by the feature's own value | > 20%: the effect depends on context |
| partner | feature with the strongest within-chunk correlation with the SHAP values | confirm with interaction values or 2-D PDP |

## Correlated features

SHAP divides credit between correlated features, and how it divides depends on the explainer:
- Interventional SHAP breaks correlations: it evaluates combinations that may not occur in reality.
- Path-dependent SHAP follows the tree's splits: a feature used first takes more credit.

Mitigations: group correlated features (sum their SHAP) and report the group; drop redundant features and
refit; report the correlation next to the ranking.

## Pitfalls

| Pitfall | Correct practice |
|---------|------------------|
| "SHAP says raising tenure lowers churn" | SHAP describes the model, not interventions; causal claims need experiments or causal models |
| Ranking with one-hot levels separately | sum levels per input feature first |
| Comparing SHAP across models in different spaces | log-odds and probability values are not comparable |
| Explaining the training set | explain held-out, production-like rows |
| Reading tiny features' shapes | below ~5% share, shapes are mostly noise |
| Trusting a surprising direction | check the data: leakage, encoding errors, target defined after the feature |
| Different backgrounds across reports | fix and document the background |

## Wording for stakeholders

- "On average the model predicts 17% churn. For this customer it predicts 94%. The biggest reasons are 12
  support calls in the last quarter (strongly raises the risk) and the basic plan (raises it a little)."
- "Across all customers, tenure has the largest influence. Newer customers are scored as riskier."
- Add: "This explains how the model scores customers. It does not prove that changing these factors would
  change behaviour."
- Avoid raw log-odds in stakeholder text. Use probabilities for the base and the prediction, and words
  (strongly / slightly raises) for the contributions.
