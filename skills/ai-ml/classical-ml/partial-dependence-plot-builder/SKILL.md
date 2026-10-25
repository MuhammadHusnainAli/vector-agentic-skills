---
name: partial-dependence-plot-builder
description: "Build and read partial dependence plots (PDP), individual conditional expectation (ICE) curves and accumulated local effects (ALE) for tabular models: generate scikit-learn partial_dependence scripts with percentile grids, the right response method and class, integer-safe columns, centred ICE with the PDP and a rug of observed values, two-way PDP heatmaps, and ALE that stays correct when features are correlated; then analyse the exported curves for direction, monotonicity, threshold-like jumps, heterogeneity, opposite effects or subgroups of different strength hidden by the average, the feature that separates them (interaction discovery), and grid regions without data support. Use when someone asks how a feature affects predictions, wants PDP/ICE/ALE plots, suspects an interaction, or needs to check that a model's response is monotonic or plausible."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Partial Dependence Plot Builder

A partial dependence plot shows how a model's prediction changes with one feature, averaged over the data.
The average hides two things. **ICE curves** show per-row responses, which reveals whether everyone reacts
the same way. **ALE** removes the unrealistic rows a PDP invents when features are correlated.
`scripts/gen_pdp_script.py` writes a script that draws centred ICE + PDP (+ ALE, + two-way PDP) and exports
the curves. `scripts/ice_analysis.py` reads the curves and reports what the average hides.

## Trigger Conditions

Activate this skill when the user:
- Asks how a feature influences predictions ("what happens to risk as tenure grows?")
- Wants PDP, ICE, ALE or two-way interaction plots
- Suspects an interaction or a subgroup that reacts differently
- Must check that a response is monotonic, plausible or within regulatory expectations

Per-row attributions: [shap-value-explainer](../shap-value-explainer/SKILL.md) (SHAP dependence plots are the
attribution counterpart). Global rankings: [feature-importance-reporter](../feature-importance-reporter/SKILL.md).
Smallest change to flip a decision: [counterfactual-explanation-generator](../counterfactual-explanation-generator/SKILL.md).

## Workflow

```
1. PICK      -> features to show: top of the importance ranking, plus any with a business question
2. GENERATE  -> python scripts/gen_pdp_script.py --model model.joblib --data test.csv --target y --features tenure plan --ale -o pdp.py
3. RUN       -> python pdp.py   (ice_<f>.csv, rows_<f>.csv, pdp_<f>.png [, ale_<f>.csv, pdp2_a_b.png])
4. ANALYSE   -> python scripts/ice_analysis.py ice_tenure.csv --features rows_tenure.csv
5. FOLLOW UP -> interaction found -> two-way PDP (--pair) or ICE coloured by the separator; correlated -> ALE
6. REPORT    -> plot, shape in words, heterogeneity, support, caveats
```

## PDP, ICE or ALE?

| Situation | Use | Why |
|-----------|-----|-----|
| First look at a feature | centred ICE + PDP | the average and its spread in one plot |
| Feature correlated with others (\|r\| > 0.5) | ALE | PDP evaluates impossible rows (a 20-year tenure with 1 month of charges) |
| Suspected interaction | ICE coloured by the second feature, two-way PDP | the 1-D average cancels opposite effects |
| Categorical feature | PDP / ICE per level | ALE needs an ordering |
| Monotonicity check | ICE: share of curves going the wrong way | a monotonic PDP can hide non-monotonic rows |
| Stakeholder chart | PDP with a confidence band or ALE, rug of observed values | simple, honest about support |

Centred ICE (each curve minus its value at the first grid point) is the default. Uncentred ICE curves
stack by level and hide shape differences. Definitions, maths and the cost of each method:
[pdp-ice-ale.md](references/pdp-ice-ale.md).

## What ice_analysis.py Reports

| Finding | Rule | Meaning |
|---------|------|---------|
| direction and monotonic share | PDP end minus start; share of steps in that direction | overall shape |
| steepest segment | largest change per unit of the grid | threshold-like effect |
| OPPOSITE EFFECTS | >= 10% of curves move against the PDP beyond noise | the average hides an interaction |
| SUBGROUPS | exact two-group split of curve changes, >= 3 pooled sd apart | two strengths of one effect |
| separator | feature with AUC >= 0.7 (or <= 0.3) for the group label | the likely interaction partner |
| low support | grid outside the 5th-95th percentile of observed values | extrapolation: do not interpret |
| heterogeneity | end-point spread / PDP range > 1 | the PDP is a poor summary |

Verified: the PDP equals `sklearn.inspection.partial_dependence`'s average. On a planted `a x sign(b)`
interaction, the separator is `b` with AUC 1.00. On the fixture, the separator recovers the planted
contract subgroup. ALE recovers the exact coefficient of a linear model with correlated features.

## Reading Rules

- **Causal language is wrong.** "Predicted churn falls with tenure in this model", not "tenure reduces churn".
- **Interpret only where data exists.** Show the rug and ignore the tails outside the observed range.
- **Correlated features make PDP lie.** Check correlations first and use ALE when |r| > 0.5.
- **Flat PDP does not mean no effect.** Opposite ICE curves can cancel. Check `ice_analysis.py`.
- **Scale matters.** Classifiers: probability (or log-odds for additivity). Say which.
- **Grid percentiles:** 5th-95th by default. Extending the grid shows extrapolation, not knowledge.

Reading guide and worked examples: [reading-pdp-ice.md](references/reading-pdp-ice.md). Monotonic
constraints, regulatory checks and stakeholder charts: [using-pdp-in-practice.md](references/using-pdp-in-practice.md).

## Output Format

When presenting partial dependence, deliver:
1. **Setup** - model, data and sample size, grid, response (probability / prediction), class.
2. **Plots** - centred ICE + PDP per feature with rug; ALE where features correlate; two-way PDP for interactions.
3. **Shape in words** - direction, thresholds, monotonicity, magnitude in output units.
4. **Heterogeneity** - opposite effects or subgroups, with the separating feature.
5. **Caveats** - support, correlation, non-causal reading.

## Scripts

```bash
python scripts/gen_pdp_script.py --model model.joblib --data test.csv --target churned --features tenure_months support_calls -o pdp.py
python scripts/gen_pdp_script.py --model pipe.joblib --data test.csv --features sqft --ale --sample 500
python scripts/gen_pdp_script.py --model m.joblib --data x.csv --features age --pair age income --class 1
```
Reorders columns to the training order and converts integer columns to float (scikit-learn refuses
integer columns for partial dependence). Uses `predict_proba` of the last class (or `--class`) for
classifiers, a 5th-95th percentile grid, and level grids for categorical features. Writes the curves, the
sampled rows and the PNGs. Verified with LightGBM and logistic-regression Pipelines, numeric and categorical
features, ALE and two-way PDP. Exit codes: 0 written, 2 usage error.

```bash
python scripts/ice_analysis.py ice_tenure.csv
python scripts/ice_analysis.py ice.csv --features rows.csv --id-col row_id --json
```
Reads ICE curves in long format (row_id, grid value, prediction); numeric or categorical grids. Exit codes:
0 analysed, 2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [pdp-ice-ale.md](references/pdp-ice-ale.md) | definitions, centred ICE, ALE algorithm, two-way PDP, H-statistic, cost, library calls |
| [reading-pdp-ice.md](references/reading-pdp-ice.md) | shapes and what they mean, interactions, support, misreadings, worked fixture example |
| [using-pdp-in-practice.md](references/using-pdp-in-practice.md) | monotonic constraints, plausibility reviews, regulated models, stakeholder charts |
