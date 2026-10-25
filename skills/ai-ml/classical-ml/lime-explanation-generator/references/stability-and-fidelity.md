# Stability and Fidelity

## Why LIME varies

1. **Sampling**: each run draws new perturbations. With few effective samples (small kernel width, many
   features), the weighted regression is noisy.
2. **Feature selection**: with `num_features` < all features, borderline features enter in some runs and
   not in others.
3. **Discretisation**: a row near a quartile boundary sits in a bin with very different neighbours.
4. **Kernel width**: different widths answer different questions. The default is arbitrary.

Alvarez-Melis and Jaakkola (2018) showed that LIME explanations can change substantially for nearby inputs.
Slack et al. (2020) showed that adversarial models can hide behaviour from LIME's perturbations, because the
perturbed samples are off the data manifold. Stability checks therefore matter.

## The checks in lime_stability.py

| Quantity | Definition |
|----------|------------|
| mean, std | weight across runs (0 when the feature is not selected in a run) |
| mean \|weight\| | used for ordering and for "negligible" (< 10% of the largest), so sign flips do not hide a feature |
| CV | std / \|mean\|: size reliability |
| sign consistency | share of non-zero runs agreeing with the majority sign |
| top-k share | share of runs with the feature in the top k by \|weight\| |
| top-k Jaccard | mean pairwise \|A intersect B\| / \|A union B\| of top-k sets, negligible features removed |
| fidelity | mean `exp.score` (weighted R^2 of the surrogate) |
| local gap | mean \|local_pred - model_pred\| |

## Troubleshooting

| Symptom | Try |
|---------|-----|
| UNSTABLE, low Jaccard | `--samples 20000`; fewer features (`--top 5`); a slightly larger kernel width |
| Sign flips on one feature | that feature's local effect is near zero or the row sits on a bin edge: report it as uncertain |
| Low fidelity (R^2 < 0.5) | `--no-discretize`; a smaller kernel width; or the model is very non-linear here, so use SHAP |
| Large local gap | the surrogate misses the model at the row itself: do not report |
| Disagreement with SHAP | different questions (local slope vs attribution relative to a baseline); trust the stable, faithful one and explain the difference |
| Very different explanations for similar rows | the model is locally unstable, or LIME is: check both with SHAP |

## LIME vs SHAP on the same row

They answer different questions:
- **LIME**: what linear function approximates the model *near this row*? Weights are local slopes per rule.
- **SHAP**: how much does each feature contribute to moving the prediction *from the baseline to this
  row*? The values are additive.

Sign agreement on the main features is expected. Disagreement often comes from non-linearity: a feature can
push the prediction up relative to the baseline (positive SHAP) while its local slope is flat or negative
(LIME). `lime_stability.py --compare shap_row.csv` lists the disagreeing features.
