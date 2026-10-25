---
name: feature-importance-reporter
description: "Produce honest feature importance reports by computing several methods on held-out data and explaining where they disagree: impurity/gain importance (LightGBM, XGBoost, CatBoost, sklearn MDI), standardised coefficients, permutation importance with repeats and standard deviations, grouped permutation for clusters of correlated features, drop-column importance and mean |SHAP|, all mapped back from encoded columns to input features. Flags features that look important only to impurity measures (split bias, redundancy), features with no measurable held-out effect, identifier-like columns, single features that dominate (leakage), and groups that share information. Use when someone asks which features matter most, needs an importance chart for stakeholders, compares importance methods, or wonders why gain, permutation and SHAP rankings differ."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# Feature Importance Reporter

"Which features matter?" has several right answers, and each importance method answers a different
question. **Gain** measures how much the model used a feature while fitting the training data.
**Permutation** importance measures how much held-out performance drops when the feature's information is
destroyed. **Mean |SHAP|** measures how much the feature moves predictions. They disagree for known reasons:
split bias, redundancy and leakage. Those disagreements are often the most useful part of the report.
`scripts/gen_importance_script.py` computes the methods on held-out data, and
`scripts/compare_importances.py` lines them up and explains the differences.

## Trigger Conditions

Activate this skill when the user:
- Asks which features matter most, or wants a feature importance chart for a report
- Sees different rankings from gain, permutation, SHAP or coefficients
- Wants to drop features and asks which are safe to remove
- Finds a surprising feature at the top (an ID, a timestamp, a post-outcome field)

Per-prediction explanations and directions: [shap-value-explainer](../shap-value-explainer/SKILL.md). Stability
of rankings across folds and seeds: [feature-selection-analyzer](../feature-selection-analyzer/SKILL.md)
(`importance_stability.py`). Shapes of effects: [partial-dependence-plot-builder](../partial-dependence-plot-builder/SKILL.md).

## Workflow

```
1. HOLD OUT  -> importance is computed on rows the model did not train on (test split or out-of-fold)
2. GENERATE  -> python scripts/gen_importance_script.py --model model.joblib --data holdout.csv --target y --shap -o imp.py
3. COMPUTE   -> python imp.py                      (importances.csv + groups.csv)
4. COMPARE   -> python scripts/compare_importances.py importances.csv --groups groups.csv
5. RESOLVE   -> investigate each flag: leakage, IDs, correlated groups, split bias
6. REPORT    -> one headline method, the others as checks, groups and caveats
```

## What Each Method Measures

| Method | Question it answers | Data | Biases |
|--------|---------------------|------|--------|
| Gain / split (impurity, MDI) | how much did the model use it while fitting? | training | favours continuous and high-cardinality features; inflates noise features the model overfits |
| \|Standardised coefficient\| | how strongly does the linear predictor depend on it? | training | meaningless without scaling; unstable under collinearity |
| Permutation (held-out) | how much does performance drop without its information? | held-out | correlated features hide each other; can be negative (noise) |
| Grouped permutation | how much does a correlated group matter together? | held-out | groups must be chosen (correlation threshold) |
| Drop-column | how much worse is a model retrained without it? | held-out, refits | expensive; also hides correlated features |
| Mean \|SHAP\| | how much does it move predictions? | any | measures use, not usefulness; correlated features share credit |

Headline recommendation: **held-out permutation importance** with its spread across repeats, grouped for
correlated features. Use SHAP for direction and per-row detail, and impurity importance only as a quick first
look. Formulas, settings and code: [importance-methods.md](references/importance-methods.md).

## Reading Disagreements

| Flag | Pattern | Usual cause | Action |
|------|---------|-------------|--------|
| IMPURITY-ONLY | high gain, little permutation | split bias or redundancy | trust permutation; check correlated partner |
| SHAP-VS-PERM | high SHAP, little permutation | a correlated feature carries the same information | group the pair |
| NO-EFFECT | permutation within 2 std of 0 | no generalisable signal | candidate to drop; refit and compare |
| ID-LIKE | identifier/hash/timestamp name | memorisation or leakage | remove from features |
| DOMINANT | > 50% of held-out importance | leakage, or a genuinely decisive feature | run [target-leakage-detector](../target-leakage-detector/SKILL.md) |
| SHARED-INFO | joint permutation > 1.3 x the sum of single ones | overlapping information | report the group |

Worked examples and how to tell redundancy from split bias:
[interpreting-disagreements.md](references/interpreting-disagreements.md).

## Reporting Rules

- Compute importance on **held-out data**, with the metric the project optimises.
- Show **uncertainty**: permutation std over repeats, or ranges across folds. Do not rank features whose
  intervals overlap as if the order were meaningful.
- **Group** one-hot levels into their input feature, and correlated features into named groups.
- Say what the numbers mean in units ("shuffling tenure lowers AUC by 0.08"), not only as percentages.
- Importance is not causation, and a low importance does not prove a feature is useless. The model may get
  the same information from a correlated feature.
- Name the model, the data, the date and the method in every chart title.

Chart templates and wording: [reporting-importance.md](references/reporting-importance.md).

## Output Format

When reporting feature importance, deliver:
1. **Setup** - model, held-out data (rows, period), metric, methods, repeats, grouping threshold.
2. **Headline ranking** - permutation importance with std (grouped), in metric units.
3. **Cross-check table** - every method's share and rank, with method agreement.
4. **Flags resolved** - each flag with the investigation result (dropped, grouped, kept with reason).
5. **Caveats** - correlated groups, non-causal reading, data coverage.

## Scripts

```bash
python scripts/gen_importance_script.py --model model.joblib --data holdout.csv --target churned -o importance.py
python scripts/gen_importance_script.py --model pipe.joblib --data test.csv --target price --scoring neg_root_mean_squared_error
python scripts/gen_importance_script.py --model m.joblib --data test.csv --target y --shap --repeats 20 --corr 0.8
```
The generated script loads a fitted model or Pipeline and held-out data, reorders the columns to the training
order, and computes model-based importance (gain, or `coef_x_std` for linear models), permutation
importance (mean and std over `--repeats`), grouped permutation for clusters of correlated numeric features
(`|Spearman| >= --corr`) and, with `--shap`, mean |SHAP|. Encoded columns are summed back to input columns.
Verified for LightGBM, XGBoost, random forest and logistic-regression Pipelines and for CatBoost. Exit
codes: 0 written, 2 usage error.

```bash
python scripts/compare_importances.py importances.csv
python scripts/compare_importances.py importances.csv --groups groups.csv --json
```
Shares, ranks, consensus rank, method agreement (Spearman) and the flags above. Recognises method kinds
from the column names and uses `<method>_std` columns. Exit codes: 0 compared, 1 a DOMINANT or ID-LIKE flag,
2 usage or read error.

## Additional Resources

| File | Content |
|------|---------|
| [importance-methods.md](references/importance-methods.md) | definitions, settings and code for each method, per library |
| [interpreting-disagreements.md](references/interpreting-disagreements.md) | split bias, redundancy, leakage, negative importances, worked examples |
| [reporting-importance.md](references/reporting-importance.md) | charts, uncertainty, grouping, wording, checklist |
