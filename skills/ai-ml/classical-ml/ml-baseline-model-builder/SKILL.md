---
name: ml-baseline-model-builder
description: "Build the baselines every ML model must beat before anyone trusts it: dummy majority/prior/mean/median predictors, the current business rule, a one-feature model (OneR), seasonal-naive and last-value forecasts, popularity recommenders, and a first honest linear model and HistGradientBoosting inside a leak-free scikit-learn Pipeline with a time-ordered, grouped or stratified holdout. Reports ROC-AUC, PR-AUC, log loss, Brier, balanced accuracy, MAE, RMSE, R2 and WAPE side by side, and warns when a first baseline looks too good (leakage). Use when starting a modelling project, asked for a baseline or a quick first model, asked whether a model is actually better than a simple rule, or when results need a reference point for a comparison report."
metadata:
  category: ai-ml
  subcategory: classical-ml
  version: "1.0.0"
---

# ML Baseline Model Builder

A model's score means nothing without a reference point. Baselines answer three questions before any
tuning: *Is there anything to learn* (dummy), *is ML better than what we do today* (the business rule,
one-feature model), and *how much does a real model add* (linear model and gradient boosting, untuned, in a
leak-free pipeline). `scripts/baseline_scores.py` scores dummy, rule and one-feature baselines on an honest
holdout with no dependencies; `scripts/scaffold_baseline.py` writes a runnable scikit-learn script with the
right split, preprocessing and metrics for the dataset's columns.

## Trigger Conditions

Activate this skill when the user:
- Starts a new tabular ML project and asks for a baseline, a first model or "something quick"
- Asks "is my model actually good?", "is 0.82 AUC good?", "does ML beat our rule?"
- Needs the reference rows for a model comparison report or a go/no-go decision
- Has a forecasting, ranking or recommendation problem and needs the naive reference (last value, seasonal
  naive, popularity)
- Got a suspiciously strong first result and wants a sanity check against trivial predictors

Statistical comparison of candidate models goes to
[ml-model-comparison-reporter](../ml-model-comparison-reporter/SKILL.md); full pipeline design to
[scikit-learn-pipeline-builder](../scikit-learn-pipeline-builder/SKILL.md); choosing the metric to
[ml-success-metric-selector](../ml-success-metric-selector/SKILL.md).

## Workflow

```
1. SPLIT      -> the holdout that mirrors deployment: time-ordered > grouped > stratified random
2. TRIVIAL    -> python scripts/baseline_scores.py data.csv --target y --time-col ts --drop id
3. RULE       -> add today's process: --rule "support_calls >= 3 or last_login_days > 30"
4. FIRST ML   -> python scripts/scaffold_baseline.py data.csv --target y --time-col ts -o baseline.py
5. RUN        -> python baseline.py  (dummy vs linear vs HistGradientBoosting, same split)
6. SANITY     -> too good (AUC > 0.97, R2 > 0.98)? leakage. No better than dummy? framing or data.
7. RECORD     -> baseline table with split, metric, numbers and noise estimate; every later model is compared to it
```

## The Baseline Ladder

Report every rung; each answers a different question.

| Rung | Classification | Regression | Answers |
|------|----------------|------------|---------|
| 0. Constant | majority class; prior probability | mean; median (MAE) | the floor; any metric at this level means no learning |
| 1. Random | stratified random labels | permuted target | what chance looks like for rank metrics |
| 2. Current process | business rule, human queue order, vendor score | last year's value, planner's estimate | does ML beat today? |
| 3. One feature | OneR: best single column, binned | per-bin mean of best column | is the signal just one obvious column? |
| 4. Simple model | logistic regression, one-hot + scaling | ridge / linear on log target | the honest ML baseline |
| 5. Default GBM | HistGradientBoosting, untuned | HistGradientBoosting | what non-linearity adds before tuning |

Tuned and fancy models are compared against rung 5 *and* rung 2; the business only cares about rung 2.

## Baselines for Other Tasks

| Task | Baseline | Notes |
|------|----------|-------|
| Forecasting | naive (last value), seasonal naive (same day last week/year), moving average, drift | MASE uses seasonal naive as its denominator; a model with MASE > 1 loses to it |
| Intermittent demand | zero forecast, Croston/SBA, mean of non-zero x rate | many series are best left at 0 |
| Ranking / search | BM25 or current ranking; popularity; random | report NDCG@k per query |
| Recommendation | most popular overall, most popular in the user's segment, recently viewed | popularity is notoriously hard to beat on accuracy metrics |
| Anomaly detection | robust z-score / IQR per feature, static thresholds | analysts' current alerts are rung 2 |
| Survival | Kaplan-Meier (no covariates) | concordance 0.5 |
| Uplift | treat everyone, treat nobody, random targeting, response model | Qini of random = 0 |
| Multiclass | majority class; class priors; keyword rules | macro-F1 of majority is tiny |
| Clustering | random assignment with the same sizes; one cluster | silhouette and stability vs random |

Code for each: [baseline-catalog.md](references/baseline-catalog.md).

## Split First, Then Baseline

The baseline is only comparable if every model uses the same holdout:

| Data | Split | Why |
|------|-------|-----|
| Model predicts the future (churn, demand, fraud) | time-ordered: train on older rows, test on newest | random splits leak future patterns and overstate scores |
| Several rows per entity (customer snapshots, patient visits) | grouped: an entity is only in train or test | the model memorises entities otherwise |
| i.i.d. rows, classification | stratified random | keeps the class rate stable |
| Small data (< ~2k rows) | repeated stratified K-fold | one split is too noisy to compare baselines |

