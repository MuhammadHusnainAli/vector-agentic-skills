# Reporting LIME

## What the weights mean

- With discretised features, a weight of +0.05 on "support_calls > 3" means: in the neighbourhood, being in
  that bin (rather than another) adds about 0.05 to the predicted probability.
- With continuous features (`--no-discretize`), a weight is a slope per standardised unit of the feature.
- The intercept plus the weights of the row's own bins gives `local_pred`. It approximates the model's
  prediction, but there is no exact additivity as with SHAP.

## Wording

- "Around this customer, the model's churn probability (12%) is driven mostly by total charges in the
  685-1486 range (raises it by about 5 points) and being in the south region (lowers it by about 5 points).
  The explanation was stable across 8 runs, but the local surrogate explains only 5% of the model's
  variation here, so treat it as a rough indication."
- Always state the number of runs, the settings and the fidelity.
- Avoid causal phrasing: "is associated with a higher score near this case", not "causes".

## Choosing a method

| Need | Method |
|------|--------|
| Exact, additive attribution for trees / linear models | SHAP (TreeExplainer / LinearExplainer) |
| Black-box model, few features, readable rules | LIME with stability checks, or Anchors |
| "What would have to change to get a different decision?" | counterfactuals |
| Global understanding | PDP/ALE, permutation importance, global SHAP |
| Regulatory reason codes | SHAP with a fixed background, reviewed wording |

## Checklist

- [ ] training data used for LIME statistics (not the test set)
- [ ] categorical features declared and decoded for the model
- [ ] at least 5-10 repeated runs with different seeds
- [ ] stability verdict, top-k Jaccard and fidelity reported
- [ ] only stable features reported; unstable ones mentioned as uncertain
- [ ] the kernel width and discretisation documented, and the same for every row in a report
- [ ] compared with SHAP where possible
