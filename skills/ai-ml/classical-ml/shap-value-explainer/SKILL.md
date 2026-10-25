---
name: shap-value-explainer
description: "Compute and explain SHAP values for tabular models correctly: choose the explainer (TreeExplainer interventional or tree_path_dependent, CatBoost native ShapValues, LinearExplainer, model-agnostic PermutationExplainer), pick the background data and the output space (log-odds versus probability), explain the final estimator of a scikit-learn Pipeline and sum one-hot columns back to their input feature, and check additivity. Summarise global importance (mean |SHAP| and share), direction (Spearman of value versus SHAP), how much of each effect depends on other features and the likely interaction partner, and the effect of missing values; turn one prediction into a text waterfall and a plain-language summary with probabilities. Covers pitfalls: correlated features sharing credit, causal misreadings, background choice, multiclass outputs. Use when someone asks to explain a model or a prediction with SHAP, read a SHAP plot, or justify a decision to a stakeholder."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# SHAP Value Explainer

SHAP splits each prediction into additive contributions: `prediction = base value + sum of SHAP values`.
That property makes SHAP the standard for both global ("what drives the model?") and local ("why this
customer?") explanations. It also makes errors easy to check. Most bad SHAP reports come from the wrong
output space, a background nobody chose deliberately, one-hot columns read separately, or SHAP read as
causation. `scripts/gen_shap_script.py` writes a script that computes SHAP correctly for the saved model
and exports two CSVs. `scripts/shap_summary.py` reads them for the global picture and
`scripts/explain_row.py` explains single predictions.

## Trigger Conditions

Activate this skill when the user:
- Wants to explain a tabular model or individual predictions with SHAP
- Shares SHAP values or a summary/beeswarm/waterfall/dependence plot and asks what it means
- Needs reason codes for a decision (credit, fraud, churn outreach) or a stakeholder-ready explanation
- Sees SHAP values that do not add up, or explanations that contradict domain knowledge

Model-agnostic importance comparisons: [feature-importance-reporter](../feature-importance-reporter/SKILL.md);
average effect curves: [partial-dependence-plot-builder](../partial-dependence-plot-builder/SKILL.md); local
surrogate explanations: [lime-explanation-generator](../lime-explanation-generator/SKILL.md); "what would change
the decision": [counterfactual-explanation-generator](../counterfactual-explanation-generator/SKILL.md).

## Workflow

```
1. GENERATE  -> python scripts/gen_shap_script.py --model model.joblib --data test.csv --target y --group -o explain.py
2. COMPUTE   -> python explain.py         (shap_values.csv + shap_features.csv, additivity asserted)
3. GLOBAL    -> python scripts/shap_summary.py shap_values.csv --features shap_features.csv
4. LOCAL     -> python scripts/explain_row.py shap_values.csv --features shap_features.csv --row 17 --link logit
5. SANITY    -> directions vs domain knowledge; leakage if one feature dominates; correlated groups
6. REPORT    -> global drivers, interactions, example explanations, caveats
```

## Choosing the Explainer

| Model | Explainer | Output space | Notes |
|-------|-----------|--------------|-------|
| LightGBM, XGBoost, sklearn GBM | `TreeExplainer` | raw margin (log-odds for classifiers) | exact, fast |
| HistGradientBoosting | `TreeExplainer(feature_perturbation="tree_path_dependent")` | log-odds | interventional mode misses the baseline in shap 0.54 (verified) |
| Random forest, extra trees, decision tree | `TreeExplainer` | probability | sklearn forests average probabilities |
| CatBoost | `model.get_feature_importance(Pool, type="ShapValues")` | log-odds | handles categorical features natively |
| Linear / logistic | `LinearExplainer(model, background)` | log-odds | SHAP_j = coef_j x (x_j - mean_j) for independent features |
| Anything else (SVM, k-NN, stacks) | `PermutationExplainer(f, Independent(background))` | probability | model-agnostic, cost grows with features x background |

**Interventional versus tree_path_dependent.** Interventional SHAP with a background sample answers "relative to
these reference rows". Tree-path-dependent SHAP uses the tree's training cover and needs no background, but it
spreads credit onto correlated features differently. Use interventional with 100-1000 representative rows
(not only positives, not the test row itself) unless the model rules it out.

**Output space.** Log-odds are additive and probabilities are not. Explain in log-odds and convert the base
and the final value to probabilities for the reader (`explain_row.py --link logit`). Per-feature probability
contributions depend on the order in which they are added.

Explainer details, backgrounds, multiclass, pipelines: [computing-shap.md](references/computing-shap.md).

## Reading SHAP

| Question | Read | Script output |
|----------|------|---------------|
| What drives the model overall? | mean \|SHAP\| | rank, share |
| Which way does a feature push? | value vs SHAP correlation | rho, direction |
| Is the effect simple? | spread of SHAP at a fixed value | spread %, partner |
| Does missingness matter? | SHAP of rows with missing values | mean SHAP of missing |
| Why this prediction? | waterfall | explain_row.py |

Rules that prevent the classic misreadings:
- **SHAP is not causal.** It shows how this model uses inputs. Changing a feature in the world may not change
  the outcome, and features the model never saw get no credit.
- **Correlated features share credit.** Two near-duplicate features each look half as important. Group them
  (sum their SHAP) before ranking, or drop one and refit.
- **One dominant feature is a red flag.** Check it with [target-leakage-detector](../target-leakage-detector/SKILL.md).
- **Mean |SHAP| depends on the rows explained.** Explain a representative sample of production-like data,
  not the training set or only positives.
- **One-hot columns belong together.** `--group` sums them back to the input column, and additivity still holds.
- **Interaction attribution is approximate.** The partner reported is a hint. Confirm it with SHAP
  interaction values for trees, or a 2-D partial dependence plot.

Plot reading (beeswarm, dependence, waterfall, force) and stakeholder wording: [reading-shap.md](references/reading-shap.md).
Reason codes, adverse-action notices and monitoring explanations over time:
[shap-in-production.md](references/shap-in-production.md).

## Output Format

When explaining a model with SHAP, deliver:
1. **Setup** - model, explainer, background (size and source), output space, rows explained.
2. **Checks** - additivity, constant base value, grouped columns.
3. **Global drivers** - top features with share and direction, interactions worth noting, missing-value effects.
4. **Local examples** - two or three waterfalls (typical high, typical low, a surprising case) in plain language.
5. **Caveats** - correlated groups, non-causal reading, data the explanation covers, anything that looked like leakage.

## Scripts

```bash
python scripts/gen_shap_script.py --model model.joblib --data test.csv --target churned -o explain.py
python scripts/gen_shap_script.py --model pipe.joblib --data test.csv --drop customer_id --group --rows 2000
python scripts/gen_shap_script.py --model rf.joblib --data x.csv --perturbation tree_path_dependent --class 2
```
Verified for LightGBM, XGBoost, random forest, HistGradientBoosting, CatBoost with categorical features,
a logistic-regression Pipeline with one-hot grouping, and an SVC Pipeline (permutation path). The script
asserts additivity before writing. Exit codes: 0 written, 2 usage error.

```bash
python scripts/shap_summary.py shap_values.csv --features shap_features.csv --top 10
```
Importance, share, signed mean, direction, spread, interaction partner, missing-value effect, additivity and
base-value checks. Exit codes: 0 summarised, 1 additivity failed, 2 usage or read error.

```bash
python scripts/explain_row.py shap_values.csv --features shap_features.csv --row 17 --link logit --label "churn probability"
python scripts/explain_row.py shap_values.csv --features shap_features.csv --select highest --top 5
```
Text waterfall with cumulative log-odds and probabilities, and a plain-language summary. Exit codes: 0
explained, 1 additivity mismatch, 2 usage or read error. Both readers share `scripts/_shap_io.py` (CSV
loading, row alignment).

## Additional Resources

| File | Content |
|------|---------|
| [computing-shap.md](references/computing-shap.md) | explainers per model, background data, interventional vs path-dependent, output spaces, multiclass, pipelines, cost |
| [reading-shap.md](references/reading-shap.md) | plot types, interactions, correlated features, pitfalls, wording for stakeholders |
| [shap-in-production.md](references/shap-in-production.md) | reason codes, adverse-action notices, explanation monitoring, latency and storage |