Both scripts take `--time-col` and the scaffold also `--group-col`. Strategy detail:
[cross-validation-strategy-designer](../cross-validation-strategy-designer/SKILL.md).

## Reading the Baseline Table

```
baseline       accuracy balanced_acc  roc_auc   pr_auc  log_loss   brier  detail
majority         0.8300       0.5000   0.5000   0.1700    5.8716  0.1700  always not 1
prior            0.8300       0.5000   0.5000   0.1700    0.4627  0.1433  p = 0.217 for every row
one_r            0.8300       0.5493   0.6311   0.2856    0.4379  0.1360  positive rate by 10 bins of last_login_days
rule             0.8500       0.7225   0.7225   0.3778    5.1808  0.1500  support_calls >= 3 or last_login_days > 30
```

- **Accuracy 0.83 from "always no"**: with 17% positives accuracy is useless; use PR-AUC, recall@capacity or
  balanced accuracy.
- **PR-AUC of a constant = prevalence** (0.17): that is the PR-AUC floor, not 0.
- **Log loss of the prior** (0.46) is the floor for probabilistic models; a model above it is worse than
  predicting the base rate.
- **The rule beats one feature** here: the business rule is the bar ML must clear, with margin.
- A hard 0/1 rule gets terrible log loss; compare rules to models on ranking or threshold metrics, not log loss.

## When the Baseline Is Already Hard to Beat

| Situation | What it means | Do |
|-----------|---------------|----|
| Linear ≈ GBM ≈ rule | signal is simple, or features are weak | ship the rule or the linear model; invest in features |
| GBM >> linear | interactions / non-linearity matter | tune the GBM; check it is not exploiting a leak |
| Everything ≈ dummy | no learnable signal with these features | revisit framing and data sources (feasibility) |
| First model AUC > 0.97 | almost certainly leakage | run [target-leakage-detector](../target-leakage-detector/SKILL.md) |
| Big gap between CV and holdout | split mismatch or drift | use a time-based holdout everywhere |

## Making the Comparison Fair

1. Same rows, same split, same metric, same preprocessing budget for every baseline.
2. Preprocessing inside a Pipeline so scalers, imputers and encoders are fit on training rows only.
3. Threshold-dependent metrics at a stated threshold (train prevalence or capacity), not silently 0.5.
4. Noise estimate: repeated splits or bootstrap CI; a 0.005 AUC gain over the baseline is often noise.
5. Rules are scored as-is (0/1); give them the same population and holdout.

Reporting templates and the noise estimate: [baseline-reporting.md](references/baseline-reporting.md).

## Output Format

When building baselines, answer with:
1. **Split used** and why (time, group, stratified), with train/test sizes and class rates.
2. **Baseline table** - every rung with the primary metric first, then secondary metrics.
3. **Reading** - which baseline is the bar, what the gap between rungs says, any leakage warning.
4. **First-model script** - the `scaffold_baseline.py` output (or equivalent code) with the same split.
5. **Next step** - feature work, tuning, or stop, based on the gaps.

## Scripts

```bash
python scripts/baseline_scores.py data.csv --target churned --time-col signup_date --drop customer_id
python scripts/baseline_scores.py data.csv --target churned --rule "support_calls >= 3 or plan == basic"
python scripts/baseline_scores.py data.csv --target price --drop house_id --test-frac 0.2 --json
```
Binary targets: majority, prior, one-feature (chosen on an inner split of the training rows, never on the test
set; smoothed positive rate per level or per 10 quantile bins) and an optional rule (`col op value` terms with
`and` / `or`, ops `>= <= > < == !=`). Metrics: accuracy at 0.5, balanced accuracy at the training rate,
ROC-AUC, tie-aware PR-AUC, log loss, Brier. Numeric targets: mean, median and one-feature, with MAE, RMSE, R2,
WAPE. Holdout: latest rows by `--time-col`, else seeded random. Exit codes: 0 scored, 2 usage error or
unusable target.

```bash
python scripts/scaffold_baseline.py data.csv --target churned --time-col signup_date -o baseline.py
python scripts/scaffold_baseline.py data.csv --target churned --group-col customer_id > baseline.py
python scripts/scaffold_baseline.py data.csv --target price --task regression --drop house_id
```
Infers numeric, categorical (including numeric-looking codes such as zip), date (expanded to year/month/day of
week) and dropped columns (IDs, near-unique text), then writes a pandas + scikit-learn script: honest split,
Dummy vs LogisticRegression/Ridge vs HistGradientBoosting, each in a Pipeline with ColumnTransformer
(median imputation with missing indicators, scaling for the linear model, one-hot with infrequent-category
grouping), a metric table, and a leakage warning when AUC > 0.97 or R2 > 0.98. Exit codes: 0 written, 2 usage
error.

## Additional Resources

| File | Content |
|------|---------|
| [baseline-catalog.md](references/baseline-catalog.md) | Code for every baseline: dummy, rules, OneR, linear, GBM, forecasting naive/seasonal/Croston, popularity recommenders, ranking, survival, uplift |
| [baseline-reporting.md](references/baseline-reporting.md) | Baseline table template, noise estimates (repeated CV, bootstrap), how to state "beats the baseline", common reading mistakes |
| [first-model-recipes.md](references/first-model-recipes.md) | Leak-free first models in scikit-learn: preprocessing defaults, time/group splits, log targets, class weights, what not to tune yet |
